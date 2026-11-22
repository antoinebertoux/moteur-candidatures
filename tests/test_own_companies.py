"""User's own companies: added by Claude through engine B, kept in the database (CAT-20…)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client import Client

from moteur.cli import main
from moteur.config import Config, ConfigError, TargetCompany, own_company, parse_catalogue
from moteur.local_db import LocalDb
from moteur.mcp_link import companies, server
from moteur.own_companies import (
    OwnCompanyError,
    add_companies,
    import_companies,
    load_with_own_companies,
    remove_companies,
)
from moteur.selection import Choice
from moteur.sources.base import SourceError
from tests.conftest import FakeClient, parsed

BOARD = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"
JOBS = {"jobs": [{"title": "ML Engineer", "absolute_url": "https://x/1"}, {"title": "Data"}]}
DUST = {
    "nom": "Dust",
    "ats": "greenhouse",
    "identifiant": "dust",
    "secteur": "numerique",
    "taille": "startup",
}
SANOFI = {
    "nom": "Sanofi",
    "ats": "lever",
    "identifiant": "sanofi",
    "secteur": "pharmacie-biotech",
    "taille": "grand-groupe",
}


@pytest.fixture
def settings(tmp_path: Path) -> Config:
    return parsed(
        {"criteres": {"recherches": ["machine learning", "data"]}},
        tmp_path,
        parse_catalogue({"entreprises": [{**SANOFI, "pays": []}]}),
    )


def add(settings: Config, client: FakeClient, *items: dict[str, Any]) -> list[dict[str, Any]]:
    with LocalDb(settings.paths.base) as base:
        answer = add_companies({"entreprises": list(items)}, settings, base, client, "2026-11-22")
    results: list[dict[str, Any]] = answer["resultats"]
    return results


def own(settings: Config) -> tuple[TargetCompany, ...]:
    with LocalDb(settings.paths.base) as base:
        return base.own_companies()


@pytest.mark.spec("CAT-20")
def test_an_own_company_needs_a_tool_a_sector_and_a_size() -> None:
    dust = own_company(DUST | {"pays": ["FR"], "site": "https://dust.tt"})
    assert (dust.ats, dust.sector, dust.size, dust.countries) == (
        "greenhouse",
        "numerique",
        "startup",
        ("fr",),
    )
    assert dust.origin == "perso"
    for missing in ("ats", "secteur", "taille"):
        with pytest.raises(ConfigError, match=rf'Dust: "{missing}" is required'):
            own_company({k: v for k, v in DUST.items() if k != missing})
    for personal in ("spontanee", "recherches"):
        with pytest.raises(ConfigError, match=personal):
            own_company(DUST | {personal: True})


@pytest.mark.spec("BASE-16", "CAT-06")
def test_own_companies_live_in_the_database_and_replace_their_catalogue_namesake(
    tmp_path: Path,
) -> None:
    file = tmp_path / "config.toml"
    file.write_text('[criteres]\nrecherches = ["ia"]\n', encoding="utf-8")
    config = load_with_own_companies(file)
    with LocalDb(config.paths.base) as base:
        assert base.save_own_company(own_company(DUST), "2026-11-22") == "added"
        assert base.save_own_company(own_company(DUST), "2026-11-23") == "unchanged"
        changed = own_company(DUST | {"identifiant": "dust-tt"})
        assert base.save_own_company(changed, "2026-11-23") == "updated"
        assert base.save_own_company(own_company(SANOFI | {"nom": "sanofi"}), "d") == "added"
    config = load_with_own_companies(file)
    assert [(c.name, c.identifier) for c in config.companies] == [
        ("Dust", "dust-tt"),
        ("sanofi", "sanofi"),
    ]
    catalogue = parse_catalogue({"entreprises": [SANOFI]})
    followed = parsed({}, tmp_path, catalogue).followed
    assert [c.name for c in followed] == ["Sanofi"]
    followed = replace(parsed({}, tmp_path, catalogue), companies=config.companies).followed
    assert [(c.name, c.origin) for c in followed] == [("Dust", "perso"), ("sanofi", "perso")]


@pytest.mark.spec("CAT-21", "ECH-30")
def test_a_company_is_given_by_tool_or_by_career_page(settings: Config) -> None:
    page = '<a href="https://boards.greenhouse.io/mistral">Jobs</a>'
    client = FakeClient(
        {
            "https://mistral.ai/careers": page,
            BOARD.format("mistral"): JOBS,
            BOARD.format("dust"): {},
        }
    )
    by_page = {
        "nom": "Mistral AI",
        "adresse": "https://mistral.ai/careers",
        "secteur": "numerique",
        "taille": "startup",
    }
    results = add(settings, client, DUST, by_page)
    assert results == [
        {"nom": "Dust", "cle": "dust", "statut": "ajoutee", "annonces": 0},
        {"nom": "Mistral AI", "cle": "mistral-ai", "statut": "ajoutee", "annonces": 2},
    ]
    mistral = own(settings)[1]
    assert (mistral.ats, mistral.identifier, mistral.site) == (
        "greenhouse",
        "mistral",
        "https://mistral.ai/careers",
    )
    both = add(settings, client, DUST | {"adresse": "https://dust.tt"})
    neither = add(
        settings, client, {k: v for k, v in DUST.items() if k not in ("ats", "identifiant")}
    )
    for (result,) in (both, neither):
        assert result["statut"] == "refusee" and "either" in result["raison"]


@pytest.mark.spec("CAT-22")
def test_the_board_is_queried_once_with_the_first_search_term(settings: Config) -> None:
    client = FakeClient({})
    smart = DUST | {"nom": "Acme", "ats": "smartrecruiters", "identifiant": "Acme1"}
    (result,) = add(settings, client, smart)
    assert result["statut"] == "ajoutee" and result["annonces"] == 0
    assert [params.get("q") for _url, params in client.calls] == ["machine learning"]
    with LocalDb(settings.paths.base) as base:
        assert base.for_the_page() == []  # nothing stored as an application


@pytest.mark.spec("CAT-22", "CAT-23")
def test_each_company_is_checked_on_its_own(settings: Config) -> None:
    class Failing(FakeClient):
        def get_json(
            self,
            url: str,
            *,
            params: Mapping[str, str] | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> Any:
            if "broken" in url:
                raise SourceError(f"{url}: HTTP 404")
            return super().get_json(url, params=params, headers=headers)

    client = Failing({BOARD.format("dust"): JOBS, "https://nowhere.io": "<p>none</p>"})
    results = add(
        settings,
        client,
        DUST | {"nom": "Broken", "identifiant": "broken"},
        DUST | {"taille": "geante"},
        {
            "nom": "Nowhere",
            "adresse": "https://nowhere.io",
            "secteur": "numerique",
            "taille": "pme",
        },
        SANOFI,
        DUST,
    )
    reasons = [r.get("raison", "") for r in results]
    assert "HTTP 404" in reasons[0]
    assert "taille" in reasons[1] and "accepted" in reasons[1]
    assert "unrecognised tool" in reasons[2]
    assert reasons[3] == "already in the catalogue (key sanofi)"
    assert results[4] == {"nom": "Dust", "cle": "dust", "statut": "ajoutee", "annonces": 2}
    assert [c.name for c in own(settings)] == ["Dust"]


@pytest.mark.spec("CAT-24")
def test_adding_again_replaces_the_fields_and_keeps_the_choices(settings: Config) -> None:
    client = FakeClient({})
    add(settings, client, DUST)
    with LocalDb(settings.paths.base) as base:
        base.record_choices([Choice("entreprise", "dust", "spontanee", True)])
    (again,) = add(settings, client, DUST | {"nom": "DUST", "identifiant": "dust-tt"})
    assert again["statut"] == "mise_a_jour"
    assert [(c.name, c.identifier) for c in own(settings)] == [("DUST", "dust-tt")]
    with LocalDb(settings.paths.base) as base:
        assert base.choices().get("entreprise", "dust", "spontanee") is True


@pytest.mark.spec("CAT-25", "ECH-32")
def test_only_own_companies_are_removed_and_their_choices_stay(settings: Config) -> None:
    add(settings, FakeClient({}), DUST)
    with LocalDb(settings.paths.base) as base:
        base.record_choices([Choice("entreprise", "dust", "actif", False)])
        with pytest.raises(OwnCompanyError, match="'sanofi' is not one of your own"):
            remove_companies({"cles": ["dust", "sanofi"]}, base)
        assert len(base.own_companies()) == 1
        with pytest.raises(OwnCompanyError):
            remove_companies({"cles": "dust"}, base)
        remove_companies({"cles": ["dust"]}, base)
        assert base.own_companies() == ()
        assert base.choices().get("entreprise", "dust") is False


@pytest.mark.spec("ECH-31")
@pytest.mark.parametrize(
    "entry",
    [{"entreprises": []}, {"entreprises": [DUST] * 21}, {"entreprises": ["Dust"]}, {"autre": []}],
)
def test_an_invalid_list_checks_nothing(settings: Config, entry: dict[str, Any]) -> None:
    client = FakeClient({})
    with LocalDb(settings.paths.base) as base, pytest.raises(OwnCompanyError, match="1 to 20"):
        add_companies(entry, settings, base, client)
    assert client.calls == []


@pytest.mark.spec("ECH-30", "ECH-32")
def test_the_tools_over_the_protocol(settings: Config) -> None:
    client = FakeClient({BOARD.format("dust"): JOBS})

    def load() -> Config:
        with LocalDb(settings.paths.base) as base:
            return replace(settings, companies=base.own_companies())

    async def scenario() -> Any:
        mcp = server(settings.paths, load_config=load, new_client=lambda: client)
        async with Client(mcp) as session:
            added = await session.call_tool("ajouter_entreprises", {"entreprises": [DUST]})
            listed = await session.call_tool("entreprises", {})
            bad = await session.call_tool("retirer_entreprises", {"cles": ["sanofi"]})
            removed = await session.call_tool("retirer_entreprises", {"cles": ["dust"]})
            empty = await session.call_tool("ajouter_entreprises", {"entreprises": []})
            return added, listed, bad, removed, empty

    added, listed, bad, removed, empty = anyio.run(scenario)
    assert not added.is_error
    assert json.loads(added.content[0].text)["resultats"][0]["annonces"] == 2
    assert '"Dust"' in listed.content[0].text
    assert bad.is_error and not removed.is_error and empty.is_error
    assert '"Dust"' not in removed.content[0].text
    assert companies(load(), settings.paths)["entreprises"][0]["nom"] == "Sanofi"


def write_old_config(tmp_path: Path) -> Path:
    file = tmp_path / "config.toml"
    file.write_text(
        '[criteres]\nrecherches = ["ia"]\n\n'
        '[[entreprises]]\nnom = "Dust"\nats = "greenhouse"\nidentifiant = "dust"\n'
        'secteur = "numerique"\ntaille = "startup"\nspontanee = true\n\n'
        '[[entreprises]]\nnom = "Libre"\nsite = "https://libre.io"\n\n'
        '[[entreprises]]\nnom = "Kayrros"\nats = "recruitee"\nidentifiant = "kayrros"\n'
        'secteur = "environnement"\ntaille = "pme"\n',
        encoding="utf-8",
    )
    return file


@pytest.mark.spec("CAT-26", "CLI-10")
def test_import_turns_the_config_companies_into_own_companies(tmp_path: Path) -> None:
    file = write_old_config(tmp_path)
    before = file.read_text(encoding="utf-8")
    lines = import_companies(file, "2026-11-22")
    assert lines[0] == "2 companies added, 0 updated, 0 already there, 1 refused"
    assert lines[1] == '  refused: Libre: "ats" is required'
    assert "delete the [[entreprises]]" in lines[-1]
    assert file.read_text(encoding="utf-8") == before  # never rewritten
    with LocalDb(tmp_path / "moteur.sqlite3") as base:
        assert [c.name for c in base.own_companies()] == ["Dust", "Kayrros"]
        assert base.choices().get("entreprise", "dust", "spontanee") is True
        assert base.choices().get("entreprise", "kayrros", "spontanee") is None
        base.record_choices([Choice("entreprise", "dust", "spontanee", False)])
    again = import_companies(file, "2026-11-23")
    assert again[0] == "0 companies added, 0 updated, 2 already there, 1 refused"
    with LocalDb(tmp_path / "moteur.sqlite3") as base:
        # User's own choice is never overwritten by the import.
        assert base.choices().get("entreprise", "dust", "spontanee") is False


@pytest.mark.spec("CLI-10", "CONF-12")
def test_the_import_command_then_the_other_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = write_old_config(tmp_path)
    assert main(["--config", str(file), "companies"]) == 1
    assert "import-companies" in capsys.readouterr().err
    assert main(["--config", str(file), "import-companies"]) == 0
    assert "2 companies added" in capsys.readouterr().out
    file.write_text('[criteres]\nrecherches = ["ia"]\n', encoding="utf-8")
    assert main(["--config", str(file), "companies"]) == 0
    assert "Dust [perso, startup] searched, unsolicited" in capsys.readouterr().out
