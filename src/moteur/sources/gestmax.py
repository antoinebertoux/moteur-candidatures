"""Gestmax career sites, e.g. ``groupe-beaumanoir.gestmax.fr``.

Their search lists are plain pages of 10 ads (title, date, city, country); the page of
each retained ad gives its text (SRC-82 to SRC-84).
"""

from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, plain_text

PAGES_MAX = 40
_ENTRY = re.compile(
    r'<a href="(https?://[^"/]+/\d+/\d+/[^"]*)"[^>]*class="list-group-item[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_TITLE = re.compile(r'<h2 class="list-group-item-heading">(.*?)</h2>', re.DOTALL)
_DATE = re.compile(
    r"listdiv-vacancy_activation_date.*?listdiv-value\">\s*(\d{2})/(\d{2})/(\d{4})", re.DOTALL
)
_CITY = re.compile(r'listdiv-dept_ville">.*?<span class="listdiv-value">(.*?)</span>', re.DOTALL)
_COUNTRY = re.compile(r'listdiv-dept_pays">\s*-?\s*(.*?)</span>', re.DOTALL)
_CONTENT = re.compile(r'<div id="content-wrapper">(.*?)<div class="apply">', re.DOTALL)


def list_address(identifier: str) -> str:
    """`https://<host>/<list path>` from the identifier, without a trailing slash."""
    text = identifier.strip()
    pieces = urlsplit(text if "://" in text else f"https://{text}")
    return f"https://{pieces.netloc}{pieces.path.rstrip('/')}"


def _found(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return plain_text(match.group(1)) if match else ""


def ads_gestmax(company: str, page: str) -> list[JobAd]:
    ads: list[JobAd] = []
    for link, entry in _ENTRY.findall(page):
        title = _found(_TITLE, entry)
        if not title:
            continue
        date = _DATE.search(entry)
        location = ", ".join(p for p in (_found(_CITY, entry), _found(_COUNTRY, entry)) if p)
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=location,
                url=link,
                source="gestmax",
                published_on=f"{date.group(3)}-{date.group(2)}-{date.group(1)}" if date else "",
            )
        )
    return ads


def last_page(page: str, path: str) -> int:
    """The highest page number the list links to (0 if none)."""
    numbers = re.findall(re.escape(path) + r"/page/(\d+)", page)
    return max((int(n) for n in numbers), default=0)


def complete_gestmax(ad: JobAd, page: str) -> JobAd:
    """The ad with its content, up to the « Postuler » button; unchanged without it."""
    found = _CONTENT.search(page)
    text = plain_text(found.group(1)) if found else ""
    return replace(ad, description=text) if text else ad


class SourceGestmax:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._list = list_address(company.identifier)

    @property
    def name(self) -> str:
        return f"gestmax:{self._company.name}"

    def collect(self) -> list[JobAd]:
        path = urlsplit(self._list).path
        seen: dict[str, JobAd] = {}
        for number in range(1, PAGES_MAX + 1):
            page = self._client.get_text(f"{self._list}/page/{number}")
            ads = ads_gestmax(self._company.name, page)
            for ad in ads:
                seen.setdefault(ad.url, ad)
            if not ads or number >= last_page(page, path):
                break
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_gestmax(ad, self._client.get_text(ad.url))
