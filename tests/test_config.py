from pathlib import Path

import pytest

from moteur.config import ConfigError, load_config, parse
from tests.conftest import parsed

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
    config = parsed({}, tmp_path)
    assert (config.batch_size, config.generation_model) == (8, "sonnet")
    assert not config.france_travail.enabled
    assert not config.station_f.enabled
    assert (config.station_f.pages_max, config.station_f.published_since) == (3, 21)
    assert config.paths.applications == tmp_path.parent / "Candidatures"


@pytest.mark.spec("CONF-12")
def test_config_lists_no_company(tmp_path: Path) -> None:
    data = {"criteres": {"recherches": ["ia"]}, "entreprises": [{"nom": "Acme"}]}
    with pytest.raises(ConfigError, match=r"moteur import-companies.*delete them"):
        parse(data, Path())
    file = tmp_path / "config.toml"
    file.write_text('[criteres]\nrecherches = ["ia"]\n[[entreprises]]\nnom = "Acme"\n')
    with pytest.raises(ConfigError, match="import-companies"):
        load_config(file)
    assert load_config(file, ignore_companies=True).companies == ()


@pytest.mark.spec("CONF-11")
def test_one_search_list_shared_by_companies_and_sources() -> None:
    data = {
        "criteres": {"recherches": ["machine learning", "data"]},
        "service_public": {"recherches": ["science des données"]},
        "entreprises": [
            {"nom": "A", "ats": "workday", "identifiant": "https://a.wd3.myworkdayjobs.com/C"},
            {"nom": "B", "ats": "smartrecruiters", "identifiant": "b"},
        ],
    }
    config = parsed(data, Path())
    shared = ("machine learning", "data")
    assert [c.searches for c in config.followed] == [shared, shared]
    assert config.france_travail.searches == shared
    assert config.station_f.searches == shared
    assert config.service_public.searches == ("science des données",)


@pytest.mark.spec("CONF-11")
def test_the_search_list_is_required() -> None:
    empty: tuple[dict[str, list[str]], ...] = ({}, {"recherches": []})
    for criteria in empty:
        with pytest.raises(ConfigError, match=r"\[criteres\] recherches is required"):
            parse({"criteres": criteria}, Path())
    with pytest.raises(ConfigError, match="recherches"):
        parse({"criteres": {"recherches": "ia"}}, Path())


@pytest.mark.spec("CONF-10")
def test_countries() -> None:
    assert parsed({}, Path()).criteria.countries == ()
    data = {"criteres": {"pays": ["FR", " gb "]}}
    assert parsed(data, Path()).criteria.countries == ("fr", "gb")
    for wrong in (["france"], ["f"], ["F1"], "fr"):
        with pytest.raises(ConfigError, match="pays"):
            parsed({"criteres": {"pays": wrong}}, Path())


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
        parsed(data, Path())


@pytest.mark.spec("CONF-01")
def test_missing_or_unreadable_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"config\.exemple\.toml"):
        load_config(tmp_path / "config.toml")
    (tmp_path / "config.toml").write_text("criteres = [", encoding="utf-8")
    with pytest.raises(ConfigError, match="unreadable"):
        load_config(tmp_path / "config.toml")
