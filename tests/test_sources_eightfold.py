"""Eightfold career sites (SRC-125 to SRC-127)."""

import pytest

from moteur.collection import add_details
from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.own_companies import source_for
from moteur.sources.eightfold import (
    SourceEightfold,
    ads_eightfold,
    eightfold_description,
    split_eightfold_address,
)
from tests.conftest import FakeClient

DSM = "https://jobs.dsm-firmenich.com/careers?domain=dsm.com&sort_by=relevance"


def _answer(ids: range, total: int) -> dict[str, object]:
    positions = [
        {
            "id": 562949978500000 + i,
            "name": f"Data scientist {i}",
            "locations": ["Paris, France", "Delft, Netherlands"],
            "postedTs": 1793007690,
        }
        for i in ids
    ]
    return {"status": 200, "data": {"positions": positions, "count": total}}


@pytest.mark.spec("SRC-125")
def test_eightfold_address_gives_host_and_domain() -> None:
    site = split_eightfold_address(DSM)
    assert (site.host, site.domain) == ("jobs.dsm-firmenich.com", "dsm.com")
    assert split_eightfold_address("jobs.dsm-firmenich.com/careers?domain=dsm.com") == site
    with pytest.raises(ValueError):
        split_eightfold_address("https://jobs.dsm-firmenich.com/careers")


@pytest.mark.spec("SRC-126", "SRC-01")
def test_eightfold_positions_become_ads() -> None:
    site = split_eightfold_address(DSM)
    answer = _answer(range(1, 2), 1)
    answer["data"]["positions"].append({"id": 9})  # type: ignore[index]
    answer["data"]["positions"].append({"name": "Sans id"})  # type: ignore[index]
    (ad,) = ads_eightfold("DSM-Firmenich", site, answer)
    assert (ad.title, ad.location, ad.published_on, ad.description, ad.source) == (
        "Data scientist 1",
        "Paris, France",
        "2026-10-26",
        "",
        "eightfold",
    )
    assert ad.url == "https://jobs.dsm-firmenich.com/careers/job/562949978500001"
    assert ads_eightfold("DSM-Firmenich", site, "pas du json") == []


@pytest.mark.spec("SRC-126")
def test_eightfold_searches_each_keyword_page_by_page() -> None:
    site = split_eightfold_address(DSM)
    pages = {
        site.search_url("data", 0): _answer(range(10), 13),
        site.search_url("data", 1): _answer(range(10, 13), 13),
        site.search_url("ia", 0): _answer(range(2), 2),
    }
    client = FakeClient(pages)
    target = TargetCompany(name="DSM", ats="eightfold", identifier=DSM, searches=("data", "ia"))
    source = source_for(target, client, ())
    assert isinstance(source, SourceEightfold)
    ads = source.collect()
    assert len(ads) == 13  # ads 0 and 1 found by both keywords are kept once
    assert sorted(u for u, _ in client.calls) == sorted(pages)
    assert "domain=dsm.com" in site.search_url("data", 1)
    assert "query=data" in site.search_url("data", 1)
    assert "start=10" in site.search_url("data", 1)


@pytest.mark.spec("SRC-126")
def test_eightfold_search_stops_at_the_page_limit() -> None:
    site = split_eightfold_address(DSM)
    pages = {
        site.search_url("data", n): _answer(range(n * 10, n * 10 + 10), 500) for n in range(12)
    }
    client = FakeClient(pages)
    target = TargetCompany(name="DSM", ats="eightfold", identifier=DSM, searches=("data",))
    assert len(SourceEightfold(client, target).collect()) == 100
    assert len(client.calls) == 10


@pytest.mark.spec("SRC-127", "SRC-02")
def test_eightfold_details_give_the_text() -> None:
    site = split_eightfold_address(DSM)
    detail = {"data": {"jobDescription": "<p><strong>Missions</strong></p><p>Profil</p>"}}
    client = FakeClient({site.detail_url("8"): detail})
    target = TargetCompany(name="DSM", ats="eightfold", identifier=DSM, searches=("data",))
    source = SourceEightfold(client, target)
    ad = JobAd("DSM", "Poste", url=site.posting_url("8"), source="eightfold")
    (completed,) = add_details([ad], [source])
    assert completed.description == eightfold_description(detail)
    assert "Missions" in completed.description and "Profil" in completed.description
    unreadable = JobAd("DSM", "Poste", url=site.posting_url("7"), source="eightfold")
    assert source.add_details(unreadable).description == ""
