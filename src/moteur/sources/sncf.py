"""The SNCF group's career site, ``emploi.sncf.com``, through its public search address.

Every ad of one group company (its number in the site's « company » filter) is read page
by page; the page of each retained ad gives its text (SRC-100 to SRC-102).
"""

from __future__ import annotations

from dataclasses import replace

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import HttpClient, items, plain_text, string, table
from moteur.sources.radancy import _job_posting

SEARCH = "https://emploi.sncf.com/internal-gw/search"
POSTING = "https://emploi.sncf.com/nos-offres/{id}"
PAGE_SIZE = 20
PAGES_MAX = 40


def ads_sncf(company: str, answer: object) -> list[JobAd]:
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
                url=POSTING.format(id=number),
                source="sncf",
                published_on=string(offer.get("publicationDate"))[:10],
            )
        )
    return ads


def complete_sncf(ad: JobAd, page: str) -> JobAd:
    """The ad with the `description` of its job posting; unchanged without it."""
    text = plain_text(string(_job_posting(page).get("description")))
    return replace(ad, description=text) if text else ad


class SourceSncf:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._number = company.identifier.strip()

    @property
    def name(self) -> str:
        return f"sncf:{self._company.name}"

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for page in range(1, PAGES_MAX + 1):
            answer = self._client.post_json(
                SEARCH,
                body={
                    "facets": {"company": [self._number]},
                    "currentPage": page,
                    "loadOffers": True,
                },
                headers={"Accept": "application/json"},
            )
            jobs = table(table(answer).get("jobs"))
            offers = items(jobs.get("offers"))
            for ad in ads_sncf(self._company.name, answer):
                seen.setdefault(ad.url, ad)
            total = jobs.get("totalCount")
            known = total if isinstance(total, int) else 0
            if len(offers) < PAGE_SIZE or (known and page * PAGE_SIZE >= known):
                break
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        return complete_sncf(ad, self._client.get_text(ad.url))
