import json
import os
from pathlib import Path

import pytest

from moteur.echange import Decision, ErreurEchange, lire_decisions, pour_la_page, serialiser
from moteur.modeles import Candidature, Offre


def test_format_lu_par_la_page() -> None:
    notee = Candidature(Offre("Acme", "Data Scientist", url="https://a"), "notee", score=80)
    generee = Candidature(
        Offre("Libre", "Lead AI", type="spontanee"),
        "generee",
        lettre_demandee=True,
        cv_ref="Candidatures/Libre/cv.pdf",
        lettre_ref="Candidatures/Libre/lettre.pdf",
    )
    premiere, seconde = pour_la_page([notee, generee])
    assert premiere == {
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
    assert "id" not in premiere
    assert "score" not in seconde
    assert seconde["cv_ref"] == "Candidatures/Libre/cv.pdf"
    assert json.loads(serialiser([notee])) == [premiere]


def test_lire_decisions() -> None:
    export = {
        "exporte_le": "2026-11-16",
        "candidatures": [
            {"id": "offre_acme_data-scientist", "statut": "acceptee", "consigne": "Plus court"},
            {"id": "offre_bolt_ai-engineer", "statut": "refusee", "consigne": None},
            {"statut": "acceptee"},
            "bruit",
        ],
    }
    assert lire_decisions(json.dumps(export)) == [
        Decision("offre_acme_data-scientist", "acceptee", "Plus court"),
        Decision("offre_bolt_ai-engineer", "refusee"),
    ]
    assert lire_decisions("[]") == []


@pytest.mark.parametrize("texte", ["pas du json", '{"autre": 1}', '"chaine"'])
def test_export_illisible(texte: str) -> None:
    with pytest.raises(ErreurEchange):
        lire_decisions(texte)


def test_lire_decisions_avec_l_offre() -> None:
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
    (decision,) = lire_decisions(json.dumps(export))
    assert decision.offre == Offre(
        "AXA",
        "Ingénieur IA",
        lieu="Paris",
        url="https://www.linkedin.com/jobs/view/1/",
        source="linkedin",
        description="Missions : ...",
    )
    assert decision.lettre_demandee


def test_date_de_generation_du_cv(tmp_path: Path) -> None:
    cv = tmp_path / "Candidatures" / "Libre" / "cv.pdf"
    cv.parent.mkdir(parents=True)
    cv.write_bytes(b"%PDF")
    os.utime(cv, (0, 1_700_000_000.5))
    generee = Candidature(Offre("Libre", "Lead AI"), "generee", cv_ref="Candidatures/Libre/cv.pdf")
    (ligne,) = pour_la_page([generee], tmp_path)
    assert ligne["genere_le"] == "2023-11-14T22:13:20.500Z"
    (sans_fichier,) = pour_la_page([generee], tmp_path / "ailleurs")
    assert "genere_le" not in sans_fichier
