"""Public career pages: Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Teamtailor,
Workable."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from email.utils import parsedate_to_datetime
from itertools import product
from typing import Any

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import (
    SEARCHES_IN_PARALLEL,
    HttpClient,
    in_parallel,
    items,
    plain_text,
    string,
    table,
)

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{id}/jobs",
    "lever": "https://api.lever.co/v0/postings/{id}",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{id}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{id}/postings",
    "recruitee": "https://{id}.recruitee.com/api/offers/",
    "teamtailor": "https://{id}.teamtailor.com/jobs.rss",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{id}",
}
PARAMETERS: dict[str, dict[str, str]] = {
    "greenhouse": {"content": "true"},
    "lever": {"mode": "json"},
    "smartrecruiters": {"limit": "100"},
    "workable": {"details": "true"},
}
# SmartRecruiters searches (SRC-35).
SMARTRECRUITERS_PAGE = 100
SMARTRECRUITERS_PAGES_MAX = 5
URL_SMARTRECRUITERS = "https://jobs.smartrecruiters.com/{id}/{ad}"
GREENHOUSE_EU = "https://boards-api.eu.greenhouse.io/v1/boards/{id}/jobs"
TEAMTAILOR_OWN_DOMAIN = "https://{id}/jobs.rss"
EU_PREFIX = "eu:"


def ats_url(ats: str, identifier: str) -> str:
    """Address of a company's ads (SRC-30), with the EU and own-domain variants."""
    if ats == "greenhouse" and identifier.startswith(EU_PREFIX):
        return GREENHOUSE_EU.format(id=identifier.removeprefix(EU_PREFIX))
    if ats == "teamtailor" and "." in identifier:
        return TEAMTAILOR_OWN_DOMAIN.format(id=identifier)
    return URLS[ats].format(id=identifier)


def ads_greenhouse(company: str, answer: object) -> list[JobAd]:
    return [
        JobAd(
            company=company,
            title=string(title.get("title")),
            location=string(table(title.get("location")).get("name")),
            url=string(title.get("absolute_url")),
            source="greenhouse",
            description=plain_text(string(title.get("content"))),
            published_on=string(title.get("updated_at"))[:10],
        )
        for title in map(table, items(table(answer).get("jobs")))
        if string(title.get("title"))
    ]


def ads_lever(company: str, answer: object) -> list[JobAd]:
    return [
        JobAd(
            company=company,
            title=string(title.get("text")),
            location=string(table(title.get("categories")).get("location")),
            url=string(title.get("hostedUrl")),
            source="lever",
            description=string(title.get("descriptionPlain")),
        )
        for title in map(table, items(answer))
        if string(title.get("text"))
    ]


def ads_ashby(company: str, answer: object) -> list[JobAd]:
    return [
        JobAd(
            company=company,
            title=string(title.get("title")),
            location=string(title.get("location")),
            url=string(title.get("jobUrl")),
            source="ashby",
            description=string(title.get("descriptionPlain")),
            published_on=string(title.get("publishedAt"))[:10],
        )
        for title in map(table, items(table(answer).get("jobs")))
        if string(title.get("title"))
    ]


def ads_smartrecruiters(company: str, identifier: str, answer: object) -> list[JobAd]:
    ads: list[JobAd] = []
    for title in map(table, items(table(answer).get("content"))):
        heading = string(title.get("name"))
        if not heading:
            continue
        location = table(title.get("location"))
        city = string(location.get("city"))
        country = string(location.get("country")).upper()
        ad_id = string(title.get("id"))
        ads.append(
            JobAd(
                company=company,
                title=heading,
                location=", ".join(x for x in (city, country) if x),
                url=URL_SMARTRECRUITERS.format(id=identifier, ad=ad_id) if ad_id else "",
                source="smartrecruiters",
                published_on=string(title.get("releasedDate"))[:10],
            )
        )
    return ads


def ads_recruitee(company: str, answer: object) -> list[JobAd]:
    return [
        JobAd(
            company=company,
            title=string(title.get("title")),
            location=string(title.get("location")),
            url=string(title.get("careers_url")),
            source="recruitee",
            description=plain_text(string(title.get("description"))),
            published_on=string(title.get("published_at"))[:10],
        )
        for title in map(table, items(table(answer).get("offers")))
        if string(title.get("title"))
    ]


def ads_workable(company: str, answer: object) -> list[JobAd]:
    ads: list[JobAd] = []
    for title in map(table, items(table(answer).get("jobs"))):
        heading = string(title.get("title"))
        if not heading:
            continue
        first = table(next(iter(items(title.get("locations"))), None))
        city = string(title.get("city")) or string(first.get("city"))
        country = string(title.get("country")) or string(first.get("country"))
        pieces = [x for x in (city, country) if x]
        if title.get("telecommuting") is True:
            pieces.append("Remote")
        ads.append(
            JobAd(
                company=company,
                title=heading,
                location=", ".join(pieces),
                url=string(title.get("url")),
                source="workable",
                description=plain_text(string(title.get("description"))),
                published_on=string(title.get("published_on"))[:10],
            )
        )
    return ads


def _text(element: ET.Element, suffix: str) -> str:
    """Text of the first descendant with tag `suffix`, namespaces ignored."""
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1] == suffix and child.text:
            return child.text.strip()
    return ""


def _rss_date(value: str) -> str:
    try:
        return parsedate_to_datetime(value).date().isoformat() if value else ""
    except (TypeError, ValueError):
        return ""


def ads_teamtailor(company: str, feed: str) -> list[JobAd]:
    """Reads the public RSS feed of a Teamtailor career page."""
    try:
        root = ET.fromstring(feed)
    except ET.ParseError:
        return []
    ads: list[JobAd] = []
    for item in root.iter("item"):
        heading = _text(item, "title")
        if not heading:
            continue
        ads.append(
            JobAd(
                company=company,
                title=heading,
                location=_text(item, "city") or _text(item, "location"),
                url=_text(item, "link"),
                source="teamtailor",
                description=plain_text(_text(item, "description")),
                published_on=_rss_date(_text(item, "pubDate")),
            )
        )
    return ads


_PARSERS: dict[str, Callable[[str, Any], list[JobAd]]] = {
    "greenhouse": ads_greenhouse,
    "lever": ads_lever,
    "ashby": ads_ashby,
    "recruitee": ads_recruitee,
    "workable": ads_workable,
}
_SUPPORTED = {*_PARSERS, "smartrecruiters", "teamtailor"}


def smartrecruiters_searches(
    keywords: Sequence[str], countries: Sequence[str]
) -> list[dict[str, str]]:
    """Parameters of each SmartRecruiters search: one per keyword and per country, per
    keyword or per country alone when the other is empty; none when both are (SRC-35)."""
    pairs = product(keywords or [""], countries or [""])
    return [
        {key: value for key, value in (("q", keyword), ("country", country)) if value}
        for keyword, country in pairs
        if keyword or country
    ]


class SourceAts:
    """The ads a company publishes on its recruiting tool."""

    def __init__(
        self, client: HttpClient, company: TargetCompany, countries: Sequence[str] = ()
    ) -> None:
        if company.ats not in _SUPPORTED:
            raise ValueError(f"{company.name} has no supported ATS")
        self._client = client
        self._company = company
        self._countries = tuple(countries)

    @property
    def name(self) -> str:
        return f"{self._company.ats}:{self._company.name}"

    def _smartrecruiters_search(self, parameters: dict[str, str]) -> list[JobAd]:
        """The ads of one SmartRecruiters search, page after page (SRC-35)."""
        url = ats_url("smartrecruiters", self._company.identifier)
        found_ones: list[JobAd] = []
        for page in range(SMARTRECRUITERS_PAGES_MAX):
            answer = self._client.get_json(
                url,
                params={
                    **parameters,
                    "limit": str(SMARTRECRUITERS_PAGE),
                    "offset": str(page * SMARTRECRUITERS_PAGE),
                },
            )
            entries = items(table(answer).get("content"))
            found_ones.extend(
                ads_smartrecruiters(self._company.name, self._company.identifier, answer)
            )
            total = table(answer).get("totalFound")
            read = (page + 1) * SMARTRECRUITERS_PAGE
            if len(entries) < SMARTRECRUITERS_PAGE or (isinstance(total, int) and read >= total):
                break
        return found_ones

    def _smartrecruiters(self, searches: list[dict[str, str]]) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._smartrecruiters_search, searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url or ad.title, ad)
        return list(seen.values())

    def collect(self) -> list[JobAd]:
        ats = self._company.ats
        if ats == "smartrecruiters":
            searches = smartrecruiters_searches(self._company.searches, self._countries)
            if searches:
                return self._smartrecruiters(searches)
        identifier = self._company.identifier
        url = ats_url(ats, identifier)
        if ats == "teamtailor":
            return ads_teamtailor(self._company.name, self._client.get_text(url))
        answer = self._client.get_json(url, params=PARAMETERS.get(ats, {}))
        if ats == "smartrecruiters":
            return ads_smartrecruiters(self._company.name, identifier, answer)
        return _PARSERS[ats](self._company.name, answer)
