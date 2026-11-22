"""Phenom career sites, e.g. ``careers.bcg.com/global/en``.

The page queries a public search address of the same host, ``/widgets``, keyword by
keyword; the page of each retained ad holds its `JobPosting` data (SRC-94 to SRC-96).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import (
    SEARCHES_IN_PARALLEL,
    HttpClient,
    in_parallel,
    items,
    string,
    table,
)
from moteur.sources.radancy import complete_radancy

PAGE_SIZE = 50
PAGES_MAX = 5


@dataclass(frozen=True, slots=True)
class PhenomSite:
    host: str
    country: str
    language: str

    @property
    def widgets(self) -> str:
        return f"https://{self.host}/widgets"

    def body(self, keyword: str, page: int) -> dict[str, Any]:
        return {
            "lang": f"{self.language}_{self.country}",
            "deviceType": "desktop",
            "country": self.country,
            "pageName": "search-results",
            "ddoKey": "refineSearch",
            "sortBy": "",
            "subsearch": "",
            "from": page * PAGE_SIZE,
            "jobs": True,
            "counts": True,
            "all_fields": [],
            "size": PAGE_SIZE,
            "clearAll": False,
            "jdsource": "facets",
            "isSliderEnable": False,
            "pageId": "page20",
            "siteType": "external",
            "keywords": keyword,
            "global": True,
            "selected_fields": {},
            "locationData": {},
        }

    def posting_url(self, job_id: str) -> str:
        return f"https://{self.host}/{self.country}/{self.language}/job/{job_id}"


def split_phenom_address(address: str) -> PhenomSite:
    """Host, country and language of a Phenom career site address (SRC-94)."""
    text = address.strip()
    pieces = urlsplit(text if "://" in text else f"https://{text}")
    segments = [s for s in pieces.path.split("/") if s]
    if not pieces.netloc or len(segments) < 2:
        raise ValueError(f"unexpected Phenom address: {address}")
    return PhenomSite(host=pieces.netloc, country=segments[0], language=segments[1])


def _search_result(answer: object) -> dict[str, Any]:
    return table(table(answer).get("refineSearch"))


def ads_phenom(company: str, site: PhenomSite, answer: object) -> list[JobAd]:
    ads: list[JobAd] = []
    for job in map(table, items(table(_search_result(answer).get("data")).get("jobs"))):
        title, job_id = string(job.get("title")), string(job.get("jobId"))
        if not title or not job_id:
            continue
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=string(job.get("location")) or string(job.get("city")),
                url=site.posting_url(job_id),
                source="phenom",
                published_on=string(job.get("postedDate"))[:10],
            )
        )
    return ads


class SourcePhenom:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._site = split_phenom_address(company.identifier)
        self._searches: Sequence[str] = company.searches

    @property
    def name(self) -> str:
        return f"phenom:{self._company.name}"

    def _search(self, keyword: str) -> list[JobAd]:
        found: list[JobAd] = []
        for page in range(PAGES_MAX):
            answer = self._client.post_json(
                self._site.widgets,
                body=self._site.body(keyword, page),
                headers={"Accept": "application/json"},
            )
            ads = ads_phenom(self._company.name, self._site, answer)
            found.extend(ads)
            hits = _search_result(answer).get("totalHits")
            total = hits if isinstance(hits, int) else 0
            if len(ads) < PAGE_SIZE or (total and (page + 1) * PAGE_SIZE >= total):
                break
        return found

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._search, self._searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url, ad)
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        """Title, text and date of the ad's `JobPosting` data (SRC-96, as SRC-51)."""
        completed = complete_radancy(ad, self._client.get_text(ad.url))
        # The search's date stays when the page gives none.
        return replace(completed, published_on=completed.published_on or ad.published_on)
