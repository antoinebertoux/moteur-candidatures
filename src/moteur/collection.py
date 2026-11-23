"""Collection: queries the sources, filters, and proposes unsolicited applications."""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable, Sequence
from pathlib import Path

from moteur.config import Criteria, TargetCompany
from moteur.filtering import filter_ads, located_after_details
from moteur.models import JobAd, normalise
from moteur.sources.base import DetailedSource, Source, SourceError, in_parallel

log = logging.getLogger(__name__)

# Sources queried at the same time.
SOURCES_IN_PARALLEL = 8
# Ad pages opened at the same time: they often come from the same site.
PAGES_IN_PARALLEL = 4
# Name prefix of the Workday sources ("workday:<company>").
WORKDAY_PREFIX = "workday:"


def companies_already_seen(path: Path) -> set[str]:
    """Normalised names from `suivi/entreprises_vues.csv` (empty if it does not exist).

    Rows whose status mentions "historique" (applications from a former job search) are
    ignored: those companies may be proposed again.
    """
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as file:
        return {
            normalise(row["entreprise"])
            for row in csv.DictReader(file, delimiter=";")
            if row.get("entreprise") and "historique" not in _status(row).lower()
        }


def _status(row: dict[str, str]) -> str:
    """Value of the status column, whatever the exact label of its header."""
    for key, value in row.items():
        if key and key.strip().lower().startswith("statut"):
            return value or ""
    return ""


def query_sources(sources: Iterable[Source]) -> list[JobAd]:
    """Gathers the ads of every source; a broken source does not stop the others.

    Sources are queried in parallel; the result keeps their order. Workday sites refusing
    with HTTP 429 are reported together, in one line (COL-10).
    """

    def one_source(source: Source) -> tuple[list[JobAd], str]:
        """The ads of a source, and its company if it is a Workday site refusing us."""
        try:
            found_ones = source.collect()
        except SourceError as error:
            if source.name.startswith(WORKDAY_PREFIX) and "HTTP 429" in str(error):
                return [], source.name.removeprefix(WORKDAY_PREFIX)
            log.warning("Source %s skipped: %s", source.name, error)
            return [], ""
        log.info("%s: %d ads", source.name, len(found_ones))
        return found_ones, ""

    results = in_parallel(one_source, sources, SOURCES_IN_PARALLEL)
    refusing = [company for _, company in results if company]
    if refusing:
        log.warning(
            "%d Workday sites refuse automated access (HTTP 429): %s",
            len(refusing),
            ", ".join(refusing),
        )
    return [ad for found_ones, _ in results for ad in found_ones]


def add_details(ads: Iterable[JobAd], sources: Iterable[Source]) -> list[JobAd]:
    """Adds the text of retained ads whose source only gives it on their own page.

    Done after filtering, so that only the pages of kept ads are opened. Pages are opened
    in parallel; the order of the ads does not change.
    """
    by_name = {source.name: source for source in sources if isinstance(source, DetailedSource)}

    def complete_ad(ad: JobAd) -> JobAd:
        # A per-company source is named "<tool>:<company>".
        source = by_name.get(f"{ad.source}:{ad.company}") or by_name.get(ad.source)
        if source is None or ad.description:
            return ad
        try:
            return source.add_details(ad)
        except SourceError as error:
            log.warning("Text of ad %s not retrieved: %s", ad.url, error)
            return ad

    return in_parallel(complete_ad, ads, PAGES_IN_PARALLEL)


def unsolicited_ones(
    targets: Sequence[TargetCompany], retained: Sequence[JobAd], already_seen: set[str], role: str
) -> list[JobAd]:
    """One unsolicited application per target company with no retained ad, never approached."""
    with_ad = {normalise(ad.company) for ad in retained}
    return [
        JobAd(company=target.name, title=role, type="spontanee", url=target.site, source="cible")
        for target in targets
        if target.unsolicited and normalise(target.name) not in with_ad | already_seen
    ]


def collect(
    sources: Sequence[Source],
    criteria: Criteria,
    targets: Sequence[TargetCompany],
    already_seen: set[str],
    unsolicited_role: str,
) -> list[JobAd]:
    filtered = filter_ads(query_sources(sources), criteria)
    retained = located_after_details(filtered, add_details(filtered, sources), criteria)
    return retained + unsolicited_ones(targets, retained, already_seen, unsolicited_role)
