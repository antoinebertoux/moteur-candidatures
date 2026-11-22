"""McKinsey career site (QuantumBlack included), through its public search address.

No key is needed; each search term is asked page by page (SRC-62, SRC-63).
"""

from __future__ import annotations

from collections.abc import Sequence

from moteur.config import TargetCompany
from moteur.models import JobAd
from moteur.sources.base import (
    SEARCHES_IN_PARALLEL,
    HttpClient,
    in_parallel,
    items,
    plain_text,
    string,
    table,
)

SEARCH = "https://gateway.mckinsey.com/apigw-x0cceuow60/v1/api/jobs/search"
POSTING = "https://www.mckinsey.com/careers/search-jobs/jobs/{slug}"
PAGE_SIZE = 100
PAGES_MAX = 5
_TEXT_FIELDS = ("whoYouWillWorkWith", "whatYouWillDo", "yourBackground")


def ads_mckinsey(company: str, answer: object) -> list[JobAd]:
    ads: list[JobAd] = []
    for job in map(table, items(table(answer).get("docs"))):
        title, slug = string(job.get("title")), string(job.get("friendlyURL"))
        if not title or not slug:
            continue
        cities = [string(city) for city in items(job.get("cities")) if string(city)]
        parts = (plain_text(string(job.get(field))) for field in _TEXT_FIELDS)
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=", ".join(cities),
                url=POSTING.format(slug=slug),
                source="mckinsey",
                description=" ".join(part for part in parts if part),
                published_on=string(job.get("postedToLinkedInDate"))[:10],
            )
        )
    return ads


class SourceMcKinsey:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._searches: Sequence[str] = company.searches

    @property
    def name(self) -> str:
        return f"mckinsey:{self._company.name}"

    def _search(self, keyword: str) -> list[JobAd]:
        found: list[JobAd] = []
        for page in range(1, PAGES_MAX + 1):
            answer = self._client.get_json(
                SEARCH,
                params={"q": keyword, "pageSize": str(PAGE_SIZE), "start": str(page), "lang": "en"},
            )
            ads = ads_mckinsey(self._company.name, answer)
            found.extend(ads)
            total = table(answer).get("numFound")
            known = total if isinstance(total, int) else 0
            if len(ads) < PAGE_SIZE or (known and page * PAGE_SIZE >= known):
                break
        return found

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._search, self._searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url, ad)
        return list(seen.values())
