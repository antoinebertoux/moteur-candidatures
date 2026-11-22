"""Oracle Recruiting Cloud career sites, e.g. Technip Energies.

The identifier is the career page address,
"https://<host>/hcmUI/CandidateExperience/<language>/sites/<site>". The page queries a
public search address of the same host, keyword by keyword (SRC-85 to SRC-88).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from urllib.parse import quote, urlsplit

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

PAGE_SIZE = 25
PAGES_MAX = 5
_ADDRESS = re.compile(r"^/hcmUI/CandidateExperience/([\w-]+)/sites/([\w-]+)")
_API = "https://{host}/hcmRestApi/resources/latest/"
_DETAIL_FIELDS = (
    "ExternalDescriptionStr",
    "ExternalResponsibilitiesStr",
    "ExternalQualificationsStr",
)


@dataclass(frozen=True, slots=True)
class OracleSite:
    host: str
    language: str
    site: str

    def search_url(self, keyword: str, page: int) -> str:
        finder = (
            f"findReqs;siteNumber={self.site},limit={PAGE_SIZE},offset={page * PAGE_SIZE},"
            f'keyword="{keyword}",sortBy=POSTING_DATES_DESC'
        )
        return (
            _API.format(host=self.host)
            + "recruitingCEJobRequisitions?onlyData=true&expand=requisitionList"
            + "&finder="
            + quote(finder, safe=";,=")
        )

    def detail_url(self, job_id: str) -> str:
        finder = f'ById;Id="{job_id}",siteNumber={self.site}'
        return (
            _API.format(host=self.host)
            + "recruitingCEJobRequisitionDetails?onlyData=true&expand=all"
            + "&finder="
            + quote(finder, safe=";,=")
        )

    def posting_url(self, job_id: str) -> str:
        return (
            f"https://{self.host}/hcmUI/CandidateExperience/{self.language}"
            f"/sites/{self.site}/job/{job_id}"
        )


def split_oracle_address(address: str) -> OracleSite:
    """Host, language and site of an Oracle career page address (SRC-85)."""
    pieces = urlsplit(address.strip() if "://" in address else f"https://{address.strip()}")
    found = _ADDRESS.match(pieces.path)
    if not pieces.netloc or not found:
        raise ValueError(f"unexpected Oracle address: {address}")
    return OracleSite(host=pieces.netloc, language=found.group(1), site=found.group(2))


def _requisitions(answer: object) -> tuple[list[dict[str, object]], int]:
    """The ads of a search answer and the announced total (0 if unknown)."""
    first = table(next(iter(items(table(answer).get("items"))), {}))
    total = first.get("TotalJobsCount")
    return [table(r) for r in items(first.get("requisitionList"))], (
        total if isinstance(total, int) else 0
    )


def ads_oracle(company: str, site: OracleSite, answer: object) -> list[JobAd]:
    requisitions, _ = _requisitions(answer)
    return [
        JobAd(
            company=company,
            title=string(r.get("Title")),
            location=string(r.get("PrimaryLocation")),
            url=site.posting_url(string(r.get("Id"))),
            source="oracle",
            published_on=string(r.get("PostedDate"))[:10],
        )
        for r in requisitions
        if string(r.get("Title")) and string(r.get("Id"))
    ]


def oracle_description(answer: object) -> str:
    """Description, responsibilities and qualifications of a detail answer (SRC-88)."""
    detail = table(next(iter(items(table(answer).get("items"))), {}))
    parts = (plain_text(string(detail.get(field))) for field in _DETAIL_FIELDS)
    return " ".join(part for part in parts if part)


class SourceOracle:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._site = split_oracle_address(company.identifier)
        self._searches: Sequence[str] = company.searches

    @property
    def name(self) -> str:
        return f"oracle:{self._company.name}"

    def _search(self, keyword: str) -> list[JobAd]:
        found: list[JobAd] = []
        for page in range(PAGES_MAX):
            answer = self._client.get_json(self._site.search_url(keyword, page))
            ads = ads_oracle(self._company.name, self._site, answer)
            found.extend(ads)
            _, total = _requisitions(answer)
            if len(ads) < PAGE_SIZE or (total and (page + 1) * PAGE_SIZE >= total):
                break
        return found

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._search, self._searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url, ad)
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        job_id = ad.url.rsplit("/job/", 1)[-1]
        text = oracle_description(self._client.get_json(self._site.detail_url(job_id)))
        return replace(ad, description=text)
