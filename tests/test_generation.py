from pathlib import Path

import pytest

from moteur.base_locale import BaseLocale
from moteur.claude_cli import ErreurClaude, ResultatProcessus
from moteur.config import Chemins
from moteur.generation import (
    RACINE_LATEX,
    Compilateur,
    ajuster_cv,
    avec_contenu,
    contenu_cv,
    extraire_tex,
    generer,
    generer_dossier,
    nom_dossier,
    pages_en_trop,
    preparer_modele,
    versions_reduites,
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


def compilateur(*sorties: str) -> tuple[list[tuple[Path, str]], Compilateur]:
    appels: list[tuple[Path, str]] = []
    restantes = list(sorties)

    def compiler(dossier: Path, fichier: str) -> ResultatProcessus:
        appels.append((dossier, fichier))
        return ResultatProcessus(0, restantes.pop(0) if restantes else "")

    return appels, compiler


@pytest.mark.spec("CV-01")
def test_nom_dossier() -> None:
    assert nom_dossier(Offre("A/B: Corp.", 'Lead "AI" ?')) == "A B Corp. - Lead AI"
    assert nom_dossier(Offre("Libre", "Lead AI", type="spontanee")) == "Libre - spontanée"


@pytest.mark.spec("CV-03")
def test_preparer_modele() -> None:
    prepare = preparer_modele(MODELE, "en")
    assert RACINE_LATEX in prepare
    assert "cv/banque-en" in prepare
    assert "cv/banque-fr" not in prepare


@pytest.mark.spec("CV-13")
def test_extraire_tex_corrige_la_racine_et_refuse_un_fichier_incomplet() -> None:
    assert extraire_tex(TEX).startswith(RACINE_LATEX)
    with pytest.raises(ErreurClaude):
        extraire_tex("Désolé, je ne peux pas.")


@pytest.mark.spec("GEN-01")
def test_pages_en_trop() -> None:
    assert pages_en_trop("ok\n⚠️  cv.pdf fait 2 pages\n") == {"cv": 2}
    assert pages_en_trop("ok") == {}


@pytest.mark.spec("LET-01")
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
    assert appels == [(dossier, "cv.tex")]
    assert len(assistant.prompts) == 1
    assert "\\pRAG" in assistant.prompts[0]
    assert "Texte de l'offre" in assistant.prompts[0]


@pytest.mark.spec("CV-03", "CV-11", "LET-01")
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


CV_COMPLET = r"""\documentclass{x}
\begin{document}
\section{\secExperience} \vspace{0.2cm}
\datedexperience{Eurofins}{\eurofinsDates}
\explanation{\eurofinsPosteIngeIA}
\explanationdetail{%
\pRAG \\
\pGCMS \\
\pAmiante \\
\pDevis \\
\pTerrain \\
\pStagiaires
}

\section{\secProjets} \vspace{0.2cm}
\projMemoire
\projMARL

\section{\secFormation} \vspace{0.2cm}
\formation
\end{document}
"""


@pytest.mark.spec("CV-14")
def test_contenu_cv_dans_l_ordre() -> None:
    puces, projets = contenu_cv(CV_COMPLET)
    assert puces == ["\\pRAG", "\\pGCMS", "\\pAmiante", "\\pDevis", "\\pTerrain", "\\pStagiaires"]
    assert projets == ["\\projMemoire", "\\projMARL"]


@pytest.mark.spec("CV-14")
def test_avec_contenu_reecrit_les_blocs() -> None:
    tex = avec_contenu(CV_COMPLET, ["\\pGCMS", "\\pRAG"], ["\\projMemoire"])
    assert contenu_cv(tex) == (["\\pGCMS", "\\pRAG"], ["\\projMemoire"])
    assert "\\pGCMS \\\\\n\\pRAG\n}" in tex
    assert "\\section{\\secFormation}" in tex


@pytest.mark.spec("CV-14")
def test_versions_reduites_retire_d_abord_le_second_projet() -> None:
    puces = [f"\\p{n}" for n in "ABCDEFG"]
    versions = list(versions_reduites(puces, ["\\projX", "\\projY"]))
    assert versions[0] == (puces, ["\\projX", "\\projY"])
    assert versions[1] == (puces, ["\\projX"])
    assert versions[2] == (puces[:6], ["\\projX"])
    assert versions[-1] == (puces[:5], ["\\projX"])


TROP = "⚠️  cv.pdf fait 2 pages"


@pytest.mark.spec("CV-14")
def test_ajuster_cv_garde_le_maximum_qui_tient(tmp_path: Path) -> None:
    cv = tmp_path / "cv.tex"
    cv.write_text(CV_COMPLET, encoding="utf-8")
    # complet puis sans 2e projet : trop long ; sans pStagiaires : tient ;
    # le 2e projet ne rentre pas, on réécrit la version qui tient.
    appels, compiler = compilateur(TROP, TROP, "", TROP, "")
    assert ajuster_cv(cv, compiler) == 1
    assert len(appels) == 5
    puces, projets = contenu_cv(cv.read_text(encoding="utf-8"))
    assert puces == ["\\pRAG", "\\pGCMS", "\\pAmiante", "\\pDevis", "\\pTerrain"]
    assert projets == ["\\projMemoire"]


@pytest.mark.spec("CV-14")
def test_ajuster_cv_comble_avec_une_puce_plus_courte(tmp_path: Path) -> None:
    huit = [f"\\p{n}" for n in "ABCDEFGH"]
    cv = tmp_path / "cv.tex"
    cv.write_text(avec_contenu(CV_COMPLET, huit, ["\\projX", "\\projY"]), encoding="utf-8")
    # 8+2, 8+1, 7+1, 6+1 : trop long ; 5+1 tient. pG rentre, pH et projY non.
    appels, compiler = compilateur(TROP, TROP, TROP, TROP, "", "", TROP, TROP, "")
    assert ajuster_cv(cv, compiler) == 1
    assert len(appels) == 9
    assert contenu_cv(cv.read_text(encoding="utf-8")) == ([*huit[:5], "\\pG"], ["\\projX"])


@pytest.mark.spec("CV-15")
def test_ajuster_cv_signale_un_cv_qui_deborde_encore(tmp_path: Path) -> None:
    cv = tmp_path / "cv.tex"
    cv.write_text(CV_COMPLET, encoding="utf-8")
    _, compiler = compilateur(*[TROP] * 10)
    assert ajuster_cv(cv, compiler) == 2
    assert len(contenu_cv(cv.read_text(encoding="utf-8"))[0]) == 5


@pytest.mark.spec("CV-10")
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


@pytest.mark.spec("BASE-09", "GEN-02")
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


@pytest.mark.spec("GEN-01")
def test_echec_de_compilation(chemins: Chemins) -> None:
    def en_echec(dossier: Path, fichier: str) -> ResultatProcessus:
        return ResultatProcessus(1, "", "Undefined control sequence")

    with BaseLocale(":memory:") as base:
        base.ajouter([OFFRE])
        base.enregistrer_note(OFFRE.cle, Note(80, "", False, "fr"))
        base.appliquer_decision(OFFRE.cle, "acceptee")
        reussites, echecs = generer(base, FauxAssistant(TEX), chemins, "sonnet", en_echec)
    assert reussites == 0
    assert "Undefined control sequence" in echecs[0]
