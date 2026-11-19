"""Chargement et validation de `config.toml`."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

from moteur.sources.service_public import DOMAINES, EMPLOYEURS, identifiant

TypeAts = Literal[
    "greenhouse",
    "lever",
    "ashby",
    "workday",
    "smartrecruiters",
    "recruitee",
    "teamtailor",
    "radancy",
    "",
]


class ErreurConfig(ValueError):
    """Le fichier de configuration est absent ou mal formé."""


@dataclass(frozen=True, slots=True)
class Criteres:
    mots_cles: tuple[str, ...]
    exclusions: tuple[str, ...]
    lieux: tuple[str, ...]
    salaire_plancher: int


@dataclass(frozen=True, slots=True)
class FranceTravail:
    actif: bool
    recherches: tuple[str, ...]
    departements: tuple[str, ...]
    publiee_depuis: int


@dataclass(frozen=True, slots=True)
class ServicePublic:
    """Recherche sur Choisir le service public ; domaines et employeurs en identifiants."""

    actif: bool
    recherches: tuple[str, ...]
    domaines: tuple[int, ...] = ()
    employeurs: tuple[int, ...] = ()
    pages_max: int = 3


@dataclass(frozen=True, slots=True)
class EntrepriseCible:
    nom: str
    ats: TypeAts = ""
    identifiant: str = ""
    site: str = ""
    spontanee: bool = False
    # Mots-clés envoyés à la recherche de l'ATS (Workday) ; vide = valeurs par défaut.
    recherches: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Chemins:
    racine: Path
    base: Path
    echange: Path

    @property
    def latex(self) -> Path:
        return self.racine / "latex"

    @property
    def candidatures(self) -> Path:
        return self.racine / "Candidatures"

    @property
    def entreprises_vues(self) -> Path:
        return self.racine / "suivi" / "entreprises_vues.csv"


@dataclass(frozen=True, slots=True)
class Config:
    profil: str
    role_spontane: str
    taille_lot: int
    modele_notation: str
    modele_generation: str
    criteres: Criteres
    france_travail: FranceTravail
    service_public: ServicePublic
    entreprises: tuple[EntrepriseCible, ...]
    chemins: Chemins


def _table(donnees: Mapping[str, Any], cle: str) -> Mapping[str, Any]:
    valeur = donnees.get(cle, {})
    if not isinstance(valeur, dict):
        raise ErreurConfig(f"[{cle}] doit être une table")
    return valeur


def _chaine(table: Mapping[str, Any], cle: str, defaut: str = "") -> str:
    valeur = table.get(cle, defaut)
    if not isinstance(valeur, str):
        raise ErreurConfig(f"« {cle} » doit être une chaîne")
    return valeur


def _chaines(table: Mapping[str, Any], cle: str) -> tuple[str, ...]:
    valeur = table.get(cle, [])
    if not isinstance(valeur, list) or not all(isinstance(v, str) for v in valeur):
        raise ErreurConfig(f"« {cle} » doit être une liste de chaînes")
    return tuple(valeur)


def _entier(table: Mapping[str, Any], cle: str, defaut: int) -> int:
    valeur = table.get(cle, defaut)
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise ErreurConfig(f"« {cle} » doit être un entier")
    return valeur


def _booleen(table: Mapping[str, Any], cle: str, defaut: bool) -> bool:
    valeur = table.get(cle, defaut)
    if not isinstance(valeur, bool):
        raise ErreurConfig(f"« {cle} » doit valoir true ou false")
    return valeur


def _identifiants(table: Mapping[str, Any], cle: str, connus: dict[str, int]) -> tuple[int, ...]:
    """Noms (« DGSE », « Numérique ») ou identifiants numériques du site."""
    valeurs = table.get(cle, [])
    if not isinstance(valeurs, list):
        raise ErreurConfig(f"« {cle} » doit être une liste")
    resultat: list[int] = []
    for valeur in valeurs:
        trouve = (
            valeur
            if isinstance(valeur, int) and not isinstance(valeur, bool)
            else identifiant(valeur, connus)
            if isinstance(valeur, str)
            else None
        )
        if trouve is None:
            noms = ", ".join(connus)
            raise ErreurConfig(f"« {cle} » : {valeur!r} inconnu (noms reconnus : {noms})")
        resultat.append(trouve)
    return tuple(resultat)


def _service_public(table: Mapping[str, Any]) -> ServicePublic:
    pages_max = _entier(table, "pages_max", 3)
    if pages_max < 1:
        raise ErreurConfig("« pages_max » doit être supérieur ou égal à 1")
    return ServicePublic(
        actif=_booleen(table, "actif", False),
        recherches=_chaines(table, "recherches"),
        domaines=_identifiants(table, "domaines", DOMAINES),
        employeurs=_identifiants(table, "employeurs", EMPLOYEURS),
        pages_max=pages_max,
    )


def _entreprise(table: Mapping[str, Any]) -> EntrepriseCible:
    nom = _chaine(table, "nom")
    if not nom:
        raise ErreurConfig("Chaque [[entreprises]] doit avoir un nom")
    ats = _chaine(table, "ats")
    if ats not in get_args(TypeAts):
        raise ErreurConfig(f"ats inconnu pour {nom} : {ats}")
    identifiant = _chaine(table, "identifiant")
    if ats and not identifiant:
        raise ErreurConfig(f"{nom} : « identifiant » est requis quand « ats » est renseigné")
    return EntrepriseCible(
        nom=nom,
        ats=cast(TypeAts, ats),
        identifiant=identifiant,
        site=_chaine(table, "site"),
        spontanee=_booleen(table, "spontanee", False),
        recherches=_chaines(table, "recherches"),
    )


def analyser(donnees: Mapping[str, Any], dossier: Path) -> Config:
    """Construit la configuration ; les chemins relatifs partent de `dossier`."""
    criteres = _table(donnees, "criteres")
    france_travail = _table(donnees, "france_travail")
    modeles = _table(donnees, "modeles")
    chemins = _table(donnees, "chemins")
    entreprises = donnees.get("entreprises", [])
    if not isinstance(entreprises, list) or not all(isinstance(e, dict) for e in entreprises):
        raise ErreurConfig("[[entreprises]] doit être une liste de tables")
    taille_lot = _entier(donnees, "taille_lot", 8)
    if taille_lot < 1:
        raise ErreurConfig("« taille_lot » doit être supérieur ou égal à 1")
    return Config(
        profil=_chaine(donnees, "profil").strip(),
        role_spontane=_chaine(donnees, "role_spontane", "Ingénieur IA"),
        taille_lot=taille_lot,
        modele_notation=_chaine(modeles, "notation", "haiku"),
        modele_generation=_chaine(modeles, "generation", "sonnet"),
        criteres=Criteres(
            mots_cles=_chaines(criteres, "mots_cles"),
            exclusions=_chaines(criteres, "exclusions"),
            lieux=_chaines(criteres, "lieux"),
            salaire_plancher=_entier(criteres, "salaire_plancher", 0),
        ),
        france_travail=FranceTravail(
            actif=_booleen(france_travail, "actif", False),
            recherches=_chaines(france_travail, "recherches"),
            departements=_chaines(france_travail, "departements"),
            publiee_depuis=_entier(france_travail, "publiee_depuis", 7),
        ),
        service_public=_service_public(_table(donnees, "service_public")),
        entreprises=tuple(_entreprise(e) for e in entreprises),
        chemins=Chemins(
            racine=(dossier / _chaine(chemins, "racine", "..")).resolve(),
            base=dossier / "moteur.sqlite3",
            echange=dossier / "echange",
        ),
    )


def charger(chemin: Path) -> Config:
    """Lit `config.toml`."""
    try:
        with chemin.open("rb") as fichier:
            donnees = tomllib.load(fichier)
    except FileNotFoundError as erreur:
        raise ErreurConfig(
            f"{chemin} introuvable : copie config.exemple.toml en config.toml"
        ) from erreur
    except tomllib.TOMLDecodeError as erreur:
        raise ErreurConfig(f"{chemin} illisible : {erreur}") from erreur
    return analyser(donnees, chemin.resolve().parent)
