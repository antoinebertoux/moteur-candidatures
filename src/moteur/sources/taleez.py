"""Taleez career sites, e.g. ``tehtris.taleez.com``.

The site reads every listed job from ``https://<host>/api/careez``; the page of each
retained ad, ``taleez.com/apply/<slug>``, gives its `JobPosting` data (SRC-103 to
SRC-105).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, items, plain_text, string, table
from moteur.sources.radancy import _job_posting, complete_radancy

APPLY = "https://taleez.com/apply"


def host_of(identifier: str) -> str:
    """The career site host, from a host or an address."""
    text = identifier.strip()
    return urlsplit(text).netloc if "://" in text else text.strip("/").split("/")[0]


def _day(milliseconds: object) -> str:
    """`publishDate` (milliseconds since 1970) as YYYY-MM-DD; empty when unusable."""
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, int | float):
        return ""
    try:
        return datetime.fromtimestamp(milliseconds / 1000, UTC).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return ""


def ads_taleez(company: str, answer: object) -> list[JobAd]:
    """The jobs of the site's list (SRC-103, SRC-104)."""
    seen: dict[str, JobAd] = {}
    for job in items(table(answer).get("jobs")):
        entry = table(job)
        title, slug = string(entry.get("label")), string(entry.get("slug"))
        if not title or not slug or slug in seen:
            continue
        place = table(entry.get("location"))
        parts = (string(place.get("city")), string(place.get("country")))
        seen[slug] = JobAd(
            company=company,
            title=title,
            location=", ".join(part for part in parts if part),
            url=f"{APPLY}/{slug}",
            source="taleez",
            published_on=_day(entry.get("publishDate")),
        )
    return list(seen.values())


def complete_taleez(ad: JobAd, page: str) -> JobAd:
    """SRC-51, the profile sought following the description (SRC-105)."""
    completed = complete_radancy(ad, page)
    profile = plain_text(string(_job_posting(page).get("qualifications")))
    if not profile:
        return completed
    text = f"{completed.description}\n{profile}" if completed.description else profile
    return replace(completed, description=text)


class SourceTaleez:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._host = host_of(company.identifier)

    @property
    def name(self) -> str:
        return f"taleez:{self._company.name}"

    def collect(self) -> list[JobAd]:
        answer = self._client.get_json(f"https://{self._host}/api/careez")
        return ads_taleez(self._company.name, answer)

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_taleez(ad, self._client.get_text(ad.url))
