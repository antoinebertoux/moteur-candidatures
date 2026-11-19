import pytest

from moteur.filtre import correspond, filtrer, salaire_annuel_max
from moteur.modeles import Offre
from tests.conftest import criteres


@pytest.mark.parametrize(
    ("libelle", "attendu"),
    [
        ("Annuel de 45000.0 Euros à 55000.0 Euros sur 12.0 mois", 55000),
        ("Annuel de 70000,00 Euros", 70000),
        ("Mensuel de 3500.0 Euros sur 13.0 mois", 45500),
        ("Mensuel de 4000 Euros à 5000 Euros", 60000),
        ("Horaire de 15.0 Euros", None),
        ("Selon profil", None),
        ("", None),
    ],
)
@pytest.mark.spec("FILT-04")
def test_salaire_annuel_max(libelle: str, attendu: int | None) -> None:
    assert salaire_annuel_max(libelle) == attendu


@pytest.mark.spec("FILT-01")
def test_garde_une_offre_qui_correspond() -> None:
    assert correspond(Offre("Acme", "Data Scientist senior", lieu="75 - PARIS 14"), criteres())


@pytest.mark.spec("FILT-01")
def test_rejette_sans_mot_cle() -> None:
    assert not correspond(Offre("Acme", "Commercial", lieu="Paris"), criteres())


@pytest.mark.spec("FILT-02")
def test_rejette_une_exclusion() -> None:
    assert not correspond(Offre("Acme", "Stage Data Scientist", lieu="Paris"), criteres())


@pytest.mark.spec("FILT-03")
def test_rejette_un_autre_lieu_mais_garde_un_lieu_inconnu() -> None:
    assert not correspond(Offre("Acme", "Data Scientist", lieu="Marseille"), criteres())
    assert correspond(Offre("Acme", "Data Scientist"), criteres())


@pytest.mark.spec("FILT-04")
def test_salaire_rejette_seulement_si_le_maximum_affiche_est_trop_bas() -> None:
    regles = criteres(salaire_plancher=55000)
    bas = Offre("Acme", "Data Scientist", salaire="Annuel de 40000 Euros à 50000 Euros")
    haut = Offre("Acme", "Data Scientist", salaire="Annuel de 60000 Euros à 75000 Euros")
    inconnu = Offre("Acme", "Data Scientist", salaire="Selon profil")
    assert [correspond(o, regles) for o in (bas, haut, inconnu)] == [False, True, True]


@pytest.mark.spec("FILT-05")
def test_filtrer_retire_les_doublons() -> None:
    offres = [
        Offre("Acme", "Data Scientist", url="a"),
        Offre("ACME", "data scientist", url="b"),
        Offre("Acme", "Commercial"),
    ]
    assert [o.url for o in filtrer(offres, criteres())] == ["a"]
