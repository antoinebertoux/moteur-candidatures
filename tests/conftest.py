"""Doublures partagées par les tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from moteur.config import Criteres


class FauxClient:
    """Client HTTP qui renvoie des réponses préparées et retient les appels."""

    def __init__(self, reponses: Mapping[str, Any]) -> None:
        self.reponses = reponses
        self.appels: list[tuple[str, dict[str, Any]]] = []

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        entetes: Mapping[str, str] | None = None,
    ) -> Any:
        self.appels.append((url, dict(params or {})))
        return self.reponses.get(url)

    def post_formulaire(
        self, url: str, *, donnees: Mapping[str, str], params: Mapping[str, str] | None = None
    ) -> Any:
        self.appels.append((url, dict(donnees)))
        return self.reponses.get(url)

    def post_json(
        self, url: str, *, corps: Mapping[str, Any], entetes: Mapping[str, str] | None = None
    ) -> Any:
        self.appels.append((url, dict(corps)))
        reponse = self.reponses.get(url)
        # Une liste de réponses est servie page par page.
        if isinstance(reponse, list):
            return reponse.pop(0) if reponse else None
        return reponse

    def get_texte(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
        self.appels.append((url, dict(params or {})))
        reponse = self.reponses.get(url)
        return reponse if isinstance(reponse, str) else ""


class FauxAssistant:
    """Assistant qui renvoie des réponses dans l'ordre et retient les prompts."""

    def __init__(self, *reponses: str) -> None:
        self.reponses = list(reponses)
        self.prompts: list[str] = []
        self.modeles: list[str] = []

    def demander(self, prompt: str, *, systeme: str, modele: str) -> str:
        self.prompts.append(prompt)
        self.modeles.append(modele)
        return self.reponses.pop(0) if len(self.reponses) > 1 else self.reponses[0]


def criteres(
    mots_cles: tuple[str, ...] = ("data scientist", "ia"),
    exclusions: tuple[str, ...] = ("stage",),
    lieux: tuple[str, ...] = ("paris",),
    salaire_plancher: int = 0,
) -> Criteres:
    return Criteres(mots_cles, exclusions, lieux, salaire_plancher)
