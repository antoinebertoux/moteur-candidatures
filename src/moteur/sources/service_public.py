"""Choisir le service public: French civil service ads (State, hospitals, local government).

The site has no read API; its result pages are read, whose address encodes the
filters: `/nos-offres/filtres/mot-cles/<words>/domaine/<ids>/organisme/<ids>/page/<n>/`.
The ministries (Armed Forces, Interior…), DGSE, DGSI, DINUM, AMIAD, ANSSI (through the
SGDSN) and most public bodies publish their positions there.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from urllib.parse import quote

from moteur.models import JobAd, normalise
from moteur.sources.base import SEARCHES_IN_PARALLEL, HttpClient, in_parallel, plain_text

SEARCH_URL = "https://choisirleservicepublic.gouv.fr/nos-offres/filtres/"
ADS_PER_PAGE = 20

# Identifiers of the site's filters (values of the "Domaine" and "Employeur" checkboxes).
DOMAINS = {
    "Défense": 3511,
    "Numérique": 3522,
    "Recherche": 3525,
    "Renseignement": 3527,
    "Sécurité": 3529,
    "Direction et pilotage des politiques publiques": 3512,
    "Organisation, contrôle et évaluation": 3523,
    "Environnement": 3514,
}
EMPLOYERS = {
    # Defence
    "Ministère des armées": 5,
    "État-major des armées": 13346,
    "DGA": 13262,
    "DGSE": 364,
    "AMIAD": 14524,
    "DIRISI": 11480,
    "SSA": 2040,
    "ONERA": 382,
    # Interior
    "Ministère de l'Intérieur": 11,
    "DGSI": 13502,
    "Agence du numérique des forces de sécurité intérieure": 14499,
    "Commandement de la gendarmerie dans le cyberespace": 14542,
    # Prime Minister and inter-ministerial
    "Premier ministre": 3,
    "DINUM": 10668,
    "SGDSN": 300,
    "Ministères économiques et financiers": 9,
    "INSEE": 978,
    "Ministère de l'Enseignement supérieur et de la Recherche": 13399,
    "CNRS": 602,
    "GIP ACYMA": 2554,
}

_CARD = re.compile(r'class="fr-card fr-card--horizontal[^"]*fr-card--offer"')
_LINK = re.compile(r'<h3 class="fr-card__title">\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_ELEMENT = re.compile(r'<li class="fr-icon-([a-z0-9-]+)[^"]*"[^>]*>(.*?)</li>', re.S)
_LABEL = re.compile(r'<span class="sr-only">.*?</span>', re.S)
# Ad page: duties and profile are in the "col-left rte" column, before the
# "niveau d'études" and "éléments de candidature" blocks.
_DETAIL_START = re.compile(r'class="[^"]*\bcol-left rte"[^>]*>')
_DETAIL_END = re.compile(r'<div class="(?:block-table|block-cards|strate)')
_BUTTON = re.compile(r"<button\b.*?</button>", re.S)
_BREAK = re.compile(r"<br\s*/?>|</p>|</h[1-6]>|</li>", re.I)
_TOTAL = re.compile(r'<span class="number">\s*([\d\s]+)')
_DATE = re.compile(r"(\d{1,2})(?:er)?\s+([a-zéû]+)\s+(\d{4})")
_MONTHS = {
    m: i
    for i, m in enumerate(
        (
            "janvier",
            "fevrier",
            "mars",
            "avril",
            "mai",
            "juin",
            "juillet",
            "aout",
            "septembre",
            "octobre",
            "novembre",
            "decembre",
        ),
        start=1,
    )
}


def identifier(name: str, table: dict[str, int]) -> int | None:
    """Identifier of a domain or employer, given by name (accents ignored) or as digits."""
    if name.strip().isdigit():
        return int(name)
    target = normalise(name)
    return next((value for key, value in table.items() if normalise(key) == target), None)


def address(
    words: str = "", domains: Sequence[int] = (), employers: Sequence[int] = (), page: int = 1
) -> str:
    """Address of a result page; the order of the filters is imposed by the site."""
    pieces = []
    if words:
        pieces.append(f"mot-cles/{quote(words, safe='')}")
    if domains:
        pieces.append("domaine/" + "-".join(map(str, domains)))
    if employers:
        pieces.append("organisme/" + "-".join(map(str, employers)))
    if page > 1:
        pieces.append(f"page/{page}")
    return SEARCH_URL + "".join(f"{m}/" for m in pieces)


def french_date(text: str) -> str:
    """'En ligne depuis le 16 novembre 2026' -> '2026-11-16' (empty if unreadable)."""
    found_one = _DATE.search(normalise(text).replace("-", " "))
    if not found_one:
        return ""
    day, month, year = found_one.groups()
    number = _MONTHS.get(month)
    return f"{year}-{number:02d}-{int(day):02d}" if number else ""


def announced_total(page: str) -> int | None:
    found_one = _TOTAL.search(page)
    return int(re.sub(r"\s", "", found_one.group(1))) if found_one else None


def public_service_description(page: str) -> str:
    """Text (duties and profile) of an ad page, one line per paragraph."""
    start = _DETAIL_START.search(page)
    if not start:
        return ""
    end = _DETAIL_END.search(page, start.end())
    block = _BUTTON.sub(" ", page[start.end() : end.start() if end else len(page)])
    rows = (plain_text(row) for row in _BREAK.split(block))
    return "\n".join(row for row in rows if row)


def ads_public_service(page: str) -> list[JobAd]:
    """Extracts the ad cards of a result page."""
    ads: list[JobAd] = []
    starts = [m.start() for m in _CARD.finditer(page)]
    for start, end in zip(starts, [*starts[1:], len(page)], strict=False):
        card = page[start:end]
        link = _LINK.search(card)
        if not link:
            continue
        title = plain_text(link.group(2))
        if not title:
            continue
        fields = {
            icon: plain_text(_LABEL.sub(" ", contents)) for icon, contents in _ELEMENT.findall(card)
        }
        ads.append(
            JobAd(
                company=fields.get("user-line") or "Fonction publique",
                title=title,
                location=fields.get("map-pin-2-line", ""),
                url=link.group(1),
                source="service_public",
                published_on=french_date(fields.get("calendar-line", "")),
            )
        )
    return ads


class SourceServicePublic:
    """One keyword search over the whole site, then the same at the tracked employers.

    Results are sorted by relevance: the second pass catches the tracked employers' ads
    that would lie beyond the first pages of the general search.
    """

    def __init__(
        self,
        client: HttpClient,
        searches: Sequence[str],
        domains: Sequence[int] = (),
        employers: Sequence[int] = (),
        pages_max: int = 3,
    ) -> None:
        self._client = client
        self._searches = searches
        self._domains = domains
        self._employers = employers
        self._pages_max = pages_max

    @property
    def name(self) -> str:
        return "service_public"

    def _walk(self, search: tuple[str, Sequence[int]]) -> list[JobAd]:
        """The ads of one search, page after page."""
        words, employers = search
        found_ones: list[JobAd] = []
        for page in range(1, self._pages_max + 1):
            contents = self._client.get_text(address(words, self._domains, employers, page))
            ads = ads_public_service(contents)
            found_ones.extend(ads)
            total = announced_total(contents)
            if len(ads) < ADS_PER_PAGE or (total is not None and page * ADS_PER_PAGE >= total):
                break
        return found_ones

    def add_details(self, ad: JobAd) -> JobAd:
        """The ad with the text of its page; search results have none."""
        return replace(ad, description=public_service_description(self._client.get_text(ad.url)))

    def collect(self) -> list[JobAd]:
        passes: list[Sequence[int]] = [(), self._employers] if self._employers else [()]
        searches = [(words, employers) for words in self._searches or ("",) for employers in passes]
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._walk, searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url, ad)
        return list(seen.values())
