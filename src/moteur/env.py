"""Reads a `.env` file (KEY=VALUE) without any external dependency."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path


def load_env(path: Path, environ: MutableMapping[str, str] | None = None) -> None:
    """Adds the variables of `path` to the environment, without overwriting existing ones."""
    target = os.environ if environ is None else environ
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for row in rows:
        row = row.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip().strip("'\"")
        if key:
            target.setdefault(key, value)
