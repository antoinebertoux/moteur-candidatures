"""The Station F job board (``jobs.stationf.co``), a Welcome Kit site.

Its search page queries Algolia with a public search key that the page publishes,
restricted to the board's ads. The source reads that key, runs one search per keyword,
then opens the page of each retained ad like any Welcome Kit site.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

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
from moteur.sources.welcomekit import complete_welcomekit

SITE = "https://jobs.stationf.co"
SEARCH_PAGE = f"{SITE}/search"
APPLICATION = "CSEKHVMS53"
INDEX = "wk_cms_jobs_production_careers"
SEARCH_URL = f"https://{APPLICATION.lower()}-dsn.algolia.net/1/indexes/{INDEX}/query"
PAGE_SIZE = 50
EXCLUDED_CONTRACTS = frozenset({"INTERNSHIP", "APPRENTICESHIP"})
REMOTE = {
    "fulltime": "télétravail total",
    "partial": "télétravail partiel",
    "punctual": "télétravail ponctuel",
}
_KEY = re.compile(
    r"<input[^>]*id=[\"']algolia_api_key[\"'][^>]*value=[\"']([^\"']+)[\"']", re.IGNORECASE
)


def search_key(page: str) -> str:
    """The Algolia key published by the search page (SRC-70)."""
    found = _KEY.search(page)
    if not found:
        raise SourceError(f"{SEARCH_PAGE}: no search key in the page")
    return found.group(1)


def _amount(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    return round(value)


def salary_label(hit: dict[str, Any]) -> str:
    """The yearly range written like France Travail's, so the floor applies (SRC-73)."""
    if string(hit.get("salary_period")) == "yearly":
        low, high = _amount(hit.get("salary_minimum")), _amount(hit.get("salary_maximum"))
    else:
        low, high = _amount(hit.get("salary_yearly_minimum")), None
    if low and high:
        return f"Annuel de {low} Euros à {high} Euros"
    if high:
        return f"Annuel jusqu'à {high} Euros"
    if low:
        return f"À partir de {low} Euros par an"
    return ""


def experience_sentence(hit: dict[str, Any]) -> str:
    years = _amount(hit.get("experience_level_minimum"))
    if not years:
        return ""
    return f"Expérience demandée : {years} an{'s' if years > 1 else ''}."


def _with_experience(sentence: str, text: str) -> str:
    return " ".join(part for part in (sentence, text) if part)


def ad_station_f(hit: dict[str, Any]) -> JobAd | None:
    """One search result as an ad; `None` without a title (SRC-01)."""
    title = string(hit.get("name"))
    if not title:
        return None
    organisation = table(hit.get("organization"))
    organisation_slug = string(
        table(organisation.get("website_organization")).get("slug")
    ) or string(organisation.get("slug"))
    slug = string(hit.get("slug"))
    city = string(table(hit.get("office")).get("city"))
    remote = REMOTE.get(string(hit.get("remote")), "")
    return JobAd(
        company=string(organisation.get("name")) or "Entreprise non précisée",
        title=title,
        location=", ".join(part for part in (city, remote) if part),
        url=f"{SITE}/companies/{organisation_slug}/jobs/{slug}"
        if organisation_slug and slug
        else "",
        source="station_f",
        description=_with_experience(
            experience_sentence(hit), plain_text(string(hit.get("profile")))
        ),
        salary=salary_label(hit),
        published_on=string(hit.get("published_at"))[:10],
    )


def is_kept(hit: dict[str, Any], oldest: date) -> bool:
    """Recent enough, and neither an internship nor an apprenticeship (SRC-72)."""
    if string(hit.get("contract_type")) in EXCLUDED_CONTRACTS:
        return False
    try:
        published = date.fromisoformat(string(hit.get("published_at"))[:10])
    except ValueError:
        return True
    return published >= oldest


class SourceStationF:
    def __init__(
        self,
        client: HttpClient,
        searches: Sequence[str],
        pages_max: int,
        published_since: int,
        *,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._client = client
        self._searches = searches
        self._pages_max = pages_max
        self._published_since = published_since
        self._today = today
        # Experience sentence of each ad, put back in front of the page's text (SRC-74).
        self._experience: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "station_f"

    def _search(self, key: str, search: str) -> list[dict[str, Any]]:
        """The results of one keyword, page after page (SRC-71)."""
        headers = {"X-Algolia-Application-Id": APPLICATION, "X-Algolia-API-Key": key}
        hits: list[dict[str, Any]] = []
        for page in range(self._pages_max):
            params = urlencode({"query": search, "hitsPerPage": PAGE_SIZE, "page": page})
            answer = table(
                self._client.post_json(SEARCH_URL, body={"params": params}, headers=headers)
            )
            hits.extend(map(table, items(answer.get("hits"))))
            pages = answer.get("nbPages")
            if not isinstance(pages, int) or page + 1 >= pages:
                break
        return hits

    def collect(self) -> list[JobAd]:
        key = search_key(self._client.get_text(SEARCH_PAGE))
        oldest = self._today() - timedelta(days=self._published_since)
        seen: dict[str, JobAd] = {}
        for hits in in_parallel(
            lambda search: self._search(key, search), self._searches, SEARCHES_IN_PARALLEL
        ):
            for hit in hits:
                ad = ad_station_f(hit) if is_kept(hit, oldest) else None
                if ad is None:
                    continue
                identifier = string(hit.get("objectID")) or ad.url or ad.key
                if identifier not in seen:
                    seen[identifier] = ad
                    self._experience[ad.url] = experience_sentence(hit)
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        """The text of the ad's page, read like a Welcome Kit ad (SRC-74)."""
        if not ad.url:
            return ad
        completed = complete_welcomekit(ad, self._client.get_text(ad.url))
        if completed is ad:
            return ad
        # Only the text is taken: the search already gives the title and the remote work.
        sentence = self._experience.get(ad.url, "")
        return replace(ad, description=_with_experience(sentence, completed.description))
