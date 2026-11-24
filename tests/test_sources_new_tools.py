"""Talentsoft, Oracle, SuccessFactors, Phenom, Avature, Gestmax, SNCF, Taleez, WeRecruit,
Cornerstone,
Rippling, Talentry, JOIN."""

import base64
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from moteur.collection import add_details
from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.own_companies import source_for
from moteur.sources.avature import SourceAvature, ads_avature, complete_avature, portal_of
from moteur.sources.base import SourceError
from moteur.sources.cornerstone import (
    SourceCornerstone,
    ads_cornerstone,
    split_cornerstone_address,
)
from moteur.sources.gestmax import (
    SourceGestmax,
    ads_gestmax,
    ads_gestmax_table,
    complete_gestmax,
)
from moteur.sources.join import SourceJoin, ads_join
from moteur.sources.magnet import SourceMagnet, ads_magnet, login_body, public_key
from moteur.sources.mckinsey import SourceMcKinsey, ads_mckinsey
from moteur.sources.oracle import (
    SourceOracle,
    ads_oracle,
    oracle_description,
    split_oracle_address,
)
from moteur.sources.phenom import SourcePhenom, ads_phenom, split_phenom_address
from moteur.sources.rippling import SourceRippling, ads_rippling, complete_rippling
from moteur.sources.sitemap import SourceSitemap, complete_sitemap, provisional_title
from moteur.sources.sncf import SEARCH as SNCF_SEARCH
from moteur.sources.sncf import SourceSncf, ads_sncf, complete_sncf
from moteur.sources.successfactors import (
    SourceSuccessFactors,
    ads_successfactors,
    announced_total,
    complete_successfactors,
)
from moteur.sources.taleez import SourceTaleez, ads_taleez, complete_taleez
from moteur.sources.talentry import SourceTalentry, ads_talentry, complete_talentry
from moteur.sources.talentsoft import SourceTalentsoft, ads_talentsoft
from moteur.sources.werecruit import SourceWeRecruit, ads_werecruit, embedded_offers
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


# --- Magnet by Hellowork -------------------------------------------------------------

MAGNET_PAGE = '<script>window.cvc = {"config": {"publicKey": "abc123", "x": 1}}</script>'


def _magnet_answer(ids: range, total: int) -> dict[str, object]:
    offers = [
        {
            "id": f"9452-{i}",
            "title": f"Soudeur {i}",
            "language": "fr",
            "localities": [{"city_label": "Yvetot", "country": "France"}],
            "description": "Souder des <b>tuyauteries</b>",
            "publication_date": "2026-11-19T14:53:33.000Z",
        }
        for i in ids
    ]
    return {"code": 200, "data": {"total": total, "list": offers}}


class _MagnetClient(FakeClient):
    """Serves the site page, the login and the search pages in order."""

    def __init__(self, token: str, pages: list[dict[str, object]]) -> None:
        super().__init__({"https://jobs.exemple.com/": MAGNET_PAGE})
        self.token, self.pages = token, pages
        self.headers: list[dict[str, str]] = []

    def post_json(
        self, url: str, *, body: Mapping[str, Any], headers: Mapping[str, str] | None = None
    ) -> Any:
        self.calls.append((url, dict(body)))
        self.headers.append(dict(headers or {}))
        if url.endswith("/security/login"):
            return {"data": {"token": self.token, "expires": "x"}} if self.token else {"data": {}}
        return self.pages.pop(0) if self.pages else None


_NOW = datetime(2026, 11, 22, 18, 2, 48, 475000, tzinfo=UTC)


@pytest.mark.spec("SRC-75")
def test_magnet_gets_an_anonymous_token_from_the_public_key() -> None:
    assert public_key(MAGNET_PAGE) == "abc123"
    assert public_key("<html></html>") == ""
    assert login_body("abc123", _NOW) == {
        "usr": base64.b64encode(b"abc123").decode(),
        "pass": base64.b64encode(b"2026-11-22T18:02:48.475Z").decode(),
    }
    target = TargetCompany(name="Fives", ats="magnet", identifier="jobs.exemple.com")
    with pytest.raises(SourceError, match="token"):
        SourceMagnet(_MagnetClient("", []), target, lambda: _NOW).collect()
    with pytest.raises(SourceError, match="public key"):
        SourceMagnet(FakeClient({}), target, lambda: _NOW).collect()


@pytest.mark.spec("SRC-76")
def test_magnet_reads_every_ad_page_by_page() -> None:
    client = _MagnetClient(
        "t0k", [_magnet_answer(range(100), 150), _magnet_answer(range(100, 150), 150)]
    )
    target = TargetCompany(name="Fives", ats="magnet", identifier="https://jobs.exemple.com/fr")
    source = source_for(target, client, ())
    assert isinstance(source, SourceMagnet)
    assert len(source.collect()) == 150
    searches = [body for url, body in client.calls if url.endswith("/v2/job-offers")]
    assert [(b["offset"], b["limit"], b["cities"]) for b in searches] == [
        (0, 100, []),
        (100, 100, []),
    ]
    assert client.headers[1]["Authorization"] == "Bearer t0k"
    assert client.headers[1]["x-session-id"] == client.headers[0]["x-session-id"]


@pytest.mark.spec("SRC-77", "SRC-01", "SRC-02")
def test_magnet_offers_become_ads() -> None:
    answer = _magnet_answer(range(1), 1)
    answer["data"]["list"] += [{"id": "x"}, {"title": "Sans id"}, {"id": "9", "title": "Sans lieu"}]  # type: ignore[index]
    first, second = ads_magnet("Fives", "jobs.exemple.com", answer)
    assert (first.title, first.location, first.published_on, first.source) == (
        "Soudeur 0",
        "Yvetot, France",
        "2026-11-19",
        "magnet",
    )
    assert first.description == "Souder des tuyauteries"
    assert first.url == "https://jobs.exemple.com/fr/offer/9452-0"
    assert (second.location, second.url) == ("", "https://jobs.exemple.com/fr/offer/9")
    assert ads_magnet("Fives", "jobs.exemple.com", None) == []


# --- Sitemap of offers ----------------------------------------------------------------

ROBOTS = (
    "User-agent: *\nDisallow: /search/\nSitemap: https://careers.exemple.com/sitemap-index.xml\n"
)
SITEMAP_INDEX = """<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://careers.exemple.com/sitemap-jobs.xml</loc></sitemap>
</sitemapindex>"""
SITEMAP_JOBS = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://careers.exemple.com/offres-d-emploi/</loc></url>
<url><loc>https://careers.exemple.com/offres-d-emploi/algo-developer-260002H8-en</loc></url>
<url><loc>https://careers.exemple.com/offres-d-emploi/algo-developer-260002H8-en</loc></url>
<url><loc>https://careers.exemple.com/offres-d-emploi/2600032A</loc></url>
<url><loc>https://careers.exemple.com/metiers/data</loc></url>
</urlset>"""


@pytest.mark.spec("SRC-52", "SRC-53")
def test_sitemap_offers_come_from_the_robots_sitemaps() -> None:
    client = FakeClient(
        {
            "https://careers.exemple.com/robots.txt": ROBOTS,
            "https://careers.exemple.com/sitemap-index.xml": SITEMAP_INDEX,
            "https://careers.exemple.com/sitemap-jobs.xml": SITEMAP_JOBS,
        }
    )
    target = TargetCompany(
        name="SG", ats="sitemap", identifier="careers.exemple.com/offres-d-emploi"
    )
    source = source_for(target, client, ())
    assert isinstance(source, SourceSitemap)
    (ad,) = source.collect()
    assert (ad.title, ad.location, ad.description, ad.source) == (
        "Algo Developer",
        "",
        "",
        "sitemap",
    )
    assert ad.url == "https://careers.exemple.com/offres-d-emploi/algo-developer-260002H8-en"
    assert provisional_title(
        "https://jobs.exail.com/fr/annonce/4701647-ingenieur-electronique-hf-78100-saint-germain"
    ) == ("Ingenieur Electronique Hf")
    assert provisional_title("https://x.com/jobs/junior-software-engineer-550851") == (
        "Junior Software Engineer"
    )
    # Without a Sitemap line, /sitemap.xml is read; an unreadable one gives nothing.
    fallback = FakeClient({"https://careers.exemple.com/sitemap.xml": SITEMAP_JOBS})
    assert len(SourceSitemap(fallback, target).collect()) == 1
    assert SourceSitemap(FakeClient({}), target).collect() == []


@pytest.mark.spec("SRC-54", "SRC-51")
def test_sitemap_page_gives_title_text_date_and_location() -> None:
    url = "https://careers.exemple.com/offres-d-emploi/algo-developer-260002H8-en"
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "JobPosting",
                "title": "Algo Developer H/F",
                "description": "<p>Coder des algorithmes</p>",
                "datePosted": "2026/02/20",
                "jobLocation": {
                    "@type": "Place",
                    "address": {"addressLocality": "Montréal", "addressCountry": "Canada"},
                },
            }
        ],
    }
    page = f'<script type="application/ld+json">{json.dumps(data)}</script>'
    source = SourceSitemap(
        FakeClient({url: page}),
        TargetCompany(name="SG", identifier="careers.exemple.com/offres-d-emploi/"),
    )
    (ad,) = add_details([JobAd("SG", "Algo Developer", url=url, source="sitemap")], [source])
    assert (ad.title, ad.description, ad.published_on, ad.location) == (
        "Algo Developer H/F",
        "Coder des algorithmes",
        "2026-02-20",
        "Montréal, Canada",
    )
    plain = JobAd("SG", "Algo Developer", url=url, source="sitemap")
    assert complete_sitemap(plain, "<html></html>") == plain


# --- McKinsey -------------------------------------------------------------------------


def _mckinsey_answer(ids: range, total: int) -> dict[str, object]:
    docs = [
        {
            "jobID": str(i),
            "title": f"Data Scientist {i}",
            "friendlyURL": f"datascientist-{i}",
            "cities": ["Paris", "London"],
            "whoYouWillWorkWith": "<div>QuantumBlack</div>",
            "whatYouWillDo": "<p>Build models</p>",
            "yourBackground": "",
            "postedToLinkedInDate": "2026-10-27",
        }
        for i in ids
    ]
    return {"numFound": total, "docs": docs}


@pytest.mark.spec("SRC-63", "SRC-01", "SRC-02")
def test_mckinsey_results_become_ads() -> None:
    answer = _mckinsey_answer(range(1), 1)
    answer["docs"].append({"title": "Sans lien"})  # type: ignore[attr-defined]
    (ad,) = ads_mckinsey("McKinsey", answer)
    assert (ad.title, ad.location, ad.description, ad.published_on, ad.source) == (
        "Data Scientist 0",
        "Paris, London",
        "QuantumBlack Build models",
        "2026-10-27",
        "mckinsey",
    )
    assert ad.url == "https://www.mckinsey.com/careers/search-jobs/jobs/datascientist-0"
    assert ads_mckinsey("McKinsey", {"docs": None}) == []


@pytest.mark.spec("SRC-62", "SRC-05")
def test_mckinsey_searches_each_keyword_page_by_page() -> None:
    class PagedClient(FakeClient):
        def get_json(
            self,
            url: str,
            *,
            params: Mapping[str, str] | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> Any:
            self.calls.append((url, dict(params or {})))
            page = int((params or {})["start"])
            return (
                _mckinsey_answer(range(100), 150)
                if page == 1
                else _mckinsey_answer(range(100, 150), 150)
            )

    client = PagedClient({})
    target = TargetCompany(
        name="McKinsey", ats="mckinsey", identifier="www.mckinsey.com", searches=("data", "ia")
    )
    source = source_for(target, client, ())
    assert isinstance(source, SourceMcKinsey)
    assert len(source.collect()) == 150  # the same ads for both keywords are kept once
    assert sorted((p["q"], p["start"], p["pageSize"]) for _, p in client.calls) == [
        ("data", "1", "100"),
        ("data", "2", "100"),
        ("ia", "1", "100"),
        ("ia", "2", "100"),
    ]


# --- Gestmax ----------------------------------------------------------------------------

GESTMAX_LIST = "https://jobs.exemple.gestmax.fr/search/index/frontsearchtab_id/7"


def _gestmax_entry(number: int, city: str = "ROUFFIAC TOLOSAN") -> str:
    link = f"https://jobs.exemple.gestmax.fr/{number}/1/responsable-h-f"
    return f"""<a href="{link}" onclick="x" class="list-group-item cell1" target="_blank" >
  <h2 class="list-group-item-heading">Responsable {number} (H/F)</h2>
  <div class="listdiv-item listdiv-vacancy_activation_date">
    <span class="listdiv-label">Date :</span><span class="listdiv-value">20/11/2026</span></div>
  <div class="listdiv-item listdiv-dept_ville">
    <span class="listdiv-label">Ville :</span><span class="listdiv-value">{city}</span></div>
  <span class="listdiv-item listdiv-dept_pays">- France</span>
</a>"""


def _gestmax_page(numbers: range, last: int) -> str:
    links = "".join(
        f'<a href="/search/index/frontsearchtab_id/7/page/{n}">{n}</a>' for n in range(1, last + 1)
    )
    return "<div>" + "".join(_gestmax_entry(n) for n in numbers) + links + "</div>"


@pytest.mark.spec("SRC-83", "SRC-01")
def test_gestmax_entries_become_ads() -> None:
    page = _gestmax_page(range(1, 2), 1) + (
        '<a href="https://jobs.exemple.gestmax.fr/9/1/x" class="list-group-item cell1">'
        '<h2 class="list-group-item-heading"> </h2></a>'
    )
    (ad,) = ads_gestmax("Beaumanoir", page)
    assert (ad.title, ad.location, ad.published_on, ad.source) == (
        "Responsable 1 (H/F)",
        "ROUFFIAC TOLOSAN, France",
        "2026-11-20",
        "gestmax",
    )
    assert ad.url == "https://jobs.exemple.gestmax.fr/1/1/responsable-h-f"


@pytest.mark.spec("SRC-82")
def test_gestmax_reads_the_list_page_by_page() -> None:
    client = FakeClient(
        {
            f"{GESTMAX_LIST}/page/1": _gestmax_page(range(10), 2),
            f"{GESTMAX_LIST}/page/2": _gestmax_page(range(5, 13), 2),
        }
    )
    target = TargetCompany(name="Beaumanoir", ats="gestmax", identifier=GESTMAX_LIST + "/")
    source = source_for(target, client, ())
    assert isinstance(source, SourceGestmax)
    assert len(source.collect()) == 13  # ads 5 to 9, listed twice, are kept once
    assert [u for u, _ in client.calls] == [f"{GESTMAX_LIST}/page/1", f"{GESTMAX_LIST}/page/2"]
    # A page without ads ends the list even if more pages are linked.
    empty = FakeClient({f"{GESTMAX_LIST}/page/1": "<html></html>"})
    assert SourceGestmax(empty, target).collect() == []


@pytest.mark.spec("SRC-84", "SRC-02")
def test_gestmax_page_gives_the_text() -> None:
    url = "https://jobs.exemple.gestmax.fr/1/1/responsable-h-f"
    page = (
        '<div id="content"><div id="content-wrapper"><div class="text"><p>Pilotez le '
        'magasin &amp; l\'&eacute;quipe.</p></div><div class="apply"><a>Postuler</a></div>'
    )
    source = SourceGestmax(
        FakeClient({url: page}), TargetCompany(name="B", identifier=GESTMAX_LIST)
    )
    (ad,) = add_details([JobAd("B", "Responsable", url=url, source="gestmax")], [source])
    assert ad.description == "Pilotez le magasin & l'équipe."
    assert complete_gestmax(ad, "<html></html>") == ad


def _gestmax_row(number: int, title: str = "PMO F/H") -> str:
    link = f"https://mbda.exemple.gestmax.fr/{number}/1/pmo-f-h?backlink=search"
    cells = (
        ("vacancy_title", title),
        ("vacancy_activation_date", "19/11/2026"),
        ("vac_sector", "Gestion de projet"),
        ("vac_localisation", "Le Plessis Robinson (92)"),
    )
    tds = "".join(
        f'<td headers="{h}" class="col_{h}">\n\t\t<a href="{link}" >\t\t{v}\n\t</a></td>'
        for h, v in cells
    )
    return f'<tr class="cell1 vacancy-id-{number}">{tds}</tr>'


@pytest.mark.spec("SRC-99", "SRC-01", "SRC-02")
def test_gestmax_table_rows_become_ads() -> None:
    page = "<table>" + _gestmax_row(1, "Ing&eacute;nieur F/H") + _gestmax_row(2, " ") + "</table>"
    (ad,) = ads_gestmax_table("MBDA", page)
    assert (ad.title, ad.location, ad.published_on, ad.source) == (
        "Ingénieur F/H",
        "Le Plessis Robinson (92)",
        "2026-11-19",
        "gestmax",
    )
    assert ad.url == "https://mbda.exemple.gestmax.fr/1/1/pmo-f-h"
    assert ads_gestmax("MBDA", page) == []


@pytest.mark.spec("SRC-99", "SRC-82")
def test_gestmax_reads_a_table_list_page_by_page() -> None:
    address = "https://mbda.exemple.gestmax.fr/search/index"
    links = '<a href="/search/index/page/1">1</a><a href="/search/index/page/2">2</a>'
    client = FakeClient(
        {
            f"{address}/page/1": "".join(_gestmax_row(n) for n in range(20)) + links,
            f"{address}/page/2": _gestmax_row(19) + _gestmax_row(20) + links,
        }
    )
    target = TargetCompany(
        name="MBDA", ats="gestmax", identifier="mbda.exemple.gestmax.fr/search/index"
    )
    assert len(SourceGestmax(client, target).collect()) == 21
    assert len(client.calls) == 2


@pytest.mark.spec("SRC-84")
def test_gestmax_page_without_content_area_starts_at_its_first_text() -> None:
    page = (
        '<div class="container"><h1>PMO F/H</h1><div class="text"><h2>Votre quotidien</h2>'
        '<p>Piloter.</p></div><div class="text"><p>Profil.</p></div>'
        '<div class="apply"><a>Postuler</a></div>'
    )
    ad = JobAd("MBDA", "PMO", url="https://mbda.exemple.gestmax.fr/1/1/pmo", source="gestmax")
    assert complete_gestmax(ad, page).description == "Votre quotidien Piloter. Profil."


# --- SNCF -------------------------------------------------------------------------------


def _sncf_offer(number: int, **fields: Any) -> dict[str, Any]:
    offer: dict[str, Any] = {
        "id": str(number),
        "company": "SNCF RESEAU",
        "title": f"Electricien {number} (F/H)",
        "location": "Lille, Nord (59)",
        "publicationDate": "2026-11-20T12:43:52+0000",
        "description": "",
        "inactive": False,
    }
    return offer | fields


def _sncf_answer(offers: list[dict[str, Any]], total: int) -> dict[str, Any]:
    return {"jobIds": [o["id"] for o in offers], "jobs": {"offers": offers, "totalCount": total}}


@pytest.mark.spec("SRC-101", "SRC-01")
def test_sncf_offers_become_ads() -> None:
    answer = _sncf_answer(
        [_sncf_offer(1), _sncf_offer(2, inactive=True), _sncf_offer(3, title=""), {"id": 4}],
        4,
    )
    (ad,) = ads_sncf("SNCF Réseau", answer)
    assert (ad.company, ad.title, ad.location, ad.published_on, ad.source) == (
        "SNCF Réseau",
        "Electricien 1 (F/H)",
        "Lille, Nord (59)",
        "2026-11-20",
        "sncf",
    )
    assert ad.url == "https://emploi.sncf.com/nos-offres/1"
    assert ads_sncf("SNCF Réseau", None) == []


@pytest.mark.spec("SRC-100")
def test_sncf_reads_every_ad_of_one_company_page_by_page() -> None:
    pages = [
        _sncf_answer([_sncf_offer(n) for n in range(20)], 25),
        _sncf_answer([_sncf_offer(n) for n in range(15, 25)], 25),
    ]
    client = FakeClient({SNCF_SEARCH: pages})
    target = TargetCompany(name="SNCF Réseau", ats="sncf", identifier=" 6684 ")
    source = source_for(target, client, ())
    assert isinstance(source, SourceSncf)
    assert len(source.collect()) == 25  # ads 15 to 19, listed twice, are kept once
    assert [body for _, body in client.calls] == [
        {"facets": {"company": ["6684"]}, "currentPage": 1, "loadOffers": True},
        {"facets": {"company": ["6684"]}, "currentPage": 2, "loadOffers": True},
    ]
    # The announced total ends the reading even after a full page.
    full = FakeClient({SNCF_SEARCH: [_sncf_answer([_sncf_offer(n) for n in range(20)], 20)]})
    assert len(SourceSncf(full, target).collect()) == 20
    assert len(full.calls) == 1


@pytest.mark.spec("SRC-102", "SRC-02")
def test_sncf_page_gives_the_text() -> None:
    url = "https://emploi.sncf.com/nos-offres/1"
    posting = {
        "@type": "JobPosting",
        "title": "Electricien",
        "description": "Publiée le 20/11/2026&lt;br /&gt;&lt;b&gt;Description du poste&lt;/b&gt;",
    }
    page = f'<script type="application/ld+json">{json.dumps(posting)}</script>'
    source = SourceSncf(FakeClient({url: page}), TargetCompany(name="S", identifier="6684"))
    (ad,) = add_details([JobAd("S", "Electricien", url=url, source="sncf")], [source])
    assert ad.description == "Publiée le 20/11/2026 Description du poste"
    assert complete_sncf(ad, "<html></html>") == ad


# --- Taleez -----------------------------------------------------------------------------

TALEEZ_LIST = "https://tehtris.taleez.com/api/careez"


def _taleez_job(slug: str, label: str = "Service Delivery Manager", **extra: Any) -> dict[str, Any]:
    job: dict[str, Any] = {
        "label": label,
        "slug": slug,
        "publishDate": 1794989392000,
        "location": {"city": "Bordeaux", "country": "FR", "postalCode": "33000"},
    }
    return job | extra


@pytest.mark.spec("SRC-104", "SRC-01")
def test_taleez_jobs_become_ads() -> None:
    answer = {
        "jobs": [
            _taleez_job("service-delivery-manager-bordeaux-tehtris-cdi"),
            _taleez_job("sans-lieu", "Analyste SOC", location=None, publishDate="hier"),
            _taleez_job("sans-titre", label=""),
            {"label": "Sans slug"},
            "pas un objet",
        ]
    }
    first, second = ads_taleez("TEHTRIS", answer)
    assert (first.title, first.location, first.published_on, first.source) == (
        "Service Delivery Manager",
        "Bordeaux, FR",
        "2026-11-18",
        "taleez",
    )
    assert first.url == "https://taleez.com/apply/service-delivery-manager-bordeaux-tehtris-cdi"
    assert (second.title, second.location, second.published_on) == ("Analyste SOC", "", "")
    assert ads_taleez("TEHTRIS", None) == []


@pytest.mark.spec("SRC-103")
def test_taleez_reads_the_site_list_once() -> None:
    answer = {"jobs": [_taleez_job("a"), _taleez_job("b"), _taleez_job("a")]}
    client = FakeClient({TALEEZ_LIST: answer})
    target = TargetCompany(name="TEHTRIS", ats="taleez", identifier="https://tehtris.taleez.com/en")
    source = source_for(target, client, ())
    assert isinstance(source, SourceTaleez)
    assert [ad.url for ad in source.collect()] == [
        "https://taleez.com/apply/a",
        "https://taleez.com/apply/b",
    ]
    assert client.calls == [(TALEEZ_LIST, {})]
    # An unreadable answer gives no ad.
    assert SourceTaleez(FakeClient({}), target).collect() == []


@pytest.mark.spec("SRC-105", "SRC-51", "SRC-02")
def test_taleez_page_gives_the_text_and_the_profile() -> None:
    url = "https://taleez.com/apply/a"
    posting = {
        "@type": "JobPosting",
        "title": "Service Delivery Manager MDR - F/M/X",
        "description": "<p><strong>CONTEXTE</strong></p><p>Au sein du MDR.</p>",
        "qualifications": "<ul><li>5 ans minimum</li></ul>",
        "datePosted": "2026-11-18T09:09:52+0100",
    }
    page = f'<script type="application/ld+json">{json.dumps(posting)}</script>'
    source = SourceTaleez(
        FakeClient({url: page}), TargetCompany(name="T", identifier="t.taleez.com")
    )
    (ad,) = add_details(
        [JobAd("T", "Service Delivery Manager", url=url, source="taleez")], [source]
    )
    assert ad.title == "Service Delivery Manager MDR - F/M/X"
    assert ad.description == "CONTEXTE Au sein du MDR.\n5 ans minimum"
    assert ad.published_on == "2026-11-18"
    without_profile = page.replace("qualifications", "autre")
    assert complete_taleez(ad, without_profile).description == "CONTEXTE Au sein du MDR."
    assert complete_taleez(ad, "<html></html>") == ad


# --- WeRecruit --------------------------------------------------------------------------

WERECRUIT_SITE = "https://careers.werecruit.io/en/unseenlabs"


def _werecruit_offer(number: int, **extra: Any) -> dict[str, Any]:
    offer: dict[str, Any] = {
        "Id": f"id-{number}",
        "Title": {"fr-fr": f"Ingénieur logiciel {number}"},
        "TitleTranslated": f"Ingénieur logiciel {number} F/H",
        "Url": f"{WERECRUIT_SITE}/offers/ingenieur-logiciel-{number}",
        "Address_City": "Cesson-Sévigné",
        "Address_State": "FR",
        "PublicationStartDate": "2026-11-20T10:40:36.2824107+00:00",
    }
    return offer | extra


def _werecruit_page(offers: list[Any]) -> str:
    return (
        "<script>window.didomiOnReady = window.didomiOnReady || [];\n"
        f"window.allOffers = {json.dumps(offers)};\n"
        'window.offersConfig = {"count":6,"step":10};</script>'
    )


@pytest.mark.spec("SRC-107", "SRC-01")
def test_werecruit_offers_become_ads() -> None:
    page = _werecruit_page(
        [
            _werecruit_offer(1),
            _werecruit_offer(2, TitleTranslated="", Address_State=None),
            _werecruit_offer(3, TitleTranslated="", Title={}),
            _werecruit_offer(4, Url=""),
        ]
    )
    first, second = ads_werecruit("Unseenlabs", page)
    assert (first.title, first.location, first.published_on, first.source) == (
        "Ingénieur logiciel 1 F/H",
        "Cesson-Sévigné, FR",
        "2026-11-20",
        "werecruit",
    )
    assert first.url == f"{WERECRUIT_SITE}/offers/ingenieur-logiciel-1"
    assert (second.title, second.location) == ("Ingénieur logiciel 2", "Cesson-Sévigné")


@pytest.mark.spec("SRC-106")
def test_werecruit_reads_the_list_embedded_in_the_home_page() -> None:
    offers = [_werecruit_offer(n) for n in range(8)] + [_werecruit_offer(3)]
    client = FakeClient({WERECRUIT_SITE: _werecruit_page(offers)})
    target = TargetCompany(name="Unseenlabs", ats="werecruit", identifier=WERECRUIT_SITE + "/")
    source = source_for(target, client, ())
    assert isinstance(source, SourceWeRecruit)
    assert len(source.collect()) == 8  # more than the 6 shown; offer 3, twice, kept once
    assert client.calls == [(WERECRUIT_SITE, {})]
    # A page without the list, or with an unreadable one, gives no ad.
    assert embedded_offers("<html></html>") == []
    assert embedded_offers("window.allOffers = [{oops};") == []


@pytest.mark.spec("SRC-108", "SRC-51")
def test_werecruit_page_gives_the_text_from_escaped_data() -> None:
    url = f"{WERECRUIT_SITE}/offers/ingenieur-logiciel-1"
    posting = {
        "@type": "JobPosting",
        "title": "Ingénieur IA - Data Scientist F/H",
        "description": "\u003cp\u003eAfin de poursuivre son d&eacute;veloppement.\u003c/p\u003e",
        "datePosted": "2026-11-10T12:59:21+00:00",
    }
    page = f'<script type="application/ld&#x2B;json">{json.dumps(posting)}</script>'
    source = SourceWeRecruit(
        FakeClient({url: page}), TargetCompany(name="G", identifier=WERECRUIT_SITE)
    )
    (ad,) = add_details([JobAd("G", "Ingénieur IA", url=url, source="werecruit")], [source])
    assert ad.title == "Ingénieur IA - Data Scientist F/H"
    assert ad.description == "Afin de poursuivre son développement."
    assert ad.published_on == "2026-11-10"


# --- Cornerstone ------------------------------------------------------------------------

CORNERSTONE_PAGE_URL = "https://hris-suez.csod.com/ux/ats/careersite/10/home?c=hris-suez"
CORNERSTONE_SEARCH = "https://uk.api.csod.com/rec-job-search/external/jobs"
CORNERSTONE_PAGE = (
    '<script>csod.context={"corp":"hris-suez","cultureID":2,'
    '"endpoints":{"cloud":"https://uk.api.csod.com/","api":"/"},"token":"SECRET"};</script>'
)


def _cornerstone_offer(number: int, **extra: Any) -> dict[str, Any]:
    return {
        "requisitionId": number,
        "postingEffectiveDate": "14/09/2026",
        "displayJobTitle": f"Data Scientist {number}",
        "locations": [{"city": "Le-Pecq", "state": "IDF", "country": "FR"}],
        "externalDescription": "<p>Missions &amp; profil</p>",
        **extra,
    }


def _cornerstone_site() -> Any:
    return split_cornerstone_address(CORNERSTONE_PAGE_URL)


@pytest.mark.spec("SRC-113", "SRC-01")
def test_cornerstone_offers_become_ads() -> None:
    answer = {
        "data": {
            "requisitions": [
                _cornerstone_offer(1),
                _cornerstone_offer(2, locations=[], postingEffectiveDate="nope"),
                _cornerstone_offer(3, displayJobTitle=""),
                _cornerstone_offer(4, requisitionId=None),
            ]
        }
    }
    first, second = ads_cornerstone("Suez", _cornerstone_site(), answer)
    assert (first.title, first.location, first.published_on, first.description) == (
        "Data Scientist 1",
        "Le-Pecq, FR",
        "2026-09-14",
        "Missions & profil",
    )
    assert first.url == (
        "https://hris-suez.csod.com/ux/ats/careersite/10/home/requisition/1?c=hris-suez"
    )
    assert first.source == "cornerstone"
    assert (second.location, second.published_on) == ("", "")
    assert ads_cornerstone("Suez", _cornerstone_site(), None) == []


@pytest.mark.spec("SRC-111", "SRC-112", "SRC-05")
def test_cornerstone_reads_the_token_then_searches_each_term_page_by_page() -> None:
    page_one = {
        "data": {"totalCount": 26, "requisitions": [_cornerstone_offer(n) for n in range(25)]}
    }
    page_two = {"data": {"totalCount": 26, "requisitions": [_cornerstone_offer(25)]}}
    client = FakeClient(
        {CORNERSTONE_PAGE_URL: CORNERSTONE_PAGE, CORNERSTONE_SEARCH: [page_one, page_two]}
    )
    target = TargetCompany(
        name="Suez",
        ats="cornerstone",
        identifier="hris-suez.csod.com/ux/ats/careersite/10/home?c=hris-suez",
        searches=("ia",),
    )
    source = source_for(target, client, ["fr"])
    assert isinstance(source, SourceCornerstone)
    assert len(source.collect()) == 26
    bodies = [call[1] for call in client.calls if call[0] == CORNERSTONE_SEARCH]
    assert [body["pageNumber"] for body in bodies] == [1, 2]
    assert bodies[0]["searchText"] == "ia"
    assert bodies[0]["cultureId"] == 2


@pytest.mark.spec("SRC-111")
def test_cornerstone_page_without_token_is_a_source_error() -> None:
    target = TargetCompany(
        name="Suez",
        ats="cornerstone",
        identifier="hris-suez.csod.com/ux/ats/careersite/10/home?c=hris-suez",
        searches=("ia",),
    )
    with pytest.raises(SourceError):
        SourceCornerstone(FakeClient({CORNERSTONE_PAGE_URL: "<html></html>"}), target).collect()
    with pytest.raises(ValueError, match="unexpected Cornerstone address"):
        split_cornerstone_address("hris-suez.csod.com/other")


@pytest.mark.spec("SRC-114")
def test_cornerstone_token_never_reaches_the_ads() -> None:
    answer = {"data": {"requisitions": [_cornerstone_offer(1)]}}
    client = FakeClient({CORNERSTONE_PAGE_URL: CORNERSTONE_PAGE, CORNERSTONE_SEARCH: answer})
    target = TargetCompany(
        name="Suez",
        ats="cornerstone",
        identifier="hris-suez.csod.com/ux/ats/careersite/10/home?c=hris-suez",
        searches=("ia",),
    )
    ads = SourceCornerstone(client, target).collect()
    assert "SECRET" not in repr(ads)


# --- Rippling -----------------------------------------------------------------------------

RIPPLING_BOARD = "https://ats.rippling.com/jus-mundi-careers/jobs"


def _rippling_page(data: dict[str, Any]) -> str:
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'


def _rippling_offer(number: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": str(number),
        "name": f"NLP Engineer {number}",
        "url": f"{RIPPLING_BOARD}/{number}",
        "locations": [{"name": "Paris, France", "countryCode": "FR"}],
        **extra,
    }


@pytest.mark.spec("SRC-116", "SRC-117", "SRC-01")
def test_rippling_offers_become_ads() -> None:
    offers = [
        _rippling_offer(1),
        _rippling_offer(2, locations=[]),
        _rippling_offer(3, name=""),
        _rippling_offer(1),
    ]
    data = {"props": {"pageProps": {"dehydratedState": {"queries": [{"state": {"data": offers}}]}}}}
    first, second = ads_rippling("Jus Mundi", _rippling_page(data))
    assert (first.title, first.location, first.url, first.source) == (
        "NLP Engineer 1",
        "Paris, France",
        f"{RIPPLING_BOARD}/1",
        "rippling",
    )
    assert second.location == ""
    assert ads_rippling("Jus Mundi", "<html></html>") == []
    assert ads_rippling("Jus Mundi", '<script id="__NEXT_DATA__">{oops</script>') == []


@pytest.mark.spec("SRC-116")
def test_rippling_reads_the_board_page_once() -> None:
    offers = [_rippling_offer(1)]
    data = {"props": {"pageProps": {"dehydratedState": {"queries": [{"state": {"data": offers}}]}}}}
    client = FakeClient({RIPPLING_BOARD: _rippling_page(data)})
    target = TargetCompany(
        name="Jus Mundi", ats="rippling", identifier="ats.rippling.com/jus-mundi-careers/jobs/"
    )
    source = source_for(target, client, ["fr"])
    assert isinstance(source, SourceRippling)
    assert len(source.collect()) == 1
    assert [call[0] for call in client.calls] == [RIPPLING_BOARD]


@pytest.mark.spec("SRC-118", "SRC-02")
def test_rippling_page_gives_the_text() -> None:
    ad = JobAd("Jus Mundi", "NLP Engineer 1", url=f"{RIPPLING_BOARD}/1", source="rippling")
    data = {
        "props": {
            "pageProps": {
                "apiData": {
                    "jobPost": {
                        "description": {"company": "<p>About us</p>", "role": "<p>Your role</p>"}
                    }
                }
            }
        }
    }
    assert complete_rippling(ad, _rippling_page(data)).description == "About us Your role"
    assert complete_rippling(ad, "<html></html>") == ad


# --- Talentry ---------------------------------------------------------------------------

TALENTRY_HOST = "fr.jobs.cerbahealthcare.com"
TALENTRY_SEARCH = f"https://{TALENTRY_HOST}/api/search"


def _talentry_offer(number: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": str(number),
        "title": f"Data Scientist {number}",
        "location": "Paris",
        "publicationDate": "2026-11-23T11:13:49+0000",
        "inactive": False,
        **extra,
    }


@pytest.mark.spec("SRC-120", "SRC-01")
def test_talentry_offers_become_ads() -> None:
    answer = {
        "jobs": {
            "offers": [
                _talentry_offer(1),
                _talentry_offer(2, inactive=True),
                _talentry_offer(3, title=""),
                _talentry_offer(4, id=""),
            ]
        }
    }
    (ad,) = ads_talentry("Cerba", TALENTRY_HOST, answer)
    assert (ad.title, ad.location, ad.published_on, ad.source) == (
        "Data Scientist 1",
        "Paris",
        "2026-11-23",
        "talentry",
    )
    assert ad.url == f"https://{TALENTRY_HOST}/our-offers/1"
    assert ads_talentry("Cerba", TALENTRY_HOST, None) == []


@pytest.mark.spec("SRC-119")
def test_talentry_reads_every_page_until_the_total() -> None:
    first = {"jobs": {"totalCount": 21, "offers": [_talentry_offer(n) for n in range(20)]}}
    second = {"jobs": {"totalCount": 21, "offers": [_talentry_offer(20), _talentry_offer(3)]}}
    client = FakeClient({TALENTRY_SEARCH: [first, second]})
    target = TargetCompany(name="Cerba", ats="talentry", identifier=f"https://{TALENTRY_HOST}/x")
    source = source_for(target, client, ["fr"])
    assert isinstance(source, SourceTalentry)
    assert len(source.collect()) == 21
    assert [call[1]["currentPage"] for call in client.calls] == [1, 2]
    assert client.calls[0][1]["facets"] == {}


@pytest.mark.spec("SRC-121", "SRC-02")
def test_talentry_page_gives_the_text() -> None:
    ad = JobAd("Cerba", "Data Scientist 1", url=f"https://{TALENTRY_HOST}/our-offers/1")
    page = (
        '<script type="application/ld+json">'
        '{"@type": "JobPosting", "description": "<p>Missions &amp; profil</p>"}</script>'
    )
    assert complete_talentry(ad, page).description == "Missions & profil"
    assert complete_talentry(ad, "<html></html>") == ad


# --- JOIN -------------------------------------------------------------------------------

JOIN_PAGE = "https://join.com/companies/lettria"


def _join_offer(number: int, **extra: Any) -> dict[str, Any]:
    return {
        "idParam": f"{number}-data-scientist",
        "title": f"Data Scientist {number}",
        "createdAt": "2026-07-23T05:57:47.958Z",
        "city": {"cityName": "Paris", "countryName": "France"},
        **extra,
    }


def _join_page(offers: list[Any], page: int = 1, count: int = 1) -> str:
    data = {
        "props": {
            "pageProps": {
                "pageData": {"jobs": {"items": offers, "pagination": {"pageCount": count}}}
            }
        }
    }
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'


@pytest.mark.spec("SRC-123", "SRC-01")
def test_join_offers_become_ads() -> None:
    page = _join_page(
        [
            _join_offer(1),
            _join_offer(2, city=None),
            _join_offer(3, title=""),
            _join_offer(4, idParam=""),
        ]
    )
    first, second = ads_join("Lettria", JOIN_PAGE, page)
    assert (first.title, first.location, first.published_on, first.source) == (
        "Data Scientist 1",
        "Paris, France",
        "2026-07-23",
        "join",
    )
    assert first.url == f"{JOIN_PAGE}/1-data-scientist"
    assert second.location == ""
    assert ads_join("Lettria", JOIN_PAGE, "<html></html>") == []


@pytest.mark.spec("SRC-122")
def test_join_reads_each_page_up_to_the_page_count() -> None:
    client = FakeClient({JOIN_PAGE: _join_page([_join_offer(1)], count=2)})
    target = TargetCompany(name="Lettria", ats="join", identifier="join.com/companies/lettria/")
    source = source_for(target, client, ["fr"])
    assert isinstance(source, SourceJoin)
    assert [ad.title for ad in source.collect()] == ["Data Scientist 1"]
    assert [call[1] for call in client.calls] == [{}, {"page": "2"}]


@pytest.mark.spec("SRC-122")
def test_join_company_without_offers_gives_no_ad() -> None:
    target = TargetCompany(name="Lettria", ats="join", identifier="join.com/companies/lettria")
    assert SourceJoin(FakeClient({JOIN_PAGE: _join_page([])}), target).collect() == []
    assert SourceJoin(FakeClient({JOIN_PAGE: "<html></html>"}), target).collect() == []


@pytest.mark.spec("SRC-124", "SRC-51")
def test_join_page_gives_the_text() -> None:
    ad = JobAd("Lettria", "Data Scientist 1", url=f"{JOIN_PAGE}/1-data-scientist", source="join")
    page = (
        '<script type="application/ld+json">'
        '{"@type": "JobPosting", "description": "<p>Missions &amp; profil</p>"}</script>'
    )
    assert (
        "Missions & profil"
        in SourceJoin(
            FakeClient({ad.url: page}),
            TargetCompany(name="Lettria", ats="join", identifier="join.com/companies/lettria"),
        )
        .add_details(ad)
        .description
    )
