"""Avature career portals, e.g. ``jobs.orano.group/fr_FR/jobs``.

The portal's RSS feed gives the first 20 ads of a search (title, link, date); the page
of each retained ad gives its location and text as (label, value) fields (SRC-97, SRC-98).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import replace
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import SEARCHES_IN_PARALLEL, HttpClient, in_parallel, plain_text
from moteur.sources.talentsoft import day

LONG_FIELD = 100
# Label then value, as <dt>/<dd> or as <div>s depending on the portal.
_FIELD = re.compile(
    r'<(dt|div) class="article__content__view__field__label"[^>]*>(.*?)</\1>\s*'
    r'<(dd|div) class="article__content__view__field__value"[^>]*>(.*?)</\3>',
    re.DOTALL,
)


def portal_of(identifier: str) -> str:
    """`https://<host>/<locale>/<portal>` from the identifier, without a trailing slash."""
    text = identifier.strip()
    pieces = urlsplit(text if "://" in text else f"https://{text}")
    segments = [s for s in pieces.path.split("/") if s][:2]
    if not pieces.netloc or len(segments) < 2:
        raise ValueError(f"unexpected Avature address: {identifier}")
    return f"https://{pieces.netloc}/{'/'.join(segments)}"


def ads_avature(company: str, feed: str) -> list[JobAd]:
    try:
        root = ET.fromstring(feed.lstrip("﻿"))
    except ET.ParseError:
        return []
    ads: list[JobAd] = []
    for item in root.iter("item"):
        title = plain_text(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        ads.append(
            JobAd(
                company=company,
                title=title,
                url=link,
                source="avature",
                published_on=day(item.findtext("pubDate") or ""),
            )
        )
    return ads


def complete_avature(ad: JobAd, page: str) -> JobAd:
    """Location (City, Country) and text (the long fields) of the ad's page."""
    fields = [(plain_text(m[1]), plain_text(m[3])) for m in _FIELD.findall(page)]
    if not fields:
        return ad
    by_label = {label.lower(): value for label, value in fields}
    location = ", ".join(v for v in (by_label.get("city"), by_label.get("country")) if v)
    text = " ".join(value for _, value in fields if len(value) >= LONG_FIELD)
    return replace(ad, location=location or ad.location, description=text or ad.description)


class SourceAvature:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._portal = portal_of(company.identifier)
        self._searches: Sequence[str] = company.searches

    @property
    def name(self) -> str:
        return f"avature:{self._company.name}"

    def _search(self, keyword: str) -> list[JobAd]:
        feed = self._client.get_text(f"{self._portal}/SearchJobs/feed/", params={"search": keyword})
        return ads_avature(self._company.name, feed)

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._search, self._searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url, ad)
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_avature(ad, self._client.get_text(ad.url))
