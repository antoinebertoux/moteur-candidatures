"""User's choice of the companies, sectors, sizes and sources searched (CAT-10 to CAT-16)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from moteur.config import SECTORS, SIZES, Config, TargetCompany
from moteur.models import normalise

Subject = Literal["entreprise", "secteur", "taille", "source"]
Field = Literal["actif", "spontanee"]
SUBJECTS: tuple[Subject, ...] = ("entreprise", "secteur", "taille", "source")

# Keyword sources (CAT-15): key -> (name shown, size it belongs to).
SOURCES: dict[str, tuple[str, str]] = {
    "france_travail": ("France Travail", ""),
    "service_public": ("Choisir le service public", "public"),
    "station_f": ("Station F", "startup"),
}


class SelectionError(ValueError):
    """A choice sent by the page is invalid (ECH-29)."""


@dataclass(frozen=True, slots=True)
class Choice:
    """One choice of User; `value` None means back to the default (BASE-15)."""

    subject: Subject
    key: str
    field: Field
    value: bool | None


@dataclass(frozen=True, slots=True)
class Choices:
    """The choices kept in the local database, by subject then key then field."""

    stored: Mapping[tuple[Subject, str, Field], bool]

    @classmethod
    def of(cls, choices: Iterable[Choice]) -> Choices:
        return cls({(c.subject, c.key, c.field): c.value for c in choices if c.value is not None})

    def get(self, subject: Subject, key: str, field: Field = "actif") -> bool | None:
        return self.stored.get((subject, key, field))

    def is_on(self, subject: Subject, key: str) -> bool:
        """A sector, size or source is on unless User turned it off."""
        return self.get(subject, key) is not False


NO_CHOICE = Choices({})


def company_key(company: TargetCompany) -> str:
    return normalise(company.name)


def active_by_default(company: TargetCompany, countries: Sequence[str]) -> bool:
    """CAT-10: an own company is searched; a catalogue one if it hires in User's countries."""
    if company.origin == "perso" or not countries or not company.countries:
        return True
    return bool(set(company.countries) & set(countries))


@dataclass(frozen=True, slots=True)
class CompanyState:
    company: TargetCompany
    active: bool
    active_default: bool
    unsolicited: bool
    unsolicited_default: bool
    reason: str
    """Why it is not searched: "", "choix", "pays", "secteur" or "taille"."""

    @property
    def searched(self) -> bool:
        return not self.reason


def company_state(company: TargetCompany, config: Config, choices: Choices) -> CompanyState:
    """CAT-13, CAT-14: own state, then sector and size."""
    key = company_key(company)
    default = active_by_default(company, config.criteria.countries)
    chosen = choices.get("entreprise", key)
    active = default if chosen is None else chosen
    # CAT-14: off unless User turned it on.
    unsolicited_default = False
    chosen_unsolicited = choices.get("entreprise", key, "spontanee")
    reason = ""
    if not active:
        reason = "choix" if chosen is False else "pays"
    elif company.sector and not choices.is_on("secteur", company.sector):
        reason = "secteur"
    elif company.size and not choices.is_on("taille", company.size):
        reason = "taille"
    return CompanyState(
        company=company,
        active=active,
        active_default=default,
        unsolicited=unsolicited_default if chosen_unsolicited is None else chosen_unsolicited,
        unsolicited_default=unsolicited_default,
        reason=reason,
    )


def states(config: Config, choices: Choices) -> list[CompanyState]:
    return [company_state(company, config, choices) for company in config.followed]


def searched_companies(config: Config, choices: Choices) -> list[TargetCompany]:
    """The companies to query, their unsolicited application set as chosen (CAT-13, CAT-14)."""
    return [
        replace(state.company, unsolicited=state.unsolicited)
        for state in states(config, choices)
        if state.searched
    ]


def configured(config: Config, source: str) -> bool:
    """`actif = true` in `config.toml` (CAT-15)."""
    return {
        "france_travail": config.france_travail.enabled,
        "service_public": config.service_public.enabled,
        "station_f": config.station_f.enabled,
    }[source]


def source_searched(config: Config, choices: Choices, source: str) -> bool:
    """CAT-15: configured, not turned off, and its size not turned off."""
    size = SOURCES[source][1]
    return (
        configured(config, source)
        and choices.is_on("source", source)
        and (not size or choices.is_on("taille", size))
    )


def summary(config: Config, choices: Choices) -> dict[str, Any]:
    """The answer of the tools `entreprises` and `selection` (ECH-27)."""
    all_states = states(config, choices)
    companies = [
        {
            "cle": company_key(state.company),
            "nom": state.company.name,
            "origine": state.company.origin,
            "secteur": state.company.sector,
            "taille": state.company.size,
            "pays": list(state.company.countries),
            "site": state.company.site,
            "recherchee": state.searched,
            "raison": state.reason,
            "actif": state.active,
            "actif_par_defaut": state.active_default,
            "spontanee": state.unsolicited,
            "spontanee_par_defaut": state.unsolicited_default,
        }
        for state in all_states
    ]

    def groups(subject: Subject, values: Sequence[str], field: str) -> list[dict[str, Any]]:
        return [
            {
                "cle": value,
                "actif": choices.is_on(subject, value),
                "entreprises": sum(1 for c in companies if c[field] == value),
            }
            for value in values
        ]

    sources = [
        {
            "cle": key,
            "nom": name,
            "taille": size,
            "configuree": configured(config, key),
            "actif": choices.is_on("source", key),
            "recherchee": source_searched(config, choices, key),
        }
        for key, (name, size) in SOURCES.items()
    ]
    return {
        "entreprises": companies,
        "secteurs": groups("secteur", SECTORS, "secteur"),
        "tailles": groups("taille", SIZES, "taille"),
        "sources": sources,
    }


def _flag(value: object, where: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise SelectionError(f"{where}: must be true, false or null")


def choices_from(entry: object, config: Config) -> list[Choice]:
    """Reads the input of `selection` (ECH-28); any fault rejects the whole input (ECH-29)."""
    if not isinstance(entry, Mapping) or not isinstance(entry.get("choix"), list):
        raise SelectionError('expected {"choix": [...]}')
    known: dict[Subject, set[str]] = {
        "entreprise": {company_key(c) for c in config.followed},
        "secteur": set(SECTORS),
        "taille": set(SIZES),
        "source": set(SOURCES),
    }
    result: list[Choice] = []
    for position, item in enumerate(entry["choix"], start=1):
        where = f"choice {position}"
        if not isinstance(item, Mapping):
            raise SelectionError(f"{where}: must be an object")
        subject = item.get("objet")
        if subject not in SUBJECTS:
            raise SelectionError(f"{where}: unknown objet {subject!r}")
        key = item.get("cle")
        if not isinstance(key, str) or key not in known[subject]:
            raise SelectionError(f"{where}: unknown {subject} {key!r}")
        where = f"{where} ({subject} {key})"
        fields: tuple[Field, ...] = (
            ("actif", "spontanee") if subject == "entreprise" else ("actif",)
        )
        unexpected = set(item) - {"objet", "cle", *fields}
        if unexpected:
            raise SelectionError(f"{where}: unexpected {', '.join(sorted(unexpected))}")
        given = [field for field in fields if field in item]
        if not given:
            raise SelectionError(f"{where}: nothing to change")
        result.extend(
            Choice(subject, key, field, _flag(item[field], f"{where} {field}")) for field in given
        )
    return result
