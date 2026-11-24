"""Talentry career sites, e.g. ``fr.jobs.cerbahealthcare.com``.

Every offer is read page by page from ``https://<host>/api/search``; the page of each
retained ad gives its text (SRC-119 to SRC-121).
"""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlsplit

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, items, plain_text, string, table
from moteur.sources.radancy import _job_posting

PAGE_SIZE = 20
PAGES_MAX = 40


def host_of(identifier: str) -> str:
    """The career site host, from a host or an address."""
    text = identifier.strip()
    return urlsplit(text).netloc if "://" in text else text.strip("/").split("/")[0]


def ads_talentry(company: str, host: str, answer: object) -> list[JobAd]:
    """The offers of a search answer (SRC-120)."""
    ads: list[JobAd] = []
    for offer in map(table, items(table(table(answer).get("jobs")).get("offers"))):
        title, number = string(offer.get("title")), string(offer.get("id"))
        if not title or not number or offer.get("inactive") is True:
            continue
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=string(offer.get("location")),
                url=f"https://{host}/our-offers/{number}",
                source="talentry",
                published_on=string(offer.get("publicationDate"))[:10],
            )
        )
    return ads


def complete_talentry(ad: JobAd, page: str) -> JobAd:
    """The ad with the `description` of its job posting; unchanged without it."""
    text = plain_text(string(_job_posting(page).get("description")))
    return replace(ad, description=text) if text else ad


class SourceTalentry:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._host = host_of(company.identifier)

    @property
    def name(self) -> str:
        return f"talentry:{self._company.name}"

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for page in range(1, PAGES_MAX + 1):
            answer = self._client.post_json(
                f"https://{self._host}/api/search",
                body={"facets": {}, "currentPage": page, "loadOffers": True},
                headers={"Accept": "application/json"},
            )
            jobs = table(table(answer).get("jobs"))
            for ad in ads_talentry(self._company.name, self._host, answer):
                seen.setdefault(ad.url, ad)
            total = jobs.get("totalCount")
            known = total if isinstance(total, int) else 0
            if len(items(jobs.get("offers"))) < PAGE_SIZE or (known and page * PAGE_SIZE >= known):
                break
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_talentry(ad, self._client.get_text(ad.url))
