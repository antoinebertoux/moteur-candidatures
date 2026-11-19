"""Contrats communs aux sources et client HTTP."""

from __future__ import annotations

import html
import re
import time
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol, TypeVar, runtime_checkable

import httpx

from moteur.modeles import Offre

_BALISE = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"\s+")

# « Trop de requêtes » (429) : nouvelles tentatives, attente par défaut et maximale.
ESSAIS_SUR_429 = 2
ATTENTE_429 = 5.0
ATTENTE_429_MAX = 30.0
# Erreur du serveur (5xx) : une nouvelle tentative, après cette attente.
ATTENTE_5XX = 2.0
# Recherches d'une même source lancées en même temps (elles visent le même site).
RECHERCHES_EN_PARALLELE = 4

_E = TypeVar("_E")
_R = TypeVar("_R")


def en_parallele(fonction: Callable[[_E], _R], elements: Iterable[_E], maximum: int) -> list[_R]:
    """Applique `fonction` à chaque élément, `maximum` à la fois ; garde l'ordre des éléments."""
    with ThreadPoolExecutor(max_workers=maximum) as executeur:
        return list(executeur.map(fonction, elements))


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


@runtime_checkable
class SourceDetaillee(Protocol):
    """Source dont les résultats n'ont pas le texte de l'offre : il faut ouvrir sa page."""

    @property
    def nom(self) -> str: ...

    def detailler(self, offre: Offre) -> Offre: ...


class ClientHttpx:
    """Client HTTP réel. Une réponse vide (204) donne `None`."""

    def __init__(
        self,
        delai: float = 20.0,
        *,
        transport: httpx.BaseTransport | None = None,
        pause: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            timeout=delai,
            follow_redirects=True,
            headers={"User-Agent": "moteur-candidatures/0.1 (usage personnel)"},
            transport=transport,
        )
        self._pause = pause

    def _envoyer(self, appel: Callable[[], httpx.Response]) -> httpx.Response:
        """Envoie la requête ; réessaie une fois sur une erreur du serveur, et sur un 429
        après le délai demandé."""
        reponse = appel()
        if reponse.is_server_error:
            self._pause(ATTENTE_5XX)
            reponse = appel()
        for _ in range(ESSAIS_SUR_429):
            if reponse.status_code != httpx.codes.TOO_MANY_REQUESTS:
                break
            self._pause(_attente(reponse.headers.get("Retry-After")))
            reponse = appel()
        return reponse

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
            reponse = self._envoyer(lambda: self._client.get(url, params=params))
            reponse.raise_for_status()
        except httpx.HTTPStatusError as erreur:
            raise ErreurSource(f"{url} : HTTP {erreur.response.status_code}") from erreur
        except httpx.HTTPError as erreur:
            raise ErreurSource(f"{url} : {erreur}") from erreur
        return reponse.text

    def fermer(self) -> None:
        self._client.close()

    def _json(self, appel: Callable[[], httpx.Response], url: str) -> Any:
        try:
            reponse = self._envoyer(appel)
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


def _attente(valeur: str | None) -> float:
    """Délai d'un en-tête Retry-After en secondes, borné ; 5 s s'il est absent ou illisible."""
    try:
        return min(max(float(valeur or ""), 0.0), ATTENTE_429_MAX)
    except ValueError:
        return ATTENTE_429


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
