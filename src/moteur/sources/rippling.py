"""Rippling career sites, e.g. ``ats.rippling.com/jus-mundi-careers/jobs``.

The list page and each offer's page embed their data in ``__NEXT_DATA__`` (SRC-116 to
SRC-118).
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, items, plain_text, string, table

_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def _next_data(page: str) -> dict[str, Any]:
    found = _DATA.search(page)
    try:
        return table(json.loads(found.group(1))) if found else {}
    except ValueError:
        return {}


def _offer_lists(value: object) -> list[list[Any]]:
    """Every list of the data whose entries have a `name` and a `url`."""
    found: list[list[Any]] = []
    if isinstance(value, dict):
        for inner in value.values():
            found.extend(_offer_lists(inner))
    elif isinstance(value, list):
        if value and all(isinstance(e, dict) and "name" in e and "url" in e for e in value):
            found.append(value)
        else:
            for inner in value:
                found.extend(_offer_lists(inner))
    return found


def board_address(identifier: str) -> str:
    text = identifier.strip()
    pieces = urlsplit(text if "://" in text else f"https://{text}")
    return f"https://{pieces.netloc}{pieces.path.rstrip('/')}"


def ads_rippling(company: str, page: str) -> list[JobAd]:
    """The offers embedded in the list page (SRC-116, SRC-117)."""
    seen: dict[str, JobAd] = {}
    for offers in _offer_lists(_next_data(page)):
        for offer in offers:
            entry = table(offer)
            title, url = string(entry.get("name")), string(entry.get("url"))
            if not title or not url or url in seen:
                continue
            place = table(next(iter(items(entry.get("locations"))), {}))
            seen[url] = JobAd(
                company=company,
                title=title,
                location=string(place.get("name")),
                url=url,
                source="rippling",
            )
    return list(seen.values())


def complete_rippling(ad: JobAd, page: str) -> JobAd:
    """Company and role descriptions of the offer's page (SRC-118)."""
    post = table(table(table(_next_data(page).get("props")).get("pageProps")).get("apiData"))
    description = table(table(post.get("jobPost")).get("description"))
    parts = (plain_text(string(description.get(key))) for key in ("company", "role"))
    text = " ".join(part for part in parts if part)
    return replace(ad, description=text) if text else ad


class SourceRippling:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._address = board_address(company.identifier)

    @property
    def name(self) -> str:
        return f"rippling:{self._company.name}"

    def collect(self) -> list[JobAd]:
        return ads_rippling(self._company.name, self._client.get_text(self._address))

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_rippling(ad, self._client.get_text(ad.url))
