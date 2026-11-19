from collections.abc import Iterator
from pathlib import Path

import pytest

from moteur.base_locale import ACCEPTEE, GENEREE, NOTEE, BaseLocale
from moteur.modeles import Note, Offre

OFFRE = Offre("Acme", "Data Scientist", lieu="Paris", description="Texte")
SPONTANEE = Offre("Libre", "Lead AI", type="spontanee")
NOTE = Note(score=82, resume="Bon poste.", lettre_demandee=True, langue="en")


@pytest.fixture
def base() -> Iterator[BaseLocale]:
    with BaseLocale(":memory:") as base_locale:
        yield base_locale


@pytest.mark.spec("BASE-01")
def test_ajouter_ignore_les_doublons(base: BaseLocale) -> None:
    assert base.ajouter([OFFRE, SPONTANEE]) == 2
    assert base.ajouter([OFFRE, Offre("ACME", "data scientist")]) == 0
    assert base.a_noter() == [OFFRE]


@pytest.mark.spec("BASE-02")
def test_une_spontanee_est_proposee_sans_notation(base: BaseLocale) -> None:
    base.ajouter([SPONTANEE])
    (candidature,) = base.pour_la_page()
    assert (candidature.statut, candidature.lettre_demandee, candidature.score) == (
        NOTEE,
        True,
        None,
    )


@pytest.mark.spec("BASE-03", "BASE-04")
def test_notation_puis_export(base: BaseLocale) -> None:
    base.ajouter([OFFRE])
    base.enregistrer_note(OFFRE.cle, NOTE)
    assert base.a_noter() == []
    (candidature,) = base.pour_la_page()
    assert (candidature.score, candidature.langue, candidature.lettre_demandee) == (82, "en", True)


@pytest.mark.spec("BASE-04", "BASE-05")
def test_decisions_de_la_page(base: BaseLocale) -> None:
    base.ajouter([OFFRE, SPONTANEE])
    base.enregistrer_note(OFFRE.cle, NOTE)
    assert base.appliquer_decision(OFFRE.cle, "acceptee")
    assert not base.appliquer_decision(OFFRE.cle, "acceptee")
    assert not base.appliquer_decision(OFFRE.cle, "prete")
    assert not base.appliquer_decision("inconnue", "refusee")
    assert base.appliquer_decision(SPONTANEE.cle, "refusee")
    assert [c.offre for c in base.a_generer()] == [OFFRE]
    assert base.pour_la_page() == []


@pytest.mark.spec("BASE-06", "BASE-09")
def test_generation_puis_retouche(base: BaseLocale) -> None:
    base.ajouter([OFFRE])
    base.enregistrer_note(OFFRE.cle, NOTE)
    base.appliquer_decision(OFFRE.cle, "acceptee")
    base.marquer_generee(OFFRE.cle, "Candidatures/Acme/cv.pdf", "")
    (generee,) = base.pour_la_page()
    assert (generee.statut, generee.cv_ref) == (GENEREE, "Candidatures/Acme/cv.pdf")
    assert not base.appliquer_decision(OFFRE.cle, "acceptee")
    assert base.a_generer() == []
    assert base.appliquer_decision(OFFRE.cle, "acceptee", "Mets le RAG en premier")
    (a_refaire,) = base.a_generer()
    assert (a_refaire.statut, a_refaire.consigne) == (ACCEPTEE, "Mets le RAG en premier")
    assert base.appliquer_decision(OFFRE.cle, "postulee")
    assert base.a_generer() == []


@pytest.mark.spec("COL-05")
def test_entreprises_connues(base: BaseLocale) -> None:
    base.ajouter([OFFRE, SPONTANEE])
    assert base.entreprises_connues() == {"acme", "libre"}


@pytest.mark.spec("BASE-07")
def test_offre_acceptee_inconnue_ajoutee_depuis_la_page(base: BaseLocale) -> None:
    manuelle = Offre("Banque de France", "AI/ML Engineer", url="https://x", source="linkedin")
    assert base.completer_depuis_la_page(manuelle.cle, manuelle, lettre_demandee=False)
    assert not base.completer_depuis_la_page(manuelle.cle, manuelle, lettre_demandee=False)
    (candidature,) = base.a_generer()
    assert candidature.offre == manuelle


@pytest.mark.spec("BASE-07")
def test_texte_de_l_offre_complete_sans_ecraser(base: BaseLocale) -> None:
    sans_texte = Offre("Orano", "Data Scientist")
    base.completer_depuis_la_page(sans_texte.cle, sans_texte, lettre_demandee=False)
    avec_texte = Offre("Orano", "Data Scientist", description="Missions : ...")
    assert base.completer_depuis_la_page(avec_texte.cle, avec_texte, lettre_demandee=False)
    autre = Offre("Orano", "Data Scientist", description="Autre texte")
    assert not base.completer_depuis_la_page(autre.cle, autre, lettre_demandee=False)
    assert base.a_generer()[0].offre.description == "Missions : ..."
    base.ajouter([OFFRE])
    assert not base.completer_depuis_la_page(
        OFFRE.cle, Offre("Acme", "Data Scientist", description="Neuf"), lettre_demandee=False
    )
    assert base.a_noter()[0].description == "Texte"


@pytest.mark.spec("BASE-11")
def test_refusal_reason_is_stored_then_cleared(base: BaseLocale) -> None:
    base.ajouter([OFFRE])
    assert not base.set_refusal_reason(OFFRE.cle, "salaire", "")  # not refused yet
    base.appliquer_decision(OFFRE.cle, "refusee")
    assert base.set_refusal_reason(OFFRE.cle, "salaire", "50 K€ affichés")
    assert not base.set_refusal_reason(OFFRE.cle, "salaire", "50 K€ affichés")
    assert base.set_refusal_reason(OFFRE.cle, "lieu", "")
    assert [(r.reason, r.detail) for r in base.recent_refusals(10)] == [("lieu", "")]
    base.appliquer_decision(OFFRE.cle, "acceptee")
    assert base.recent_refusals(10) == []
    base.appliquer_decision(OFFRE.cle, "refusee")
    assert base.recent_refusals(10) == []  # the old reason does not come back


@pytest.mark.spec("BASE-11", "NOT-08")
def test_recent_refusals_skip_duplicates_and_missing_reasons(base: BaseLocale) -> None:
    autres = [Offre(f"E{i}", "Data Scientist") for i in range(3)]
    base.ajouter([OFFRE, *autres])
    for offre, reason in zip(
        [OFFRE, *autres], ["conseil", "doublon", "", "trop_senior"], strict=True
    ):
        base.appliquer_decision(offre.cle, "refusee")
        base.set_refusal_reason(offre.cle, reason, "")
    assert {r.reason for r in base.recent_refusals(10)} == {"conseil", "trop_senior"}
    assert len(base.recent_refusals(1)) == 1


@pytest.mark.spec("BASE-10")
def test_older_database_gets_the_refusal_columns(tmp_path: Path) -> None:
    import sqlite3

    chemin = tmp_path / "ancienne.sqlite3"
    with sqlite3.connect(chemin) as connexion:
        connexion.execute(
            "CREATE TABLE candidatures (cle TEXT PRIMARY KEY, type TEXT NOT NULL,"
            " entreprise TEXT NOT NULL, poste TEXT NOT NULL, lieu TEXT NOT NULL DEFAULT '',"
            " url TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',"
            " description TEXT NOT NULL DEFAULT '', salaire TEXT NOT NULL DEFAULT '',"
            " date_publication TEXT NOT NULL DEFAULT '', statut TEXT NOT NULL, score INTEGER,"
            " resume TEXT NOT NULL DEFAULT '', lettre_demandee INTEGER NOT NULL DEFAULT 0,"
            " langue TEXT NOT NULL DEFAULT 'fr', consigne TEXT NOT NULL DEFAULT '',"
            " cv_ref TEXT NOT NULL DEFAULT '', lettre_ref TEXT NOT NULL DEFAULT '',"
            " date_ajout TEXT NOT NULL)"
        )
    with BaseLocale(chemin) as ancienne:
        ancienne.ajouter([OFFRE])
        ancienne.appliquer_decision(OFFRE.cle, "refusee")
        assert ancienne.set_refusal_reason(OFFRE.cle, "secteur", "")
