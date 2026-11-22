"""Radancy (TalentBrew) career sites, for example Moody's.

Their search is forbidden to robots by `robots.txt`; the sitemap (`sitemap.xml`) and the
ad pages are allowed. The sitemap gives each ad's address,
`…/job/<city>/<title>/<organisation>/<number>`, from which a provisional title and
location are taken; the page of the retained ads gives the rest.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, items, plain_text, string, table

_DATA = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE
)


def _readable(segment: str) -> str:
    """« new-york » → « New York »."""
    return " ".join(word.capitalize() for word in segment.split("-") if word)


def ads_radancy(company: str, plan: str) -> list[JobAd]:
    """The ads listed in the sitemap; other addresses are ignored."""
    try:
        root = ET.fromstring(plan.lstrip("﻿"))
    except ET.ParseError:
        return []
    ads: list[JobAd] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "loc" or not element.text:
            continue
        address = element.text.strip()
        segments = [s for s in urlsplit(address).path.split("/") if s]
        if "job" not in segments:
            continue
        follow_up = segments[segments.index("job") + 1 :]
        if len(follow_up) != 4 or not follow_up[1]:
            continue
        city, job_title = follow_up[0], follow_up[1]
        ads.append(
            JobAd(
                company=company,
                title=_readable(job_title),
                location=_readable(city),
                url=address,
                source="radancy",
            )
        )
    return ads


def _job_posting(page: str) -> dict[str, Any]:
    """The `JobPosting` data of the page, or an empty object."""
    for block in _DATA.findall(page):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        candidates = data if isinstance(data, list) else [data]
        # Some sites wrap their data in an "@graph" list.
        candidates += [g for c in list(candidates) for g in items(table(c).get("@graph"))]
        for candidate in candidates:
            if table(candidate).get("@type") == "JobPosting":
                return table(candidate)
    return {}


def complete_radancy(ad: JobAd, page: str) -> JobAd:
    data = _job_posting(page)
    if not data:
        return ad
    return replace(
        ad,
        title=string(data.get("title")) or ad.title,
        description=plain_text(string(data.get("description"))),
        published_on=string(data.get("datePosted"))[:10],
    )


class SourceRadancy:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        host = company.identifier.strip()
        self._host = urlsplit(host).netloc if "://" in host else host.strip("/")

    @property
    def name(self) -> str:
        return f"radancy:{self._company.name}"

    def collect(self) -> list[JobAd]:
        plan = self._client.get_text(f"https://{self._host}/sitemap.xml")
        return ads_radancy(self._company.name, plan)

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_radancy(ad, self._client.get_text(ad.url))
