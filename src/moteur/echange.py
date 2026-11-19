"""Fichiers échangés avec la page de suivi : propositions à importer, décisions à relire."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from moteur.modeles import Candidature, DemandePreparation, Offre, lettre_par_defaut
from moteur.refusal import normalise_detail, normalise_reason


class ErreurEchange(ValueError):
    """Le fichier exporté par la page est illisible."""


@dataclass(frozen=True, slots=True)
class Decision:
    """Une ligne de l'export de la page.

    `offre` décrit la candidature telle que la page la connaît : elle sert à ajouter
    dans la base locale celles qui n'en viennent pas (ajout manuel, moteur A).
    """

    cle: str
    statut: str
    consigne: str = ""
    offre: Offre | None = None
    lettre_demandee: bool = False
    lettre: bool | None = None
    """Choix fait avec l'interrupteur de la page (champ « lettre » : « oui » ou « non »)."""
    lettre_refaire_le: str = ""
    """Moment où « Régénérer la lettre » a été cliqué (format `toISOString()`)."""
    lettre_consigne: str = ""
    motif_refus: str = ""
    """Refusal reason code chosen in the page (PAGE-10), `autre` if unknown."""
    motif_detail: str = ""
    preparation: DemandePreparation | None = None
    """Interview preparation request (PREP-01), None if the page made none."""

    @property
    def avec_lettre(self) -> bool:
        """Le choix de la page s'il existe, sinon la règle par défaut."""
        if self.lettre is not None:
            return self.lettre
        return self.lettre_demandee or (self.offre is not None and lettre_par_defaut(self.offre))


def _texte(entree: dict[str, Any], champ: str) -> str:
    valeur = entree.get(champ)
    return valeur.strip() if isinstance(valeur, str) else ""


def _offre(entree: dict[str, Any]) -> Offre | None:
    entreprise, poste = _texte(entree, "entreprise"), _texte(entree, "poste")
    if not entreprise or not poste:
        return None
    return Offre(
        entreprise=entreprise,
        poste=poste,
        type="spontanee" if entree.get("type") == "spontanee" else "offre",
        lieu=_texte(entree, "lieu"),
        url=_texte(entree, "url"),
        source=_texte(entree, "source"),
        description=_texte(entree, "texte_offre"),
    )


_CONTEXTE = (
    ("date_postulee", "Envoyée le"),
    ("suite", "Suite"),
    ("contact", "Contact"),
    ("notes", "Notes"),
)
MAX_CHAMP_PREPARATION = 2_000


def _preparation(entree: dict[str, Any]) -> DemandePreparation | None:
    """The page's preparation request, with what it knows of the follow-up (PREP-10)."""
    demandee_le = _texte(entree, "preparation_demandee_le")
    if not demandee_le:
        return None
    contexte = [
        f"{libelle} : {_texte(entree, champ)}"
        for champ, libelle in _CONTEXTE
        if _texte(entree, champ)
    ]
    return DemandePreparation(
        demandee_le,
        _texte(entree, "pretentions")[:MAX_CHAMP_PREPARATION],
        _texte(entree, "entretien_infos")[:MAX_CHAMP_PREPARATION],
        _texte(entree, "preparation_consigne")[:MAX_CHAMP_PREPARATION],
        "\n".join(contexte)[:10_000],
    )


def date_fichier(fichier: Path) -> str | None:
    """Date de modification au format de `Date.toISOString()` de la page, ou None."""
    try:
        moment = datetime.fromtimestamp(fichier.stat().st_mtime, UTC)
    except OSError:
        return None
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def pour_la_page(
    candidatures: Iterable[Candidature], racine: Path | None = None
) -> list[dict[str, Any]]:
    """Format lu par le bouton « Importer » de la page.

    La page recalcule elle-même l'identifiant à partir du type, de l'entreprise et du
    poste : il ne faut donc pas le lui envoyer.
    """
    lignes: list[dict[str, Any]] = []
    for candidature in candidatures:
        offre = candidature.offre
        ligne: dict[str, Any] = {
            "type": offre.type,
            "entreprise": offre.entreprise,
            "poste": offre.poste,
            "lieu": offre.lieu,
            "url": offre.url,
            "source": offre.source,
            "moteur": "B",
            "resume": candidature.resume,
            "lettre_demandee": candidature.lettre_demandee,
        }
        if candidature.score is not None:
            ligne["score"] = candidature.score
        if candidature.cv_ref:
            ligne["cv_ref"] = candidature.cv_ref
            # La page ne repasse un dossier en « À valider » que s'il a été généré après
            # la dernière consigne de retouche : un vieil export ne l'écrase pas.
            genere_le = date_fichier(racine / candidature.cv_ref) if racine else None
            if genere_le:
                ligne["genere_le"] = genere_le
        if candidature.lettre_ref:
            ligne["lettre_ref"] = candidature.lettre_ref
            # Permet à la page d'effacer sa demande de régénération une fois servie.
            lettre_le = date_fichier(racine / candidature.lettre_ref) if racine else None
            if lettre_le:
                ligne["lettre_generee_le"] = lettre_le
        if candidature.preparation:
            ligne["preparation"] = candidature.preparation
            ligne["preparation_le"] = candidature.preparation_le
        lignes.append(ligne)
    return lignes


def serialiser(candidatures: Iterable[Candidature], racine: Path | None = None) -> str:
    return json.dumps(pour_la_page(candidatures, racine), ensure_ascii=False, indent=2)


def _choix_lettre(valeur: object) -> bool | None:
    if valeur in ("oui", True):
        return True
    if valeur in ("non", False):
        return False
    return None


def lire_decisions(texte: str) -> list[Decision]:
    """Reads the page's export (`{"candidatures": [...]}` or the array itself)."""
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as erreur:
        raise ErreurEchange("Export illisible : ce n'est pas du JSON") from erreur
    return decisions_depuis(donnees)


def decisions_depuis(donnees: object) -> list[Decision]:
    """Decisions from already decoded page documents (file export or direct link)."""
    if isinstance(donnees, dict):
        donnees = donnees.get("candidatures")
    if not isinstance(donnees, list):
        raise ErreurEchange("Export illisible : tableau « candidatures » introuvable")
    decisions: list[Decision] = []
    for entree in donnees:
        if not isinstance(entree, dict):
            continue
        cle, statut = entree.get("id"), entree.get("statut")
        if isinstance(cle, str) and isinstance(statut, str):
            decisions.append(
                Decision(
                    cle,
                    statut,
                    _texte(entree, "consigne"),
                    _offre(entree),
                    entree.get("lettre_demandee") is True,
                    _choix_lettre(entree.get("lettre")),
                    _texte(entree, "lettre_refaire_le"),
                    _texte(entree, "lettre_consigne"),
                    normalise_reason(entree.get("motif_refus")),
                    normalise_detail(entree.get("motif_detail")),
                    _preparation(entree),
                )
            )
    return decisions
