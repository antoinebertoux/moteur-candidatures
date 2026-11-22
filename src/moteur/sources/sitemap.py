"""In-house career sites listing their offers in a sitemap, e.g. Société Générale.

The sitemaps named in ``robots.txt`` give each offer's address, from which a provisional
title is taken; the page of each retained ad gives its `JobPosting` data (SRC-52 to
SRC-54).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, SourceError, items, string, table
from moteur.sources.radancy import _job_posting, complete_radancy

_SITEMAP_LINE = re.compile(r"^\s*sitemap\s*:\s*(\S+)", re.IGNORECASE | re.MULTILINE)


def _locations(sitemap: str) -> tuple[list[str], list[str]]:
    """(sitemap addresses, page addresses) listed in a sitemap or a sitemap index."""
    try:
        root = ET.fromstring(sitemap.lstrip("﻿").strip())
    except ET.ParseError:
        return [], []
    nested: list[str] = []
    pages: list[str] = []
    for element in root:
        kind = element.tag.rsplit("}", 1)[-1]
        loc = next((c.text for c in element if c.tag.rsplit("}", 1)[-1] == "loc"), None)
        if not loc:
            continue
        (nested if kind == "sitemap" else pages).append(loc.strip())
    return nested, pages


def provisional_title(address: str) -> str:
    """Words of the last segment before the first one holding a digit (SRC-53)."""
    segment = [s for s in urlsplit(address).path.split("/") if s][-1:] or [""]
    words: list[str] = []
    for word in segment[0].split("-"):
        if any(character.isdigit() for character in word):
            break
        if word:
            words.append(word.capitalize())
    return " ".join(words)


def offers_prefix(identifier: str) -> str:
    """`https://<host>/<path>/` from the identifier."""
    text = identifier.strip()
    pieces = urlsplit(text if "://" in text else f"https://{text}")
    path = pieces.path if pieces.path.endswith("/") else f"{pieces.path}/"
    return f"https://{pieces.netloc}{path}"


def complete_sitemap(ad: JobAd, page: str) -> JobAd:
    """SRC-51 plus the location of the first `jobLocation` (SRC-54)."""
    completed = complete_radancy(ad, page)
    data = _job_posting(page)
    places = data.get("jobLocation")
    first = table(next(iter(items(places)), {}) if isinstance(places, list) else places)
    address = table(first.get("address"))
    country = address.get("addressCountry")
    country_name = string(table(country).get("name")) if isinstance(country, dict) else ""
    parts = (string(address.get("addressLocality")), country_name or string(country))
    location = ", ".join(part for part in parts if part)
    return replace(
        completed,
        location=location or completed.location,
        published_on=completed.published_on.replace("/", "-"),
    )


class SourceSitemap:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._prefix = offers_prefix(company.identifier)
        self._host = urlsplit(self._prefix).netloc

    @property
    def name(self) -> str:
        return f"sitemap:{self._company.name}"

    def _read(self, address: str) -> str:
        try:
            return self._client.get_text(address)
        except SourceError:
            return ""

    def collect(self) -> list[JobAd]:
        robots = self._read(f"https://{self._host}/robots.txt")
        sitemaps = _SITEMAP_LINE.findall(robots) or [f"https://{self._host}/sitemap.xml"]
        pages: list[str] = []
        for sitemap in sitemaps:
            nested, found = _locations(self._read(sitemap))
            pages.extend(found)
            for inner in nested:
                pages.extend(_locations(self._read(inner))[1])
        ads: dict[str, JobAd] = {}
        for page in pages:
            if not page.startswith(self._prefix) or len(page) <= len(self._prefix):
                continue
            title = provisional_title(page)
            if title and page not in ads:
                ads[page] = JobAd(self._company.name, title, url=page, source="sitemap")
        return list(ads.values())

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_sitemap(ad, self._client.get_text(ad.url))
