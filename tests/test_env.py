from pathlib import Path

import pytest

from moteur.env import load_env


@pytest.mark.spec("CONF-08")
def test_reads_the_variables(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    contents = "# commentaire\nA=1\nexport B='deux'\n\nC=\"x=y\"\nsans_egal\n"
    file.write_text(contents, encoding="utf-8")
    environ: dict[str, str] = {}
    load_env(file, environ)
    assert environ == {"A": "1", "B": "deux", "C": "x=y"}


@pytest.mark.spec("CONF-08")
def test_does_not_overwrite_existing(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_text("A=fichier\n", encoding="utf-8")
    environ = {"A": "shell"}
    load_env(file, environ)
    assert environ["A"] == "shell"


@pytest.mark.spec("CONF-08")
def test_missing_file(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    load_env(tmp_path / ".env", environ)
    assert environ == {}
