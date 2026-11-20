"""Refusal reasons chosen in the tracking page (PAGE-10), shared by the database and scoring."""

from __future__ import annotations

from dataclasses import dataclass

REASONS = {
    "competences": "Compétences inadaptées",
    "trop_senior": "Trop senior",
    "trop_junior": "Trop junior",
    "salaire": "Salaire",
    "lieu": "Lieu / télétravail",
    "secteur": "Secteur ou mission",
    "conseil": "Conseil / ESN",
    "ml_pur": "Trop ML pur",
    "entreprise": "Entreprise",
    "doublon": "Doublon",
    "autre": "Autre",
}
DUPLICATE = "doublon"
DETAIL_LENGTH = 200


def normalise_reason(value: object) -> str:
    """A known reason code, `autre` for an unknown one, empty when there is none."""
    if not isinstance(value, str) or not value.strip():
        return ""
    code = value.strip()
    return code if code in REASONS else "autre"


def normalise_detail(value: object) -> str:
    return value.strip()[:DETAIL_LENGTH] if isinstance(value, str) else ""


@dataclass(frozen=True, slots=True)
class Refusal:
    """A past refusal given to the scoring model as a counter-example (NOT-08)."""

    company: str
    title: str
    reason: str
    detail: str = ""

    def line(self) -> str:
        text = f"- {self.company} — {self.title} : {REASONS.get(self.reason, self.reason)}"
        return f"{text} ({self.detail})" if self.detail else text
