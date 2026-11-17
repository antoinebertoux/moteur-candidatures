from collections.abc import Iterator

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


def test_ajouter_ignore_les_doublons(base: BaseLocale) -> None:
    assert base.ajouter([OFFRE, SPONTANEE]) == 2
    assert base.ajouter([OFFRE, Offre("ACME", "data scientist")]) == 0
    assert base.a_noter() == [OFFRE]


def test_une_spontanee_est_proposee_sans_notation(base: BaseLocale) -> None:
    base.ajouter([SPONTANEE])
    (candidature,) = base.pour_la_page()
    assert (candidature.statut, candidature.lettre_demandee, candidature.score) == (
        NOTEE,
        True,
        None,
    )


def test_notation_puis_export(base: BaseLocale) -> None:
    base.ajouter([OFFRE])
    base.enregistrer_note(OFFRE.cle, NOTE)
    assert base.a_noter() == []
    (candidature,) = base.pour_la_page()
    assert (candidature.score, candidature.langue, candidature.lettre_demandee) == (82, "en", True)


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


def test_generation_puis_retouche(base: BaseLocale) -> None:
    base.ajouter([OFFRE])
    base.enregistrer_note(OFFRE.cle, NOTE)
    base.appliquer_decision(OFFRE.cle, "acceptee")
    base.marquer_generee(OFFRE.cle, "Candidatures/Acme/cv.pdf", "")
    (generee,) = base.pour_la_page()
    assert (generee.statut, generee.cv_ref) == (GENEREE, "Candidatures/Acme/cv.pdf")
    assert base.appliquer_decision(OFFRE.cle, "acceptee", "Mets le RAG en premier")
    (a_refaire,) = base.a_generer()
    assert (a_refaire.statut, a_refaire.consigne) == (ACCEPTEE, "Mets le RAG en premier")
    assert base.appliquer_decision(OFFRE.cle, "postulee")
    assert base.a_generer() == []


def test_entreprises_connues(base: BaseLocale) -> None:
    base.ajouter([OFFRE, SPONTANEE])
    assert base.entreprises_connues() == {"acme", "libre"}
