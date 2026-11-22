"""SAP SuccessFactors career sites, e.g. ``jobsearch.alstom.com``.

Their search page (``/search/``) is allowed to robots and lists 25 ads per page; their
RSS feeds (``/services/``) are not allowed (SRC-90 to SRC-92).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from itertools import product

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import SEARCHES_IN_PARALLEL, HttpClient, in_parallel, plain_text
from moteur.sources.talentsoft import host_of

PAGE_SIZE = 25
PAGES_MAX = 5
_ROW = re.compile(r'<tr class="data-row[^"]*">(.*?)</tr>', re.DOTALL)
_TITLE = re.compile(r'<a href="(/job/[^"]+)" class="jobTitle-link">(.*?)</a>', re.DOTALL)
_LOCATION = re.compile(
    r'<td class="colLocation[^"]*"[^>]*>\s*<span class="jobLocation">(.*?)</span>', re.DOTALL
)
_TOTAL = re.compile(r'paginationLabel"[^>]*>.*?</b>[^<]*<b>\s*([\d\s.,]+)</b>', re.DOTALL)
_DESCRIPTION_OPEN = re.compile(r'<span[^>]*class="jobdescription"[^>]*>', re.IGNORECASE)
_SPAN = re.compile(r"<(/?)span\b", re.IGNORECASE)


def ads_successfactors(company: str, host: str, page: str) -> list[JobAd]:
    ads: list[JobAd] = []
    for row in _ROW.findall(page):
        title = _TITLE.search(row)
        if not title or not plain_text(title.group(2)):
            continue
        location = _LOCATION.search(row)
        ads.append(
            JobAd(
                company=company,
                title=plain_text(title.group(2)),
                location=plain_text(location.group(1)) if location else "",
                url=f"https://{host}{title.group(1)}",
                source="successfactors",
            )
        )
    return ads


def announced_total(page: str) -> int:
    """N of « Results 1 – 25 of N », or 0 if missing."""
    found = _TOTAL.search(page)
    digits = re.sub(r"\D", "", found.group(1)) if found else ""
    return int(digits) if digits else 0


def complete_successfactors(ad: JobAd, page: str) -> JobAd:
    """The ad with the text of its `jobdescription` block; unchanged without it."""
    start = _DESCRIPTION_OPEN.search(page)
    if not start:
        return ad
    depth, end = 1, len(page)
    for tag in _SPAN.finditer(page, start.end()):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            end = tag.start()
            break
    text = plain_text(page[start.end() : end])
    return replace(ad, description=text) if text else ad


class SourceSuccessFactors:
    def __init__(
        self, client: HttpClient, company: TargetCompany, countries: Sequence[str] = ()
    ) -> None:
        self._client = client
        self._company = company
        self._host = host_of(company.identifier)
        self._searches: Sequence[str] = company.searches
        self._countries = tuple(c.upper() for c in countries)

    @property
    def name(self) -> str:
        return f"successfactors:{self._company.name}"

    def _search(self, search: tuple[str, str]) -> list[JobAd]:
        keyword, country = search
        found: list[JobAd] = []
        for page in range(PAGES_MAX):
            params = {"q": keyword, "startrow": str(page * PAGE_SIZE)}
            if country:
                params["optionsFacetsDD_country"] = country
            text = self._client.get_text(f"https://{self._host}/search/", params=params)
            ads = ads_successfactors(self._company.name, self._host, text)
            found.extend(ads)
            total = announced_total(text)
            if len(ads) < PAGE_SIZE or (total and (page + 1) * PAGE_SIZE >= total):
                break
        return found

    def collect(self) -> list[JobAd]:
        searches = list(product(self._searches, self._countries or ("",)))
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._search, searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url, ad)
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_successfactors(ad, self._client.get_text(ad.url))
