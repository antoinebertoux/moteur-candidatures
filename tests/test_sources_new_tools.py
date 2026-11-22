"""Talentsoft, Oracle Recruiting Cloud, SuccessFactors, Phenom and Avature sources."""

import json
from collections.abc import Mapping

import pytest

from moteur.collection import add_details
from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.own_companies import source_for
from moteur.sources.avature import SourceAvature, ads_avature, complete_avature, portal_of
from moteur.sources.oracle import (
    SourceOracle,
    ads_oracle,
    oracle_description,
    split_oracle_address,
)
from moteur.sources.phenom import SourcePhenom, ads_phenom, split_phenom_address
from moteur.sources.successfactors import (
    SourceSuccessFactors,
    ads_successfactors,
    announced_total,
    complete_successfactors,
)
from moteur.sources.talentsoft import SourceTalentsoft, ads_talentsoft
from tests.conftest import FakeClient

# --- Talentsoft ---------------------------------------------------------------------

FEED_TALENTSOFT = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <link>https://exemple.talent-soft.com/Pages/Offre/detailoffre.aspx?idOffre=1</link>
  <category>Financement</category><category>CDI</category><category>Orléans</category>
  <title>2026-110801 - Originateur Small Cap H/F</title>
  <description>&lt;b&gt;Description :&lt;/b&gt;&lt;br /&gt;Accompagner.</description>
  <pubDate>Sat, 21 Nov 2026 23:10:33 Z</pubDate>
</item>
<item>
  <link>https://exemple.talent-soft.com/Pages/Offre/detailoffre.aspx?idOffre=2</link>
  <category>Finance</category><category>CDI</category>
  <title>Analyste crédit</title>
  <pubDate>pas une date</pubDate>
</item>
<item><title>2026-3 - </title></item>
</channel></rss>"""


@pytest.mark.spec("SRC-81", "SRC-01", "SRC-02")
def test_talentsoft_items_become_ads() -> None:
    first, second = ads_talentsoft("Exemple", FEED_TALENTSOFT)
    assert (first.title, first.location, first.published_on, first.source) == (
        "Originateur Small Cap H/F",
        "Orléans",
        "2026-11-21",
        "talentsoft",
    )
    assert first.description == "Description : Accompagner."
    assert first.url.endswith("idOffre=1")
    assert (second.title, second.location, second.published_on) == ("Analyste crédit", "", "")
    assert ads_talentsoft("Exemple", "pas du xml") == []


@pytest.mark.spec("SRC-80")
def test_talentsoft_reads_the_whole_feed_of_the_host() -> None:
    client = FakeClient({"https://carriere.exemple.com/handlers/offerRss.ashx": FEED_TALENTSOFT})
    target = TargetCompany(
        name="Exemple", ats="talentsoft", identifier="https://carriere.exemple.com/"
    )
    source = source_for(target, client, ())
    assert isinstance(source, SourceTalentsoft)
    assert len(source.collect()) == 2
    assert client.calls == [
        ("https://carriere.exemple.com/handlers/offerRss.ashx", {"LCID": "1036", "top": "1000"})
    ]


# --- Oracle Recruiting Cloud --------------------------------------------------------

ORACLE = "https://hcxg.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs"


def _oracle_answer(ids: range, total: int) -> dict[str, object]:
    requisitions = [
        {
            "Id": str(i),
            "Title": f"Data engineer {i}",
            "PrimaryLocation": "Nanterre, France",
            "PostedDate": "2026-11-20",
        }
        for i in ids
    ]
    return {"items": [{"TotalJobsCount": total, "requisitionList": requisitions}]}


@pytest.mark.spec("SRC-85")
def test_oracle_address_gives_host_language_and_site() -> None:
    site = split_oracle_address(ORACLE)
    assert (site.host, site.language, site.site) == ("hcxg.fa.em2.oraclecloud.com", "en", "CX_1")
    with pytest.raises(ValueError):
        split_oracle_address("https://hcxg.fa.em2.oraclecloud.com/autre/page")


@pytest.mark.spec("SRC-87", "SRC-01", "SRC-02")
def test_oracle_results_become_ads() -> None:
    site = split_oracle_address(ORACLE)
    answer = _oracle_answer(range(1, 2), 1)
    answer["items"][0]["requisitionList"].append({"Id": "9"})  # type: ignore[index]
    (ad,) = ads_oracle("Technip", site, answer)
    assert (ad.title, ad.location, ad.published_on, ad.description, ad.source) == (
        "Data engineer 1",
        "Nanterre, France",
        "2026-11-20",
        "",
        "oracle",
    )
    assert ad.url == (
        "https://hcxg.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/1"
    )
    assert ads_oracle("Technip", site, "pas du json") == []


@pytest.mark.spec("SRC-86")
def test_oracle_searches_each_keyword_page_by_page() -> None:
    site = split_oracle_address(ORACLE)
    pages = {
        site.search_url("data", 0): _oracle_answer(range(25), 30),
        site.search_url("data", 1): _oracle_answer(range(25, 30), 30),
        site.search_url("ia", 0): _oracle_answer(range(3), 3),
    }
    client = FakeClient(pages)
    target = TargetCompany(name="Technip", ats="oracle", identifier=ORACLE, searches=("data", "ia"))
    ads = SourceOracle(client, target).collect()
    assert len(ads) == 30  # ads 0 to 2 found by both keywords are kept once
    assert sorted(u for u, _ in client.calls) == sorted(pages)
    assert "keyword=%22data%22" in site.search_url("data", 0)
    assert "offset=25" in site.search_url("data", 1)


@pytest.mark.spec("SRC-88")
def test_oracle_details_replace_the_text() -> None:
    site = split_oracle_address(ORACLE)
    detail = {
        "items": [
            {
                "ExternalDescriptionStr": "<p>Description</p>",
                "ExternalResponsibilitiesStr": "Missions",
                "ExternalQualificationsStr": "",
            }
        ]
    }
    assert oracle_description(detail) == "Description Missions"
    client = FakeClient({site.detail_url("7"): detail})
    source = SourceOracle(client, TargetCompany(name="T", ats="oracle", identifier=ORACLE))
    ad = JobAd("T", "Data", url=site.posting_url("7"), source="oracle")
    (completed,) = add_details([ad], [source])
    assert completed.description == "Description Missions"
    assert source.add_details(JobAd("T", "D", url=site.posting_url("8"))).description == ""


# --- SuccessFactors -----------------------------------------------------------------


def _sf_row(number: int, city: str = "Saint-Ouen, FR") -> str:
    return f"""<tr class="data-row">
  <td class="colTitle"><span class="jobTitle hidden-phone">
    <a href="/job/Ville-Poste-{number}/{number}/" class="jobTitle-link">Data &amp; IA {number}</a>
  </span></td>
  <td class="colLocation hidden-phone" headers="hdrLocation">
    <span class="jobLocation"> {city} </span>
  </td>
  <td class="colDate hidden-phone"><span class="jobDate">6 nov. 2026</span></td>
</tr>"""


def _sf_page(numbers: range, total: int) -> str:
    rows = "".join(_sf_row(n) for n in numbers)
    label = f'<span class="paginationLabel" aria-label="x">Results <b>1 – 25</b> of <b>{total}</b>'
    return f"<html>{label}<table>{rows}</table></html>"


@pytest.mark.spec("SRC-91", "SRC-01", "SRC-02")
def test_successfactors_rows_become_ads() -> None:
    page = _sf_page(range(1, 3), 2) + '<tr class="data-row"><td>sans lien</td></tr>'
    first, _ = ads_successfactors("Alstom", "jobsearch.alstom.com", page)
    assert (first.title, first.location, first.published_on, first.source) == (
        "Data & IA 1",
        "Saint-Ouen, FR",
        "",
        "successfactors",
    )
    assert first.url == "https://jobsearch.alstom.com/job/Ville-Poste-1/1/"
    assert announced_total(page) == 2
    assert announced_total("<html></html>") == 0


@pytest.mark.spec("SRC-90", "SRC-05")
def test_successfactors_searches_each_keyword_and_country() -> None:
    pages = [_sf_page(range(25), 30), _sf_page(range(25, 30), 30)]
    url = "https://jobsearch.alstom.com/search/"

    class PagedClient(FakeClient):
        def get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
            self.calls.append((url, dict(params or {})))
            start = int((params or {}).get("startrow", "0"))
            return pages[start // 25] if start // 25 < len(pages) else ""

    client = PagedClient({})
    target = TargetCompany(
        name="Alstom", ats="successfactors", identifier="jobsearch.alstom.com", searches=("data",)
    )
    source = source_for(target, client, ("fr", "de"))
    assert isinstance(source, SourceSuccessFactors)
    assert len(source.collect()) == 30  # the same ads in both countries are kept once
    assert sorted((p["optionsFacetsDD_country"], p["startrow"]) for _, p in client.calls) == [
        ("DE", "0"),
        ("DE", "25"),
        ("FR", "0"),
        ("FR", "25"),
    ]
    assert {u for u, _ in client.calls} == {url}
    assert all(p["q"] == "data" for _, p in client.calls)
    client.calls.clear()
    SourceSuccessFactors(client, target).collect()
    assert all("optionsFacetsDD_country" not in p for _, p in client.calls)


@pytest.mark.spec("SRC-92")
def test_successfactors_page_gives_the_text() -> None:
    url = "https://jobsearch.alstom.com/job/Ville-Poste-1/1/"
    page = (
        '<div><span itemprop="description" class="jobdescription"><p>Concevoir '
        "<span>des trains</span>.</p></span></div><span>Pied de page</span>"
    )
    client = FakeClient({url: page})
    source = SourceSuccessFactors(
        client, TargetCompany(name="Alstom", identifier="jobsearch.alstom.com")
    )
    (ad,) = add_details([JobAd("Alstom", "Poste", url=url, source="successfactors")], [source])
    assert ad.description == "Concevoir des trains ."
    assert complete_successfactors(ad, "<html></html>") == ad


# --- Phenom -------------------------------------------------------------------------


def _phenom_answer(ids: range, total: int) -> dict[str, object]:
    jobs = [
        {
            "jobId": str(i),
            "title": f"Consultant {i}",
            "location": "Paris, France",
            "postedDate": "2026-06-18T00:00:00.000+0000",
        }
        for i in ids
    ]
    return {"refineSearch": {"totalHits": total, "data": {"jobs": jobs}}}


@pytest.mark.spec("SRC-94")
def test_phenom_address_gives_country_and_language() -> None:
    site = split_phenom_address("https://careers.bcg.com/global/en/")
    assert (site.host, site.country, site.language) == ("careers.bcg.com", "global", "en")
    assert site.body("data", 1)["lang"] == "en_global"
    assert site.body("data", 1)["from"] == 50
    with pytest.raises(ValueError):
        split_phenom_address("careers.bcg.com")


@pytest.mark.spec("SRC-95", "SRC-01")
def test_phenom_searches_each_keyword_page_by_page() -> None:
    site = split_phenom_address("careers.bcg.com/global/en")
    answer = _phenom_answer(range(1, 2), 1)
    answer["refineSearch"]["data"]["jobs"].append({"jobId": "", "title": "x"})  # type: ignore[index]
    answer["refineSearch"]["data"]["jobs"].append({"jobId": "4", "city": "Lyon"})  # type: ignore[index]
    (ad,) = ads_phenom("BCG", site, answer)
    assert (ad.title, ad.location, ad.published_on, ad.url, ad.source) == (
        "Consultant 1",
        "Paris, France",
        "2026-06-18",
        "https://careers.bcg.com/global/en/job/1",
        "phenom",
    )
    client = FakeClient(
        {
            "https://careers.bcg.com/widgets": [
                _phenom_answer(range(50), 60),
                _phenom_answer(range(50, 60), 60),
            ]
        }
    )
    target = TargetCompany(
        name="BCG", ats="phenom", identifier="careers.bcg.com/global/en", searches=("data",)
    )
    assert len(SourcePhenom(client, target).collect()) == 60
    assert [body["from"] for _, body in client.calls] == [0, 50]
    assert all(body["keywords"] == "data" for _, body in client.calls)


@pytest.mark.spec("SRC-96")
def test_phenom_page_gives_title_text_and_date() -> None:
    url = "https://careers.bcg.com/global/en/job/1"
    data = {"@type": "JobPosting", "title": "Consultant", "description": "<p>Conseiller</p>"}
    page = f'<script type="application/ld+json">{json.dumps(data)}</script>'
    client = FakeClient({url: page})
    source = SourcePhenom(client, TargetCompany(name="BCG", identifier="careers.bcg.com/global/en"))
    ad = JobAd("BCG", "Consultant 1", url=url, source="phenom", published_on="2026-06-18")
    (completed,) = add_details([ad], [source])
    assert (completed.title, completed.description, completed.published_on) == (
        "Consultant",
        "Conseiller",
        "2026-06-18",
    )


# --- Avature ------------------------------------------------------------------------

FEED_AVATURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title><![CDATA[Ingénieur Mécanique F/H]]></title>
  <link>https://jobs.orano.group/jobs/JobDetail/Ing-nieur-M-canique-F-H/6365</link>
  <pubDate>Thu, 26 Feb 2026 00:00:00 +0000</pubDate>
</item>
<item><title><![CDATA[Sans lien]]></title></item>
</channel></rss>"""


@pytest.mark.spec("SRC-97", "SRC-01")
def test_avature_feed_is_searched_per_keyword() -> None:
    (ad,) = ads_avature("Orano", FEED_AVATURE)
    assert (ad.title, ad.location, ad.published_on, ad.source) == (
        "Ingénieur Mécanique F/H",
        "",
        "2026-02-26",
        "avature",
    )
    assert ads_avature("Orano", "pas du xml") == []
    assert portal_of("https://jobs.orano.group/fr_FR/jobs/SearchJobs") == (
        "https://jobs.orano.group/fr_FR/jobs"
    )
    with pytest.raises(ValueError):
        portal_of("jobs.orano.group")
    feed = "https://jobs.orano.group/fr_FR/jobs/SearchJobs/feed/"
    client = FakeClient({feed: FEED_AVATURE})
    target = TargetCompany(
        name="Orano", ats="avature", identifier="jobs.orano.group/fr_FR/jobs", searches=("a", "b")
    )
    assert len(SourceAvature(client, target).collect()) == 1
    assert client.calls == [(feed, {"search": "a"}), (feed, {"search": "b"})]


@pytest.mark.spec("SRC-98", "SRC-02")
def test_avature_page_gives_location_and_text() -> None:
    url = "https://jobs.orano.group/jobs/JobDetail/Ing-nieur-M-canique-F-H/6365"
    long_text = "Votre mission : " + "concevoir des &eacute;quipements. " * 5
    page = "".join(
        f'<dl><dt class="article__content__view__field__label" > {label} </dt>'
        f'<dd class="article__content__view__field__value"> {value} </dd></dl>'
        for label, value in (("Ref #", "6365"), ("Country", "France"), ("City", "Aix"))
    ) + (
        '<div class="article__content__view__field__label">Description</div>'
        f'<div class="article__content__view__field__value"><p>{long_text}</p></div>'
    )
    client = FakeClient({url: page})
    source = SourceAvature(
        client, TargetCompany(name="Orano", identifier="jobs.orano.group/fr_FR/jobs")
    )
    (ad,) = add_details([JobAd("Orano", "Ingénieur", url=url, source="avature")], [source])
    assert ad.location == "Aix, France"
    assert ad.description.startswith("Votre mission : concevoir des équipements.")
    assert complete_avature(ad, "<html></html>") == ad
