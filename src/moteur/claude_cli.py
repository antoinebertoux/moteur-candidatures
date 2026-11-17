"""Appels à Claude par `claude -p`, donc avec l'abonnement et sans clé API.

Chaque appel part sans outils, sans serveurs MCP et avec un prompt système court :
c'est ce qui garde la consommation de quota au minimum.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
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


Executeur = Callable[[Sequence[str], str], ResultatProcessus]


class Assistant(Protocol):
    def demander(self, prompt: str, *, systeme: str, modele: str) -> str: ...


def executer(commande: Sequence[str], entree: str) -> ResultatProcessus:
    """Lance une commande en lui passant `entree` sur l'entrée standard."""
    try:
        resultat = subprocess.run(
            list(commande),
            input=entree,
            capture_output=True,
            text=True,
            timeout=DELAI_SECONDES,
            check=False,
        )
    except FileNotFoundError as erreur:
        raise ErreurClaude(f"Commande introuvable : {commande[0]}") from erreur
    except subprocess.TimeoutExpired as erreur:
        raise ErreurClaude(f"{commande[0]} n'a pas répondu en {DELAI_SECONDES} s") from erreur
    return ResultatProcessus(resultat.returncode, resultat.stdout, resultat.stderr)


class ClaudeCli:
    def __init__(self, executeur: Executeur = executer, binaire: str = "claude") -> None:
        self._executeur = executeur
        self._binaire = binaire

    def commande(self, *, systeme: str, modele: str) -> list[str]:
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
            "",
            "--disallowedTools",
            "mcp__*",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]

    def demander(self, prompt: str, *, systeme: str, modele: str) -> str:
        resultat = self._executeur(self.commande(systeme=systeme, modele=modele), prompt)
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
