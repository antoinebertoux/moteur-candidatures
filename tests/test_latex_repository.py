"""The `latex/` folder: example shipped, required files, personal instructions."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from moteur.config import Paths
from moteur.cover_letter import generate_letters
from moteur.generation import (
    CV_ANSWER,
    CV_SYSTEM,
    LATEX_ROOT,
    LETTER_SYSTEM,
    cv_contents,
    cv_pdf_name,
    extra_pages,
    fit_cv,
    generate,
    generate_folder,
    prepare_template,
    system_prompt,
)
from moteur.latex_repository import (
    EXAMPLE,
    REQUIRED_FILES,
    LatexRepositoryError,
    check,
    init_latex,
    missing_files,
)
from moteur.local_db import LocalDb
from moteur.models import Application, JobAd, Rating
from tests.conftest import FakeAssistant
from tests.test_generation import TEX, compile_fn, paths  # noqa: F401  (shared fixture)

AD = JobAd("Acme", "Data Scientist", url="https://a")
_MACRO = re.compile(r"\\newcommand\{\\(\w+)\}")


def _text(name: str) -> str:
    return (EXAMPLE / name).read_text(encoding="utf-8")


def _accepted(base: LocalDb, *ads: tuple[JobAd, str]) -> None:
    base.add([ad for ad, _ in ads])
    for ad, language in ads:
        base.record_score(ad.key, Rating(80, "", False, language))  # type: ignore[arg-type]
        base.apply_decision(ad.key, "acceptee")


@pytest.mark.spec("LTX-01")
def test_example_is_complete_and_fictional() -> None:
    assert missing_files(EXAMPLE) == []
    for name in (
        "cv/banque-fr.tex",
        "cv/banque-en.tex",
        "cv/jobcv.cls",
        "lettres/lettre.cls",
        "consignes-cv.md",
        "consignes-lettre.md",
    ):
        assert (EXAMPLE / name).is_file(), name
    details = _text("commun/coordonnees.tex")
    assert "\\newcommand{\\coPrenom}{Jane}" in details
    assert "example.com" in details


@pytest.mark.spec("LTX-02", "LTX-13", "LTX-15")
def test_engine_reads_the_example() -> None:
    bullets, projects = cv_contents(_text("cv/modele-cv.tex"))
    assert len(bullets) == 8
    assert projects == ["\\projMemoire", "\\projKaggle"]
    assert cv_pdf_name(EXAMPLE) == "cv_Jane_Doe.pdf"


@pytest.mark.spec("LTX-02")
def test_example_banks_define_every_block_in_both_languages() -> None:
    french = set(_MACRO.findall(_text("cv/banque-fr.tex")))
    english = set(_MACRO.findall(_text("cv/banque-en.tex")))
    assert french == english
    used = set(re.findall(r"\\((?:p|proj|comp|extra)[A-Z]\w*)", _text("cv/modele-cv.tex")))
    assert used <= french


@pytest.mark.spec("LTX-03")
def test_init_latex_copies_the_example(tmp_path: Path) -> None:
    target = tmp_path / "latex"
    to_adapt = init_latex(target)
    assert missing_files(target) == []
    assert "commun/coordonnees.tex" in to_adapt
    assert "consignes-cv.md" in to_adapt
    assert os.access(target / "compiler.sh", os.X_OK)


@pytest.mark.spec("LTX-03")
def test_init_latex_refuses_an_existing_folder(tmp_path: Path) -> None:
    target = tmp_path / "latex"
    target.mkdir()
    (target / "mine.tex").write_text("mine", encoding="utf-8")
    with pytest.raises(LatexRepositoryError, match="already exists"):
        init_latex(target)
    assert [p.name for p in target.iterdir()] == ["mine.tex"]


@pytest.mark.spec("LTX-10")
def test_check_lists_missing_files(tmp_path: Path) -> None:
    (tmp_path / "cv").mkdir()
    (tmp_path / "cv" / "modele-cv.tex").write_text("x", encoding="utf-8")
    assert missing_files(tmp_path) == [f for f in REQUIRED_FILES if f != "cv/modele-cv.tex"]
    with pytest.raises(LatexRepositoryError, match="moteur init-latex") as error:
        check(tmp_path)
    assert "compiler.sh" in str(error.value)


@pytest.mark.spec("LTX-10")
def test_generate_stops_before_any_folder(paths: Paths) -> None:  # noqa: F811
    (paths.latex / "compiler.sh").unlink()
    with LocalDb(":memory:") as base:
        _accepted(base, (AD, "fr"))
        assistant = FakeAssistant(TEX)
        with pytest.raises(LatexRepositoryError, match=r"compiler\.sh"):
            generate(base, assistant, paths, "sonnet", compile_fn()[1])
        with pytest.raises(LatexRepositoryError):
            generate_letters(base, assistant, paths, "sonnet", compile_fn()[1], [AD.key])
        assert assistant.prompts == []
        assert not paths.applications.exists()
        assert [c.ad for c in base.to_generate()] == [AD]


@pytest.mark.spec("LTX-10")
def test_missing_bank_fails_only_that_language(paths: Paths) -> None:  # noqa: F811
    (paths.latex / "cv" / "banque-en.tex").unlink()
    english = JobAd("Bolt", "AI Engineer")
    with LocalDb(":memory:") as base:
        _accepted(base, (AD, "fr"), (english, "en"))
        successes, failures = generate(base, FakeAssistant(TEX), paths, "s", compile_fn()[1])
        assert successes == 1
        assert len(failures) == 1
        assert failures[0].startswith("Bolt")
        assert "banque-en.tex" in failures[0]
    assert not (paths.applications / "Bolt - AI Engineer").exists()


def _fake_tools(folder: Path, latexmk_code: int, pages: int) -> dict[str, str]:
    folder.mkdir()
    (folder / "latexmk").write_text(
        f'#!/bin/sh\n[ "$1" = "-c" ] && exit 0\ntouch "${{6%.tex}}.pdf"\nexit {latexmk_code}\n',
        encoding="utf-8",
    )
    (folder / "pdfinfo").write_text(f"#!/bin/sh\necho 'Pages: {pages}'\n", encoding="utf-8")
    for tool in ("latexmk", "pdfinfo"):
        (folder / tool).chmod(0o755)
    return {**os.environ, "PATH": f"{folder}{os.pathsep}{os.environ['PATH']}"}


@pytest.mark.spec("LTX-11")
def test_example_compiler_reports_extra_pages_and_failures(tmp_path: Path) -> None:
    application = tmp_path / "Acme"
    application.mkdir()
    (application / "cv.tex").write_text("x", encoding="utf-8")
    script = str(EXAMPLE / "compiler.sh")
    env = _fake_tools(tmp_path / "bin", 0, 2)
    result = subprocess.run(
        [script, str(application), "cv.tex"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0
    assert extra_pages(result.stdout) == {"cv": 2}
    env = _fake_tools(tmp_path / "bin2", 1, 1)
    failed = subprocess.run([script, str(application), "cv.tex"], env=env, capture_output=True)
    assert failed.returncode != 0


@pytest.mark.spec("LTX-12")
def test_example_template_is_rewritten_for_the_folder() -> None:
    tex = prepare_template(_text("cv/modele-cv.tex"), "en")
    assert LATEX_ROOT in tex
    assert "cv/banque-en" in tex
    assert "cv/banque-fr" not in tex


GENERIC_CV = r"""\documentclass{x}
\begin{document}
\section{\secExperience} \vspace{0.2cm}
\datedexperience{\posteEntreprise}{\posteDates}
\explanation{\posteIntitule}
\explanationdetail{%
\pB \\
\pA
}
\datedexperience{Autre}{2020}
\explanationdetail{\pIgnored}

\section{\secProjets}
\projOne

\section{\secFormation}
\end{document}
"""


@pytest.mark.spec("LTX-13")
def test_main_experience_is_the_first_one_whatever_its_name() -> None:
    assert cv_contents(GENERIC_CV) == (["\\pB", "\\pA"], ["\\projOne"])


@pytest.mark.spec("LTX-13")
def test_cv_without_main_experience_is_compiled_as_written(tmp_path: Path) -> None:
    cv = tmp_path / "cv.tex"
    tex = "\\documentclass{x}\n\\begin{document}\nTexte\n\\end{document}\n"
    cv.write_text(tex, encoding="utf-8")
    calls, compiler = compile_fn("⚠️  cv.pdf fait 2 pages")
    assert fit_cv(cv, compiler) == 2
    assert len(calls) == 1
    assert cv.read_text(encoding="utf-8") == tex


@pytest.mark.spec("LTX-14")
def test_every_example_headline_has_a_usage_comment() -> None:
    for bank in ("cv/banque-fr.tex", "cv/banque-en.tex"):
        rows = _text(bank).splitlines()
        headlines = [i for i, row in enumerate(rows) if row.startswith("\\newcommand{\\profil")]
        assert headlines, bank
        for i in headlines:
            assert rows[i - 1].startswith("% Usage : "), (bank, rows[i])


@pytest.mark.spec("LTX-16")
def test_example_letter_skeleton() -> None:
    skeleton = _text("lettres/modele-lettre.tex")
    assert "\\companyname{ENTREPRISE}" in skeleton
    assert skeleton.count("\\lettercontent{") >= 4


@pytest.mark.spec("LTX-17")
def test_personal_instructions_come_after_the_general_rules(tmp_path: Path) -> None:
    (tmp_path / "consignes-cv.md").write_text("- Garde 7 puces.\n", encoding="utf-8")
    system = system_prompt(CV_SYSTEM, CV_ANSWER, tmp_path, "consignes-cv.md")
    assert system.index(CV_SYSTEM) < system.index("- Garde 7 puces.") < system.index(CV_ANSWER)
    assert "propres au candidat" in system


@pytest.mark.spec("LTX-17")
def test_missing_or_empty_instructions_add_nothing(tmp_path: Path) -> None:
    assert system_prompt(CV_SYSTEM, CV_ANSWER, tmp_path, "consignes-cv.md") == (
        f"{CV_SYSTEM}\n\n{CV_ANSWER}"
    )
    (tmp_path / "consignes-cv.md").write_text("  \n", encoding="utf-8")
    assert "propres au candidat" not in system_prompt(
        CV_SYSTEM, CV_ANSWER, tmp_path, "consignes-cv.md"
    )


@pytest.mark.spec("LTX-17")
def test_generation_sends_both_instruction_files(paths: Paths) -> None:  # noqa: F811
    (paths.latex / "consignes-cv.md").write_text("Règle CV perso", encoding="utf-8")
    (paths.latex / "consignes-lettre.md").write_text("Règle lettre perso", encoding="utf-8")
    assistant = FakeAssistant(TEX)
    application = Application(AD, "acceptee", letter_requested=True)
    generate_folder(application, assistant, paths, "sonnet", compile_fn()[1])
    cv_system, letter_system = assistant.systems
    assert "Règle CV perso" in cv_system
    assert "Règle lettre perso" not in cv_system
    assert letter_system.startswith(LETTER_SYSTEM)
    assert "Règle lettre perso" in letter_system
