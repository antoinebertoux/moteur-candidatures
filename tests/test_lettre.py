import json
from pathlib import Path

import pytest

from moteur.base_locale import BaseLocale
from moteur.claude_cli import ResultatProcessus
from moteur.config import Chemins
from moteur.echange import Decision, date_fichier, lire_decisions, pour_la_page
from moteur.generation import Compilateur
from moteur.lettre import generer_lettre, generer_lettres
from moteur.modeles import Candidature, Offre, lettre_par_defaut
from tests.conftest import FauxAssistant
from tests.test_generation import TEX, chemins  # noqa: F401  (fixture partagée)

OFFRE = Offre("Banque de France", "AI/ML Engineer", description="Texte")


def compilateur(sortie: str = "") -> tuple[list[str], Compilateur]:
    fichiers: list[str] = []

    def compiler(dossier: Path, fichier: str) -> ResultatProcessus:
        fichiers.append(fichier)
        return ResultatProcessus(0, sortie)

    return fichiers, compiler


@pytest.mark.parametrize(
    ("offre", "attendu"),
    [
        (Offre("Direction générale de la sécurité intérieure", "DS"), True),
        (Offre("Secrétariat Général", "AI Engineer", source="service_public"), True),
        (Offre("Rothschild & Co", "DS"), True),
        (Offre("Société Générale", "DS"), True),
        (Offre("Qevlar AI", "Lead AI", type="spontanee"), True),
        (Offre("Mistral AI", "Applied AI"), False),
        (Offre("Publicis", "DS"), False),
    ],
)
@pytest.mark.spec("ID-04")
def test_lettre_par_defaut(offre: Offre, attendu: bool) -> None:
    assert lettre_par_defaut(offre) is attendu


@pytest.mark.spec("LET-02", "ECH-11")
def test_l_interrupteur_de_la_page_l_emporte_sur_la_regle() -> None:
    (banque_sans,) = lire_decisions(
        json.dumps(
            [
                {
                    "id": "x",
                    "statut": "acceptee",
                    "entreprise": "BNP Paribas",
                    "poste": "DS",
                    "lettre": "non",
                }
            ]
        )
    )
    (startup_avec,) = lire_decisions(
        json.dumps(
            [
                {
                    "id": "y",
                    "statut": "acceptee",
                    "entreprise": "Mistral AI",
                    "poste": "DS",
                    "lettre": "oui",
                }
            ]
        )
    )
    (startup_defaut,) = lire_decisions(
        json.dumps([{"id": "z", "statut": "acceptee", "entreprise": "Mistral AI", "poste": "DS"}])
    )
    assert banque_sans.avec_lettre is False
    assert startup_avec.avec_lettre is True
    assert startup_defaut.avec_lettre is False


@pytest.mark.spec("BASE-08")
def test_fixer_lettre_et_lettres_manquantes(tmp_path: Path) -> None:
    with BaseLocale(tmp_path / "b.sqlite3") as base:
        base.ajouter([OFFRE])
        base.completer_depuis_la_page(OFFRE.cle, OFFRE, False)
        base.appliquer_decision(OFFRE.cle, "acceptee")
        base.marquer_generee(OFFRE.cle, "Candidatures/x/cv.pdf", "")
        assert base.lettres_manquantes() == []
        assert base.fixer_lettre(OFFRE.cle, True)
        assert not base.fixer_lettre(OFFRE.cle, True)
        assert [c.offre.cle for c in base.lettres_manquantes()] == [OFFRE.cle]
        base.marquer_lettre(OFFRE.cle, "Candidatures/x/lettre.pdf")
        assert base.lettres_manquantes() == []


@pytest.mark.spec("LET-04")
def test_generer_lettre_ne_touche_pas_au_cv(chemins: Chemins) -> None:  # noqa: F811
    dossier = chemins.candidatures / "Banque de France - AI ML Engineer"
    dossier.mkdir(parents=True)
    (dossier / "cv.tex").write_text("CV intact", encoding="utf-8")
    fichiers, compiler = compilateur()
    ref = generer_lettre(Candidature(OFFRE, "generee"), FauxAssistant(TEX), chemins, "m", compiler)
    assert fichiers == ["lettre.tex"]
    assert (dossier / "cv.tex").read_text(encoding="utf-8") == "CV intact"
    assert (dossier / "lettre.tex").exists()
    assert ref.endswith("lettre.pdf")


@pytest.mark.spec("LET-06")
def test_generer_lettres_signale_une_lettre_trop_longue_et_une_cle_inconnue(
    chemins: Chemins,  # noqa: F811
) -> None:
    _, compiler = compilateur("⚠️  lettre.pdf fait 2 pages")
    with BaseLocale(chemins.base) as base:
        base.ajouter([OFFRE])
        reussites, echecs = generer_lettres(
            base, FauxAssistant(TEX), chemins, "m", compiler, [OFFRE.cle, "inconnue"]
        )
        assert reussites == 0
        assert len(echecs) == 2
        assert "2 pages" in echecs[1]
        assert base.trouver(OFFRE.cle) is not None
        assert base.trouver(OFFRE.cle).lettre_ref == ""  # type: ignore[union-attr]


@pytest.mark.spec("LET-07")
def test_regenerer_la_lettre_seulement_si_la_demande_est_plus_recente(tmp_path: Path) -> None:
    from moteur.decisions import lettres_a_refaire

    lettre = tmp_path / "Candidatures" / "x" / "lettre.pdf"
    lettre.parent.mkdir(parents=True)
    lettre.write_bytes(b"%PDF")
    faite_le = date_fichier(lettre)
    assert faite_le is not None
    with BaseLocale(tmp_path / "b.sqlite3") as base:
        base.ajouter([OFFRE])
        base.appliquer_decision(OFFRE.cle, "acceptee")
        base.marquer_generee(OFFRE.cle, "Candidatures/x/cv.pdf", "Candidatures/x/lettre.pdf")
        ancienne = Decision(OFFRE.cle, "prete", lettre_refaire_le="2000-01-01T00:00:00.000Z")
        assert lettres_a_refaire([ancienne], base, tmp_path) == 0
        demande = Decision(
            OFFRE.cle,
            "prete",
            lettre_refaire_le="2999-01-01T00:00:00.000Z",
            lettre_consigne="Plus court",
        )
        assert lettres_a_refaire([demande], base, tmp_path) == 1
        (manquante,) = base.lettres_manquantes()
        assert manquante.consigne_lettre == "Plus court"
        base.marquer_lettre(OFFRE.cle, "Candidatures/x/lettre.pdf")
        assert base.trouver(OFFRE.cle).consigne_lettre == ""  # type: ignore[union-attr]


@pytest.mark.spec("LET-05")
def test_la_consigne_de_lettre_repart_de_la_lettre_existante(chemins: Chemins) -> None:  # noqa: F811
    dossier = chemins.candidatures / "Banque de France - AI ML Engineer"
    dossier.mkdir(parents=True)
    (dossier / "lettre.tex").write_text("ANCIENNE LETTRE", encoding="utf-8")
    assistant = FauxAssistant(TEX)
    _, compiler = compilateur()
    candidature = Candidature(OFFRE, "generee", consigne_lettre="Plus court")
    generer_lettre(candidature, assistant, chemins, "m", compiler)
    assert "ANCIENNE LETTRE" in assistant.prompts[0]
    assert "Plus court" in assistant.prompts[0]


@pytest.mark.spec("ECH-02")
def test_export_donne_la_date_de_la_lettre(tmp_path: Path) -> None:
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "lettre.pdf").write_bytes(b"%PDF")
    candidature = Candidature(OFFRE, "generee", cv_ref="x/cv.pdf", lettre_ref="x/lettre.pdf")
    (ligne,) = pour_la_page([candidature], tmp_path)
    assert ligne["lettre_generee_le"].endswith("Z")


@pytest.mark.spec("BASE-10")
def test_ancienne_base_sans_colonne_consigne_lettre(tmp_path: Path) -> None:
    import sqlite3

    chemin = tmp_path / "vieille.sqlite3"
    connexion = sqlite3.connect(chemin)
    connexion.execute(
        "CREATE TABLE candidatures (cle TEXT PRIMARY KEY, type TEXT NOT NULL,"
        " entreprise TEXT NOT NULL, poste TEXT NOT NULL, lieu TEXT NOT NULL DEFAULT '',"
        " url TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',"
        " description TEXT NOT NULL DEFAULT '', salaire TEXT NOT NULL DEFAULT '',"
        " date_publication TEXT NOT NULL DEFAULT '', statut TEXT NOT NULL, score INTEGER,"
        " resume TEXT NOT NULL DEFAULT '', lettre_demandee INTEGER NOT NULL DEFAULT 0,"
        " langue TEXT NOT NULL DEFAULT 'fr', consigne TEXT NOT NULL DEFAULT '',"
        " cv_ref TEXT NOT NULL DEFAULT '', lettre_ref TEXT NOT NULL DEFAULT '',"
        " date_ajout TEXT NOT NULL)"
    )
    connexion.commit()
    connexion.close()
    with BaseLocale(chemin) as base:
        base.ajouter([OFFRE])
        assert base.trouver(OFFRE.cle) is not None
