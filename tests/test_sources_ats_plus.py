import threading
from collections.abc import Mapping
from typing import Any

import pytest

from moteur.config import TargetCompany
from moteur.sources.ats import (
    URLS,
    SourceAts,
    ads_recruitee,
    ads_smartrecruiters,
    ads_teamtailor,
)
from moteur.sources.workday import SourceWorkday, ads_workday, split_address, workday_description
from tests.conftest import FakeClient

EXAMPLE = "https://exemple.wd3.myworkdayjobs.com/fr-FR/Careers"


@pytest.mark.spec("SRC-40")
def test_split_a_workday_address() -> None:
    site = split_address(EXAMPLE)
    assert (site.host, site.tenant, site.site) == (
        "exemple.wd3.myworkdayjobs.com",
        "exemple",
        "Careers",
    )
    assert site.api == "https://exemple.wd3.myworkdayjobs.com/wday/cxs/exemple/Careers/jobs"
    assert split_address("groupe.wd3.myworkdayjobs.com/Groupe").site == "Groupe"
    with pytest.raises(ValueError):
        split_address("https://exemple.fr/carrieres")


@pytest.mark.spec("SRC-41")
def test_workday_ads() -> None:
    answer = {
        "total": 1,
        "jobPostings": [
            {
                "title": "Ingénieur IA F/H",
                "externalPath": "/job/Velizy/Ingenieur-IA_R001",
                "locationsText": "Vélizy-Villacoublay",
            },
            {"title": ""},
        ],
    }
    (ad,) = ads_workday("Exemple", split_address(EXAMPLE), answer)
    assert (ad.title, ad.location, ad.source) == (
        "Ingénieur IA F/H",
        "Vélizy-Villacoublay",
        "workday",
    )
    assert ad.url == "https://exemple.wd3.myworkdayjobs.com/Careers/job/Velizy/Ingenieur-IA_R001"
    assert ads_workday("Exemple", split_address(EXAMPLE), None) == []


def _page(start: int, count: int, total: int) -> dict[str, object]:
    return {
        "total": total,
        "jobPostings": [
            {"title": f"Poste {i}", "externalPath": f"/job/{i}"}
            for i in range(start, start + count)
        ],
    }


class WorkdayClient(FakeClient):
    """Answers by keyword and offset, whatever the order of the calls."""

    def __init__(
        self,
        pages: dict[tuple[str, int], dict[str, object]],
        gate: threading.Barrier | None = None,
    ) -> None:
        super().__init__({})
        self.pages = pages
        self.gate = gate

    def post_json(
        self, url: str, *, body: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Any:
        self.calls.append((url, dict(body)))
        if self.gate is not None and body["offset"] == 0:
            self.gate.wait()  # fails if the keywords run one after the other
        return self.pages.get((body["searchText"], body["offset"]))


@pytest.mark.spec("SRC-41")
def test_workday_pages_and_deduplicates() -> None:
    # Total given on the first page only, as Workday does.
    client = WorkdayClient(
        {("ia", 0): _page(0, 20, 25), ("ia", 20): _page(20, 5, 0), ("data", 0): _page(0, 3, 3)}
    )
    target = TargetCompany(
        name="Exemple", ats="workday", identifier=EXAMPLE, searches=("ia", "data")
    )
    source = SourceWorkday(client, target)
    ads = source.collect()
    assert len(ads) == 25  # the 3 ads for "data" are already seen
    assert sorted((c["searchText"], c["offset"]) for _, c in client.calls) == [
        ("data", 0),
        ("ia", 0),
        ("ia", 20),
    ]
    assert source.name == "workday:Exemple"


@pytest.mark.spec("SRC-05")
def test_workday_runs_keywords_in_parallel_keeping_order() -> None:
    client = WorkdayClient(
        {("ia", 0): _page(0, 2, 2), ("data", 0): _page(1, 2, 2)}, threading.Barrier(2, timeout=5)
    )
    target = TargetCompany(
        name="Exemple", ats="workday", identifier=EXAMPLE, searches=("ia", "data")
    )
    ads = SourceWorkday(client, target).collect()
    assert [o.title for o in ads] == ["Poste 0", "Poste 1", "Poste 2"]


@pytest.mark.spec("SRC-42")
def test_workday_opens_the_detail_page_of_a_retained_ad() -> None:
    detail = "https://exemple.wd3.myworkdayjobs.com/wday/cxs/exemple/Careers/job/Paris/IA_R001"
    client = FakeClient(
        {detail: {"jobPostingInfo": {"jobDescription": "<p>Missions &amp; profil</p>"}}}
    )
    target = TargetCompany(name="Exemple", ats="workday", identifier=EXAMPLE)
    (ad,) = ads_workday(
        "Exemple",
        split_address(EXAMPLE),
        {"jobPostings": [{"title": "IA", "externalPath": "/job/Paris/IA_R001"}]},
    )
    detailed = SourceWorkday(client, target).add_details(ad)
    assert detailed.description == "Missions & profil"
    assert client.calls[0][0] == detail


@pytest.mark.spec("SRC-42")
def test_workday_unreadable_or_foreign_detail_leaves_no_text() -> None:
    assert workday_description(None) == ""
    assert workday_description({"jobPostingInfo": "?"}) == ""
    client = FakeClient({})
    target = TargetCompany(name="Exemple", ats="workday", identifier=EXAMPLE)
    source = SourceWorkday(client, target)
    (ad,) = ads_workday(
        "Exemple",
        split_address(EXAMPLE),
        {"jobPostings": [{"title": "IA", "externalPath": "/job/1"}]},
    )
    assert source.add_details(ad).description == ""
    from dataclasses import replace

    foreign = replace(ad, url="https://ailleurs.fr/offre/1")
    assert source.add_details(foreign) is foreign
    assert len(client.calls) == 1


@pytest.mark.spec("SRC-31")
def test_smartrecruiters() -> None:
    answer = {
        "content": [
            {
                "id": "744",
                "name": "Data Scientist",
                "releasedDate": "2026-11-02T09:00:00.000Z",
                "location": {"city": "Paris", "country": "fr"},
            },
            {"name": ""},
        ]
    }
    (ad,) = ads_smartrecruiters("Acme", "Acme1", answer)
    assert (ad.title, ad.location, ad.published_on) == (
        "Data Scientist",
        "Paris, FR",
        "2026-11-02",
    )
    assert ad.url == "https://jobs.smartrecruiters.com/Acme1/744"


@pytest.mark.spec("SRC-31")
def test_recruitee() -> None:
    answer = {
        "offers": [
            {
                "title": "Lead AI",
                "location": "Paris, France",
                "careers_url": "https://acme.recruitee.com/o/lead-ai",
                "description": "<p>Diriger l’IA</p>",
                "published_at": "2026-11-05 10:00:00 UTC",
            }
        ]
    }
    (ad,) = ads_recruitee("Acme", answer)
    assert (ad.title, ad.description, ad.published_on) == (
        "Lead AI",
        "Diriger l’IA",
        "2026-11-05",
    )


FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:tt="https://teamtailor.com/locations">
  <channel>
    <item>
      <title>AI Engineer</title>
      <link>https://acme.teamtailor.com/jobs/1-ai-engineer</link>
      <description>&lt;p&gt;Agents LLM&lt;/p&gt;</description>
      <pubDate>Tue, 10 Nov 2026 08:00:00 +0100</pubDate>
      <tt:locations><tt:location><tt:city>Paris</tt:city></tt:location></tt:locations>
    </item>
    <item><title></title></item>
  </channel>
</rss>"""


@pytest.mark.spec("SRC-31")
def test_teamtailor() -> None:
    (ad,) = ads_teamtailor("Acme", FEED)
    assert (ad.title, ad.location, ad.url) == (
        "AI Engineer",
        "Paris",
        "https://acme.teamtailor.com/jobs/1-ai-engineer",
    )
    assert (ad.description, ad.published_on) == ("Agents LLM", "2026-11-10")
    assert ads_teamtailor("Acme", "pas du xml") == []


@pytest.mark.spec("SRC-30")
def test_teamtailor_source_reads_the_rss_feed() -> None:
    url = URLS["teamtailor"].format(id="acme")
    client = FakeClient({url: FEED})
    target = TargetCompany(name="Acme", ats="teamtailor", identifier="acme")
    assert [o.title for o in SourceAts(client, target).collect()] == ["AI Engineer"]
    assert client.calls == [(url, {})]


@pytest.mark.spec("SRC-30")
def test_smartrecruiters_source_calls_the_right_address() -> None:
    url = URLS["smartrecruiters"].format(id="Acme1")
    client = FakeClient({url: {"content": [{"id": "1", "name": "ML Engineer"}]}})
    target = TargetCompany(name="Acme", ats="smartrecruiters", identifier="Acme1")
    assert [o.title for o in SourceAts(client, target).collect()] == ["ML Engineer"]
    assert client.calls == [(url, {"limit": "100"})]
