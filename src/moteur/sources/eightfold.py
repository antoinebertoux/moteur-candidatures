"""Eightfold career sites, e.g. DSM-Firmenich.

The identifier is the career page address with its `domain`,
"https://<host>/careers?domain=<domain>". The page queries a public search address of
the same host, keyword by keyword (SRC-125 to SRC-127).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urlsplit

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

# The site's own page size, which a request cannot change (SRC-126).
PAGE_SIZE = 10
PAGES_MAX = 10


@dataclass(frozen=True, slots=True)
class EightfoldSite:
    host: str
    domain: str

    def search_url(self, keyword: str, page: int) -> str:
        query = urlencode({"domain": self.domain, "query": keyword, "start": page * PAGE_SIZE})
        return f"https://{self.host}/api/pcsx/search?{query}"

    def detail_url(self, position_id: str) -> str:
        query = urlencode({"position_id": position_id, "domain": self.domain})
        return f"https://{self.host}/api/pcsx/position_details?{query}"

    def posting_url(self, position_id: str) -> str:
        return f"https://{self.host}/careers/job/{position_id}"


def split_eightfold_address(address: str) -> EightfoldSite:
    """Host and domain of an Eightfold career page address (SRC-125)."""
    text = address.strip()
    pieces = urlsplit(text if "://" in text else f"https://{text}")
    domain = next(iter(parse_qs(pieces.query).get("domain", [])), "").strip()
    if not pieces.netloc or not domain:
        raise ValueError(f"unexpected Eightfold address (no domain): {address}")
    return EightfoldSite(host=pieces.netloc, domain=domain)


def _positions(answer: object) -> tuple[list[dict[str, object]], int]:
    """The positions of a search answer and the announced total (0 if unknown)."""
    data = table(table(answer).get("data"))
    total = data.get("count")
    return [table(p) for p in items(data.get("positions"))], (
        total if isinstance(total, int) else 0
    )


def _day(timestamp: object) -> str:
    """The day of a time in seconds since 1970, empty when there is none."""
    if isinstance(timestamp, bool) or not isinstance(timestamp, int | float) or timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp, tz=UTC).date().isoformat()


def ads_eightfold(company: str, site: EightfoldSite, answer: object) -> list[JobAd]:
    """The ads of a search answer (SRC-126); positions without name or id are skipped."""
    positions, _ = _positions(answer)
    ads = []
    for position in positions:
        title = string(position.get("name"))
        raw_id = position.get("id")
        position_id = str(raw_id) if isinstance(raw_id, int | str) else ""
        if not title or not position_id:
            continue
        ads.append(
            JobAd(
                company=company,
                title=title,
                location=string(next(iter(items(position.get("locations"))), "")),
                url=site.posting_url(position_id),
                source="eightfold",
                published_on=_day(position.get("postedTs")),
            )
        )
    return ads


def eightfold_description(answer: object) -> str:
    """The plain `jobDescription` of a detail answer (SRC-127)."""
    data = table(table(answer).get("data"))
    return plain_text(string(data.get("jobDescription")))


class SourceEightfold:
    def __init__(self, client: HttpClient, company: TargetCompany) -> None:
        self._client = client
        self._company = company
        self._site = split_eightfold_address(company.identifier)
        self._searches: Sequence[str] = company.searches

    @property
    def name(self) -> str:
        return f"eightfold:{self._company.name}"

    def _search(self, keyword: str) -> list[JobAd]:
        found: list[JobAd] = []
        for page in range(PAGES_MAX):
            answer = self._client.get_json(self._site.search_url(keyword, page))
            positions, total = _positions(answer)
            found.extend(ads_eightfold(self._company.name, self._site, answer))
            if len(positions) < PAGE_SIZE or (total and (page + 1) * PAGE_SIZE >= total):
                break
        return found

    def collect(self) -> list[JobAd]:
        seen: dict[str, JobAd] = {}
        for ads in in_parallel(self._search, self._searches, SEARCHES_IN_PARALLEL):
            for ad in ads:
                seen.setdefault(ad.url, ad)
        return list(seen.values())

    def add_details(self, ad: JobAd) -> JobAd:
        position_id = ad.url.rsplit("/job/", 1)[-1]
        text = eightfold_description(self._client.get_json(self._site.detail_url(position_id)))
        return replace(ad, description=text)
