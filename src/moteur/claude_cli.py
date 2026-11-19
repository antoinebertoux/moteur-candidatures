"""Calls to Claude through `claude -p`, so with the subscription and no API key.

Every call runs without MCP servers and with a short system prompt, which keeps quota
use to a minimum. Only the interview preparation is given tools: web search and page
fetching (CLA-04).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

DELAI_SECONDES = 600
_BLOC = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.DOTALL)


class ErreurClaude(Exception):
    """L'appel à Claude a échoué ou sa réponse est inexploitable."""


@dataclass(frozen=True, slots=True)
class ResultatProcessus:
    code: int
    sortie: str
    erreur: str = ""


Executeur = Callable[[Sequence[str], str, int], ResultatProcessus]
"""Runs a command with the given standard input and a time limit in seconds."""


class Assistant(Protocol):
    def demander(
        self,
        prompt: str,
        *,
        systeme: str,
        modele: str,
        outils: tuple[str, ...] = (),
        delai: int = DELAI_SECONDES,
    ) -> str: ...


def executer(commande: Sequence[str], entree: str, delai: int) -> ResultatProcessus:
    """Runs a command, passing `entree` on its standard input."""
    try:
        resultat = subprocess.run(
            list(commande),
            input=entree,
            capture_output=True,
            text=True,
            timeout=delai,
            check=False,
        )
    except FileNotFoundError as erreur:
        raise ErreurClaude(f"Commande introuvable : {commande[0]}") from erreur
    except subprocess.TimeoutExpired as erreur:
        raise ErreurClaude(f"{commande[0]} n'a pas répondu en {delai} s") from erreur
    return ResultatProcessus(resultat.returncode, resultat.stdout, resultat.stderr)


def binaire_claude() -> str:
    """`claude` from the PATH, or its usual install place when the PATH lacks it.

    A process started by the desktop app (PREP-41) may not have `~/.local/bin` in its PATH.
    """
    trouve = shutil.which("claude")
    if trouve:
        return trouve
    installe = Path.home() / ".local" / "bin" / "claude"
    return str(installe) if installe.exists() else "claude"


class ClaudeCli:
    def __init__(self, executeur: Executeur = executer, binaire: str = "claude") -> None:
        self._executeur = executeur
        self._binaire = binaire

    def commande(self, *, systeme: str, modele: str, outils: tuple[str, ...] = ()) -> list[str]:
        # CLA-01: no tools at all, except the web tools of the interview preparation.
        autorises = ["--allowedTools", ",".join(outils)] if outils else []
        return [
            self._binaire,
            "-p",
            "--model",
            modele,
            "--output-format",
            "json",
            "--system-prompt",
            systeme,
            "--tools",
            ",".join(outils),
            *autorises,
            "--disallowedTools",
            "mcp__*",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]

    def demander(
        self,
        prompt: str,
        *,
        systeme: str,
        modele: str,
        outils: tuple[str, ...] = (),
        delai: int = DELAI_SECONDES,
    ) -> str:
        commande = self.commande(systeme=systeme, modele=modele, outils=outils)
        resultat = self._executeur(commande, prompt, delai)
        if resultat.code != 0:
            detail = (resultat.erreur or resultat.sortie).strip()[:500]
            raise ErreurClaude(f"claude a échoué (code {resultat.code}) : {detail}")
        try:
            reponse = json.loads(resultat.sortie)
        except json.JSONDecodeError as erreur:
            raise ErreurClaude("Sortie de claude illisible (JSON attendu)") from erreur
        if not isinstance(reponse, dict) or reponse.get("is_error"):
            raise ErreurClaude(f"claude a renvoyé une erreur : {str(reponse)[:500]}")
        texte = reponse.get("result")
        if not isinstance(texte, str) or not texte.strip():
            raise ErreurClaude("Réponse de claude vide")
        return texte


def extraire_bloc(texte: str) -> str:
    """Contenu du premier bloc ``` de la réponse, ou la réponse entière s'il n'y en a pas."""
    bloc = _BLOC.search(texte)
    return (bloc.group(1) if bloc else texte).strip()


def extraire_json(texte: str) -> Any:
    """Décode le JSON d'une réponse, même entouré de texte ou d'un bloc ```."""
    candidat = extraire_bloc(texte)
    debuts = [i for i in (candidat.find("["), candidat.find("{")) if i >= 0]
    fin = max(candidat.rfind("]"), candidat.rfind("}"))
    if not debuts or fin < min(debuts):
        raise ErreurClaude("Pas de JSON dans la réponse de claude")
    try:
        return json.loads(candidat[min(debuts) : fin + 1])
    except json.JSONDecodeError as erreur:
        raise ErreurClaude("JSON invalide dans la réponse de claude") from erreur
