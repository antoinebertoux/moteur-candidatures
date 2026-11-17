"""Petit serveur local pour ouvrir les CV et lettres depuis la page de suivi.

La page est hébergée sur claude.ai : un navigateur refuse d'y suivre un lien `file://`.
Elle pointe donc vers `http://127.0.0.1:<port>/Candidatures/...`, que ce serveur sert en
lecture seule. Seul le dossier `Candidatures/` est exposé (pas `config.toml`, `.env`,
`latex/`…), et uniquement sur la machine elle-même.

`/export` renvoie le fichier préparé pour la page, que celle-ci importe toute seule. Il
n'est lisible que par une page de claude.ai (CORS), pas par n'importe quel site ouvert
pendant que le serveur tourne.
"""

from __future__ import annotations

import contextlib
import functools
import logging
import posixpath
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlsplit

PORT_PAR_DEFAUT = 8765
PREFIXE = "Candidatures"
CHEMIN_EXPORT = "/export"
# Domaines d'où la page de suivi peut être servie.
_DOMAINES_PAGE = ("claude.ai", "claudeusercontent.com", "claude.site")

journal = logging.getLogger("moteur")


def origine_autorisee(origine: str | None) -> bool:
    """Vrai si `origine` (en-tête Origin) est une page https de claude.ai."""
    if not origine:
        return False
    morceaux = urlsplit(origine)
    hote = morceaux.hostname or ""
    return morceaux.scheme == "https" and any(
        hote == d or hote.endswith("." + d) for d in _DOMAINES_PAGE
    )


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
    def __init__(self, *args: object, dossier: Path, export: Path, **kwargs: object) -> None:
        self._dossier = dossier
        self._export = export
        super().__init__(*args, directory=str(dossier), **kwargs)  # type: ignore[arg-type]

    def _en_tetes_cors(self) -> bool:
        origine = self.headers.get("Origin")
        if not origine_autorisee(origine):
            journal.warning("Export refusé à l'origine %s", origine)
            return False
        self.send_header("Access-Control-Allow-Origin", origine or "")
        self.send_header("Vary", "Origin")
        # Accès au réseau local depuis un site public (Chrome) : demandé en pré-vol.
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Local-Network", "true")
        return True

    def do_OPTIONS(self) -> None:
        if urlsplit(self.path).path != CHEMIN_EXPORT:
            self.send_error(404)
            return
        self.send_response(204)
        if self._en_tetes_cors():
            self.send_header("Access-Control-Allow-Methods", "GET")
            self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def _envoyer_export(self) -> None:
        try:
            contenu = self._export.read_bytes()
        except FileNotFoundError:
            contenu = b"[]"
        self.send_response(200)
        self._en_tetes_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(contenu)))
        self.end_headers()
        self.wfile.write(contenu)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == CHEMIN_EXPORT:
            self._envoyer_export()
            return
        super().do_GET()

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


def creer_serveur(dossier: Path, export: Path, port: int = PORT_PAR_DEFAUT) -> ThreadingHTTPServer:
    gestionnaire = functools.partial(_Gestionnaire, dossier=dossier, export=export)
    return ThreadingHTTPServer(("127.0.0.1", port), gestionnaire)


def servir(dossier: Path, export: Path, port: int = PORT_PAR_DEFAUT) -> None:
    with creer_serveur(dossier, export, port) as serveur:
        print(f"CV et lettres servis sur http://127.0.0.1:{port}/{PREFIXE}/ (Ctrl+C pour arrêter)")
        with contextlib.suppress(KeyboardInterrupt):
            serveur.serve_forever()
