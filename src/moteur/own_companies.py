"""User's own companies: checked, added, removed and imported (CAT-20 to CAT-26, CLI-10)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from moteur.config import (
    Config,
    ConfigError,
    TargetCompany,
    load_config,
    own_company,
    read_toml,
)
from moteur.detection import detect
from moteur.local_db import LocalDb
from moteur.models import normalise
from moteur.selection import Choice
from moteur.sources.ats import SourceAts
from moteur.sources.avature import SourceAvature
from moteur.sources.base import HttpClient, Source, SourceError
from moteur.sources.oracle import SourceOracle
from moteur.sources.phenom import SourcePhenom
from moteur.sources.radancy import SourceRadancy
from moteur.sources.successfactors import SourceSuccessFactors
from moteur.sources.talentsoft import SourceTalentsoft
from moteur.sources.welcomekit import SourceWelcomeKit
from moteur.sources.workday import SourceWorkday

# Companies one call of `ajouter_entreprises` may hold (ECH-30).
MAX_PER_CALL = 20


class OwnCompanyError(ValueError):
    """The input of `ajouter_entreprises` or `retirer_entreprises` is invalid (ECH-31, ECH-32)."""


def load_with_own_companies(path: Path) -> Config:
    """`config.toml`, the catalogue and User's own companies from the database (CAT-06)."""
    config = load_config(path)
    with LocalDb(config.paths.base) as base:
        return replace(config, companies=base.own_companies())


def source_for(
    target: TargetCompany, client: HttpClient, countries: Sequence[str]
) -> Source | None:
    """The source reading a company's board (SRC-30 and following); None without a tool."""
    if target.ats == "workday":
        return SourceWorkday(client, target)
    if target.ats == "radancy":
        return SourceRadancy(client, target)
    if target.ats == "welcomekit":
        return SourceWelcomeKit(client, target)
    if target.ats == "talentsoft":
        return SourceTalentsoft(client, target)
    if target.ats == "oracle":
        return SourceOracle(client, target)
    if target.ats == "successfactors":
        return SourceSuccessFactors(client, target, countries)
    if target.ats == "phenom":
        return SourcePhenom(client, target)
    if target.ats == "avature":
        return SourceAvature(client, target)
    if target.ats:
        return SourceAts(client, target, countries)
    return None


def check_board(company: TargetCompany, config: Config, client: HttpClient) -> int:
    """CAT-22: queries the board once and returns the number of ads; raises SourceError."""
    target = replace(company, searches=config.criteria.searches[:1])
    source = source_for(target, client, config.criteria.countries)
    if source is None:
        raise SourceError("no recruiting tool")
    return len(source.collect())


def _resolved(item: Mapping[str, Any], client: HttpClient) -> TargetCompany:
    """CAT-21: the tool and identifier given, or found from the career page `adresse`."""
    fields = dict(item)
    address = fields.pop("adresse", None)
    given = "ats" in fields or "identifiant" in fields
    name = fields.get("nom", "?")
    if address is not None and not isinstance(address, str):
        raise ConfigError(f'{name}: "adresse" must be a string')
    if bool(address) == given:
        raise ConfigError(f'{name}: give either "ats" and "identifiant", or "adresse"')
    if address:
        found = detect(address, client)
        if found.error:
            raise ConfigError(f"{name}: {found.error}")
        fields.update(ats=found.ats, identifiant=found.identifier)
        if not fields.get("site"):
            fields["site"] = address.strip()
    return own_company(fields)


def _refused(name: object, reason: str) -> dict[str, Any]:
    shown = name if isinstance(name, str) else ""
    return {"nom": shown, "cle": normalise(shown), "statut": "refusee", "raison": reason}


def add_companies(
    entry: object, config: Config, base: LocalDb, client: HttpClient, day: str = ""
) -> dict[str, Any]:
    """ECH-30: checks and keeps each company on its own (CAT-22 to CAT-24)."""
    items = entry.get("entreprises") if isinstance(entry, Mapping) else None
    if (
        not isinstance(items, list)
        or not 1 <= len(items) <= MAX_PER_CALL
        or not all(isinstance(item, Mapping) for item in items)
    ):
        raise OwnCompanyError(
            f'expected {{"entreprises": [...]}} with 1 to {MAX_PER_CALL} companies'
        )
    day = day or date.today().isoformat()
    catalogue = {normalise(company.name) for company in config.catalogue}
    results: list[dict[str, Any]] = []
    for item in items:
        name = item.get("nom")
        key = normalise(name) if isinstance(name, str) else ""
        if key and key in catalogue:
            # CAT-23: turned on with `selection` rather than added.
            results.append(_refused(name, f"already in the catalogue (key {key})"))
            continue
        try:
            company = _resolved(item, client)
            ads = check_board(company, config, client)
        except (ConfigError, SourceError) as error:
            results.append(_refused(name, str(error)))
            continue
        outcome = base.save_own_company(company, day)
        results.append(
            {
                "nom": company.name,
                "cle": normalise(company.name),
                "statut": "ajoutee" if outcome == "added" else "mise_a_jour",
                "annonces": ads,
            }
        )
    return {"resultats": results}


def remove_companies(entry: object, base: LocalDb) -> None:
    """ECH-32: removes own companies (CAT-25); one unknown key removes none."""
    keys = entry.get("cles") if isinstance(entry, Mapping) else None
    if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
        raise OwnCompanyError('expected {"cles": [...]}, a list of company keys')
    own = {normalise(company.name) for company in base.own_companies()}
    for key in keys:
        if key not in own:
            raise OwnCompanyError(f"{key!r} is not one of your own companies")
    base.remove_own_companies(keys)


def import_companies(path: Path, day: str = "") -> list[str]:
    """CLI-10: the `[[entreprises]]` of `config.toml` become own companies.

    Their boards are not queried. `config.toml` is never rewritten.
    """
    entries = read_toml(path).get("entreprises", [])
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ConfigError("[[entreprises]] must be a list of tables")
    config = load_config(path, ignore_companies=True)
    day = day or date.today().isoformat()
    counts = {"added": 0, "updated": 0, "unchanged": 0}
    lines: list[str] = []
    with LocalDb(config.paths.base) as base:
        chosen = base.choices()
        for entry in entries:
            fields = {k: v for k, v in entry.items() if k != "spontanee"}
            try:
                company = own_company(fields)
            except ConfigError as error:
                lines.append(f"  refused: {error}")
                continue
            counts[base.save_own_company(company, day)] += 1
            key = normalise(company.name)
            if (
                entry.get("spontanee") is True
                and chosen.get("entreprise", key, "spontanee") is None
            ):
                base.record_choices([Choice("entreprise", key, "spontanee", True)])
    refused = len(lines)
    summary = (
        f"{counts['added']} companies added, {counts['updated']} updated, "
        f"{counts['unchanged']} already there, {refused} refused"
    )
    return [
        summary,
        *lines,
        "Now delete the [[entreprises]] from config.toml: engine B reads them from its database.",
    ]
