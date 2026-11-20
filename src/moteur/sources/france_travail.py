"""France Travail "Offres d'emploi v2" API (free credentials on francetravail.io)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from moteur.models import JobAd
from moteur.sources.base import HttpClient, SourceError, items, string, table

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
DETAIL_URL = "https://candidat.francetravail.fr/offres/recherche/detail/"
SCOPE = "api_offresdemploiv2 o2dsoffre"


def ad_from_result(result: dict[str, Any]) -> JobAd | None:
    """Converts an API result; `None` if the title is missing."""
    title = string(result.get("intitule"))
    if not title:
        return None
    identifier = string(result.get("id"))
    url = string(table(result.get("origineOffre")).get("urlOrigine"))
    return JobAd(
        company=string(table(result.get("entreprise")).get("nom")) or "Entreprise non précisée",
        title=title,
        location=string(table(result.get("lieuTravail")).get("libelle")),
        url=url or (DETAIL_URL + identifier if identifier else ""),
        source="france_travail",
        description=string(result.get("description")),
        salary=string(table(result.get("salaire")).get("libelle")),
        published_on=string(result.get("dateCreation"))[:10],
    )


class SourceFranceTravail:
    def __init__(
        self,
        client: HttpClient,
        identifier: str,
        secret: str,
        searches: Sequence[str],
        departments: Sequence[str] = (),
        published_since: int = 7,
    ) -> None:
        self._client = client
        self._identifier = identifier
        self._secret = secret
        self._searches = searches
        self._departments = departments
        self._published_since = published_since

    @property
    def name(self) -> str:
        return "france_travail"

    def _token(self) -> str:
        answer = self._client.post_form(
            TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": self._identifier,
                "client_secret": self._secret,
                "scope": SCOPE,
            },
        )
        token = string(table(answer).get("access_token"))
        if not token:
            raise SourceError("France Travail: no access token in the answer")
        return token

    def collect(self) -> list[JobAd]:
        headers = {"Authorization": f"Bearer {self._token()}", "Accept": "application/json"}
        ads: list[JobAd] = []
        for words in self._searches:
            for department in self._departments or ("",):
                params = {
                    "motsCles": words,
                    "publieeDepuis": str(self._published_since),
                    "range": "0-149",
                }
                if department:
                    params["departement"] = department
                answer = self._client.get_json(SEARCH_URL, params=params, headers=headers)
                for result in items(table(answer).get("resultats")):
                    ad = ad_from_result(table(result))
                    if ad is not None:
                        ads.append(ad)
        return ads
