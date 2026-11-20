"""Small local server to open CVs and letters from the tracking page.

The page is hosted on claude.ai, where a browser refuses to follow a `file://` link.
It therefore points to `http://127.0.0.1:<port>/Candidatures/...`, which this server
serves read-only. Only the `Candidatures/` folder is exposed (not `config.toml`, `.env`,
`latex/`…), and only on the machine itself.
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

DEFAULT_PORT = 8765
PREFIX = "Candidatures"


def local_path(url_path: str, folder: Path) -> Path | None:
    """File of `folder` named by `/Candidatures/...`, or None if it is outside the folder."""
    pieces = [m for m in posixpath.normpath(unquote(urlsplit(url_path).path)).split("/") if m]
    if not pieces or pieces[0] != PREFIX or ".." in pieces:
        return None
    target = folder.joinpath(*pieces[1:]).resolve()
    root = folder.resolve()
    if target != root and root not in target.parents:
        return None
    return target


class _Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, folder: Path, **kwargs: object) -> None:
        self._folder = folder
        super().__init__(*args, directory=str(folder), **kwargs)  # type: ignore[arg-type]

    def send_head(self) -> BytesIO | BinaryIO | None:
        target = local_path(self.path, self._folder)
        if target is None or not target.is_file():
            self.send_error(404)
            return None
        return super().send_head()

    def translate_path(self, path: str) -> str:
        target = local_path(path, self._folder)
        return str(target if target is not None else self._folder)

    def end_headers(self) -> None:
        # A PDF regenerated after an instruction must show up to date.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


def make_server(folder: Path, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = functools.partial(_Handler, folder=folder)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(folder: Path, port: int = DEFAULT_PORT) -> None:
    with make_server(folder, port) as server:
        print(f"CVs and letters served on http://127.0.0.1:{port}/{PREFIX}/ (Ctrl+C to stop)")
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()
