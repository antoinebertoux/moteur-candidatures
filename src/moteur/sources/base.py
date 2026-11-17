"""Contrats communs aux sources et client HTTP."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from moteur.modeles import Offre

_BALISE = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"\s+")


class ErreurSource(Exception):
    """Une source n'a pas pu être interrogée ; les autres continuent."""


class ClientHttp(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        entetes: Mapping[str, str] | None = None,
    ) -> Any: ...

    def post_formulaire(
        self, url: str, *, donnees: Mapping[str, str], params: Mapping[str, str] | None = None
    ) -> Any: ...

    def post_json(
        self, url: str, *, corps: Mapping[str, Any], entetes: Mapping[str, str] | None = None
    ) -> Any: ...

    def get_texte(self, url: str, *, params: Mapping[str, str] | None = None) -> str: ...


class Source(Protocol):
    @property
    def nom(self) -> str: ...

    def collecter(self) -> list[Offre]: ...


class ClientHttpx:
    """Client HTTP réel. Une réponse vide (204) donne `None`."""

    def __init__(self, delai: float = 20.0) -> None:
        self._client = httpx.Client(
            timeout=delai,
            follow_redirects=True,
            headers={"User-Agent": "moteur-candidatures/0.1 (usage personnel)"},
        )

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        entetes: Mapping[str, str] | None = None,
    ) -> Any:
        return self._json(lambda: self._client.get(url, params=params, headers=entetes), url)

    def post_formulaire(
        self, url: str, *, donnees: Mapping[str, str], params: Mapping[str, str] | None = None
    ) -> Any:
        return self._json(lambda: self._client.post(url, data=donnees, params=params), url)

    def post_json(
        self, url: str, *, corps: Mapping[str, Any], entetes: Mapping[str, str] | None = None
    ) -> Any:
        return self._json(lambda: self._client.post(url, json=dict(corps), headers=entetes), url)

    def get_texte(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
        try:
            reponse = self._client.get(url, params=params)
            reponse.raise_for_status()
        except httpx.HTTPStatusError as erreur:
            raise ErreurSource(f"{url} : HTTP {erreur.response.status_code}") from erreur
        except httpx.HTTPError as erreur:
            raise ErreurSource(f"{url} : {erreur}") from erreur
        return reponse.text

    def fermer(self) -> None:
        self._client.close()

    @staticmethod
    def _json(appel: Any, url: str) -> Any:
        try:
            reponse: httpx.Response = appel()
            reponse.raise_for_status()
            if reponse.status_code == httpx.codes.NO_CONTENT or not reponse.content:
                return None
            return reponse.json()
        except httpx.HTTPStatusError as erreur:
            # Le corps explique souvent l'erreur (ex. OAuth : invalid_scope, invalid_client).
            detail = " ".join(erreur.response.text.split())[:300]
            message = f"{url} : HTTP {erreur.response.status_code}"
            raise ErreurSource(f"{message} : {detail}" if detail else message) from erreur
        except (httpx.HTTPError, ValueError) as erreur:
            raise ErreurSource(f"{url} : {erreur}") from erreur


def texte_brut(contenu: str) -> str:
    """Retire les balises HTML (éventuellement échappées) et resserre les espaces."""
    sans_balises = _BALISE.sub(" ", html.unescape(contenu))
    return _ESPACES.sub(" ", html.unescape(sans_balises)).strip()


def chaine(valeur: object) -> str:
    """Convertit une valeur JSON incertaine en chaîne propre."""
    return valeur.strip() if isinstance(valeur, str) else ""


def table(valeur: object) -> dict[str, Any]:
    """Renvoie la valeur si c'est un objet JSON, sinon un objet vide."""
    return valeur if isinstance(valeur, dict) else {}


def liste(valeur: object) -> list[Any]:
    """Renvoie la valeur si c'est un tableau JSON, sinon un tableau vide."""
    return valeur if isinstance(valeur, list) else []
