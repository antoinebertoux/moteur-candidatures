"""Cornerstone OnDemand career sites, e.g. ``hris-suez.csod.com``.

The identifier is the career page address,
``<host>/ux/ats/careersite/<site number>/home?c=<tenant>``. The page holds an access
token and the search service address in its ``csod.context``; the source uses them to ask
for the offers, term by term (SRC-111 to SRC-114).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import (
    SEARCHES_IN_PARALLEL,
    HttpClient,
    SourceError,
    in_parallel,
    items,
    plain_text,
    string,
    table,
)

PAGE_SIZE = 25
PAGES_MAX = 40
_PATH = re.compile(r"^/ux/ats/careersite/(\d+)/home")
_CONTEXT = re.compile(r"csod\.context\s*=\s*(\{.*?\})\s*;", re.DOTALL)


@dataclass(frozen=True, slots=True)
class CornerstoneSite:
    host: str
    number: str
    tenant: str

    @property
    def page(self) -> str:
        return f"https://{self.host}/ux/ats/careersite/{self.number}/home?c={self.tenant}"

    def posting_url(self, requisition: str) -> str:
        return (
            f"https://{self.host}/ux/ats/careersite/{self.number}/home/requisition/"
            f"{requisition}?c={self.tenant}"
        )


def split_cornerstone_address(address: str) -> CornerstoneSite:
    """Host, site number and tenant of a Cornerstone career page address (SRC-111)."""
    pieces = urlsplit(address.strip() if "://" in address else f"https://{address.strip()}")
    found = _PATH.match(pieces.path)
    tenant = parse_qs(pieces.query).get("c", [""])[0]
    if not pieces.netloc or not found or not tenant:
        raise ValueError(f"unexpected Cornerstone address: {address}")
    return CornerstoneSite(host=pieces.netloc, number=found.group(1), tenant=tenant)


def read_context(page: str) -> tuple[str, str, int]:
    """Token, search service address and language number of a career page (SRC-111)."""
    found = _CONTEXT.search(page)
    try:
        context = table(json.loads(found.group(1))) if found else {}
    except ValueError:
        context = {}
    token = string(context.get("token"))
    cloud = string(table(context.get("endpoints")).get("cloud"))
    culture = context.get("cultureID")
    if not token or not cloud:
        raise SourceError("no access token in the career page")
    return (
        token,
        cloud if cloud.endswith("/") else cloud + "/",
        culture if isinstance(culture, int) and not isinstance(culture, bool) else 1,
    )


def _day(text: str) -> str:
    """`14/09/2026` as `2026-09-14`; empty when unusable."""
    try:
        return datetime.strptime(text, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return ""


def ads_cornerstone(company: str, site: CornerstoneSite, answer: object) -> list[JobAd]:
    """The offers of a search answer (SRC-113)."""
    ads: list[JobAd] = []
    for offer in items(table(table(answer).get("data")).get("requisitions")):
        entry = table(offer)
        title, number = string(entry.get("displayJobTitle")), entry.get("requisitionId")
        if not title or isinstance(number, bool) or not isinstance(number, int | str):
            continue
        place = table(next(iter(items(entry.get("locations"))), {}))
        parts = (string(place.get("city")), string(place.get("country")))
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=", ".join(part for part in parts if part),
                url=site.posting_url(str(number)),
                source="cornerstone",
                description=plain_text(string(entry.get("externalDescription"))),
                published_on=_day(string(entry.get("postingEffectiveDate"))),
            )
        )
    return ads


def _total(answer: object) -> int:
    total = table(table(answer).get("data")).get("totalCount")
    return total if isinstance(total, int) and not isinstance(total, bool) else 0


class SourceCornerstone:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._site = split_cornerstone_address(company.identifier)
        self._searches: Sequence[str] = company.searches

    @property
    def name(self) -> str:
        return f"cornerstone:{self._company.name}"

    def _search(self, keyword: str, token: str, cloud: str, culture: int) -> list[JobAd]:
        found: list[JobAd] = []
        for page in range(1, PAGES_MAX + 1):
            answer = self._client.post_json(
                f"{cloud}rec-job-search/external/jobs",
                body={
                    "careerSiteId": int(self._site.number),
                    "careerSitePageId": int(self._site.number),
                    "pageNumber": page,
                    "pageSize": PAGE_SIZE,
                    "cultureId": culture,
                    "searchText": keyword,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            ads = ads_cornerstone(self._company.name, self._site, answer)
            found.extend(ads)
            total = _total(answer)
            if len(ads) < PAGE_SIZE or (total and page * PAGE_SIZE >= total):
                break
        return found

    def collect(self) -> list[JobAd]:
        token, cloud, culture = read_context(self._client.get_text(self._site.page))
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(
            lambda keyword: self._search(keyword, token, cloud, culture),
            self._searches,
            SEARCHES_IN_PARALLEL,
        ):
            for ad in ads:
                seen.setdefault(ad.url, ad)
        return list(seen.values())
