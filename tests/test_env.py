from pathlib import Path

from moteur.env import charger_env


def test_lit_les_variables(tmp_path: Path) -> None:
    fichier = tmp_path / ".env"
    contenu = "# commentaire\nA=1\nexport B='deux'\n\nC=\"x=y\"\nsans_egal\n"
    fichier.write_text(contenu, encoding="utf-8")
    environ: dict[str, str] = {}
    charger_env(fichier, environ)
    assert environ == {"A": "1", "B": "deux", "C": "x=y"}


def test_n_ecrase_pas_l_existant(tmp_path: Path) -> None:
    fichier = tmp_path / ".env"
    fichier.write_text("A=fichier\n", encoding="utf-8")
    environ = {"A": "shell"}
    charger_env(fichier, environ)
    assert environ["A"] == "shell"


def test_fichier_absent(tmp_path: Path) -> None:
    environ: dict[str, str] = {}
    charger_env(tmp_path / ".env", environ)
    assert environ == {}
