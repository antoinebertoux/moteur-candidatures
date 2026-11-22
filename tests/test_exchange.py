import json
import os
from pathlib import Path

import pytest

from moteur.exchange import Decision, ExchangeError, for_the_page, read_decisions, serialise
from moteur.models import Application, JobAd


@pytest.mark.spec("ECH-01")
def test_format_read_by_the_page() -> None:
    scored = Application(JobAd("Acme", "Data Scientist", url="https://a"), "notee", score=80)
    generated = Application(
        JobAd("Libre", "Lead AI", type="spontanee"),
        "generee",
        letter_requested=True,
        cv_ref="Candidatures/Libre/cv.pdf",
        letter_ref="Candidatures/Libre/lettre.pdf",
    )
    first_one, second_one = for_the_page([scored, generated])
    assert first_one == {
        "type": "offre",
        "entreprise": "Acme",
        "poste": "Data Scientist",
        "lieu": "",
        "url": "https://a",
        "source": "",
        "moteur": "B",
        "resume": "",
        "lettre_demandee": False,
        "score": 80,
    }
    assert "id" not in first_one
    assert "score" not in second_one
    assert second_one["cv_ref"] == "Candidatures/Libre/cv.pdf"
    assert json.loads(serialise([scored])) == [first_one]


@pytest.mark.spec("ECH-10")
def test_read_decisions() -> None:
    export = {
        "exporte_le": "2026-11-16",
        "candidatures": [
            {"id": "offre_acme_data-scientist", "statut": "acceptee", "consigne": "Plus court"},
            {"id": "offre_bolt_ai-engineer", "statut": "refusee", "consigne": None},
            {"statut": "acceptee"},
            "bruit",
        ],
    }
    assert read_decisions(json.dumps(export)) == [
        Decision("offre_acme_data-scientist", "acceptee", "Plus court"),
        Decision("offre_bolt_ai-engineer", "refusee"),
    ]
    assert read_decisions("[]") == []


@pytest.mark.spec("ECH-10")
@pytest.mark.parametrize("text", ["pas du json", '{"autre": 1}', '"chaine"'])
def test_unreadable_export(text: str) -> None:
    with pytest.raises(ExchangeError):
        read_decisions(text)


@pytest.mark.spec("ECH-11")
def test_read_decisions_with_the_ad() -> None:
    export = [
        {
            "id": "offre_axa_ingenieur-ia",
            "statut": "acceptee",
            "type": "offre",
            "entreprise": "AXA",
            "poste": "Ingénieur IA",
            "lieu": "Paris",
            "url": "https://www.linkedin.com/jobs/view/1/",
            "source": "linkedin",
            "texte_offre": "  Missions : ...  ",
            "lettre_demandee": True,
        }
    ]
    (decision,) = read_decisions(json.dumps(export))
    assert decision.ad == JobAd(
        "AXA",
        "Ingénieur IA",
        location="Paris",
        url="https://www.linkedin.com/jobs/view/1/",
        source="linkedin",
        description="Missions : ...",
    )
    assert decision.letter_requested


@pytest.mark.spec("ECH-02")
def test_cv_generation_date(tmp_path: Path) -> None:
    cv = tmp_path / "Candidatures" / "Libre" / "cv.pdf"
    cv.parent.mkdir(parents=True)
    cv.write_bytes(b"%PDF")
    os.utime(cv, (0, 1_700_000_000.5))
    generated = Application(
        JobAd("Libre", "Lead AI"), "generee", cv_ref="Candidatures/Libre/cv.pdf"
    )
    (row,) = for_the_page([generated], tmp_path)
    assert row["genere_le"] == "2023-11-14T22:13:20.500Z"
    (without_file,) = for_the_page([generated], tmp_path / "ailleurs")
    assert "genere_le" not in without_file


@pytest.mark.spec("ECH-11", "BASE-11")
def test_refusal_reason_is_read_from_the_page() -> None:
    export = [
        {"id": "a", "statut": "refusee", "motif_refus": "salaire", "motif_detail": " 45 K€ "},
        {"id": "b", "statut": "refusee", "motif_refus": "inconnu", "motif_detail": "x" * 300},
        {"id": "c", "statut": "refusee"},
    ]
    a, b, c = read_decisions(json.dumps(export))
    assert (a.refusal_reason, a.reason_detail) == ("salaire", "45 K€")
    assert (b.refusal_reason, len(b.reason_detail)) == ("autre", 200)
    assert (c.refusal_reason, c.reason_detail) == ("", "")


@pytest.mark.spec("ECH-05")
def test_ad_text_sent_with_folders_and_sheets_only() -> None:
    long_text = "x" * 25_000
    scored = Application(JobAd("Acme", "Data Scientist", description="Texte"), "notee")
    generated = Application(
        JobAd("Orano", "Lead AI", description=long_text), "generee", cv_ref="c/cv.pdf"
    )
    sheet = Application(
        JobAd("Ilo", "Head of AI", description="Offre"), "close", preparation="# Fiche"
    )
    first_one, second_one, third_one = for_the_page([scored, generated, sheet])
    assert "texte_offre" not in first_one
    assert second_one["texte_offre"] == "x" * 20_000
    assert third_one["texte_offre"] == "Offre"


@pytest.mark.spec("ECH-06")
def test_applied_ones_sent_for_their_text_only() -> None:
    applied = Application(JobAd("Ilo", "Head of AI", url="https://i", description="Offre"), "close")
    without_text = Application(JobAd("Zed", "Lead AI"), "close")
    (row,) = for_the_page([], archived=[applied, without_text])
    assert row == {
        "type": "offre",
        "entreprise": "Ilo",
        "poste": "Head of AI",
        "moteur": "B",
        "texte_offre": "Offre",
        "archive": True,
    }
    assert json.loads(serialise([], archived=[applied])) == [row]
