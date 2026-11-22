"""WeRecruit career sites, e.g. ``careers.werecruit.io/fr/glimps``.

The home page holds every offer of the company in its code (``window.allOffers``); the
page of each retained ad gives its `JobPosting` data (SRC-106 to SRC-108).
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, items, string, table
from moteur.sources.radancy import complete_radancy

_OFFERS = re.compile(r"window\.allOffers\s*=\s*")


def site_address(identifier: str) -> str:
    """`https://careers.werecruit.io/<language>/<company>` from the identifier."""
    text = identifier.strip()
    pieces = urlsplit(text if "://" in text else f"https://{text}")
    return f"https://{pieces.netloc}{pieces.path.rstrip('/')}"


def embedded_offers(page: str) -> list[object]:
    """The list given to `window.allOffers` in the page; empty when absent or unreadable."""
    start = _OFFERS.search(page)
    if start is None:
        return []
    try:
        offers, _ = json.JSONDecoder().raw_decode(page, start.end())
    except ValueError:
        return []
    return items(offers)


def _title(offer: dict[str, object]) -> str:
    translated = string(offer.get("TitleTranslated"))
    if translated:
        return translated
    return next((string(v) for v in table(offer.get("Title")).values() if string(v)), "")


def ads_werecruit(company: str, page: str) -> list[JobAd]:
    """The offers of the embedded list (SRC-106, SRC-107)."""
    seen: dict[str, JobAd] = {}
    for item in embedded_offers(page):
        offer = table(item)
        title, link = _title(offer), string(offer.get("Url"))
        key = string(offer.get("Id")) or link
        if not title or not link or key in seen:
            continue
        parts = (string(offer.get("Address_City")), string(offer.get("Address_State")))
        seen[key] = JobAd(
            company=company,
            title=title,
            location=", ".join(part for part in parts if part),
            url=link,
            source="werecruit",
            published_on=string(offer.get("PublicationStartDate"))[:10],
        )
    return list(seen.values())


class SourceWeRecruit:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._address = site_address(company.identifier)

    @property
    def name(self) -> str:
        return f"werecruit:{self._company.name}"

    def collect(self) -> list[JobAd]:
        return ads_werecruit(self._company.name, self._client.get_text(self._address))

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_radancy(ad, self._client.get_text(ad.url))
