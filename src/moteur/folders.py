"""Where an application's folder is filed in `Candidatures/` (CV-17 to CV-21).

- the root: not sent yet, or dropped by User;
- `sent/`: applied, not refused by the company;
- `hold/`: applied, then refused by the company.
"""

from __future__ import annotations

import filecmp
import logging
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

Place = Literal["", "sent", "hold"]
"""Sub-folder of `Candidatures/`; "" is the root."""

SENT: Place = "sent"
HOLD: Place = "hold"
PLACES: tuple[Place, ...] = ("", SENT, HOLD)

APPLIED = "postulee"
"""Page status of an application sent (BASE-05)."""
REFUSED_BY_COMPANY = "refus"
"""Page follow-up of an application the company turned down (PAGE-08)."""


def place_for(status: str, follow_up: str) -> Place | None:
    """Where CV-18 files the folder of a page document; None: it is not moved."""
    if status != APPLIED:
        return None
    return HOLD if follow_up == REFUSED_BY_COMPANY else SENT


def path_in(applications: Path, place: Place, name: str) -> Path:
    return applications / place / name if place else applications / name


def locate(applications: Path, name: str) -> Path | None:
    """The folder named `name` at the root, in `sent/` or in `hold/` (CV-17)."""
    for place in PLACES:
        candidate = path_in(applications, place, name)
        if candidate.is_dir():
            return candidate
    return None


def folder_for_writing(applications: Path, name: str, default: Place = "") -> Path:
    """The folder where it is filed, otherwise created in `default` (CV-21)."""
    folder = locate(applications, name) or path_in(applications, default, name)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _merge(source: Path, target: Path) -> bool:
    """Moves `source`'s files into `target` without losing any (CV-19); True if
    anything changed."""
    changed = False
    for entry in sorted(source.iterdir()):
        destination = target / entry.name
        if not destination.exists():
            entry.rename(destination)
            changed = True
        elif entry.is_file() and destination.is_file() and filecmp.cmp(entry, destination, False):
            entry.unlink()
            changed = True
        elif entry.is_dir() and destination.is_dir():
            changed |= _merge(entry, destination)
        else:
            log.warning("%s kept: a different %s already exists", entry, destination)
    if not any(source.iterdir()):
        source.rmdir()
        changed = True
    return changed


def file_folder(applications: Path, name: str, place: Place) -> Path | None:
    """Files the folder `name` into `place` (CV-18, CV-19).

    Returns the folder's new path when something was moved, otherwise None (no folder,
    or already filed there).
    """
    target = path_in(applications, place, name)
    others = [
        path_in(applications, p, name)
        for p in PLACES
        if p != place and path_in(applications, p, name).is_dir()
    ]
    if not others:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    changed = False
    for source in others:
        if target.exists():
            changed |= _merge(source, target)
        else:
            source.rename(target)
            changed = True
    return target if changed else None


def moved_ref(ref: str, root: Path, folder: Path) -> str:
    """A PDF path relative to `root`, pointed at the same file name in `folder` (CV-20)."""
    if not ref:
        return ref
    return str((folder / Path(ref).name).relative_to(root))
