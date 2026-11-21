from collections.abc import Mapping
from datetime import date
from typing import Any
from urllib.parse import parse_qs

import pytest

from moteur.models import JobAd
from moteur.sources.base import SourceError
from moteur.sources.station_f import (
    SEARCH_PAGE,
    SEARCH_URL,
    SourceStationF,
    ad_station_f,
    salary_label,
)
from tests.conftest import FakeClient
from tests.test_sources_welcomekit_workable import PAGE

SEARCH_HTML = """<div class='search-filters'>
<input type="hidden" name="algolia_api_key" id="algolia_api_key" value="CLE123" />
</div>"""


def _hit(number: int, **fields: Any) -> dict[str, Any]:
    hit: dict[str, Any] = {
        "objectID": str(number),
        "name": f"Lead AI {number}",
        "slug": f"lead-ai-{number}_paris",
        "published_at": "2026-11-10T10:00:00.000+01:00",
        "contract_type": "FULL_TIME",
        "remote": "partial",
        "office": {"city": "Paris"},
        "organization": {"name": "Été Labs", "website_organization": {"slug": "ete-labs"}},
        "profile": "<p>Python &amp; LLM</p>",
    }
    hit.update(fields)
    return hit


class AlgoliaClient(FakeClient):
    """Serves the search page and Algolia answers by keyword and page."""

    def __init__(self, pages: Mapping[str, list[dict[str, Any]]], **answers: Any) -> None:
        super().__init__({SEARCH_PAGE: SEARCH_HTML, **answers})
        self.pages = pages
        self.headers: list[Mapping[str, str]] = []

    def post_json(
        self, url: str, *, body: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Any:
        self.calls.append((url, dict(body)))
        self.headers.append(dict(headers or {}))
        params = parse_qs(body["params"])
        answers = self.pages.get(params["query"][0], [])
        page = int(params["page"][0])
        return answers[page] if page < len(answers) else None


def _source(
    client: FakeClient, searches: tuple[str, ...] = ("lead ai",), pages: int = 3
) -> SourceStationF:
    return SourceStationF(client, searches, pages, 21, today=lambda: date(2026, 11, 21))


@pytest.mark.spec("SRC-70")
def test_the_key_is_read_from_the_search_page() -> None:
    client = AlgoliaClient({"lead ai": [{"hits": [_hit(1)], "nbPages": 1}]})
    assert len(_source(client).collect()) == 1
    assert client.calls[0][0] == SEARCH_PAGE
    assert client.headers[0] == {
        "X-Algolia-Application-Id": "CSEKHVMS53",
        "X-Algolia-API-Key": "CLE123",
    }


@pytest.mark.spec("SRC-70")
def test_a_search_page_without_key_is_a_source_error() -> None:
    client = AlgoliaClient({}, **{SEARCH_PAGE: "<html></html>"})
    with pytest.raises(SourceError):
        _source(client).collect()


@pytest.mark.spec("SRC-71")
def test_pages_are_read_until_the_last_one_and_duplicates_dropped() -> None:
    pages = {
        "lead ai": [
            {"hits": [_hit(1)], "nbPages": 3},
            {"hits": [_hit(2)], "nbPages": 3},
            {"hits": [_hit(3)], "nbPages": 3},
        ],
        "head of ai": [{"hits": [_hit(2), _hit(4)], "nbPages": 1}],
    }
    client = AlgoliaClient(pages)
    ads = _source(client, ("lead ai", "head of ai"), pages=2).collect()
    assert [ad.title for ad in ads] == ["Lead AI 1", "Lead AI 2", "Lead AI 4"]
    searches = [parse_qs(body["params"]) for url, body in client.calls if url == SEARCH_URL]
    assert sorted((s["query"][0], s["page"][0], s["hitsPerPage"][0]) for s in searches) == [
        ("head of ai", "0", "50"),
        ("lead ai", "0", "50"),
        ("lead ai", "1", "50"),
    ]


@pytest.mark.spec("SRC-72")
def test_old_ads_internships_and_apprenticeships_are_left_out() -> None:
    hits = [
        _hit(1),
        _hit(2, published_at="2026-10-01T10:00:00.000+02:00"),
        _hit(3, contract_type="INTERNSHIP"),
        _hit(4, contract_type="APPRENTICESHIP"),
        _hit(5, published_at=None),
        _hit(6, published_at="2026-10-31T09:00:00.000+01:00"),
    ]
    client = AlgoliaClient({"lead ai": [{"hits": hits, "nbPages": 1}]})
    assert [ad.title for ad in _source(client).collect()] == [
        "Lead AI 1",
        "Lead AI 5",
        "Lead AI 6",
    ]


@pytest.mark.spec("SRC-73", "SRC-01", "SRC-02")
def test_fields_of_a_result() -> None:
    ad = ad_station_f(
        _hit(
            1,
            experience_level_minimum=3,
            salary_period="yearly",
            salary_minimum=60000,
            salary_maximum=75000,
        )
    )
    assert ad == JobAd(
        company="Été Labs",
        title="Lead AI 1",
        location="Paris, télétravail partiel",
        url="https://jobs.stationf.co/companies/ete-labs/jobs/lead-ai-1_paris",
        source="station_f",
        description="Expérience demandée : 3 ans. Python & LLM",
        salary="Annuel de 60000 Euros à 75000 Euros",
        published_on="2026-11-10",
    )
    assert ad_station_f(_hit(2, name="")) is None
    unusual = ad_station_f({"name": "Data Scientist", "office": "Paris", "remote": "no"})
    assert unusual is not None
    assert (unusual.company, unusual.location, unusual.url) == ("Entreprise non précisée", "", "")


@pytest.mark.spec("SRC-73")
@pytest.mark.parametrize(
    ("fields", "label"),
    [
        (
            {"salary_period": "yearly", "salary_minimum": 60000, "salary_maximum": 75000},
            "Annuel de 60000 Euros à 75000 Euros",
        ),
        ({"salary_period": "yearly", "salary_maximum": 80000}, "Annuel jusqu'à 80000 Euros"),
        ({"salary_period": "yearly", "salary_minimum": 50000}, "À partir de 50000 Euros par an"),
        (
            {"salary_period": "monthly", "salary_minimum": 4000, "salary_yearly_minimum": 48000},
            "À partir de 48000 Euros par an",
        ),
        ({"salary_period": "yearly", "salary_minimum": None}, ""),
        ({}, ""),
    ],
)
def test_salary_label(fields: dict[str, Any], label: str) -> None:
    assert salary_label(fields) == label


@pytest.mark.spec("SRC-74")
def test_the_ad_page_gives_the_text() -> None:
    url = "https://jobs.stationf.co/companies/ete-labs/jobs/lead-ai-1_paris"
    client = AlgoliaClient(
        {"lead ai": [{"hits": [_hit(1, experience_level_minimum=1)], "nbPages": 1}]},
        **{url: PAGE},
    )
    source = _source(client)
    (ad,) = source.collect()
    complete = source.add_details(ad)
    assert (complete.title, complete.location) == ("Lead AI 1", "Paris, télétravail partiel")
    assert complete.description == (
        "Expérience demandée : 1 an. About Chiffrement homomorphe. "
        "Job Description Construire des modèles."
    )
    empty = AlgoliaClient({"lead ai": [{"hits": [_hit(1)], "nbPages": 1}]})
    source = _source(empty)
    (ad,) = source.collect()
    assert source.add_details(ad) == ad
