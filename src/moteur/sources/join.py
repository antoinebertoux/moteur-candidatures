"""JOIN career pages, e.g. ``join.com/companies/lettria``.

The page embeds its offers in ``__NEXT_DATA__`` (5 per page, ``?page=<n>`` for the
others); the page of each retained ad gives its `JobPosting` data (SRC-122 to SRC-124).
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, items, string, table
from moteur.sources.radancy import complete_radancy

PAGES_MAX = 40
_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def company_page(identifier: str) -> str:
    """`https://join.com/companies/<company>` from the identifier."""
    text = identifier.strip()
    pieces = urlsplit(text if "://" in text else f"https://{text}")
    return f"https://{pieces.netloc}{pieces.path.rstrip('/')}"


def _jobs(page: str) -> dict[str, Any]:
    """The `pageData.jobs` table of a page; empty when missing or unreadable (SRC-122)."""
    found = _DATA.search(page)
    try:
        data = table(json.loads(found.group(1))) if found else {}
    except ValueError:
        return {}
    return table(table(table(data.get("props")).get("pageProps")).get("pageData")).get("jobs") or {}


def ads_join(company: str, address: str, page: str) -> list[JobAd]:
    """The offers of one page (SRC-123)."""
    ads: list[JobAd] = []
    for offer in map(table, items(table(_jobs(page)).get("items"))):
        title, slug = string(offer.get("title")), string(offer.get("idParam"))
        if not title or not slug:
            continue
        city = table(offer.get("city"))
        parts = (string(city.get("cityName")), string(city.get("countryName")))
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=", ".join(part for part in parts if part),
                url=f"{address}/{slug}",
                source="join",
                published_on=string(offer.get("createdAt"))[:10],
            )
        )
    return ads


def page_count(page: str) -> int:
    count = table(table(_jobs(page)).get("pagination")).get("pageCount")
    return count if isinstance(count, int) and not isinstance(count, bool) else 0


class SourceJoin:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._address = company_page(company.identifier)

    @property
    def name(self) -> str:
        return f"join:{self._company.name}"

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        count = 1
        number = 1
        while number <= min(count, PAGES_MAX):
            if number == 1:
                page = self._client.get_text(self._address)
            else:
                page = self._client.get_text(self._address, params={"page": str(number)})
            if not _jobs(page):
                break
            count = page_count(page) or 1
            for ad in ads_join(self._company.name, self._address, page):
                seen.setdefault(ad.url, ad)
            number += 1
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_radancy(ad, self._client.get_text(ad.url))
