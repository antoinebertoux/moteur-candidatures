"""Data models shared by the whole engine."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

ApplicationType = Literal["offre", "spontanee"]
Language = Literal["fr", "en"]

MAX_KEY_LENGTH = 150
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def normalise(text: str) -> str:
    """Lowercase, no accents, everything else replaced by hyphens.

    Must stay identical to the `norm` function of the tracking page: this is what lets
    both sides recognise the same application.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_ALPHANUMERIC.sub("-", without_accents).strip("-")


def contains_expression(text: str, expression: str) -> bool:
    """True if `expression` appears in `text` as whole words.

    So "ia" does not match "commercial".
    """
    target = normalise(expression)
    return bool(target) and f"-{target}-" in f"-{normalise(text)}-"


@dataclass(frozen=True, slots=True)
class JobAd:
    """A job ad, or a company targeted by an unsolicited application."""

    company: str
    title: str
    type: ApplicationType = "offre"
    location: str = ""
    url: str = ""
    source: str = ""
    description: str = ""
    salary: str = ""
    published_on: str = ""

    @property
    def key(self) -> str:
        """Stable identifier, identical to the one the tracking page computes."""
        raw = f"{normalise(self.type)}_{normalise(self.company)}_{normalise(self.title)}"
        return raw[:MAX_KEY_LENGTH]


@dataclass(frozen=True, slots=True)
class Rating:
    """Result of Claude scoring an ad."""

    score: int
    summary: str
    letter_requested: bool
    language: Language


@dataclass(frozen=True, slots=True)
class Application:
    """An ad and its state in the local database."""

    ad: JobAd
    status: str
    score: int | None = None
    summary: str = ""
    letter_requested: bool = False
    language: Language = "fr"
    instruction: str = ""
    cv_ref: str = ""
    letter_ref: str = ""
    letter_instruction: str = ""
    preparation: str = ""
    """Interview preparation sheet (Markdown), empty if none (PREP-32)."""
    preparation_le: str = ""
    """Time the sheet was written, in the page's `toISOString()` format."""


@dataclass(frozen=True, slots=True)
class PrepRequest:
    """An interview preparation request from the page (PREP-01)."""

    requested_at: str
    """Time of the click, in the page's `toISOString()` format."""
    salary_expectations: str = ""
    interview_details: str = ""
    instruction: str = ""
    context: str = ""
    """What the page knows of the follow-up: sent date, follow-up, contact, notes."""


# Organisations for which a letter is made by default (the page's toggle can always
# remove it). Must stay identical to MOTS_LETTRE in the tracking page (ID-05).
PUBLIC_SOURCES = ("service_public", "choisirleservicepublic.gouv.fr", "place-emploi-public")
PUBLIC_WORDS = (
    "ministere",
    "direction generale",
    "dgsi",
    "dgse",
    "dga",
    "dinum",
    "anssi",
    "agence de l'innovation de defense",
    "commissariat",
    "secretariat general",
    "autorite",
    "tracfin",
    "prefecture",
    "armees",
    "gendarmerie",
    "police nationale",
    "service statistique",
    "cnes",
    "cnrs",
    "inria",
    "interpol",
    "beta.gouv",
)
BANK_WORDS = (
    "banque",
    "bank",
    "bnp paribas",
    "societe generale",
    "credit agricole",
    "cacib",
    "lcl",
    "natixis",
    "bpce",
    "caisse d'epargne",
    "credit mutuel",
    "cic",
    "bpifrance",
    "rothschild",
    "lazard",
    "hsbc",
    "la banque postale",
    "oddo",
    "amundi",
)


def default_letter(ad: JobAd) -> bool:
    """True for unsolicited applications, the public sector and banks."""
    if ad.type == "spontanee" or ad.source in PUBLIC_SOURCES:
        return True
    return any(contains_expression(ad.company, word) for word in PUBLIC_WORDS + BANK_WORDS)
