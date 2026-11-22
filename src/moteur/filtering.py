"""Sorting ads with simple rules, without any call to Claude."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from moteur.config import Criteria
from moteur.models import JobAd, contains_expression

_AMOUNT = re.compile(r"(\d+(?:[.,]\d+)?)\s*euros", re.IGNORECASE)
_MONTHS = re.compile(r"sur\s+(\d+(?:[.,]\d+)?)\s*mois", re.IGNORECASE)


def max_annual_salary(label: str) -> int | None:
    """Annual upper bound of a France Travail salary label, or `None` if unknown.

    Examples: "Annuel de 45000.0 Euros à 55000.0 Euros sur 12.0 mois",
    "Mensuel de 3500.0 Euros sur 13.0 mois".
    """
    amounts = [float(m.replace(",", ".")) for m in _AMOUNT.findall(label)]
    if not amounts:
        return None
    start = label.strip().lower()
    if start.startswith("annuel"):
        return round(max(amounts))
    if start.startswith("mensuel"):
        month = _MONTHS.search(label)
        return round(max(amounts) * (float(month.group(1).replace(",", ".")) if month else 12.0))
    return None


def location_matches(ad: JobAd, criteria: Criteria) -> bool:
    """FILT-03: true without configured locations, without location, or when one matches."""
    return (
        not criteria.locations
        or not ad.location
        or any(contains_expression(ad.location, location) for location in criteria.locations)
    )


def located_after_details(
    before: Sequence[JobAd], after: Sequence[JobAd], criteria: Criteria
) -> list[JobAd]:
    """FILT-06: drops the ads whose page gave a location outside the configured ones."""
    return [
        completed
        for ad, completed in zip(before, after, strict=True)
        if ad.location or location_matches(completed, criteria)
    ]


def matches(ad: JobAd, criteria: Criteria) -> bool:
    """True if the ad meets the criteria. Missing information never causes a rejection."""
    if criteria.keywords and not any(
        contains_expression(ad.title, word) for word in criteria.keywords
    ):
        return False
    if any(contains_expression(ad.title, word) for word in criteria.exclusions):
        return False
    if not location_matches(ad, criteria):
        return False
    if criteria.salary_floor:
        maximum = max_annual_salary(ad.salary)
        if maximum is not None and maximum < criteria.salary_floor:
            return False
    return True


def filter_ads(ads: Iterable[JobAd], criteria: Criteria) -> list[JobAd]:
    """Keeps the matching ads, without duplicates (same company and same title)."""
    retained: dict[str, JobAd] = {}
    for ad in ads:
        if matches(ad, criteria):
            retained.setdefault(ad.key, ad)
    return list(retained.values())
