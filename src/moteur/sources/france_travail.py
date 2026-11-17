"""API « Offres d'emploi v2 » de France Travail (identifiants gratuits sur francetravail.io)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from moteur.modeles import Offre
from moteur.sources.base import ClientHttp, ErreurSource, chaine, liste, table

URL_JETON = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
URL_RECHERCHE = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
URL_DETAIL = "https://candidat.francetravail.fr/offres/recherche/detail/"
PORTEE = "api_offresdemploiv2 o2dsoffre"


def offre_depuis_resultat(resultat: dict[str, Any]) -> Offre | None:
    """Convertit un résultat de l'API ; `None` si l'intitulé manque."""
    poste = chaine(resultat.get("intitule"))
    if not poste:
        return None
    identifiant = chaine(resultat.get("id"))
    url = chaine(table(resultat.get("origineOffre")).get("urlOrigine"))
    return Offre(
        entreprise=chaine(table(resultat.get("entreprise")).get("nom"))
        or "Entreprise non précisée",
        poste=poste,
        lieu=chaine(table(resultat.get("lieuTravail")).get("libelle")),
        url=url or (URL_DETAIL + identifiant if identifiant else ""),
        source="france_travail",
        description=chaine(resultat.get("description")),
        salaire=chaine(table(resultat.get("salaire")).get("libelle")),
        date_publication=chaine(resultat.get("dateCreation"))[:10],
    )


class SourceFranceTravail:
    def __init__(
        self,
        client: ClientHttp,
        identifiant: str,
        secret: str,
        recherches: Sequence[str],
        departements: Sequence[str] = (),
        publiee_depuis: int = 7,
    ) -> None:
        self._client = client
        self._identifiant = identifiant
        self._secret = secret
        self._recherches = recherches
        self._departements = departements
        self._publiee_depuis = publiee_depuis

    @property
    def nom(self) -> str:
        return "france_travail"

    def _jeton(self) -> str:
        reponse = self._client.post_formulaire(
            URL_JETON,
            params={"realm": "/partenaire"},
            donnees={
                "grant_type": "client_credentials",
                "client_id": self._identifiant,
                "client_secret": self._secret,
                "scope": PORTEE,
            },
        )
        jeton = chaine(table(reponse).get("access_token"))
        if not jeton:
            raise ErreurSource("France Travail : pas de jeton d'accès dans la réponse")
        return jeton

    def collecter(self) -> list[Offre]:
        entetes = {"Authorization": f"Bearer {self._jeton()}", "Accept": "application/json"}
        offres: list[Offre] = []
        for mots in self._recherches:
            for departement in self._departements or ("",):
                params = {
                    "motsCles": mots,
                    "publieeDepuis": str(self._publiee_depuis),
                    "range": "0-149",
                }
                if departement:
                    params["departement"] = departement
                reponse = self._client.get_json(URL_RECHERCHE, params=params, entetes=entetes)
                for resultat in liste(table(reponse).get("resultats")):
                    offre = offre_depuis_resultat(table(resultat))
                    if offre is not None:
                        offres.append(offre)
        return offres
