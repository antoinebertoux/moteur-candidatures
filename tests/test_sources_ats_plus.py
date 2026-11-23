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
    smartrecruiters_searches,
)
from moteur.sources.base import SourceError
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

    def __init__(self, pages: dict[tuple[str, int], dict[str, object]]) -> None:
        super().__init__({})
        self.pages = pages

    def post_json(
        self, url: str, *, body: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Any:
        self.calls.append((url, dict(body)))
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


@pytest.mark.spec("SRC-44")
def test_workday_keywords_keep_their_order_in_the_result() -> None:
    client = WorkdayClient({("ia", 0): _page(0, 2, 2), ("data", 0): _page(1, 2, 2)})
    target = TargetCompany(
        name="Exemple", ats="workday", identifier=EXAMPLE, searches=("ia", "data")
    )
    ads = SourceWorkday(client, target, lambda _: None, lambda: 0.0).collect()
    assert [o.title for o in ads] == ["Poste 0", "Poste 1", "Poste 2"]
    assert [c["searchText"] for _, c in client.calls] == ["ia", "data"]


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


class PagedSmartRecruiters(FakeClient):
    """SmartRecruiters double: answers each search (q, country) page by page."""

    def __init__(self, boards: Mapping[tuple[str, str], list[str]], total: bool = True) -> None:
        super().__init__({})
        self.boards = boards
        self.total = total
        self.lock = threading.Lock()

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        parameters = dict(params or {})
        with self.lock:
            self.calls.append((url, parameters))
        ids = self.boards.get((parameters.get("q", ""), parameters.get("country", "")), [])
        start, size = int(parameters.get("offset", "0")), int(parameters["limit"])
        page = [{"id": i, "name": f"Ad {i}"} for i in ids[start : start + size]]
        answer: dict[str, Any] = {"content": page}
        if self.total:
            answer["totalFound"] = len(ids)
        return answer


def _smartrecruiters(
    client: FakeClient, searches: tuple[str, ...] = (), countries: tuple[str, ...] = ()
) -> list[str]:
    target = TargetCompany(
        name="Acme", ats="smartrecruiters", identifier="Acme1", searches=searches
    )
    return [o.title for o in SourceAts(client, target, countries).collect()]


@pytest.mark.spec("SRC-35")
def test_smartrecruiters_searches_combine_keywords_and_countries() -> None:
    assert smartrecruiters_searches(["ia", "data"], ["fr", "gb"]) == [
        {"q": "ia", "country": "fr"},
        {"q": "ia", "country": "gb"},
        {"q": "data", "country": "fr"},
        {"q": "data", "country": "gb"},
    ]
    assert smartrecruiters_searches(["ia"], []) == [{"q": "ia"}]
    assert smartrecruiters_searches([], ["fr"]) == [{"country": "fr"}]
    assert smartrecruiters_searches([], []) == []


@pytest.mark.spec("SRC-35")
def test_smartrecruiters_search_reads_pages_until_the_total() -> None:
    client = PagedSmartRecruiters({("ia", "fr"): [str(i) for i in range(250)]})
    titles = _smartrecruiters(client, ("ia",), ("fr",))
    assert len(titles) == 250
    assert [c[1]["offset"] for c in client.calls] == ["0", "100", "200"]
    assert all(c[1]["q"] == "ia" and c[1]["country"] == "fr" for c in client.calls)


@pytest.mark.spec("SRC-35")
def test_smartrecruiters_search_stops_on_a_full_last_page_and_at_five_pages() -> None:
    exact = PagedSmartRecruiters({("", "fr"): [str(i) for i in range(200)]})
    assert len(_smartrecruiters(exact, countries=("fr",))) == 200
    assert len(exact.calls) == 2
    endless = PagedSmartRecruiters({("ia", ""): [str(i) for i in range(900)]}, total=False)
    assert len(_smartrecruiters(endless, ("ia",))) == 500
    assert len(endless.calls) == 5


@pytest.mark.spec("SRC-35")
def test_smartrecruiters_ad_found_by_several_searches_is_kept_once() -> None:
    client = PagedSmartRecruiters({("ia", ""): ["1", "2"], ("data", ""): ["2", "3"]})
    assert _smartrecruiters(client, ("ia", "data")) == ["Ad 1", "Ad 2", "Ad 3"]


@pytest.mark.spec("SRC-35")
def test_smartrecruiters_without_keywords_or_countries_keeps_the_plain_address() -> None:
    client = PagedSmartRecruiters({})
    _smartrecruiters(client)
    assert client.calls == [(URLS["smartrecruiters"].format(id="Acme1"), {"limit": "100"})]


class _BusyWorkday(FakeClient):
    """Workday client refusing the first `refusals` pages with HTTP 429."""

    def __init__(self, refusals: int) -> None:
        super().__init__({})
        self.refusals = refusals

    def post_json(self, url: str, *, body: Any, headers: Any = None) -> Any:
        self.calls.append((url, dict(body)))
        if self.refusals:
            self.refusals -= 1
            raise SourceError(f"{url}: HTTP 429: busy")
        return {"total": 1, "jobPostings": [{"title": "Data", "externalPath": "/job/1"}]}


class _Clock:
    """Fake clock: time only moves when the source pauses."""

    def __init__(self) -> None:
        self.now = 0.0
        self.pauses: list[float] = []

    def clock(self) -> float:
        return self.now

    def pause(self, seconds: float) -> None:
        self.pauses.append(seconds)
        self.now += seconds


WORKDAY_TARGET = TargetCompany(
    name="T", ats="workday", identifier="https://t.wd3.myworkdayjobs.com/C", searches=("ia",)
)


@pytest.mark.spec("SRC-43")
def test_workday_pauses_when_still_refused() -> None:
    clock = _Clock()
    target = WORKDAY_TARGET
    assert len(SourceWorkday(_BusyWorkday(2), target, clock.pause, clock.clock).collect()) == 1
    assert clock.pauses == [60.0, 60.0]
    with pytest.raises(SourceError, match="429"):
        SourceWorkday(_BusyWorkday(3), target, clock.pause, clock.clock).collect()


@pytest.mark.spec("SRC-44")
def test_workday_searches_run_one_after_another_two_seconds_apart() -> None:
    clock = _Clock()
    client = _BusyWorkday(0)
    target = TargetCompany(
        name="T",
        ats="workday",
        identifier="https://t.wd3.myworkdayjobs.com/C",
        searches=("ia", "data"),
    )
    SourceWorkday(client, target, clock.pause, clock.clock).collect()
    assert [body["searchText"] for _, body in client.calls] == ["ia", "data"]
    assert clock.pauses == [2.0]


@pytest.mark.spec("SRC-44")
def test_workday_detail_pages_are_spaced_from_the_searches() -> None:
    clock = _Clock()
    client = _BusyWorkday(0)
    source = SourceWorkday(client, WORKDAY_TARGET, clock.pause, clock.clock)
    (ad,) = source.collect()
    assert clock.pauses == []
    source.add_details(ad)
    assert clock.pauses == [2.0]
