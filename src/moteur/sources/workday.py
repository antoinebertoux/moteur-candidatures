"""Workday career pages of large companies.

The identifier is the address of the career page as shown in the browser, for example
"https://exemple.wd3.myworkdayjobs.com/fr-FR/Careers". Workday does not return every ad
at once: its search is queried with a few keywords, page by page.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import (
    SEARCHES_IN_PARALLEL,
    HttpClient,
    HttpxClient,
    SourceError,
    UrllibClient,
    in_parallel,
    items,
    plain_text,
    string,
    table,
)

PAGE_SIZE = 20
PAGES_MAX = 5
# Still "too many requests" after the client's own retries (SRC-43).
PAUSES_ON_429 = 2
PAUSE_429 = 30.0
_LANGUAGE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


@dataclass(frozen=True, slots=True)
class WorkdaySite:
    host: str
    tenant: str
    site: str

    @property
    def api(self) -> str:
        return f"https://{self.host}/wday/cxs/{self.tenant}/{self.site}/jobs"

    def posting_url(self, path: str) -> str:
        return f"https://{self.host}/{self.site}{path}" if path else ""

    def detail_url(self, ad_url: str) -> str:
        """Public detail address of an ad, from its link (empty if the link is foreign)."""
        prefix = f"https://{self.host}/{self.site}/"
        if not ad_url.startswith(prefix):
            return ""
        return f"https://{self.host}/wday/cxs/{self.tenant}/{self.site}/{ad_url[len(prefix) :]}"


def split_address(address: str) -> WorkdaySite:
    """Extracts host, tenant and site from a Workday career page address."""
    pieces = urlsplit(address if "://" in address else f"https://{address}")
    host = pieces.netloc
    segments = [s for s in pieces.path.split("/") if s and not _LANGUAGE.match(s)]
    if not host.endswith("myworkdayjobs.com") or not segments:
        raise ValueError(f"unexpected Workday address: {address}")
    return WorkdaySite(host=host, tenant=host.split(".")[0], site=segments[0])


def workday_description(response: object) -> str:
    """Plain text of an ad from its detail response (empty if unreadable)."""
    return plain_text(string(table(table(response).get("jobPostingInfo")).get("jobDescription")))


def ads_workday(company: str, site: WorkdaySite, answer: object) -> list[JobAd]:
    return [
        JobAd(
            company=company,
            title=string(title.get("title")),
            location=string(title.get("locationsText")),
            url=site.posting_url(string(title.get("externalPath"))),
            source="workday",
        )
        for title in map(table, items(table(answer).get("jobPostings")))
        if string(title.get("title"))
    ]


def client_for_workday(client: HttpClient) -> HttpClient:
    """The standard-library client in place of the usual one, which Workday refuses
    (SRC-110); any other client (e.g. a test one) is kept."""
    return UrllibClient() if isinstance(client, HttpxClient) else client


class SourceWorkday:
    def __init__(
        self,
        client: HttpClient,
        company: TargetCompany,
        pause: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client_for_workday(client)
        self._company = company
        self._site = split_address(company.identifier)
        self._searches: Sequence[str] = company.searches
        self._pause = pause

    def _page(self, body: dict[str, object]) -> object:
        """One search page; a lasting 429 is asked again after a pause (SRC-43)."""
        for attempt in range(PAUSES_ON_429 + 1):
            try:
                return self._client.post_json(
                    self._site.api, body=body, headers={"Accept": "application/json"}
                )
            except SourceError as error:
                if "HTTP 429" not in str(error) or attempt == PAUSES_ON_429:
                    raise
                self._pause(PAUSE_429)
        return None

    @property
    def name(self) -> str:
        return f"workday:{self._company.name}"

    def _search(self, search: str) -> list[JobAd]:
        """The ads of one keyword, page after page."""
        found_ones: list[JobAd] = []
        total = 0
        for page in range(PAGES_MAX):
            answer = self._page(
                {
                    "appliedFacets": {},
                    "limit": PAGE_SIZE,
                    "offset": page * PAGE_SIZE,
                    "searchText": search,
                }
            )
            ads = ads_workday(self._company.name, self._site, answer)
            found_ones.extend(ads)
            # Workday only gives the total on the first page.
            posting = table(answer).get("total")
            if isinstance(posting, int) and posting > 0:
                total = posting
            if len(ads) < PAGE_SIZE or (total and (page + 1) * PAGE_SIZE >= total):
                break
        return found_ones

    def add_details(self, ad: JobAd) -> JobAd:
        """The ad with the text of its detail page; search results give none (SRC-42)."""
        url = self._site.detail_url(ad.url)
        if not url:
            return ad
        response = self._client.get_json(url, headers={"Accept": "application/json"})
        return replace(ad, description=workday_description(response))

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._search, self._searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url or ad.title, ad)
        return list(seen.values())
