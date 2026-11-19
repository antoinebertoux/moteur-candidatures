from pathlib import Path

import pytest

from moteur.config import ErreurConfig, analyser, charger

RACINE = Path(__file__).resolve().parent.parent


@pytest.mark.spec("CONF-06")
def test_la_config_d_exemple_est_valide() -> None:
    config = charger(RACINE / "config.exemple.toml")
    assert config.modele_notation == "haiku"
    assert config.criteres.salaire_plancher == 0
    assert config.profil.startswith("Décris ici ton profil")
    assert config.entreprises == ()
    assert config.chemins.latex == RACINE.parent / "latex"
    assert config.chemins.base == RACINE / "moteur.sqlite3"


@pytest.mark.spec("CONF-02", "CONF-07")
def test_valeurs_par_defaut(tmp_path: Path) -> None:
    config = analyser({}, tmp_path)
    assert (config.taille_lot, config.modele_generation) == (8, "sonnet")
    assert not config.france_travail.actif
    assert config.chemins.candidatures == tmp_path.parent / "Candidatures"


@pytest.mark.spec("CONF-04")
def test_entreprises() -> None:
    donnees = {
        "entreprises": [
            {"nom": "Acme", "ats": "lever", "identifiant": "acme", "spontanee": True},
            {"nom": "Libre", "site": "https://libre.io"},
        ]
    }
    acme, libre = analyser(donnees, Path()).entreprises
    assert (acme.ats, acme.identifiant, acme.spontanee) == ("lever", "acme", True)
    assert (libre.ats, libre.site, libre.spontanee) == ("", "https://libre.io", False)


@pytest.mark.spec("CONF-04")
def test_entreprise_workday_avec_recherches() -> None:
    donnees = {
        "entreprises": [
            {
                "nom": "Exemple",
                "ats": "workday",
                "identifiant": "https://exemple.wd3.myworkdayjobs.com/Careers",
                "recherches": ["IA", "data"],
            }
        ]
    }
    (exemple,) = analyser(donnees, Path()).entreprises
    assert (exemple.ats, exemple.recherches) == ("workday", ("IA", "data"))
    with pytest.raises(ErreurConfig):
        analyser({"entreprises": [{"nom": "X", "recherches": "IA"}]}, Path())


@pytest.mark.parametrize(
    "donnees",
    [
        {"criteres": "texte"},
        {"criteres": {"mots_cles": "ia"}},
        {"criteres": {"salaire_plancher": "55000"}},
        {"taille_lot": 0},
        {"france_travail": {"actif": "oui"}},
        {"entreprises": [{"nom": "Acme", "ats": "taleo", "identifiant": "x"}]},
        {"entreprises": [{"nom": "Acme", "ats": "lever"}]},
        {"entreprises": [{"ats": "lever", "identifiant": "x"}]},
    ],
)
@pytest.mark.spec("CONF-03")
def test_config_invalide(donnees: dict[str, object]) -> None:
    with pytest.raises(ErreurConfig):
        analyser(donnees, Path())


@pytest.mark.spec("CONF-01")
def test_fichier_absent_ou_illisible(tmp_path: Path) -> None:
    with pytest.raises(ErreurConfig, match=r"config\.exemple\.toml"):
        charger(tmp_path / "config.toml")
    (tmp_path / "config.toml").write_text("criteres = [", encoding="utf-8")
    with pytest.raises(ErreurConfig, match="illisible"):
        charger(tmp_path / "config.toml")
