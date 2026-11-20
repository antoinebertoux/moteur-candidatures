from collections.abc import Iterator
from pathlib import Path

import pytest

from moteur.local_db import ACCEPTED, GENERATED, SCORED, LocalDb
from moteur.models import JobAd, Rating

AD = JobAd("Acme", "Data Scientist", location="Paris", description="Texte")
UNSOLICITED = JobAd("Libre", "Lead AI", type="spontanee")
NOTE = Rating(score=82, summary="Bon poste.", letter_requested=True, language="en")


@pytest.fixture
def base() -> Iterator[LocalDb]:
    with LocalDb(":memory:") as db:
        yield db


@pytest.mark.spec("BASE-01")
def test_ajouter_ignore_les_doublons(base: LocalDb) -> None:
    assert base.add([AD, UNSOLICITED]) == 2
    assert base.add([AD, JobAd("ACME", "data scientist")]) == 0
    assert base.to_score() == [AD]


@pytest.mark.spec("BASE-02")
def test_an_unsolicited_application_is_proposed_without_scoring(base: LocalDb) -> None:
    base.add([UNSOLICITED])
    (application,) = base.for_the_page()
    assert (application.status, application.letter_requested, application.score) == (
        SCORED,
        True,
        None,
    )


@pytest.mark.spec("BASE-03", "BASE-04")
def test_scoring_then_export(base: LocalDb) -> None:
    base.add([AD])
    base.record_score(AD.key, NOTE)
    assert base.to_score() == []
    (application,) = base.for_the_page()
    assert (application.score, application.language, application.letter_requested) == (
        82,
        "en",
        True,
    )


@pytest.mark.spec("BASE-04", "BASE-05")
def test_decisions_from_the_page(base: LocalDb) -> None:
    base.add([AD, UNSOLICITED])
    base.record_score(AD.key, NOTE)
    assert base.apply_decision(AD.key, "acceptee")
    assert not base.apply_decision(AD.key, "acceptee")
    assert not base.apply_decision(AD.key, "prete")
    assert not base.apply_decision("inconnue", "refusee")
    assert base.apply_decision(UNSOLICITED.key, "refusee")
    assert [c.ad for c in base.to_generate()] == [AD]
    assert base.for_the_page() == []


@pytest.mark.spec("BASE-06", "BASE-09")
def test_generation_then_edit(base: LocalDb) -> None:
    base.add([AD])
    base.record_score(AD.key, NOTE)
    base.apply_decision(AD.key, "acceptee")
    base.mark_generated(AD.key, "Candidatures/Acme/cv.pdf", "")
    (generated,) = base.for_the_page()
    assert (generated.status, generated.cv_ref) == (GENERATED, "Candidatures/Acme/cv.pdf")
    assert not base.apply_decision(AD.key, "acceptee")
    assert base.to_generate() == []
    assert base.apply_decision(AD.key, "acceptee", "Mets le RAG en premier")
    (to_redo,) = base.to_generate()
    assert (to_redo.status, to_redo.instruction) == (ACCEPTED, "Mets le RAG en premier")
    assert base.apply_decision(AD.key, "postulee")
    assert base.to_generate() == []


@pytest.mark.spec("COL-05")
def test_known_companies(base: LocalDb) -> None:
    base.add([AD, UNSOLICITED])
    assert base.known_companies() == {"acme", "libre"}


@pytest.mark.spec("BASE-07")
def test_unknown_accepted_ad_added_from_the_page(base: LocalDb) -> None:
    manual = JobAd("Banque de France", "AI/ML Engineer", url="https://x", source="linkedin")
    assert base.complete_from_the_page(manual.key, manual, letter_requested=False)
    assert not base.complete_from_the_page(manual.key, manual, letter_requested=False)
    (application,) = base.to_generate()
    assert application.ad == manual


@pytest.mark.spec("BASE-07")
def test_ad_text_completed_without_overwriting(base: LocalDb) -> None:
    without_text = JobAd("Orano", "Data Scientist")
    base.complete_from_the_page(without_text.key, without_text, letter_requested=False)
    with_text = JobAd("Orano", "Data Scientist", description="Missions : ...")
    assert base.complete_from_the_page(with_text.key, with_text, letter_requested=False)
    other = JobAd("Orano", "Data Scientist", description="Autre texte")
    assert not base.complete_from_the_page(other.key, other, letter_requested=False)
    assert base.to_generate()[0].ad.description == "Missions : ..."
    base.add([AD])
    assert not base.complete_from_the_page(
        AD.key, JobAd("Acme", "Data Scientist", description="Neuf"), letter_requested=False
    )
    assert base.to_score()[0].description == "Texte"


@pytest.mark.spec("BASE-11")
def test_refusal_reason_is_stored_then_cleared(base: LocalDb) -> None:
    base.add([AD])
    assert not base.set_refusal_reason(AD.key, "salaire", "")  # not refused yet
    base.apply_decision(AD.key, "refusee")
    assert base.set_refusal_reason(AD.key, "salaire", "50 K€ affichés")
    assert not base.set_refusal_reason(AD.key, "salaire", "50 K€ affichés")
    assert base.set_refusal_reason(AD.key, "lieu", "")
    assert [(r.reason, r.detail) for r in base.recent_refusals(10)] == [("lieu", "")]
    base.apply_decision(AD.key, "acceptee")
    assert base.recent_refusals(10) == []
    base.apply_decision(AD.key, "refusee")
    assert base.recent_refusals(10) == []  # the old reason does not come back


@pytest.mark.spec("BASE-11", "NOT-08")
def test_recent_refusals_skip_duplicates_and_missing_reasons(base: LocalDb) -> None:
    others = [JobAd(f"E{i}", "Data Scientist") for i in range(3)]
    base.add([AD, *others])
    for ad, reason in zip([AD, *others], ["conseil", "doublon", "", "trop_senior"], strict=True):
        base.apply_decision(ad.key, "refusee")
        base.set_refusal_reason(ad.key, reason, "")
    assert {r.reason for r in base.recent_refusals(10)} == {"conseil", "trop_senior"}
    assert len(base.recent_refusals(1)) == 1


@pytest.mark.spec("BASE-10")
def test_older_database_gets_the_refusal_columns(tmp_path: Path) -> None:
    import sqlite3

    path = tmp_path / "ancienne.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
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
    with LocalDb(path) as old:
        old.add([AD])
        old.apply_decision(AD.key, "refusee")
        assert old.set_refusal_reason(AD.key, "secteur", "")
