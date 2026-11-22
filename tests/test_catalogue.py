"""Company catalogue and User's choice of what is searched (catalogue.md)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client import Client

from moteur.cli import build_sources, command_collect, companies_report
from moteur.config import (
    CATALOGUE,
    CATALOGUE_SIZES,
    SECTORS,
    Config,
    ConfigError,
    load_catalogue,
    parse_catalogue,
)
from moteur.local_db import LocalDb
from moteur.mcp_link import companies, record_selection, server
from moteur.selection import (
    NO_CHOICE,
    Choice,
    Choices,
    SelectionError,
    searched_companies,
    source_searched,
)
from tests.conftest import SEARCHES, FakeClient, parsed

THALES = {
    "nom": "Thales",
    "ats": "workday",
    "identifiant": "https://thales.wd3.myworkdayjobs.com/Careers",
    "secteur": "defense",
    "taille": "grand-groupe",
    "pays": ["fr", "gb"],
}
SANOFI = {
    "nom": "Sanofi",
    "ats": "lever",
    "identifiant": "sanofi",
    "secteur": "pharmacie-biotech",
    "taille": "grand-groupe",
    "pays": [],
}
INSEE = {"nom": "INSEE", "secteur": "administration", "taille": "public", "pays": ["fr"]}


def config(
    own: list[dict[str, Any]] | None = None,
    catalogue: list[dict[str, Any]] | None = None,
    countries: list[str] | None = None,
    **tables: Any,
) -> Config:
    data: dict[str, Any] = {
        "entreprises": own or [],
        "criteres": {"mots_cles": ["data scientist"], "pays": countries or []},
        **tables,
    }
    entries = [THALES, SANOFI, INSEE] if catalogue is None else catalogue
    return parsed(data, Path(), parse_catalogue({"entreprises": entries}))


def names(companies_: list[Any]) -> list[str]:
    return [company.name for company in companies_]


def choices(*items: tuple[str, str, str, bool]) -> Choices:
    return Choices.of(Choice(s, k, f, v) for s, k, f, v in items)  # type: ignore[arg-type]


@pytest.mark.spec("CAT-01", "CAT-05")
def test_the_shipped_catalogue_is_valid() -> None:
    assert CATALOGUE.name == "entreprises.toml" and CATALOGUE.parent.name == "catalogue"
    catalogue = load_catalogue()
    assert len(catalogue) >= 20
    with CATALOGUE.open("rb") as file:
        raw = tomllib.load(file)["entreprises"]
    for entry in raw:
        assert not {"spontanee", "recherches"} & set(entry)


@pytest.mark.spec("CAT-01")
def test_a_missing_catalogue_is_empty(tmp_path: Path) -> None:
    assert load_catalogue(tmp_path / "none.toml") == ()


@pytest.mark.spec("CAT-02")
def test_a_catalogue_entry_carries_sector_size_and_countries() -> None:
    (thales,) = parse_catalogue({"entreprises": [THALES]})
    assert (thales.sector, thales.size, thales.countries) == (
        "defense",
        "grand-groupe",
        ("fr", "gb"),
    )
    assert thales.origin == "catalogue"
    for personal in ("spontanee", "recherches"):
        value: Any = True if personal == "spontanee" else ["ia"]
        with pytest.raises(ConfigError, match=rf"Thales.*{personal}"):
            parse_catalogue({"entreprises": [THALES | {personal: value}]})
    with pytest.raises(ConfigError, match=r"Thales.*pays"):
        parse_catalogue({"entreprises": [THALES | {"pays": ["france"]}]})


@pytest.mark.spec("CAT-03")
def test_the_catalogue_only_holds_public_bodies_and_large_groups() -> None:
    assert CATALOGUE_SIZES == ("public", "grand-groupe")
    assert {company.size for company in load_catalogue()} <= set(CATALOGUE_SIZES)
    with pytest.raises(ConfigError, match=r"Thales.*taille"):
        parse_catalogue({"entreprises": [THALES | {"taille": "startup"}]})
    with pytest.raises(ConfigError, match=r"Thales.*taille"):
        parse_catalogue({"entreprises": [{k: v for k, v in THALES.items() if k != "taille"}]})


@pytest.mark.spec("CAT-04")
def test_sectors_are_a_fixed_list() -> None:
    assert len(SECTORS) == 30 and len(set(SECTORS)) == 30
    assert {"defense", "aeronautique-spatial", "esn", "economie-sociale"} <= set(SECTORS)
    with pytest.raises(ConfigError, match=r"Thales.*secteur.*accepted"):
        parse_catalogue({"entreprises": [THALES | {"secteur": "paris-sportifs"}]})
    with pytest.raises(ConfigError, match=r"Thales.*secteur"):
        parse_catalogue({"entreprises": [{k: v for k, v in THALES.items() if k != "secteur"}]})


@pytest.mark.spec("CAT-05")
def test_a_company_is_never_listed_twice() -> None:
    with pytest.raises(ConfigError, match="twice"):
        parse_catalogue({"entreprises": [THALES, THALES | {"nom": "THALÈS"}]})


@pytest.mark.spec("CONF-04")
def test_an_own_company_may_have_a_sector_and_a_size() -> None:
    (own,) = config([{"nom": "Dust", "secteur": "numerique", "taille": "startup"}]).companies
    assert (own.sector, own.size, own.origin) == ("numerique", "startup", "perso")
    with pytest.raises(ConfigError, match=r"Dust.*taille.*accepted"):
        config([{"nom": "Dust", "taille": "geante"}])


@pytest.mark.spec("CAT-06")
def test_own_companies_replace_their_catalogue_namesake() -> None:
    followed = config([{"nom": "thales", "ats": "lever", "identifiant": "t"}]).followed
    assert names(list(followed)) == ["thales", "Sanofi", "INSEE"]
    assert followed[0].origin == "perso"


@pytest.mark.spec("CAT-07")
def test_every_company_uses_the_shared_search_terms() -> None:
    own = {"nom": "Helsing", "ats": "workday", "identifiant": "https://h.wd3.myworkdayjobs.com/C"}
    assert {c.searches for c in config([own]).followed} == {tuple(SEARCHES)}


@pytest.mark.spec("CAT-10")
def test_default_selection_follows_the_countries() -> None:
    own = [{"nom": "Dust"}]
    everywhere = searched_companies(config(own), NO_CHOICE)
    assert names(everywhere) == ["Dust", "Thales", "Sanofi", "INSEE"]
    belgium = searched_companies(config(own, countries=["be"]), NO_CHOICE)
    # Thales and INSEE hire elsewhere; Sanofi has no countries; Dust is User's own.
    assert names(belgium) == ["Dust", "Sanofi"]


@pytest.mark.spec("CAT-11")
def test_defaults_move_with_the_countries_but_not_the_choices() -> None:
    chosen = choices(("entreprise", "thales", "actif", True))
    assert "Thales" in names(searched_companies(config(countries=["be"]), chosen))
    assert "INSEE" not in names(searched_companies(config(countries=["be"]), chosen))
    assert "INSEE" in names(searched_companies(config(countries=["fr"]), chosen))


@pytest.mark.spec("CAT-12", "CAT-13")
def test_a_company_is_searched_only_if_it_its_sector_and_its_size_are_on() -> None:
    settings = config([{"nom": "Dust", "secteur": "numerique", "taille": "startup"}])
    assert names(searched_companies(settings, choices(("entreprise", "dust", "actif", False)))) == [
        "Thales",
        "Sanofi",
        "INSEE",
    ]
    no_defense = choices(("secteur", "defense", "actif", False))
    assert "Thales" not in names(searched_companies(settings, no_defense))
    # A ticked company stays left out while its sector is off.
    ticked = choices(
        ("secteur", "defense", "actif", False), ("entreprise", "thales", "actif", True)
    )
    assert "Thales" not in names(searched_companies(settings, ticked))
    no_startup = choices(("taille", "startup", "actif", False))
    assert "Dust" not in names(searched_companies(settings, no_startup))
    # An own company without sector nor size only answers to its own box.
    bare = config([{"nom": "Libre"}])
    off = choices(("taille", "startup", "actif", False), ("secteur", "numerique", "actif", False))
    assert "Libre" in names(searched_companies(bare, off))


@pytest.mark.spec("CAT-14")
def test_unsolicited_application_follows_the_config_then_the_choice() -> None:
    settings = config([{"nom": "Dust", "spontanee": True}])
    by_name = {c.name: c for c in searched_companies(settings, NO_CHOICE)}
    assert by_name["Dust"].unsolicited and not by_name["Sanofi"].unsolicited
    chosen = choices(
        ("entreprise", "dust", "spontanee", False), ("entreprise", "sanofi", "spontanee", True)
    )
    by_name = {c.name: c for c in searched_companies(settings, chosen)}
    assert not by_name["Dust"].unsolicited and by_name["Sanofi"].unsolicited


@pytest.mark.spec("CAT-15")
def test_keyword_sources_need_the_config_and_no_veto() -> None:
    settings = config(service_public={"actif": True}, station_f={"actif": True})
    assert source_searched(settings, NO_CHOICE, "service_public")
    assert not source_searched(settings, NO_CHOICE, "france_travail")
    # Turning on a source that is off in config.toml changes nothing.
    assert not source_searched(
        settings, choices(("source", "france_travail", "actif", True)), "france_travail"
    )
    assert not source_searched(
        settings, choices(("source", "station_f", "actif", False)), "station_f"
    )
    assert not source_searched(
        settings, choices(("taille", "public", "actif", False)), "service_public"
    )
    assert not source_searched(
        settings, choices(("taille", "startup", "actif", False)), "station_f"
    )
    sources = build_sources(settings, FakeClient({}), choices(("taille", "public", "actif", False)))
    assert "service_public" not in {source.name for source in sources}


@pytest.mark.spec("CAT-16", "BASE-15")
def test_choices_are_kept_in_the_local_database(tmp_path: Path) -> None:
    with LocalDb(tmp_path / "m.sqlite3") as base:
        base.record_choices(
            [
                Choice("entreprise", "disparue", "actif", False),
                Choice("secteur", "defense", "actif", False),
                Choice("entreprise", "thales", "spontanee", True),
            ]
        )
        base.record_choices([Choice("secteur", "defense", "actif", None)])
    with LocalDb(tmp_path / "m.sqlite3") as base:
        kept = base.choices()
    assert kept.get("secteur", "defense") is None
    assert kept.get("entreprise", "thales", "spontanee") is True
    # A vanished company's choice stays, and applies if it comes back (CAT-16).
    assert kept.get("entreprise", "disparue") is False
    back = config(catalogue=[SANOFI | {"nom": "Disparue"}])
    assert searched_companies(back, kept) == []


@pytest.mark.spec("COL-09")
def test_collection_only_queries_searched_companies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = config(catalogue=[SANOFI, SANOFI | {"nom": "Ipsen", "identifiant": "ipsen"}])
    settings = parsed(
        {"criteres": {"mots_cles": ["data scientist"]}},
        tmp_path,
        settings.catalogue,
    )

    class ClosingClient(FakeClient):
        def close(self) -> None:
            return None

    monkeypatch.setattr("moteur.cli.HttpxClient", lambda: ClosingClient({}))
    with LocalDb(settings.paths.base) as base:
        base.record_choices([Choice("entreprise", "ipsen", "actif", False)])
        command_collect(settings, base)
    assert "1 companies left out by your choices" in capsys.readouterr().out
    assert [s.name for s in build_sources(settings, FakeClient({}), Choices.of([]))] == [
        "lever:Sanofi",
        "lever:Ipsen",
    ]


@pytest.mark.spec("CLI-09")
def test_companies_report() -> None:
    settings = config([{"nom": "Dust", "taille": "startup"}], service_public={"actif": True})
    report = companies_report(
        settings,
        choices(
            ("secteur", "defense", "actif", False), ("entreprise", "sanofi", "spontanee", True)
        ),
    )
    assert "defense (off)" in report
    assert "Thales [catalogue, grand-groupe] not searched: sector off" in report
    assert "Sanofi [catalogue, grand-groupe] searched, unsolicited" in report
    assert "no sector\n  Dust [perso, startup] searched" in report
    assert "Choisir le service public searched" in report
    assert "France Travail not searched: off in config.toml" in report


@pytest.fixture
def paths_config(tmp_path: Path) -> Config:
    return parsed(
        {"entreprises": [{"nom": "Dust", "spontanee": True}], "station_f": {"actif": True}},
        tmp_path,
        parse_catalogue({"entreprises": [THALES, INSEE]}),
    )


@pytest.mark.spec("ECH-27")
def test_the_entreprises_tool_describes_companies_and_groups(paths_config: Config) -> None:
    answer = companies(paths_config, paths_config.paths)
    dust, thales, _insee = answer["entreprises"]
    assert dust == {
        "cle": "dust",
        "nom": "Dust",
        "origine": "perso",
        "secteur": "",
        "taille": "",
        "pays": [],
        "site": "",
        "recherchee": True,
        "raison": "",
        "actif": True,
        "actif_par_defaut": True,
        "spontanee": True,
        "spontanee_par_defaut": True,
    }
    assert thales["origine"] == "catalogue" and not thales["spontanee"]
    defense = next(s for s in answer["secteurs"] if s["cle"] == "defense")
    assert defense == {"cle": "defense", "actif": True, "entreprises": 1}
    assert [s["cle"] for s in answer["tailles"]] == ["public", "grand-groupe", "pme", "startup"]
    station_f = next(s for s in answer["sources"] if s["cle"] == "station_f")
    assert (station_f["configuree"], station_f["recherchee"]) == (True, True)


@pytest.mark.spec("ECH-28")
def test_selection_records_and_answers_like_entreprises(paths_config: Config) -> None:
    entry = {
        "choix": [
            {"objet": "entreprise", "cle": "thales", "actif": False, "spontanee": True},
            {"objet": "taille", "cle": "public", "actif": False},
        ]
    }
    answer = record_selection(paths_config, paths_config.paths, entry)
    assert answer == companies(paths_config, paths_config.paths)
    thales = answer["entreprises"][1]
    assert (thales["actif"], thales["spontanee"], thales["raison"]) == (False, True, "choix")
    assert record_selection(paths_config, paths_config.paths, entry) == answer
    back = {"choix": [{"objet": "entreprise", "cle": "thales", "actif": None}]}
    assert record_selection(paths_config, paths_config.paths, back)["entreprises"][1]["actif"]


@pytest.mark.spec("ECH-29")
@pytest.mark.parametrize(
    "bad",
    [
        {"objet": "pays", "cle": "fr", "actif": False},
        {"objet": "entreprise", "cle": "inconnue", "actif": False},
        {"objet": "secteur", "cle": "defense", "actif": "non"},
        {"objet": "secteur", "cle": "defense", "spontanee": True},
        {"objet": "secteur", "cle": "defense"},
    ],
)
def test_an_invalid_choice_records_nothing(paths_config: Config, bad: dict[str, Any]) -> None:
    good = {"objet": "taille", "cle": "public", "actif": False}
    with pytest.raises(SelectionError, match="choice 2"):
        record_selection(paths_config, paths_config.paths, {"choix": [good, bad]})
    with LocalDb(paths_config.paths.base) as base:
        assert base.choices().stored == {}
    with pytest.raises(SelectionError):
        record_selection(paths_config, paths_config.paths, {"autre": []})


@pytest.mark.spec("ECH-27", "ECH-29")
def test_the_tools_over_the_protocol(paths_config: Config) -> None:
    async def scenario() -> Any:
        async with Client(server(paths_config.paths, load_config=lambda: paths_config)) as client:
            good = await client.call_tool(
                "selection", {"choix": [{"objet": "secteur", "cle": "defense", "actif": False}]}
            )
            bad = await client.call_tool("selection", {"choix": [{"objet": "x"}]})
            read = await client.call_tool("entreprises", {})
            return good, bad, read

    good, bad, read = anyio.run(scenario)
    assert not good.is_error and bad.is_error and not read.is_error
    assert '"secteur"' in read.content[0].text
