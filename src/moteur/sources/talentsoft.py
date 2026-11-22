"""Talentsoft (Cegid) career sites, e.g. ``casa-cacib-recrute.talent-soft.com``.

Each site publishes every ad, with its full text, in one public RSS feed (SRC-80, SRC-81).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, plain_text

FEED = "https://{host}/handlers/offerRss.ashx"
FEED_PARAMETERS = {"LCID": "1036", "top": "1000"}
# "2026-110801 - Originateur H/F": the reference that starts every title.
_REFERENCE = re.compile(r"^\s*\d{4}-\d+\s+-\s+")


def host_of(identifier: str) -> str:
    """The host of a career site written as a host or as an address."""
    text = identifier.strip()
    return urlsplit(text).netloc if "://" in text else text.strip("/").split("/")[0]


def day(value: str) -> str:
    """The day (YYYY-MM-DD) of an RSS date, or empty if unreadable."""
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def ads_talentsoft(company: str, feed: str) -> list[JobAd]:
    try:
        root = ET.fromstring(feed.lstrip("﻿"))
    except ET.ParseError:
        return []
    ads: list[JobAd] = []
    for item in root.iter("item"):
        title = _REFERENCE.sub("", item.findtext("title") or "").strip()
        if not title:
            continue
        categories = [(c.text or "").strip() for c in item.findall("category")]
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=categories[2] if len(categories) >= 3 else "",
                url=(item.findtext("link") or "").strip(),
                source="talentsoft",
                description=plain_text(item.findtext("description") or ""),
                published_on=day(item.findtext("pubDate") or ""),
            )
        )
    return ads


class SourceTalentsoft:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._host = host_of(company.identifier)

    @property
    def name(self) -> str:
        return f"talentsoft:{self._company.name}"

    def collect(self) -> list[JobAd]:
        feed = self._client.get_text(FEED.format(host=self._host), params=FEED_PARAMETERS)
        return ads_talentsoft(self._company.name, feed)
