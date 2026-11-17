"""Modèles de données partagés par tout le moteur."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

TypeCandidature = Literal["offre", "spontanee"]
Langue = Literal["fr", "en"]

LONGUEUR_MAX_CLE = 150
_NON_ALPHANUMERIQUE = re.compile(r"[^a-z0-9]+")


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, tout le reste remplacé par des tirets.

    Doit rester identique à la fonction `norm` de la page de suivi : c'est ce qui
    permet aux deux côtés de reconnaître la même candidature.
    """
    decompose = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return _NON_ALPHANUMERIQUE.sub("-", sans_accents).strip("-")


def contient_expression(texte: str, expression: str) -> bool:
    """Vrai si `expression` apparaît dans `texte` en mots entiers.

    Ainsi « ia » ne correspond pas à « commercial ».
    """
    cible = normaliser(expression)
    return bool(cible) and f"-{cible}-" in f"-{normaliser(texte)}-"


@dataclass(frozen=True, slots=True)
class Offre:
    """Une offre d'emploi ou une entreprise visée en candidature spontanée."""

    entreprise: str
    poste: str
    type: TypeCandidature = "offre"
    lieu: str = ""
    url: str = ""
    source: str = ""
    description: str = ""
    salaire: str = ""
    date_publication: str = ""

    @property
    def cle(self) -> str:
        """Identifiant stable, identique à celui que calcule la page de suivi."""
        brut = f"{normaliser(self.type)}_{normaliser(self.entreprise)}_{normaliser(self.poste)}"
        return brut[:LONGUEUR_MAX_CLE]


@dataclass(frozen=True, slots=True)
class Note:
    """Résultat de la notation d'une offre par Claude."""

    score: int
    resume: str
    lettre_demandee: bool
    langue: Langue


@dataclass(frozen=True, slots=True)
class Candidature:
    """Une offre et son état dans la base locale."""

    offre: Offre
    statut: str
    score: int | None = None
    resume: str = ""
    lettre_demandee: bool = False
    langue: Langue = "fr"
    consigne: str = ""
    cv_ref: str = ""
    lettre_ref: str = ""
    consigne_lettre: str = ""


# Organismes pour lesquels une lettre est faite d'office (l'interrupteur de la page peut
# toujours la retirer). Doit rester identique à LETTRE_D_OFFICE dans la page de suivi.
SOURCES_PUBLIQUES = ("service_public", "choisirleservicepublic.gouv.fr", "place-emploi-public")
MOTS_PUBLIC = (
    "ministere",
    "direction generale",
    "dgsi",
    "dgse",
    "dga",
    "dinum",
    "anssi",
    "agence de l'innovation de defense",
    "commissariat",
    "secretariat general",
    "autorite",
    "tracfin",
    "prefecture",
    "armees",
    "gendarmerie",
    "police nationale",
    "service statistique",
    "cnes",
    "cnrs",
    "inria",
    "interpol",
    "beta.gouv",
)
MOTS_BANQUE = (
    "banque",
    "bank",
    "bnp paribas",
    "societe generale",
    "credit agricole",
    "cacib",
    "lcl",
    "natixis",
    "bpce",
    "caisse d'epargne",
    "credit mutuel",
    "cic",
    "bpifrance",
    "rothschild",
    "lazard",
    "hsbc",
    "la banque postale",
    "oddo",
    "amundi",
)


def lettre_par_defaut(offre: Offre) -> bool:
    """Vrai pour les spontanées, le secteur public et les banques."""
    if offre.type == "spontanee" or offre.source in SOURCES_PUBLIQUES:
        return True
    return any(contient_expression(offre.entreprise, mot) for mot in MOTS_PUBLIC + MOTS_BANQUE)
