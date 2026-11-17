"""Lecture d'un fichier `.env` (KEY=VALUE) sans dépendance externe."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path


def charger_env(chemin: Path, environ: MutableMapping[str, str] | None = None) -> None:
    """Ajoute les variables de `chemin` à l'environnement, sans écraser l'existant."""
    cible = os.environ if environ is None else environ
    try:
        lignes = chemin.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        cle = cle.removeprefix("export ").strip()
        valeur = valeur.strip().strip("'\"")
        if cle:
            cible.setdefault(cle, valeur)
