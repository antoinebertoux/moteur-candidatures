"""Interview preparation sheets (specs/interview-prep.md)."""

# ruff: noqa: F811  (the shared `chemins` fixture is imported, then requested by name)

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from moteur.base_locale import BaseLocale
from moteur.claude_cli import ClaudeCli, ErreurClaude, ResultatProcessus
from moteur.config import Chemins
from moteur.decisions import appliquer
from moteur.echange import decisions_depuis, pour_la_page
from moteur.generation import nom_dossier
from moteur.liaison import decisions as outil_decisions
from moteur.modeles import DemandePreparation, Offre
from moteur.preparation import (
    COUPEE,
    FICHIER_FICHE,
    LONGUEUR_MAX,
    OUTILS_WEB,
    chemin_verrou,
    infos_permises,
    lancer_en_arriere_plan,
    nettoyer_fiche,
    preparer,
    preparer_seul,
    prompt_preparation,
    verrou,
)
from tests.conftest import FauxAssistant
from tests.test_generation import chemins  # noqa: F401  (shared fixture)

OFFRE = Offre("Acme", "Lead AI", lieu="Paris", url="https://a", description="Texte de l'offre")
FICHE = "# Préparation : Acme — Lead AI\n## À retenir\nTout."
INFOS = """# Infos pour remplir les formulaires de candidature

## Identité
- Prénom / Nom : Jean Exemple

## Contact
- Téléphone : 06 00 00 00 00

## Situation
- Préavis : 3 mois
- Critère de tri des offres (NE JAMAIS COMMUNIQUER) : plancher 65K€ brut/an
- Habilitation défense : aucune

## Préférences
- Télétravail souhaité : si possible

## Formation
- Diplôme : Master

## Réponses types aux questions fréquentes
- Pourquoi quitter votre poste actuel : nouveau défi
"""


def document(**champs: Any) -> dict[str, Any]:
    """A page document of the application, interview requested."""
    entree = {
        "id": OFFRE.cle,
        "statut": "postulee",
        "entreprise": OFFRE.entreprise,
        "poste": OFFRE.poste,
        "lieu": OFFRE.lieu,
        "url": OFFRE.url,
        "texte_offre": OFFRE.description,
        "date_postulee": "2026-11-10",
        "suite": "entretien",
        "notes": "2026-11-18 : appel du recruteur",
        "preparation_demandee_le": "2026-11-19T10:00:00.000Z",
        "pretentions": "70 k€",
        "entretien_infos": "Jeudi 14 h, visio avec le CTO",
        "preparation_consigne": "insiste sur le RAG",
    }
    entree.update(champs)
    return entree


def demander(base: BaseLocale, chemins: Chemins, **champs: Any) -> int:
    return appliquer(base, decisions_depuis([document(**champs)]), chemins.racine).preparations


@pytest.fixture
def base(chemins: Chemins) -> Any:
    with BaseLocale(chemins.base) as ouverte:
        yield ouverte


@pytest.mark.spec("PREP-01", "BASE-12", "ECH-11")
def test_la_demande_de_la_page_est_enregistree(base: BaseLocale, chemins: Chemins) -> None:
    base.ajouter([OFFRE])
    base.appliquer_decision(OFFRE.cle, "postulee")
    assert demander(base, chemins) == 1
    demande = base.demande_preparation(OFFRE.cle)
    assert demande is not None
    assert demande.demandee_le == "2026-11-19T10:00:00.000Z"
    assert (demande.pretentions, demande.entretien_infos, demande.consigne) == (
        "70 k€",
        "Jeudi 14 h, visio avec le CTO",
        "insiste sur le RAG",
    )
    assert "Envoyée le : 2026-11-10" in demande.contexte
    assert "appel du recruteur" in demande.contexte
    candidature = base.trouver(OFFRE.cle)
    assert candidature is not None
    assert candidature.statut == "close"


@pytest.mark.spec("BASE-12")
def test_une_demande_identique_ou_plus_ancienne_ne_change_rien(
    base: BaseLocale, chemins: Chemins
) -> None:
    base.ajouter([OFFRE])
    assert demander(base, chemins) == 1
    assert demander(base, chemins) == 0
    assert demander(base, chemins, preparation_demandee_le="2026-11-01T00:00:00.000Z") == 0
    assert demander(base, chemins, preparation_demandee_le="2026-11-20T00:00:00.000Z") == 1


@pytest.mark.spec("PREP-02")
def test_une_demande_est_en_attente_tant_qu_elle_est_plus_recente_que_la_fiche(
    base: BaseLocale, chemins: Chemins
) -> None:
    base.ajouter([OFFRE])
    assert base.preparations_en_attente() == []
    demander(base, chemins)
    assert base.preparations_en_attente() == [OFFRE.cle]
    base.enregistrer_preparation(OFFRE.cle, FICHE, "2026-11-19T10:05:00.000Z")
    assert base.preparations_en_attente() == []
    demander(base, chemins, preparation_demandee_le="2026-11-19T11:00:00.000Z")
    assert base.preparations_en_attente() == [OFFRE.cle]


@pytest.mark.spec("PREP-03")
def test_une_candidature_inconnue_est_ajoutee_depuis_la_page(
    base: BaseLocale, chemins: Chemins
) -> None:
    assert demander(base, chemins) == 1
    candidature = base.trouver(OFFRE.cle)
    assert candidature is not None
    assert candidature.statut == "close"
    assert candidature.offre.description == "Texte de l'offre"
    assert base.preparations_en_attente() == [OFFRE.cle]


@pytest.mark.spec("PREP-12")
def test_seules_les_sections_permises_partent_et_jamais_le_plancher() -> None:
    infos = infos_permises(INFOS)
    assert "Préavis : 3 mois" in infos
    assert "Télétravail" in infos
    assert "nouveau défi" in infos
    for absent in ("plancher", "65K", "Critère de tri", "Jean Exemple", "06 00", "Master"):
        assert absent not in infos


@pytest.mark.spec("PREP-10", "PREP-11", "PREP-12")
def test_claude_recoit_tout_ce_qui_a_ete_envoye(base: BaseLocale, chemins: Chemins) -> None:
    (chemins.latex / "commun").mkdir()
    (chemins.latex / "commun" / "infos-candidature.md").write_text(INFOS, encoding="utf-8")
    dossier = chemins.candidatures / nom_dossier(OFFRE)
    dossier.mkdir(parents=True)
    (dossier / "cv.tex").write_text("\\setjob{Lead AI}", encoding="utf-8")
    (dossier / "lettre.tex").write_text("Ma lettre promet un POC", encoding="utf-8")
    demander(base, chemins)
    candidature = base.trouver(OFFRE.cle)
    demande = base.demande_preparation(OFFRE.cle)
    assert candidature is not None and demande is not None
    prompt = prompt_preparation(candidature, demande, chemins, "Mon profil")
    for attendu in (
        "Entreprise : Acme",
        "Poste : Lead AI",
        "Lien de l'offre : https://a",
        "Envoyée le : 2026-11-10",
        "Suite : entretien",
        "appel du recruteur",
        "Texte de l'offre",
        "\\setjob{Lead AI}",
        "Ma lettre promet un POC",
        "70 k€",
        "Jeudi 14 h",
        "## Consigne du candidat (prioritaire)\ninsiste sur le RAG",
        "Mon profil",
        "\\newcommand{\\pRAG}{RAG}",
        "Paragraphe.",
        "Préavis : 3 mois",
    ):
        assert attendu in prompt
    assert "plancher" not in prompt
    assert "Jean Exemple" not in prompt


@pytest.mark.spec("PREP-20", "CLA-04")
def test_l_appel_n_a_que_les_outils_web(base: BaseLocale, chemins: Chemins) -> None:
    demander(base, chemins)
    assistant = FauxAssistant(FICHE)
    assert preparer(base, assistant, chemins, "sonnet", "profil") == (1, [])
    assert assistant.outils == [OUTILS_WEB]
    assert assistant.modeles == ["sonnet"]
    assert assistant.delais == [900]


@pytest.mark.spec("CLA-04", "CLA-01")
def test_la_commande_claude_n_autorise_que_les_outils_demandes() -> None:
    appels: list[tuple[list[str], int]] = []

    def executeur(commande: Sequence[str], entree: str, delai: int) -> ResultatProcessus:
        appels.append((list(commande), delai))
        return ResultatProcessus(0, json.dumps({"result": "ok"}))

    claude = ClaudeCli(executeur)
    claude.demander("q", systeme="s", modele="haiku")
    claude.demander("q", systeme="s", modele="sonnet", outils=OUTILS_WEB, delai=900)
    (sans, delai_sans), (avec, delai_avec) = appels
    assert sans[sans.index("--tools") + 1] == ""
    assert "--allowedTools" not in sans
    assert avec[avec.index("--tools") + 1] == "WebSearch,WebFetch"
    assert avec[avec.index("--allowedTools") + 1] == "WebSearch,WebFetch"
    assert "mcp__*" in avec and "--strict-mcp-config" in avec
    assert (delai_sans, delai_avec) == (600, 900)


@pytest.mark.spec("PREP-21")
def test_une_fiche_ratee_reste_en_attente_et_les_autres_continuent(
    base: BaseLocale, chemins: Chemins
) -> None:
    autre = Offre("Beta", "Head of AI")
    demander(base, chemins)
    demander(
        base,
        chemins,
        id=autre.cle,
        entreprise="Beta",
        poste="Head of AI",
        preparation_demandee_le="2026-11-19T12:00:00.000Z",
    )

    class Capricieux(FauxAssistant):
        def demander(self, prompt: str, **options: Any) -> str:
            if "Acme" in prompt:
                raise ErreurClaude("délai dépassé")
            return super().demander(prompt, **options)

    reussites, echecs = preparer(base, Capricieux(FICHE), chemins, "sonnet", "")
    assert reussites == 1
    assert len(echecs) == 1 and "Acme" in echecs[0]
    assert base.preparations_en_attente() == [OFFRE.cle]


@pytest.mark.spec("PREP-32", "ECH-03")
def test_la_fiche_est_ecrite_stockee_et_envoyee_a_la_page(
    base: BaseLocale, chemins: Chemins
) -> None:
    demander(base, chemins)
    reponse = f"Voici la fiche.\n\n{FICHE}"
    preparer(
        base,
        FauxAssistant(reponse),
        chemins,
        "sonnet",
        "",
        horloge=lambda: "2026-11-19T10:05:00.000Z",
    )
    dossier = chemins.candidatures / nom_dossier(OFFRE)
    assert (dossier / FICHIER_FICHE).read_text(encoding="utf-8") == FICHE + "\n"
    assert (dossier / "offre.md").exists()
    (ligne,) = pour_la_page(base.pour_la_page(), chemins.racine)
    assert ligne["preparation"] == FICHE + "\n"
    assert ligne["preparation_le"] == "2026-11-19T10:05:00.000Z"
    # A new request replaces the previous sheet.
    demander(base, chemins, preparation_demandee_le="2026-11-20T00:00:00.000Z")
    preparer(
        base,
        FauxAssistant("# Nouvelle"),
        chemins,
        "sonnet",
        "",
        horloge=lambda: "2026-11-20T00:05:00.000Z",
    )
    assert (dossier / FICHIER_FICHE).read_text(encoding="utf-8") == "# Nouvelle\n"


@pytest.mark.spec("PREP-32")
def test_une_fiche_trop_longue_est_coupee() -> None:
    fiche = nettoyer_fiche("# Fiche\n" + "x" * (LONGUEUR_MAX * 2))
    assert len(fiche) <= LONGUEUR_MAX
    assert fiche.endswith(COUPEE + "\n")
    assert nettoyer_fiche("```markdown\n# Fiche\nTexte\n```") == "# Fiche\nTexte\n"
    with pytest.raises(ErreurClaude):
        nettoyer_fiche("   ")


@pytest.mark.spec("PREP-40")
def test_preparer_traite_les_cles_donnees_ou_toutes_les_demandes(
    base: BaseLocale, chemins: Chemins
) -> None:
    base.ajouter([OFFRE])
    assert preparer(base, FauxAssistant(FICHE), chemins, "sonnet", "") == (0, [])
    assert preparer(base, FauxAssistant(FICHE), chemins, "sonnet", "", [OFFRE.cle]) == (1, [])
    assert preparer(base, FauxAssistant(FICHE), chemins, "sonnet", "", ["inconnue"])[1] == [
        "inconnue : inconnue de la base locale"
    ]


@pytest.mark.spec("PREP-42")
def test_une_demande_arrivee_pendant_la_course_est_traitee(
    base: BaseLocale, chemins: Chemins
) -> None:
    autre = Offre("Beta", "Head of AI")
    demander(base, chemins)

    class Pendant(FauxAssistant):
        def demander(self, prompt: str, **options: Any) -> str:
            if len(self.prompts) == 0:
                demander(
                    base,
                    chemins,
                    id=autre.cle,
                    entreprise="Beta",
                    poste="Head of AI",
                    preparation_demandee_le="2026-11-19T12:00:00.000Z",
                )
            return super().demander(prompt, **options)

    assert preparer_seul(base, Pendant(FICHE), chemins, "sonnet", "") == (2, [])
    assert base.preparations_en_attente() == []
    assert not chemin_verrou(chemins).exists()


@pytest.mark.spec("PREP-42")
def test_une_seule_preparation_a_la_fois(base: BaseLocale, chemins: Chemins) -> None:
    demander(base, chemins)
    fichier = chemin_verrou(chemins)
    fichier.write_text(str(os.getpid()), encoding="utf-8")
    assistant = FauxAssistant(FICHE)
    assert preparer_seul(base, assistant, chemins, "sonnet", "") is None
    assert assistant.prompts == []
    # A lock left by a process that no longer exists is ignored.
    fichier.write_text("999999999", encoding="utf-8")
    assert preparer_seul(base, assistant, chemins, "sonnet", "") == (1, [])
    assert not fichier.exists()


@pytest.mark.spec("PREP-42")
def test_le_verrou_est_rendu_meme_apres_une_erreur(tmp_path: Path) -> None:
    fichier = tmp_path / "v.lock"
    with pytest.raises(RuntimeError), verrou(fichier) as tenu:
        assert tenu
        raise RuntimeError
    assert not fichier.exists()


@pytest.mark.spec("PREP-41", "ECH-26")
def test_decisions_lance_la_preparation_seulement_pour_une_nouvelle_demande(
    chemins: Chemins,
) -> None:
    lancements: list[int] = []
    documents = {"candidatures": [document()]}
    bilan = outil_decisions(chemins, documents, lambda: lancements.append(1))
    assert bilan["preparations"] == 1
    assert lancements == [1]
    outil_decisions(chemins, documents, lambda: lancements.append(1))
    assert lancements == [1]
    sans = {"candidatures": [document(preparation_demandee_le="")]}
    outil_decisions(chemins, sans, lambda: lancements.append(1))
    assert lancements == [1]


@pytest.mark.spec("ECH-26")
def test_un_lancement_rate_ne_change_pas_la_reponse(chemins: Chemins) -> None:
    def en_panne() -> None:
        raise OSError("pas de python")

    bilan = outil_decisions(chemins, {"candidatures": [document()]}, en_panne)
    assert bilan["preparations"] == 1


@pytest.mark.spec("PREP-41", "PREP-43")
def test_le_lancement_est_detache_et_journalise(
    chemins: Chemins,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lances: list[dict[str, Any]] = []

    def popen(commande: list[str], **options: Any) -> None:
        options["stdout"].write("sortie\n")
        lances.append({"commande": commande, **options})

    monkeypatch.setattr("moteur.preparation.subprocess.Popen", popen)
    config = chemins.racine / "config.toml"
    journal = chemins.echange / "preparation.log"
    chemins.echange.mkdir()
    journal.write_text("ancienne course\n", encoding="utf-8")
    lancer_en_arriere_plan(config, chemins)
    (lance,) = lances
    assert lance["commande"][-3:] == ["--config", str(config), "preparer"]
    assert lance["start_new_session"] is True
    assert lance["stdin"] == subprocess.DEVNULL
    assert journal.read_text(encoding="utf-8") == "sortie\n"
    # Nothing is started while a run holds the lock.
    chemin_verrou(chemins).write_text(str(os.getpid()), encoding="utf-8")
    lancer_en_arriere_plan(config, chemins)
    assert len(lances) == 1


@pytest.mark.spec("PREP-01")
def test_une_demande_absente_ou_vide_n_est_pas_lue() -> None:
    (sans,) = decisions_depuis([document(preparation_demandee_le="")])
    assert sans.preparation is None
    (avec,) = decisions_depuis([document(pretentions="x" * 5000)])
    assert avec.preparation == DemandePreparation(
        "2026-11-19T10:00:00.000Z",
        "x" * 2000,
        "Jeudi 14 h, visio avec le CTO",
        "insiste sur le RAG",
        avec.preparation.contexte if avec.preparation else "",
    )
