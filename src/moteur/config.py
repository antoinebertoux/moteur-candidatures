"""Loading and validation of `config.toml`."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

from moteur.company_links import is_web_address
from moteur.sources.service_public import DOMAINS, EMPLOYERS, identifier

AtsType = Literal[
    "greenhouse",
    "lever",
    "ashby",
    "workday",
    "smartrecruiters",
    "recruitee",
    "teamtailor",
    "radancy",
    "workable",
    "welcomekit",
    "",
]


class ConfigError(ValueError):
    """The configuration file is missing or malformed."""


@dataclass(frozen=True, slots=True)
class Criteria:
    keywords: tuple[str, ...]
    exclusions: tuple[str, ...]
    locations: tuple[str, ...]
    salary_floor: int


@dataclass(frozen=True, slots=True)
class FranceTravail:
    enabled: bool
    searches: tuple[str, ...]
    departments: tuple[str, ...]
    published_since: int


@dataclass(frozen=True, slots=True)
class PublicService:
    """Search on Choisir le service public; domains and employers as identifiers."""

    enabled: bool
    searches: tuple[str, ...]
    domains: tuple[int, ...] = ()
    employers: tuple[int, ...] = ()
    pages_max: int = 3


@dataclass(frozen=True, slots=True)
class TargetCompany:
    name: str
    ats: AtsType = ""
    identifier: str = ""
    site: str = ""
    unsolicited: bool = False
    linkedin: str = ""
    """LinkedIn page of the company (CONF-09)."""
    # Keywords sent to the ATS search (Workday); empty = defaults.
    searches: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Paths:
    root: Path
    base: Path
    exchange: Path

    @property
    def latex(self) -> Path:
        return self.root / "latex"

    @property
    def applications(self) -> Path:
        return self.root / "Candidatures"

    @property
    def seen_companies(self) -> Path:
        return self.root / "suivi" / "entreprises_vues.csv"


@dataclass(frozen=True, slots=True)
class Config:
    profile: str
    unsolicited_role: str
    batch_size: int
    scoring_model: str
    generation_model: str
    criteria: Criteria
    france_travail: FranceTravail
    service_public: PublicService
    companies: tuple[TargetCompany, ...]
    paths: Paths
    preparation_model: str = "sonnet"


def _table(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{key}] must be a table")
    return value


def _string(table: Mapping[str, Any], key: str, default_value: str = "") -> str:
    value = table.get(key, default_value)
    if not isinstance(value, str):
        raise ConfigError(f'"{key}" must be a string')
    return value


def _strings(table: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f'"{key}" must be a list of strings')
    return tuple(value)


def _integer(table: Mapping[str, Any], key: str, default_value: int) -> int:
    value = table.get(key, default_value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f'"{key}" must be an integer')
    return value


def _boolean(table: Mapping[str, Any], key: str, default_value: bool) -> bool:
    value = table.get(key, default_value)
    if not isinstance(value, bool):
        raise ConfigError(f'"{key}" must be true or false')
    return value


def _identifiers(table: Mapping[str, Any], key: str, known: dict[str, int]) -> tuple[int, ...]:
    """Names ("DGSE", "Numérique") or numeric identifiers of the site."""
    values = table.get(key, [])
    if not isinstance(values, list):
        raise ConfigError(f'"{key}" must be a list')
    result: list[int] = []
    for value in values:
        found_one = (
            value
            if isinstance(value, int) and not isinstance(value, bool)
            else identifier(value, known)
            if isinstance(value, str)
            else None
        )
        if found_one is None:
            names = ", ".join(known)
            raise ConfigError(f'"{key}": unknown {value!r} (known names: {names})')
        result.append(found_one)
    return tuple(result)


def _public_service(table: Mapping[str, Any]) -> PublicService:
    pages_max = _integer(table, "pages_max", 3)
    if pages_max < 1:
        raise ConfigError('"pages_max" must be at least 1')
    return PublicService(
        enabled=_boolean(table, "actif", False),
        searches=_strings(table, "recherches"),
        domains=_identifiers(table, "domaines", DOMAINS),
        employers=_identifiers(table, "employeurs", EMPLOYERS),
        pages_max=pages_max,
    )


def _company(table: Mapping[str, Any]) -> TargetCompany:
    name = _string(table, "nom")
    if not name:
        raise ConfigError("Every [[entreprises]] must have a nom")
    ats = _string(table, "ats")
    if ats not in get_args(AtsType):
        raise ConfigError(f"unknown ats for {name}: {ats}")
    identifier = _string(table, "identifiant")
    if ats and not identifier:
        raise ConfigError(f'{name}: "identifiant" is required when "ats" is set')
    links = {key: _string(table, key).strip() for key in ("site", "linkedin")}
    for key, value in links.items():
        if value and not is_web_address(value):
            raise ConfigError(f'{name}: "{key}" must be an http(s) address')
    return TargetCompany(
        name=name,
        ats=cast(AtsType, ats),
        identifier=identifier,
        site=links["site"],
        linkedin=links["linkedin"],
        unsolicited=_boolean(table, "spontanee", False),
        searches=_strings(table, "recherches"),
    )


def parse(data: Mapping[str, Any], folder: Path) -> Config:
    """Builds the configuration; relative paths start from `folder`."""
    criteria = _table(data, "criteres")
    france_travail = _table(data, "france_travail")
    models = _table(data, "modeles")
    paths = _table(data, "chemins")
    companies = data.get("entreprises", [])
    if not isinstance(companies, list) or not all(isinstance(e, dict) for e in companies):
        raise ConfigError("[[entreprises]] must be a list of tables")
    batch_size = _integer(data, "taille_lot", 8)
    if batch_size < 1:
        raise ConfigError('"taille_lot" must be at least 1')
    return Config(
        profile=_string(data, "profil").strip(),
        unsolicited_role=_string(data, "role_spontane", "Ingénieur IA"),
        batch_size=batch_size,
        scoring_model=_string(models, "notation", "haiku"),
        generation_model=_string(models, "generation", "sonnet"),
        criteria=Criteria(
            keywords=_strings(criteria, "mots_cles"),
            exclusions=_strings(criteria, "exclusions"),
            locations=_strings(criteria, "lieux"),
            salary_floor=_integer(criteria, "salaire_plancher", 0),
        ),
        france_travail=FranceTravail(
            enabled=_boolean(france_travail, "actif", False),
            searches=_strings(france_travail, "recherches"),
            departments=_strings(france_travail, "departements"),
            published_since=_integer(france_travail, "publiee_depuis", 7),
        ),
        service_public=_public_service(_table(data, "service_public")),
        companies=tuple(_company(e) for e in companies),
        paths=Paths(
            root=(folder / _string(paths, "racine", "..")).resolve(),
            base=folder / "moteur.sqlite3",
            exchange=folder / "echange",
        ),
        preparation_model=_string(models, "preparation", "sonnet"),
    )


def load_config(path: Path) -> Config:
    """Lit `config.toml`."""
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError as error:
        raise ConfigError(f"{path} not found: copy config.exemple.toml to config.toml") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} unreadable: {error}") from error
    return parse(data, path.resolve().parent)
