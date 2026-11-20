"""The user's `latex/` folder: required files, personal instructions, example copy.

Its format is described in `specs/latex-repository.md`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from moteur.models import Language

EXAMPLE = Path(__file__).resolve().parents[2] / "latex-exemple"
"""Example shipped with the repository, for a fictional person (LTX-01)."""

REQUIRED_FILES = (
    "compiler.sh",
    "commun/coordonnees.tex",
    "cv/modele-cv.tex",
    "lettres/modele-lettre.tex",
    "lettres/banque-paragraphes.md",
)
"""Files without which no folder can be prepared (LTX-10)."""

TO_ADAPT = (
    "commun/coordonnees.tex",
    "cv/banque-fr.tex",
    "cv/banque-en.tex",
    "lettres/banque-paragraphes.md",
    "consignes-cv.md",
    "consignes-lettre.md",
)

CV_INSTRUCTIONS = "consignes-cv.md"
LETTER_INSTRUCTIONS = "consignes-lettre.md"


class LatexRepositoryError(Exception):
    """The `latex/` folder is missing files, or cannot be created."""


def bank(latex: Path, language: Language) -> Path:
    return latex / "cv" / f"banque-{language}.tex"


def missing_files(latex: Path) -> list[str]:
    """Required files absent from the folder (LTX-10)."""
    return [name for name in REQUIRED_FILES if not (latex / name).is_file()]


def check(latex: Path) -> None:
    """Stops before any folder is prepared if a required file is missing (LTX-10)."""
    missing = missing_files(latex)
    if missing:
        raise LatexRepositoryError(
            f"{latex} is missing: {', '.join(missing)}. "
            "Run `moteur init-latex` to start from the example, "
            "or see specs/latex-repository.md for the expected format"
        )


def personal_instructions(latex: Path, name: str) -> str:
    """Candidate's own rules for Claude; empty when the file is missing (LTX-17)."""
    try:
        return (latex / name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def init_latex(target: Path, example: Path = EXAMPLE) -> list[str]:
    """Copies the example to `target` (LTX-03); returns the files to adapt."""
    if target.exists():
        raise LatexRepositoryError(f"{target} already exists: nothing copied")
    if not example.is_dir():
        raise LatexRepositoryError(f"The example {example} is missing from the repository")
    shutil.copytree(example, target)
    return [name for name in TO_ADAPT if (target / name).exists()]
