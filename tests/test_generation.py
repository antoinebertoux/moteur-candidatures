from pathlib import Path

import pytest

from moteur.claude_cli import ClaudeError, ProcessResult
from moteur.config import Paths
from moteur.generation import (
    LATEX_ROOT,
    Compiler,
    cv_contents,
    cv_pdf_name,
    extra_pages,
    extract_tex,
    fit_cv,
    folder_name,
    generate,
    generate_folder,
    prepare_template,
    reduced_versions,
    with_content,
)
from moteur.local_db import LocalDb
from moteur.models import Application, JobAd, Rating
from tests.conftest import FakeAssistant

TEMPLATE = "\\def\\latexroot{../}\n\\documentclass{moncv}\n\\input{\\latexroot cv/banque-fr}\n"
TEX = "```latex\n\\def\\latexroot{../}\n\\documentclass{x}\n\\begin{document}\\end{document}\n```"
AD = JobAd("Acme", "Data Scientist", url="https://a", description="Texte de l'offre")


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    latex = tmp_path / "latex"
    (latex / "cv").mkdir(parents=True)
    (latex / "lettres").mkdir()
    (latex / "cv" / "modele-cv.tex").write_text(TEMPLATE, encoding="utf-8")
    (latex / "cv" / "banque-fr.tex").write_text("\\newcommand{\\pRAG}{RAG}", encoding="utf-8")
    (latex / "cv" / "banque-en.tex").write_text("\\newcommand{\\pRAG}{RAG en}", encoding="utf-8")
    (latex / "lettres" / "modele-lettre.tex").write_text(TEMPLATE, encoding="utf-8")
    (latex / "lettres" / "banque-paragraphes.md").write_text("Paragraphe.", encoding="utf-8")
    return Paths(root=tmp_path, base=tmp_path / "b.sqlite3", exchange=tmp_path / "echange")


def compile_fn(*outputs: str) -> tuple[list[tuple[Path, str]], Compiler]:
    calls: list[tuple[Path, str]] = []
    remaining = list(outputs)

    def compiler(folder: Path, file: str) -> ProcessResult:
        calls.append((folder, file))
        return ProcessResult(0, remaining.pop(0) if remaining else "")

    return calls, compiler


@pytest.mark.spec("CV-01")
def test_folder_name() -> None:
    assert folder_name(JobAd("A/B: Corp.", 'Lead "AI" ?')) == "A B Corp. - Lead AI"
    assert folder_name(JobAd("Libre", "Lead AI", type="spontanee")) == "Libre - spontanée"


@pytest.mark.spec("CV-03")
def test_prepare_template() -> None:
    prepare = prepare_template(TEMPLATE, "en")
    assert LATEX_ROOT in prepare
    assert "cv/banque-en" in prepare
    assert "cv/banque-fr" not in prepare


@pytest.mark.spec("CV-13")
def test_extract_tex_fixes_root_and_rejects_incomplete_file() -> None:
    assert extract_tex(TEX).startswith(LATEX_ROOT)
    with pytest.raises(ClaudeError):
        extract_tex("Désolé, je ne peux pas.")


@pytest.mark.spec("GEN-01")
def test_extra_pages() -> None:
    assert extra_pages("ok\n⚠️  cv.pdf fait 2 pages\n") == {"cv": 2}
    assert extra_pages("ok") == {}


@pytest.mark.spec("LET-01")
def test_folder_without_letter(paths: Paths) -> None:
    assistant = FakeAssistant(TEX)
    calls, compiler = compile_fn()
    application = Application(AD, "acceptee", summary="Bon poste.")
    cv_ref, letter_ref = generate_folder(application, assistant, paths, "sonnet", compiler)
    folder = paths.applications / "Acme - Data Scientist"
    assert (cv_ref, letter_ref) == ("Candidatures/Acme - Data Scientist/cv.pdf", "")
    assert (folder / "cv.tex").read_text(encoding="utf-8").startswith(LATEX_ROOT)
    assert not (folder / "lettre.tex").exists()
    assert "https://a" in (folder / "offre.md").read_text(encoding="utf-8")
    assert calls == [(folder, "cv.tex")]
    assert len(assistant.prompts) == 1
    assert "\\pRAG" in assistant.prompts[0]
    assert "Texte de l'offre" in assistant.prompts[0]


@pytest.mark.spec("CV-03", "CV-11", "LET-01")
def test_unsolicited_in_english_with_letter(paths: Paths) -> None:
    assistant = FakeAssistant(TEX)
    _, compiler = compile_fn()
    application = Application(
        JobAd("Libre", "Lead AI", type="spontanee"), "acceptee", language="en"
    )
    cv_ref, letter_ref = generate_folder(application, assistant, paths, "sonnet", compiler)
    assert letter_ref == "Candidatures/Libre - spontanée/lettre.pdf"
    assert cv_ref.endswith("cv.pdf")
    cv_prompt, letter_prompt = assistant.prompts
    assert "RAG en" in cv_prompt
    assert "cv/banque-en" in cv_prompt
    assert "Paragraphe." in letter_prompt
    assert "anglais" in letter_prompt


FULL_CV = r"""\documentclass{x}
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
def test_cv_contents_in_order() -> None:
    bullets, projects = cv_contents(FULL_CV)
    assert bullets == ["\\pRAG", "\\pGCMS", "\\pAmiante", "\\pDevis", "\\pTerrain", "\\pStagiaires"]
    assert projects == ["\\projMemoire", "\\projMARL"]


@pytest.mark.spec("CV-14")
def test_avec_contenu_reecrit_les_blocs() -> None:
    tex = with_content(FULL_CV, ["\\pGCMS", "\\pRAG"], ["\\projMemoire"])
    assert cv_contents(tex) == (["\\pGCMS", "\\pRAG"], ["\\projMemoire"])
    assert "\\pGCMS \\\\\n\\pRAG\n}" in tex
    assert "\\section{\\secFormation}" in tex


@pytest.mark.spec("CV-14")
def test_reduced_versions_drop_the_second_project_first() -> None:
    bullets = [f"\\p{n}" for n in "ABCDEFG"]
    versions = list(reduced_versions(bullets, ["\\projX", "\\projY"]))
    assert versions[0] == (bullets, ["\\projX", "\\projY"])
    assert versions[1] == (bullets, ["\\projX"])
    assert versions[2] == (bullets[:6], ["\\projX"])
    assert versions[-1] == (bullets[:5], ["\\projX"])


TOO_MANY = "⚠️  cv.pdf fait 2 pages"


@pytest.mark.spec("CV-14")
def test_ajuster_cv_garde_le_maximum_qui_tient(tmp_path: Path) -> None:
    cv = tmp_path / "cv.tex"
    cv.write_text(FULL_CV, encoding="utf-8")
    # full, then without the 2nd project: too long; without pStagiaires: fits;
    # the 2nd project does not fit, the version that fits is written again.
    calls, compiler = compile_fn(TOO_MANY, TOO_MANY, "", TOO_MANY, "")
    assert fit_cv(cv, compiler) == 1
    assert len(calls) == 5
    bullets, projects = cv_contents(cv.read_text(encoding="utf-8"))
    assert bullets == ["\\pRAG", "\\pGCMS", "\\pAmiante", "\\pDevis", "\\pTerrain"]
    assert projects == ["\\projMemoire"]


@pytest.mark.spec("CV-14")
def test_ajuster_cv_comble_avec_une_puce_plus_courte(tmp_path: Path) -> None:
    eight = [f"\\p{n}" for n in "ABCDEFGH"]
    cv = tmp_path / "cv.tex"
    cv.write_text(with_content(FULL_CV, eight, ["\\projX", "\\projY"]), encoding="utf-8")
    # 8+2, 8+1, 7+1, 6+1: too long; 5+1 fits. pG fits, pH and projY do not.
    calls, compiler = compile_fn(
        TOO_MANY, TOO_MANY, TOO_MANY, TOO_MANY, "", "", TOO_MANY, TOO_MANY, ""
    )
    assert fit_cv(cv, compiler) == 1
    assert len(calls) == 9
    assert cv_contents(cv.read_text(encoding="utf-8")) == ([*eight[:5], "\\pG"], ["\\projX"])


@pytest.mark.spec("CV-15")
def test_ajuster_cv_signale_un_cv_qui_deborde_encore(tmp_path: Path) -> None:
    cv = tmp_path / "cv.tex"
    cv.write_text(FULL_CV, encoding="utf-8")
    _, compiler = compile_fn(*[TOO_MANY] * 10)
    assert fit_cv(cv, compiler) == 2
    assert len(cv_contents(cv.read_text(encoding="utf-8"))[0]) == 5


@pytest.mark.spec("CV-10")
def test_edit_starts_from_existing_cv(paths: Paths) -> None:
    folder = paths.applications / "Acme - Data Scientist"
    folder.mkdir(parents=True)
    (folder / "cv.tex").write_text("% version précédente", encoding="utf-8")
    assistant = FakeAssistant(TEX)
    _, compiler = compile_fn()
    application = Application(AD, "acceptee", instruction="Mets le RAG en premier")
    generate_folder(application, assistant, paths, "sonnet", compiler)
    assert "% version précédente" in assistant.prompts[0]
    assert "Mets le RAG en premier" in assistant.prompts[0]


@pytest.mark.spec("BASE-09", "GEN-02")
def test_generate_marks_successes_and_lists_failures(paths: Paths) -> None:
    other = JobAd("Bolt", "AI Engineer")
    assistant = FakeAssistant(TEX, "Désolé.")
    _, compiler = compile_fn()
    with LocalDb(":memory:") as base:
        base.add([AD, other])
        for ad in (AD, other):
            base.record_score(ad.key, Rating(80, "", False, "fr"))
            base.apply_decision(ad.key, "acceptee")
        successes, failures = generate(base, assistant, paths, "sonnet", compiler)
        assert successes == 1
        assert len(failures) == 1
        assert failures[0].startswith("Bolt")
        assert [c.ad for c in base.to_generate()] == [other]
        assert [c.cv_ref for c in base.for_the_page()] == [
            "Candidatures/Acme - Data Scientist/cv.pdf"
        ]


@pytest.mark.spec("GEN-01")
def test_compilation_failure(paths: Paths) -> None:
    def failing(folder: Path, file: str) -> ProcessResult:
        return ProcessResult(1, "", "Undefined control sequence")

    with LocalDb(":memory:") as base:
        base.add([AD])
        base.record_score(AD.key, Rating(80, "", False, "fr"))
        base.apply_decision(AD.key, "acceptee")
        successes, failures = generate(base, FakeAssistant(TEX), paths, "sonnet", failing)
    assert successes == 0
    assert "Undefined control sequence" in failures[0]


def _details(paths: Paths, text: str) -> None:
    (paths.latex / "commun").mkdir(exist_ok=True)
    (paths.latex / "commun" / "coordonnees.tex").write_text(text, encoding="utf-8")


@pytest.mark.spec("CV-16")
def test_cv_pdf_name_from_contact_details(paths: Paths) -> None:
    assert cv_pdf_name(paths.latex) == "cv.pdf"
    _details(paths, "\\newcommand{\\coPrenom}{Jane}\n\\newcommand{\\coNom}{Doe}\n")
    assert cv_pdf_name(paths.latex) == "cv_Jane_Doe.pdf"
    _details(paths, "\\newcommand{\\coPrenom}{Jean Marc}\n\\newcommand{\\coNom}{L/X}\n")
    assert cv_pdf_name(paths.latex) == "cv_Jean-Marc_L-X.pdf"
    _details(paths, "\\newcommand{\\coPrenom}{Jane}\n")
    assert cv_pdf_name(paths.latex) == "cv.pdf"


@pytest.mark.spec("CV-16", "GEN-02")
def test_compiled_cv_is_renamed(paths: Paths) -> None:
    _details(paths, "\\newcommand{\\coPrenom}{Jane}\n\\newcommand{\\coNom}{Doe}\n")
    folder = paths.applications / "Acme - Data Scientist"

    def compiler(folder: Path, file: str) -> ProcessResult:
        (folder / file).with_suffix(".pdf").write_bytes(b"%PDF")
        return ProcessResult(0, "")

    application = Application(AD, "acceptee")
    cv_ref, _ = generate_folder(application, FakeAssistant(TEX), paths, "sonnet", compiler)
    assert cv_ref == "Candidatures/Acme - Data Scientist/cv_Jane_Doe.pdf"
    assert (folder / "cv_Jane_Doe.pdf").exists()
    assert not (folder / "cv.pdf").exists()
    assert (folder / "cv.tex").exists()
