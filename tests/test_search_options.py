"""Search criteria and sources chosen in the page (config.md CONF-13 to CONF-15)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from moteur.config import (
    Config,
    ConfigError,
    clean_criterion,
    parse_catalogue,
    with_criteria,
)
from moteur.local_db import LocalDb
from moteur.mcp_link import companies, record_selection
from moteur.own_companies import load_with_own_companies
from moteur.selection import NO_CHOICE, SelectionError, searched_companies
from tests.conftest import parsed

THALES = {
    "nom": "Thales",
    "ats": "workday",
    "identifiant": "https://thales.wd3.myworkdayjobs.com/Careers",
    "secteur": "defense",
    "taille": "grand-groupe",
    "pays": ["gb"],
}


def settings(folder: Path = Path(), **tables: Any) -> Config:
    data: dict[str, Any] = {
        "criteres": {
            "mots_cles": ["data scientist"],
            "lieux": ["lyon"],
            "pays": ["fr"],
            "recherches": ["ia"],
        },
        **tables,
    }
    return parsed(data, folder, parse_catalogue({"entreprises": [THALES]}))


@pytest.mark.spec("CONF-13")
def test_replaced_lists_win_over_config_toml() -> None:
    base = settings()
    config = with_criteria(base, {"lieux": ("paris",), "pays": ("gb",)})
    assert config.criteria.locations == ("paris",)
    assert config.criteria.keywords == ("data scientist",)
    assert config.criteria_defaults.locations == ("lyon",)
    assert config.replaced_criteria == ("lieux", "pays")
    # The default selection follows the replaced countries (CAT-10, CAT-11).
    assert [c.name for c in searched_companies(base, NO_CHOICE)] == []
    assert [c.name for c in searched_companies(config, NO_CHOICE)] == ["Thales"]
    # Applied again, it starts from config.toml: an empty replacement means back to it.
    again = with_criteria(config, {})
    assert again.criteria == base.criteria and again.replaced_criteria == ()


@pytest.mark.spec("CONF-13", "BASE-17")
def test_every_command_reads_the_replaced_lists(tmp_path: Path) -> None:
    file = tmp_path / "config.toml"
    file.write_text('[criteres]\nrecherches = ["ia"]\nlieux = ["lyon"]\n', encoding="utf-8")
    with LocalDb(tmp_path / "moteur.sqlite3") as base:
        base.record_criteria({"lieux": ("paris", "remote"), "recherches": ("data",)})
        assert base.criteria() == {"lieux": ("paris", "remote"), "recherches": ("data",)}
    config = load_with_own_companies(file)
    assert config.criteria.locations == ("paris", "remote")
    assert config.criteria.searches == ("data",)
    with LocalDb(tmp_path / "moteur.sqlite3") as base:
        base.record_criteria({"lieux": None})
        assert base.criteria() == {"recherches": ("data",)}
    assert load_with_own_companies(file).criteria.locations == ("lyon",)


@pytest.mark.spec("CONF-14")
def test_a_list_from_the_page_is_cleaned_and_checked() -> None:
    assert clean_criterion("lieux", [" Lyon ", "", "lyon", "Télétravail", "teletravail"]) == (
        "Lyon",
        "Télétravail",
    )
    assert clean_criterion("pays", ["FR", " gb"]) == ("fr", "gb")
    assert clean_criterion("mots_cles", []) == ()
    with pytest.raises(ConfigError, match="two-letter"):
        clean_criterion("pays", ["france"])
    with pytest.raises(ConfigError, match="cannot be empty"):
        clean_criterion("recherches", ["  "])
    with pytest.raises(ConfigError, match="list of strings"):
        clean_criterion("lieux", "lyon")
    with pytest.raises(ConfigError, match="unknown"):
        clean_criterion("salaire_plancher", [])


@pytest.mark.spec("CONF-15")
def test_a_source_with_its_own_terms_keeps_them() -> None:
    base = settings(station_f={"recherches": ["ml"]})
    config = with_criteria(base, {"recherches": ("data", "nlp")})
    assert config.station_f.searches == ("ml",)
    assert config.service_public.searches == ("data", "nlp")
    assert config.france_travail.searches == ("data", "nlp")
    assert [c.searches for c in config.followed] == [("data", "nlp")]


@pytest.fixture
def page_config(tmp_path: Path) -> Config:
    return settings(tmp_path, station_f={"recherches": ["ml"]})


@pytest.mark.spec("ECH-27")
def test_the_entreprises_tool_gives_criteria_and_sources(
    page_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FRANCE_TRAVAIL_ID", raising=False)
    answer = companies(page_config, page_config.paths)
    assert answer["criteres"][2] == {
        "cle": "lieux",
        "valeur": ["lyon"],
        "defaut": ["lyon"],
        "modifie": False,
    }
    assert [c["cle"] for c in answer["criteres"]] == [
        "mots_cles",
        "exclusions",
        "lieux",
        "pays",
        "recherches",
    ]
    sources = {s["cle"]: s for s in answer["sources"]}
    assert sources["france_travail"]["identifiants"] is False
    assert sources["station_f"]["recherches_propres"] is True
    assert sources["station_f"]["actif"] is None


@pytest.mark.spec("ECH-28")
def test_selection_replaces_a_criterion(page_config: Config) -> None:
    paths = page_config.paths
    entry = {"choix": [{"objet": "critere", "cle": "lieux", "valeur": ["Paris", "paris"]}]}
    answer = record_selection(page_config, paths, entry)
    lieux = answer["criteres"][2]
    assert (lieux["valeur"], lieux["defaut"], lieux["modifie"]) == (["Paris"], ["lyon"], True)
    assert record_selection(page_config, paths, entry) == answer
    assert companies(page_config, paths) == answer
    # Countries replaced: the catalogue companies move at once (CAT-11).
    gb = {"choix": [{"objet": "critere", "cle": "pays", "valeur": ["gb"]}]}
    assert record_selection(page_config, paths, gb)["entreprises"][0]["recherchee"]
    back = {"choix": [{"objet": "critere", "cle": "lieux", "valeur": None}]}
    assert record_selection(page_config, paths, back)["criteres"][2]["modifie"] is False


@pytest.mark.spec("ECH-29")
@pytest.mark.parametrize(
    "bad",
    [
        {"objet": "critere", "cle": "salaire", "valeur": []},
        {"objet": "critere", "cle": "pays", "valeur": ["france"]},
        {"objet": "critere", "cle": "recherches", "valeur": []},
        {"objet": "critere", "cle": "lieux", "valeur": "lyon"},
        {"objet": "critere", "cle": "lieux"},
        {"objet": "critere", "cle": "lieux", "valeur": [], "actif": True},
    ],
)
def test_an_invalid_criterion_records_nothing(page_config: Config, bad: dict[str, Any]) -> None:
    good = {"objet": "critere", "cle": "lieux", "valeur": ["paris"]}
    with pytest.raises(SelectionError, match="choice 2"):
        record_selection(page_config, page_config.paths, {"choix": [good, bad]})
    with LocalDb(page_config.paths.base) as base:
        assert base.criteria() == {}
