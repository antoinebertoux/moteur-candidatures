"""Loading and validation of `config.toml`."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast, get_args

from moteur.company_links import is_web_address
from moteur.models import normalise
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


_COUNTRY_CODE = re.compile(r"[a-z]{2}")

# Sizes (CAT-03); the catalogue only holds the first two.
SIZES = ("public", "grand-groupe", "pme", "startup")
CATALOGUE_SIZES = SIZES[:2]
# Sectors, a fixed list (CAT-04).
SECTORS = (
    "administration",
    "defense",
    "aeronautique-spatial",
    "naval-maritime",
    "cybersecurite",
    "energie",
    "environnement",
    "sante",
    "pharmacie-biotech",
    "banque",
    "assurance",
    "industrie",
    "automobile",
    "chimie-materiaux",
    "electronique-semiconducteurs",
    "transport-logistique",
    "numerique",
    "telecommunications",
    "jeux-video",
    "commerce-distribution",
    "luxe-mode",
    "medias-culture",
    "tourisme-hotellerie",
    "recherche-enseignement",
    "conseil",
    "esn",
    "interim-rh",
    "btp-immobilier",
    "agroalimentaire",
    "economie-sociale",
)
Origin = Literal["catalogue", "perso"]


# Shipped with the repository (CAT-01).
CATALOGUE = Path(__file__).resolve().parents[2] / "catalogue" / "entreprises.toml"


class ConfigError(ValueError):
    """The configuration file is missing or malformed."""


@dataclass(frozen=True, slots=True)
class Criteria:
    keywords: tuple[str, ...]
    exclusions: tuple[str, ...]
    locations: tuple[str, ...]
    salary_floor: int
    # ISO 3166-1 alpha-2 codes, lower case; empty = every country (CONF-10).
    countries: tuple[str, ...] = ()
    searches: tuple[str, ...] = ()
    """Search terms shared by every company and source (CONF-11)."""


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
class StationF:
    """Search on the Station F job board (SRC-70 to SRC-74)."""

    enabled: bool = False
    searches: tuple[str, ...] = ()
    pages_max: int = 3
    published_since: int = 21


@dataclass(frozen=True, slots=True)
class TargetCompany:
    name: str
    ats: AtsType = ""
    identifier: str = ""
    site: str = ""
    unsolicited: bool = False
    linkedin: str = ""
    """LinkedIn page of the company (CONF-09)."""
    # Terms sent to the ATS search (SRC-41, SRC-35): always `[criteres] recherches` (CAT-07).
    searches: tuple[str, ...] = ()
    sector: str = ""
    """One of SECTORS, or empty for an own company that has none (CAT-04)."""
    size: str = ""
    """One of SIZES, or empty for an own company that has none (CAT-03)."""
    countries: tuple[str, ...] = ()
    """Countries where a catalogue company hires (CAT-02)."""
    origin: Origin = "perso"


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
    station_f: StationF = StationF()
    catalogue: tuple[TargetCompany, ...] = ()
    """Companies of `catalogue/entreprises.toml` (CAT-01)."""

    @property
    def followed(self) -> tuple[TargetCompany, ...]:
        """The catalogue's companies and User's own; an own one replaces its namesake (CAT-06).

        Every company is searched with the shared terms of `[criteres] recherches` (CAT-07).
        """
        own = {normalise(company.name) for company in self.companies}
        others = tuple(c for c in self.catalogue if normalise(c.name) not in own)
        return tuple(replace(c, searches=self.criteria.searches) for c in self.companies + others)


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


def _countries(table: Mapping[str, Any], owner: str = "") -> tuple[str, ...]:
    """Two-letter country codes of `pays`, in lower case (CONF-10)."""
    codes = tuple(code.strip().lower() for code in _strings(table, "pays"))
    for code in codes:
        if not _COUNTRY_CODE.fullmatch(code):
            prefix = f"{owner}: " if owner else ""
            raise ConfigError(f'{prefix}"pays": {code!r} is not a two-letter ISO 3166-1 code')
    return codes


def _one_of(table: Mapping[str, Any], key: str, name: str, accepted: tuple[str, ...]) -> str:
    value = _string(table, key).strip()
    if value and value not in accepted:
        raise ConfigError(f'{name}: unknown "{key}" {value!r} (accepted: {", ".join(accepted)})')
    return value


def _public_service(table: Mapping[str, Any], searches: tuple[str, ...]) -> PublicService:
    pages_max = _integer(table, "pages_max", 3)
    if pages_max < 1:
        raise ConfigError('"pages_max" must be at least 1')
    return PublicService(
        enabled=_boolean(table, "actif", False),
        searches=_strings(table, "recherches") or searches,
        domains=_identifiers(table, "domaines", DOMAINS),
        employers=_identifiers(table, "employeurs", EMPLOYERS),
        pages_max=pages_max,
    )


def _station_f(table: Mapping[str, Any], searches: tuple[str, ...]) -> StationF:
    pages_max = _integer(table, "pages_max", 3)
    if pages_max < 1:
        raise ConfigError('"pages_max" must be at least 1')
    published_since = _integer(table, "publiee_depuis", 21)
    if published_since < 1:
        raise ConfigError('"publiee_depuis" must be at least 1')
    return StationF(
        enabled=_boolean(table, "actif", False),
        searches=_strings(table, "recherches") or searches,
        pages_max=pages_max,
        published_since=published_since,
    )


def _company(table: Mapping[str, Any]) -> TargetCompany:
    name = _string(table, "nom")
    if not name:
        raise ConfigError("Every [[entreprises]] must have a nom")
    if "recherches" in table:
        raise ConfigError(
            f'{name}: "recherches" is shared by every company, move it to [criteres] recherches'
        )
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
        sector=_one_of(table, "secteur", name, SECTORS),
        size=_one_of(table, "taille", name, SIZES),
    )


def _catalogue_company(table: Mapping[str, Any]) -> TargetCompany:
    """A catalogue entry (CAT-02): an own company's fields, plus sector, size and countries."""
    for personal in ("spontanee", "recherches"):
        if personal in table:
            name = table.get("nom", "?")
            raise ConfigError(f'{name}: "{personal}" has no place in the catalogue')
    company = _company(table)
    if not company.sector:
        raise ConfigError(f'{company.name}: "secteur" is required in the catalogue')
    if company.size not in CATALOGUE_SIZES:
        accepted = ", ".join(CATALOGUE_SIZES)
        raise ConfigError(f'{company.name}: "taille" must be one of {accepted} in the catalogue')
    return replace(company, countries=_countries(table, company.name), origin="catalogue")


def parse_catalogue(data: Mapping[str, Any]) -> tuple[TargetCompany, ...]:
    """Builds the catalogue (CAT-02 to CAT-05)."""
    entries = data.get("entreprises", [])
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ConfigError("[[entreprises]] of the catalogue must be a list of tables")
    companies = tuple(_catalogue_company(entry) for entry in entries)
    seen: set[str] = set()
    for company in companies:
        key = normalise(company.name)
        if key in seen:
            raise ConfigError(f"{company.name}: listed twice in the catalogue")
        seen.add(key)
    return companies


def load_catalogue(path: Path = CATALOGUE) -> tuple[TargetCompany, ...]:
    """Reads the catalogue; a missing file means an empty catalogue."""
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError:
        return ()
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} unreadable: {error}") from error
    return parse_catalogue(data)


def parse(
    data: Mapping[str, Any], folder: Path, catalogue: tuple[TargetCompany, ...] = ()
) -> Config:
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
    searches = _strings(criteria, "recherches")
    config = Config(
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
            countries=_countries(criteria),
            searches=searches,
        ),
        france_travail=FranceTravail(
            enabled=_boolean(france_travail, "actif", False),
            searches=_strings(france_travail, "recherches") or searches,
            departments=_strings(france_travail, "departements"),
            published_since=_integer(france_travail, "publiee_depuis", 7),
        ),
        service_public=_public_service(_table(data, "service_public"), searches),
        companies=tuple(_company(e) for e in companies),
        paths=Paths(
            root=(folder / _string(paths, "racine", "..")).resolve(),
            base=folder / "moteur.sqlite3",
            exchange=folder / "echange",
        ),
        preparation_model=_string(models, "preparation", "sonnet"),
        station_f=_station_f(_table(data, "station_f"), searches),
        catalogue=catalogue,
    )
    if not searches:
        # Checked last, so that any other fault of the file is reported first.
        raise ConfigError(
            "[criteres] recherches is required: the search terms sent to the sites "
            "(see config.exemple.toml)"
        )
    return config


def load_config(path: Path) -> Config:
    """Lit `config.toml`."""
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError as error:
        raise ConfigError(f"{path} not found: copy config.exemple.toml to config.toml") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} unreadable: {error}") from error
    return parse(data, path.resolve().parent, load_catalogue())
