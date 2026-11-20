from __future__ import annotations

import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from moteur.pdf_server import local_path, make_server


@pytest.mark.spec("SRV-02")
def test_local_path_stays_in_the_folder(tmp_path: Path) -> None:
    assert (
        local_path("/Candidatures/A%20-%20B/cv.pdf", tmp_path)
        == (tmp_path / "A - B" / "cv.pdf").resolve()
    )
    assert local_path("/Candidatures/../moteur/.env", tmp_path) is None
    assert local_path("/latex/cv/modele-cv.tex", tmp_path) is None
    assert local_path("/", tmp_path) is None


@pytest.fixture
def address(tmp_path: Path) -> Iterator[str]:
    folder = tmp_path / "Candidatures"
    (folder / "Acme - Lead AI").mkdir(parents=True)
    (folder / "Acme - Lead AI" / "cv.pdf").write_bytes(b"%PDF-1.5")
    (tmp_path / "secret.txt").write_text("non", encoding="utf-8")
    server = make_server(folder, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.mark.spec("SRV-03")
def test_serves_a_pdf(address: str) -> None:
    with urllib.request.urlopen(f"{address}/Candidatures/Acme%20-%20Lead%20AI/cv.pdf") as answer:
        assert answer.read() == b"%PDF-1.5"
        assert answer.headers["Content-Type"] == "application/pdf"
        assert answer.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "path",
    [
        "/Candidatures/",
        "/Candidatures/Acme%20-%20Lead%20AI/",
        "/secret.txt",
        "/Candidatures/%2e%2e/secret.txt",
    ],
)
@pytest.mark.spec("SRV-02")
def test_refuses_the_rest(address: str, path: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(address + path)
    assert error.value.code == 404
