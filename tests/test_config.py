from pathlib import Path

import pytest

from moteur.config import ConfigError, load_config, parse

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.spec("CONF-06")
def test_the_example_config_is_valid() -> None:
    config = load_config(ROOT / "config.exemple.toml")
    assert config.scoring_model == "haiku"
    assert config.criteria.salary_floor == 0
    assert config.profile.startswith("Décris ici ton profil")
    assert config.companies == ()
    assert config.paths.latex == ROOT.parent / "latex"
    assert config.paths.base == ROOT / "moteur.sqlite3"


@pytest.mark.spec("CONF-02", "CONF-07")
def test_default_values(tmp_path: Path) -> None:
    config = parse({}, tmp_path)
    assert (config.batch_size, config.generation_model) == (8, "sonnet")
    assert not config.france_travail.enabled
    assert not config.station_f.enabled
    assert (config.station_f.pages_max, config.station_f.published_since) == (3, 21)
    assert config.paths.applications == tmp_path.parent / "Candidatures"


@pytest.mark.spec("CONF-04")
def test_companies() -> None:
    data = {
        "entreprises": [
            {"nom": "Acme", "ats": "lever", "identifiant": "acme", "spontanee": True},
            {"nom": "Libre", "site": "https://libre.io"},
        ]
    }
    acme, free = parse(data, Path()).companies
    assert (acme.ats, acme.identifier, acme.unsolicited) == ("lever", "acme", True)
    assert (free.ats, free.site, free.unsolicited) == ("", "https://libre.io", False)


@pytest.mark.spec("CONF-04")
def test_workable_and_welcomekit_companies() -> None:
    data = {
        "entreprises": [
            {"nom": "A", "ats": "workable", "identifiant": "a"},
            {"nom": "B", "ats": "welcomekit", "identifiant": "jobs.b.org"},
        ]
    }
    assert [e.ats for e in parse(data, Path()).companies] == ["workable", "welcomekit"]


@pytest.mark.spec("CONF-04")
def test_workday_company_with_searches() -> None:
    data = {
        "entreprises": [
            {
                "nom": "Exemple",
                "ats": "workday",
                "identifiant": "https://exemple.wd3.myworkdayjobs.com/Careers",
                "recherches": ["IA", "data"],
            }
        ]
    }
    (example,) = parse(data, Path()).companies
    assert (example.ats, example.searches) == ("workday", ("IA", "data"))
    with pytest.raises(ConfigError):
        parse({"entreprises": [{"nom": "X", "recherches": "IA"}]}, Path())


@pytest.mark.spec("CONF-10")
def test_countries() -> None:
    assert parse({}, Path()).criteria.countries == ()
    data = {"criteres": {"pays": ["FR", " gb "]}}
    assert parse(data, Path()).criteria.countries == ("fr", "gb")
    for wrong in (["france"], ["f"], ["F1"], "fr"):
        with pytest.raises(ConfigError, match="pays"):
            parse({"criteres": {"pays": wrong}}, Path())


@pytest.mark.spec("CONF-04")
def test_smartrecruiters_company_with_searches() -> None:
    data = {
        "entreprises": [
            {"nom": "Acme", "ats": "smartrecruiters", "identifiant": "acme", "recherches": ["IA"]}
        ]
    }
    (acme,) = parse(data, Path()).companies
    assert (acme.ats, acme.searches) == ("smartrecruiters", ("IA",))


@pytest.mark.parametrize(
    "data",
    [
        {"criteres": "texte"},
        {"criteres": {"mots_cles": "ia"}},
        {"criteres": {"salaire_plancher": "55000"}},
        {"taille_lot": 0},
        {"france_travail": {"actif": "oui"}},
        {"station_f": {"pages_max": 0}},
        {"station_f": {"publiee_depuis": 0}},
        {"station_f": {"recherches": "ia"}},
        {"entreprises": [{"nom": "Acme", "ats": "taleo", "identifiant": "x"}]},
        {"entreprises": [{"nom": "Acme", "ats": "lever"}]},
        {"entreprises": [{"ats": "lever", "identifiant": "x"}]},
    ],
)
@pytest.mark.spec("CONF-03")
def test_invalid_config(data: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        parse(data, Path())


@pytest.mark.spec("CONF-01")
def test_missing_or_unreadable_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"config\.exemple\.toml"):
        load_config(tmp_path / "config.toml")
    (tmp_path / "config.toml").write_text("criteres = [", encoding="utf-8")
    with pytest.raises(ConfigError, match="unreadable"):
        load_config(tmp_path / "config.toml")
