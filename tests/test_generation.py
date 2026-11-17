from pathlib import Path

import pytest

from moteur.base_locale import BaseLocale
from moteur.claude_cli import ErreurClaude, ResultatProcessus
from moteur.config import Chemins
from moteur.generation import (
    RACINE_LATEX,
    Compilateur,
    extraire_tex,
    generer,
    generer_dossier,
    nom_dossier,
    pages_en_trop,
    preparer_modele,
)
from moteur.modeles import Candidature, Note, Offre
from tests.conftest import FauxAssistant

MODELE = "\\def\\latexroot{../}\n\\documentclass{moncv}\n\\input{\\latexroot cv/banque-fr}\n"
TEX = "```latex\n\\def\\latexroot{../}\n\\documentclass{x}\n\\begin{document}\\end{document}\n```"
OFFRE = Offre("Acme", "Data Scientist", url="https://a", description="Texte de l'offre")


@pytest.fixture
def chemins(tmp_path: Path) -> Chemins:
    latex = tmp_path / "latex"
    (latex / "cv").mkdir(parents=True)
    (latex / "lettres").mkdir()
    (latex / "cv" / "modele-cv.tex").write_text(MODELE, encoding="utf-8")
    (latex / "cv" / "banque-fr.tex").write_text("\\newcommand{\\pRAG}{RAG}", encoding="utf-8")
    (latex / "cv" / "banque-en.tex").write_text("\\newcommand{\\pRAG}{RAG en}", encoding="utf-8")
    (latex / "lettres" / "modele-lettre.tex").write_text(MODELE, encoding="utf-8")
    (latex / "lettres" / "banque-paragraphes.md").write_text("Paragraphe.", encoding="utf-8")
    return Chemins(racine=tmp_path, base=tmp_path / "b.sqlite3", echange=tmp_path / "echange")


def compilateur(*sorties: str) -> tuple[list[Path], Compilateur]:
    appels: list[Path] = []
    restantes = list(sorties)

    def compiler(dossier: Path) -> ResultatProcessus:
        appels.append(dossier)
        return ResultatProcessus(0, restantes.pop(0) if restantes else "")

    return appels, compiler


def test_nom_dossier() -> None:
    assert nom_dossier(Offre("A/B: Corp.", 'Lead "AI" ?')) == "A B Corp. - Lead AI"
    assert nom_dossier(Offre("Libre", "Lead AI", type="spontanee")) == "Libre - spontanée"


def test_preparer_modele() -> None:
    prepare = preparer_modele(MODELE, "en")
    assert RACINE_LATEX in prepare
    assert "cv/banque-en" in prepare
    assert "cv/banque-fr" not in prepare


def test_extraire_tex_corrige_la_racine_et_refuse_un_fichier_incomplet() -> None:
    assert extraire_tex(TEX).startswith(RACINE_LATEX)
    with pytest.raises(ErreurClaude):
        extraire_tex("Désolé, je ne peux pas.")


def test_pages_en_trop() -> None:
    assert pages_en_trop("ok\n⚠️  cv.pdf fait 2 pages\n") == {"cv": 2}
    assert pages_en_trop("ok") == {}


def test_dossier_sans_lettre(chemins: Chemins) -> None:
    assistant = FauxAssistant(TEX)
    appels, compiler = compilateur()
    candidature = Candidature(OFFRE, "acceptee", resume="Bon poste.")
    cv_ref, lettre_ref = generer_dossier(candidature, assistant, chemins, "sonnet", compiler)
    dossier = chemins.candidatures / "Acme - Data Scientist"
    assert (cv_ref, lettre_ref) == ("Candidatures/Acme - Data Scientist/cv.pdf", "")
    assert (dossier / "cv.tex").read_text(encoding="utf-8").startswith(RACINE_LATEX)
    assert not (dossier / "lettre.tex").exists()
    assert "https://a" in (dossier / "offre.md").read_text(encoding="utf-8")
    assert appels == [dossier]
    assert len(assistant.prompts) == 1
    assert "\\pRAG" in assistant.prompts[0]
    assert "Texte de l'offre" in assistant.prompts[0]


def test_spontanee_en_anglais_avec_lettre(chemins: Chemins) -> None:
    assistant = FauxAssistant(TEX)
    _, compiler = compilateur()
    candidature = Candidature(Offre("Libre", "Lead AI", type="spontanee"), "acceptee", langue="en")
    cv_ref, lettre_ref = generer_dossier(candidature, assistant, chemins, "sonnet", compiler)
    assert lettre_ref == "Candidatures/Libre - spontanée/lettre.pdf"
    assert cv_ref.endswith("cv.pdf")
    cv_prompt, lettre_prompt = assistant.prompts
    assert "RAG en" in cv_prompt
    assert "cv/banque-en" in cv_prompt
    assert "Paragraphe." in lettre_prompt
    assert "anglais" in lettre_prompt


def test_cv_trop_long_est_redemande_une_fois(chemins: Chemins) -> None:
    assistant = FauxAssistant(TEX)
    appels, compiler = compilateur("⚠️  cv.pdf fait 2 pages", "")
    generer_dossier(Candidature(OFFRE, "acceptee"), assistant, chemins, "sonnet", compiler)
    assert len(appels) == 2
    assert len(assistant.prompts) == 2
    assert "2 pages" in assistant.prompts[1]


def test_retouche_repart_du_cv_existant(chemins: Chemins) -> None:
    dossier = chemins.candidatures / "Acme - Data Scientist"
    dossier.mkdir(parents=True)
    (dossier / "cv.tex").write_text("% version précédente", encoding="utf-8")
    assistant = FauxAssistant(TEX)
    _, compiler = compilateur()
    candidature = Candidature(OFFRE, "acceptee", consigne="Mets le RAG en premier")
    generer_dossier(candidature, assistant, chemins, "sonnet", compiler)
    assert "% version précédente" in assistant.prompts[0]
    assert "Mets le RAG en premier" in assistant.prompts[0]


def test_generer_marque_les_reussites_et_liste_les_echecs(chemins: Chemins) -> None:
    autre = Offre("Bolt", "AI Engineer")
    assistant = FauxAssistant(TEX, "Désolé.")
    _, compiler = compilateur()
    with BaseLocale(":memory:") as base:
        base.ajouter([OFFRE, autre])
        for offre in (OFFRE, autre):
            base.enregistrer_note(offre.cle, Note(80, "", False, "fr"))
            base.appliquer_decision(offre.cle, "acceptee")
        reussites, echecs = generer(base, assistant, chemins, "sonnet", compiler)
        assert reussites == 1
        assert len(echecs) == 1
        assert echecs[0].startswith("Bolt")
        assert [c.offre for c in base.a_generer()] == [autre]
        assert [c.cv_ref for c in base.pour_la_page()] == [
            "Candidatures/Acme - Data Scientist/cv.pdf"
        ]


def test_echec_de_compilation(chemins: Chemins) -> None:
    def en_echec(dossier: Path) -> ResultatProcessus:
        return ResultatProcessus(1, "", "Undefined control sequence")

    with BaseLocale(":memory:") as base:
        base.ajouter([OFFRE])
        base.enregistrer_note(OFFRE.cle, Note(80, "", False, "fr"))
        base.appliquer_decision(OFFRE.cle, "acceptee")
        reussites, echecs = generer(base, FauxAssistant(TEX), chemins, "sonnet", en_echec)
    assert reussites == 0
    assert "Undefined control sequence" in echecs[0]
