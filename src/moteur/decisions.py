"""Applies the page's decisions to the local database (file export or direct link)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from moteur import echange
from moteur.base_locale import BaseLocale


@dataclass(frozen=True, slots=True)
class Bilan:
    """What a batch of decisions changed, and what is left to do."""

    decisions: int
    completees: int
    lettres: int
    a_generer: int
    lettres_a_ajouter: int

    def en_dict(self) -> dict[str, int]:
        return asdict(self)

    def phrase(self) -> str:
        return (
            f"{self.decisions} décisions reportées, {self.completees} offres ajoutées ou"
            f" complétées depuis la page, {self.lettres} choix ou régénérations de lettre,"
            f" {self.a_generer} dossiers à générer, {self.lettres_a_ajouter} lettres à ajouter"
        )


def lettres_a_refaire(decisions: list[echange.Decision], base: BaseLocale, racine: Path) -> int:
    """Letters the page asked to regenerate since they were last generated."""
    redemandees = 0
    for decision in decisions:
        if not decision.lettre_refaire_le:
            continue
        candidature = base.trouver(decision.cle)
        if candidature is None or not candidature.lettre_ref:
            continue
        faite_le = echange.date_fichier(racine / candidature.lettre_ref)
        if faite_le is None or faite_le < decision.lettre_refaire_le:
            redemandees += base.redemander_lettre(decision.cle, decision.lettre_consigne)
    return redemandees


def appliquer(base: BaseLocale, decisions: list[echange.Decision], racine: Path) -> Bilan:
    """ECH-12 order: unknown accepted ones, letter choices, statuses, letter regenerations."""
    completees = sum(
        base.completer_depuis_la_page(d.cle, d.offre, d.avec_lettre)
        for d in decisions
        if d.statut == "acceptee" and d.offre is not None
    )
    lettres = sum(
        base.fixer_lettre(d.cle, d.avec_lettre)
        for d in decisions
        if d.statut in ("acceptee", "prete", "validee") and d.offre is not None
    )
    changees = sum(base.appliquer_decision(d.cle, d.statut, d.consigne) for d in decisions)
    changees += sum(
        base.set_refusal_reason(d.cle, d.motif_refus, d.motif_detail)
        for d in decisions
        if d.statut == "refusee"
    )
    lettres += lettres_a_refaire(decisions, base, racine)
    return Bilan(
        changees, completees, lettres, len(base.a_generer()), len(base.lettres_manquantes())
    )
