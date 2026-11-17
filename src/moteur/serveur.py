"""Petit serveur local pour ouvrir les CV et lettres depuis la page de suivi.

La page est hébergée sur claude.ai : un navigateur refuse d'y suivre un lien `file://`.
Elle pointe donc vers `http://127.0.0.1:<port>/Candidatures/...`, que ce serveur sert en
lecture seule. Seul le dossier `Candidatures/` est exposé (pas `config.toml`, `.env`,
`latex/`…), et uniquement sur la machine elle-même.
"""

from __future__ import annotations

import contextlib
import functools
import posixpath
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlsplit

PORT_PAR_DEFAUT = 8765
PREFIXE = "Candidatures"


def chemin_local(chemin_url: str, dossier: Path) -> Path | None:
    """Fichier de `dossier` désigné par `/Candidatures/...`, ou None s'il est hors du dossier."""
    morceaux = [m for m in posixpath.normpath(unquote(urlsplit(chemin_url).path)).split("/") if m]
    if not morceaux or morceaux[0] != PREFIXE or ".." in morceaux:
        return None
    cible = dossier.joinpath(*morceaux[1:]).resolve()
    racine = dossier.resolve()
    if cible != racine and racine not in cible.parents:
        return None
    return cible


class _Gestionnaire(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, dossier: Path, **kwargs: object) -> None:
        self._dossier = dossier
        super().__init__(*args, directory=str(dossier), **kwargs)  # type: ignore[arg-type]

    def send_head(self) -> BytesIO | BinaryIO | None:
        cible = chemin_local(self.path, self._dossier)
        if cible is None or not cible.is_file():
            self.send_error(404)
            return None
        return super().send_head()

    def translate_path(self, path: str) -> str:
        cible = chemin_local(path, self._dossier)
        return str(cible if cible is not None else self._dossier)

    def end_headers(self) -> None:
        # Un PDF régénéré après une consigne doit s'afficher à jour.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


def creer_serveur(dossier: Path, port: int = PORT_PAR_DEFAUT) -> ThreadingHTTPServer:
    gestionnaire = functools.partial(_Gestionnaire, dossier=dossier)
    return ThreadingHTTPServer(("127.0.0.1", port), gestionnaire)


def servir(dossier: Path, port: int = PORT_PAR_DEFAUT) -> None:
    with creer_serveur(dossier, port) as serveur:
        print(f"CV et lettres servis sur http://127.0.0.1:{port}/{PREFIXE}/ (Ctrl+C pour arrêter)")
        with contextlib.suppress(KeyboardInterrupt):
            serveur.serve_forever()
