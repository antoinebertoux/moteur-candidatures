"""Career sites hosted by Welcome Kit (Welcome to the Jungle), e.g. ``jobs.zama.org``.

The home page lists each job as a ``/jobs/<slug>`` link with its title; the slug ends
with the city. The page of each retained ad gives the exact title, location and text.
The Welcome to the Jungle site itself refuses automated requests and is not used.
"""

from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, plain_text

_LINK = re.compile(
    r"<a[^>]*href=[\"'](/jobs/[^\"'?#]+)[\"'][^>]*>\s*<h3[^>]*jobs-list-item-title[^>]*>(.*?)</h3>",
    re.DOTALL | re.IGNORECASE,
)
_UNSOLICITED_SLUG = "candidatures-spontanees"
_TITLE = re.compile(r"<h1[^>]*main-header-title[^>]*>(.*?)</h1>", re.DOTALL | re.IGNORECASE)
_LOCATION = re.compile(r"icon-location[^>]*>\s*</i>([^<]*)<", re.IGNORECASE)
_BLOCK = re.compile(
    r"<div class=[\"']block block-job-text block-job-(about|description|profile|more)[\"']>",
    re.IGNORECASE,
)
_END = re.compile(r"<div class=[\"'](?:main-content|block block-job-text)", re.IGNORECASE)


def _readable(segment: str) -> str:
    """« saint-malo » → « Saint Malo »."""
    return " ".join(word.capitalize() for word in segment.split("-") if word)


def ads_welcomekit(company: str, host: str, page: str) -> list[JobAd]:
    """The jobs listed on the career site's home page; the spontaneous link is ignored."""
    ads: list[JobAd] = []
    seen: set[str] = set()
    for path, html_title in _LINK.findall(page):
        slug = path.rstrip("/").rsplit("/", 1)[-1]
        heading = plain_text(html_title)
        if not heading or slug == _UNSOLICITED_SLUG or path in seen:
            continue
        seen.add(path)
        city = slug.rsplit("_", 1)[1] if "_" in slug else ""
        ads.append(
            JobAd(
                company=company,
                title=heading,
                location=_readable(city),
                url=f"https://{host}{path}",
                source="welcomekit",
            )
        )
    return ads


def complete_welcomekit(ad: JobAd, page: str) -> JobAd:
    """Exact title, location and text from the ad's page; unchanged without text blocks."""
    starts = [m.end() for m in _BLOCK.finditer(page)]
    if not starts:
        return ad
    pieces = []
    for start in starts:
        end = _END.search(page, start)
        pieces.append(plain_text(page[start : end.start() if end else len(page)]))
    heading = _TITLE.search(page)
    location = _LOCATION.search(page)
    return replace(
        ad,
        title=(plain_text(heading.group(1)) if heading else "") or ad.title,
        location=(plain_text(location.group(1)) if location else "") or ad.location,
        description=" ".join(m for m in pieces if m),
    )


class SourceWelcomeKit:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        host = company.identifier.strip()
        self._host = urlsplit(host).netloc if "://" in host else host.strip("/")

    @property
    def name(self) -> str:
        return f"welcomekit:{self._company.name}"

    def collect(self) -> list[JobAd]:
        page = self._client.get_text(f"https://{self._host}/")
        return ads_welcomekit(self._company.name, self._host, page)

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_welcomekit(ad, self._client.get_text(ad.url))
