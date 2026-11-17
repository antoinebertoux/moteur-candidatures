from __future__ import annotations

import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from moteur.serveur import chemin_local, creer_serveur


def test_chemin_local_reste_dans_le_dossier(tmp_path: Path) -> None:
    assert (
        chemin_local("/Candidatures/A%20-%20B/cv.pdf", tmp_path)
        == (tmp_path / "A - B" / "cv.pdf").resolve()
    )
    assert chemin_local("/Candidatures/../moteur/.env", tmp_path) is None
    assert chemin_local("/latex/cv/modele-cv.tex", tmp_path) is None
    assert chemin_local("/", tmp_path) is None


@pytest.fixture
def adresse(tmp_path: Path) -> Iterator[str]:
    dossier = tmp_path / "Candidatures"
    (dossier / "Acme - Lead AI").mkdir(parents=True)
    (dossier / "Acme - Lead AI" / "cv.pdf").write_bytes(b"%PDF-1.5")
    (tmp_path / "secret.txt").write_text("non", encoding="utf-8")
    serveur = creer_serveur(dossier, port=0)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    yield f"http://127.0.0.1:{serveur.server_address[1]}"
    serveur.shutdown()
    serveur.server_close()


def test_sert_un_pdf(adresse: str) -> None:
    with urllib.request.urlopen(f"{adresse}/Candidatures/Acme%20-%20Lead%20AI/cv.pdf") as reponse:
        assert reponse.read() == b"%PDF-1.5"
        assert reponse.headers["Content-Type"] == "application/pdf"
        assert reponse.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "chemin",
    [
        "/Candidatures/",
        "/Candidatures/Acme%20-%20Lead%20AI/",
        "/secret.txt",
        "/Candidatures/%2e%2e/secret.txt",
    ],
)
def test_refuse_le_reste(adresse: str, chemin: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as erreur:
        urllib.request.urlopen(adresse + chemin)
    assert erreur.value.code == 404
