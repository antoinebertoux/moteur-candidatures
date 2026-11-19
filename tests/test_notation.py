import json

import pytest

from moteur.base_locale import BaseLocale
from moteur.claude_cli import ErreurClaude
from moteur.modeles import Note, Offre
from moteur.notation import (
    LONGUEUR_DESCRIPTION,
    analyser_reponse,
    construire_prompt,
    noter,
    systeme,
)
from tests.conftest import FauxAssistant

A = Offre("Acme", "Data Scientist", description="x" * 5000)
B = Offre("Bolt", "AI Engineer")


def reponse(*entrees: dict[str, object]) -> str:
    return json.dumps(list(entrees))


@pytest.mark.spec("NOT-03")
def test_prompt_tronque_la_description_et_porte_la_cle() -> None:
    (entree,) = json.loads(construire_prompt([A]))
    assert entree["cle"] == A.cle
    assert len(entree["description"]) == LONGUEUR_DESCRIPTION


@pytest.mark.spec("NOT-04")
def test_systeme_contient_le_profil() -> None:
    assert systeme("Vise un poste de Lead AI").endswith("Vise un poste de Lead AI")


@pytest.mark.spec("NOT-06")
def test_analyser_reponse_borne_et_filtre() -> None:
    texte = reponse(
        {"cle": A.cle, "score": 140, "resume": "Bien.", "lettre_demandee": True, "langue": "en"},
        {"cle": B.cle, "score": 61.4},
        {"cle": "inconnue", "score": 50},
        {"cle": A.cle + "x", "score": True},
    )
    notes = analyser_reponse(texte, {A.cle, B.cle})
    assert notes == {
        A.cle: Note(100, "Bien.", True, "en"),
        B.cle: Note(61, "", False, "fr"),
    }


@pytest.mark.spec("NOT-06")
def test_analyser_reponse_refuse_autre_chose_qu_un_tableau() -> None:
    with pytest.raises(ErreurClaude):
        analyser_reponse('{"cle": "a"}', {"a"})


@pytest.mark.spec("NOT-01", "NOT-02")
def test_noter_par_lots_et_garde_les_echecs_en_attente() -> None:
    assistant = FauxAssistant(reponse({"cle": A.cle, "score": 70}), "illisible")
    with BaseLocale(":memory:") as base:
        base.ajouter([A, B])
        notees = noter(base, assistant, profil="p", modele="haiku", taille_lot=1)
        assert notees == 1
        assert base.a_noter() == [B]
        assert [c.score for c in base.pour_la_page()] == [70]
    assert assistant.modeles == ["haiku", "haiku"]


@pytest.mark.spec("NOT-04", "NOT-08")
def test_system_prompt_lists_past_refusals() -> None:
    from moteur.refusal import Refusal

    assert "refusées" not in systeme("profil")
    texte = systeme(
        "profil",
        [Refusal("Capgemini", "Data Scientist", "conseil", "ESN"), Refusal("X", "Y", "lieu")],
    )
    assert "profil" in texte
    assert "- Capgemini — Data Scientist : Conseil / ESN (ESN)" in texte
    assert "- X — Y : Lieu / télétravail" in texte


@pytest.mark.spec("NOT-08")
def test_scoring_sends_the_refusals_from_the_database() -> None:
    from moteur.base_locale import BaseLocale
    from tests.conftest import FauxAssistant

    systems: list[str] = []

    class Spy(FauxAssistant):
        def demander(self, prompt: str, *, systeme: str, modele: str) -> str:
            systems.append(systeme)
            return super().demander(prompt, systeme=systeme, modele=modele)

    with BaseLocale(":memory:") as base:
        refusee, nouvelle = Offre("Sopra", "Data Scientist"), Offre("Acme", "Lead AI")
        base.ajouter([refusee, nouvelle])
        base.appliquer_decision(refusee.cle, "refusee")
        base.set_refusal_reason(refusee.cle, "conseil", "")
        assistant = Spy("[]")
        noter(base, assistant, profil="p", modele="haiku", taille_lot=8)
        assert "Sopra — Data Scientist : Conseil / ESN" in systems[0]
