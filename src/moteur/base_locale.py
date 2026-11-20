"""Base SQLite locale : ce que le moteur a déjà vu, noté, et ce qu'il doit générer."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import Self

from moteur.company_links import CompanyLinks, company_key
from moteur.modeles import Candidature, DemandePreparation, Note, Offre, normaliser
from moteur.refusal import DUPLICATE, Refusal

A_NOTER = "a_noter"
NOTEE = "notee"
ACCEPTEE = "acceptee"
GENEREE = "generee"
REFUSEE = "refusee"
CLOSE = "close"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candidatures (
    cle TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    entreprise TEXT NOT NULL,
    poste TEXT NOT NULL,
    lieu TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    salaire TEXT NOT NULL DEFAULT '',
    date_publication TEXT NOT NULL DEFAULT '',
    statut TEXT NOT NULL,
    score INTEGER,
    resume TEXT NOT NULL DEFAULT '',
    lettre_demandee INTEGER NOT NULL DEFAULT 0,
    langue TEXT NOT NULL DEFAULT 'fr',
    consigne TEXT NOT NULL DEFAULT '',
    cv_ref TEXT NOT NULL DEFAULT '',
    lettre_ref TEXT NOT NULL DEFAULT '',
    consigne_lettre TEXT NOT NULL DEFAULT '',
    date_ajout TEXT NOT NULL
)
"""

# Company links (LNK-01): what the config and the lookup gave, and User's corrections
# from the page, kept per application so that one can be withdrawn (BASE-13).
_COMPANY_SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS entreprises (
    cle TEXT PRIMARY KEY,
    site_config TEXT NOT NULL DEFAULT '',
    linkedin_config TEXT NOT NULL DEFAULT '',
    site_recherche TEXT NOT NULL DEFAULT '',
    linkedin_recherche TEXT NOT NULL DEFAULT '',
    recherchee_le TEXT NOT NULL DEFAULT ''
)
""",
    """
CREATE TABLE IF NOT EXISTS liens_corriges (
    candidature TEXT PRIMARY KEY,
    entreprise TEXT NOT NULL,
    site TEXT NOT NULL DEFAULT '',
    linkedin TEXT NOT NULL DEFAULT '',
    ordre INTEGER NOT NULL
)
""",
)

# Colonnes ajoutées après coup : créées au besoin dans les bases existantes.
_COLONNES_AJOUTEES = {
    "consigne_lettre": "TEXT NOT NULL DEFAULT ''",
    "motif_refus": "TEXT NOT NULL DEFAULT ''",
    "motif_detail": "TEXT NOT NULL DEFAULT ''",
    "refusee_le": "TEXT NOT NULL DEFAULT ''",
    "preparation_demandee_le": "TEXT NOT NULL DEFAULT ''",
    "pretentions": "TEXT NOT NULL DEFAULT ''",
    "entretien_infos": "TEXT NOT NULL DEFAULT ''",
    "preparation_consigne": "TEXT NOT NULL DEFAULT ''",
    "contexte_page": "TEXT NOT NULL DEFAULT ''",
    "preparation": "TEXT NOT NULL DEFAULT ''",
    "preparation_le": "TEXT NOT NULL DEFAULT ''",
}

# A request is pending while it is more recent than the sheet, or there is no sheet
# (PREP-02). Both times use the `toISOString()` format, so they compare as text.
_EN_ATTENTE = "preparation_demandee_le != '' AND preparation_demandee_le > preparation_le"

# Statut de la page de suivi -> statut local. Les statuts absents ne changent rien.
_DECISIONS = {"acceptee": ACCEPTEE, "refusee": REFUSEE, "postulee": CLOSE}


def _candidature(ligne: sqlite3.Row) -> Candidature:
    return Candidature(
        offre=Offre(
            entreprise=ligne["entreprise"],
            poste=ligne["poste"],
            type="spontanee" if ligne["type"] == "spontanee" else "offre",
            lieu=ligne["lieu"],
            url=ligne["url"],
            source=ligne["source"],
            description=ligne["description"],
            salaire=ligne["salaire"],
            date_publication=ligne["date_publication"],
        ),
        statut=ligne["statut"],
        score=ligne["score"],
        resume=ligne["resume"],
        lettre_demandee=bool(ligne["lettre_demandee"]),
        langue="en" if ligne["langue"] == "en" else "fr",
        consigne=ligne["consigne"],
        cv_ref=ligne["cv_ref"],
        lettre_ref=ligne["lettre_ref"],
        consigne_lettre=ligne["consigne_lettre"],
        preparation=ligne["preparation"],
        preparation_le=ligne["preparation_le"],
    )


class BaseLocale:
    def __init__(self, chemin: Path | str) -> None:
        self._connexion = sqlite3.connect(str(chemin))
        self._connexion.row_factory = sqlite3.Row
        with self._connexion:
            self._connexion.execute(_SCHEMA)
            for schema in _COMPANY_SCHEMA:
                self._connexion.execute(schema)
            existantes = {
                ligne["name"]
                for ligne in self._connexion.execute("PRAGMA table_info(candidatures)")
            }
            for colonne, definition in _COLONNES_AJOUTEES.items():
                if colonne not in existantes:
                    self._connexion.execute(
                        f"ALTER TABLE candidatures ADD COLUMN {colonne} {definition}"
                    )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        type_erreur: type[BaseException] | None,
        erreur: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.fermer()

    def fermer(self) -> None:
        self._connexion.close()

    def ajouter(self, offres: Iterable[Offre]) -> int:
        """Ajoute les offres inconnues et renvoie leur nombre.

        Une candidature spontanée n'a rien à noter : elle est proposée telle quelle.
        """
        ajoutees = 0
        with self._connexion:
            for offre in offres:
                curseur = self._connexion.execute(
                    "INSERT OR IGNORE INTO candidatures (cle, type, entreprise, poste, lieu, url,"
                    " source, description, salaire, date_publication, statut, lettre_demandee,"
                    " date_ajout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        offre.cle,
                        offre.type,
                        offre.entreprise,
                        offre.poste,
                        offre.lieu,
                        offre.url,
                        offre.source,
                        offre.description,
                        offre.salaire,
                        offre.date_publication,
                        NOTEE if offre.type == "spontanee" else A_NOTER,
                        int(offre.type == "spontanee"),
                        date.today().isoformat(),
                    ),
                )
                ajoutees += curseur.rowcount
        return ajoutees

    def _par_statut(self, *statuts: str) -> list[Candidature]:
        marques = ", ".join("?" for _ in statuts)
        lignes = self._connexion.execute(
            f"SELECT * FROM candidatures WHERE statut IN ({marques}) ORDER BY date_ajout, cle",
            statuts,
        ).fetchall()
        return [_candidature(ligne) for ligne in lignes]

    def a_noter(self) -> list[Offre]:
        return [c.offre for c in self._par_statut(A_NOTER)]

    def enregistrer_note(self, cle: str, note: Note) -> None:
        with self._connexion:
            self._connexion.execute(
                "UPDATE candidatures SET statut = ?, score = ?, resume = ?, lettre_demandee = ?,"
                " langue = ? WHERE cle = ? AND statut = ?",
                (
                    NOTEE,
                    note.score,
                    note.resume,
                    int(note.lettre_demandee),
                    note.langue,
                    cle,
                    A_NOTER,
                ),
            )

    def pour_la_page(self) -> list[Candidature]:
        """What the page must know: scored proposals, ready folders (BASE-04) and every
        application with a preparation sheet, whatever its status (ECH-03)."""
        lignes = self._connexion.execute(
            "SELECT * FROM candidatures WHERE statut IN (?, ?) OR preparation != ''"
            " ORDER BY date_ajout, cle",
            (NOTEE, GENEREE),
        ).fetchall()
        return [_candidature(ligne) for ligne in lignes]

    def a_generer(self) -> list[Candidature]:
        return self._par_statut(ACCEPTEE)

    def appliquer_decision(self, cle: str, statut_page: str, consigne: str = "") -> bool:
        """Reporte une décision prise dans la page. Renvoie vrai si la base a changé.

        Un dossier déjà généré que la page montre encore « acceptée » (export pas
        encore réimporté) n'est régénéré que si une consigne de retouche l'accompagne.
        """
        statut = _DECISIONS.get(statut_page)
        if statut is None:
            return False
        if statut == ACCEPTEE and not consigne:
            condition = " AND statut != ?"
            parametres: tuple[str, ...] = (GENEREE,)
        else:
            condition, parametres = "", ()
        # Leaving `refusee` clears the reason; entering it records the day (BASE-11).
        with self._connexion:
            curseur = self._connexion.execute(
                "UPDATE candidatures SET"
                " motif_refus = CASE WHEN ? = ? THEN motif_refus ELSE '' END,"
                " motif_detail = CASE WHEN ? = ? THEN motif_detail ELSE '' END,"
                " refusee_le = CASE WHEN ? != ? THEN '' WHEN statut != ? THEN ?"
                " ELSE refusee_le END,"
                " statut = ?, consigne = ?"
                " WHERE cle = ? AND (statut != ? OR consigne != ?)" + condition,
                (
                    statut,
                    REFUSEE,
                    statut,
                    REFUSEE,
                    statut,
                    REFUSEE,
                    REFUSEE,
                    date.today().isoformat(),
                    statut,
                    consigne,
                    cle,
                    statut,
                    consigne,
                    *parametres,
                ),
            )
        return curseur.rowcount > 0

    def set_refusal_reason(self, cle: str, reason: str, detail: str) -> bool:
        """Stores the page's refusal reason of a `refusee` application (BASE-11)."""
        with self._connexion:
            curseur = self._connexion.execute(
                "UPDATE candidatures SET motif_refus = ?, motif_detail = ?"
                " WHERE cle = ? AND statut = ? AND (motif_refus != ? OR motif_detail != ?)",
                (reason, detail, cle, REFUSEE, reason, detail),
            )
        return curseur.rowcount > 0

    def recent_refusals(self, limit: int) -> list[Refusal]:
        """Most recent refusals that have a reason, duplicates excepted (NOT-08)."""
        lignes = self._connexion.execute(
            "SELECT entreprise, poste, motif_refus, motif_detail FROM candidatures"
            " WHERE statut = ? AND motif_refus NOT IN ('', ?)"
            " ORDER BY refusee_le DESC, date_ajout DESC, cle LIMIT ?",
            (REFUSEE, DUPLICATE, limit),
        ).fetchall()
        return [Refusal(*ligne) for ligne in lignes]

    def completer_depuis_la_page(
        self, cle: str, offre: Offre, lettre_demandee: bool, statut: str = ACCEPTEE
    ) -> bool:
        """Ajoute une candidature acceptée dans la page mais inconnue de la base.

        C'est le cas des offres ajoutées à la main ou trouvées par le moteur A. Pour une
        candidature déjà connue, complète seulement le texte de l'offre s'il manquait.
        Renvoie vrai si la base a changé.
        """
        with self._connexion:
            curseur = self._connexion.execute(
                "INSERT OR IGNORE INTO candidatures (cle, type, entreprise, poste, lieu, url,"
                " source, description, statut, lettre_demandee, date_ajout)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cle,
                    offre.type,
                    offre.entreprise,
                    offre.poste,
                    offre.lieu,
                    offre.url,
                    offre.source,
                    offre.description,
                    statut,
                    int(lettre_demandee),
                    date.today().isoformat(),
                ),
            )
            if curseur.rowcount:
                return True
            if not offre.description:
                return False
            curseur = self._connexion.execute(
                "UPDATE candidatures SET description = ? WHERE cle = ? AND description = ''",
                (offre.description, cle),
            )
        return curseur.rowcount > 0

    def fixer_lettre(self, cle: str, avec_lettre: bool) -> bool:
        """Reporte le choix « lettre oui / non » de la page. Renvoie vrai si la base a changé."""
        with self._connexion:
            curseur = self._connexion.execute(
                "UPDATE candidatures SET lettre_demandee = ?"
                " WHERE cle = ? AND lettre_demandee != ?",
                (int(avec_lettre), cle, int(avec_lettre)),
            )
        return curseur.rowcount > 0

    def lettres_manquantes(self) -> list[Candidature]:
        """Dossiers générés pour lesquels une lettre est prévue mais pas encore faite."""
        return [c for c in self._par_statut(GENEREE) if c.lettre_demandee and not c.lettre_ref]

    def trouver(self, cle: str) -> Candidature | None:
        ligne = self._connexion.execute(
            "SELECT * FROM candidatures WHERE cle = ?", (cle,)
        ).fetchone()
        return _candidature(ligne) if ligne else None

    def redemander_lettre(self, cle: str, consigne: str = "") -> bool:
        """Remet la lettre d'un dossier généré dans la file « à générer »."""
        with self._connexion:
            curseur = self._connexion.execute(
                "UPDATE candidatures SET lettre_ref = '', lettre_demandee = 1,"
                " consigne_lettre = ? WHERE cle = ? AND statut = ?",
                (consigne, cle, GENEREE),
            )
        return curseur.rowcount > 0

    def marquer_lettre(self, cle: str, lettre_ref: str) -> None:
        with self._connexion:
            self._connexion.execute(
                "UPDATE candidatures SET lettre_ref = ?, lettre_demandee = 1,"
                " consigne_lettre = '' WHERE cle = ?",
                (lettre_ref, cle),
            )

    def marquer_generee(self, cle: str, cv_ref: str, lettre_ref: str) -> None:
        with self._connexion:
            self._connexion.execute(
                "UPDATE candidatures SET statut = ?, cv_ref = ?, lettre_ref = ?, consigne = ''"
                " WHERE cle = ?",
                (GENEREE, cv_ref, lettre_ref, cle),
            )

    def demander_preparation(self, cle: str, demande: DemandePreparation) -> bool:
        """Stores a preparation request (BASE-12); an older or identical one changes nothing.

        Returns true if the request is new. The status is never changed.
        """
        with self._connexion:
            curseur = self._connexion.execute(
                "UPDATE candidatures SET preparation_demandee_le = ?, pretentions = ?,"
                " entretien_infos = ?, preparation_consigne = ?, contexte_page = ?"
                " WHERE cle = ? AND preparation_demandee_le < ?",
                (
                    demande.demandee_le,
                    demande.pretentions,
                    demande.entretien_infos,
                    demande.consigne,
                    demande.contexte,
                    cle,
                    demande.demandee_le,
                ),
            )
        return curseur.rowcount > 0

    def demande_preparation(self, cle: str) -> DemandePreparation | None:
        """The last preparation request of an application, or None if there is none."""
        ligne = self._connexion.execute(
            "SELECT preparation_demandee_le, pretentions, entretien_infos,"
            " preparation_consigne, contexte_page FROM candidatures"
            " WHERE cle = ? AND preparation_demandee_le != ''",
            (cle,),
        ).fetchone()
        return DemandePreparation(*ligne) if ligne else None

    def preparations_en_attente(self) -> list[str]:
        """Identifiers of the applications whose preparation is pending (PREP-02)."""
        lignes = self._connexion.execute(
            f"SELECT cle FROM candidatures WHERE {_EN_ATTENTE}"
            " ORDER BY preparation_demandee_le, cle"
        ).fetchall()
        return [ligne["cle"] for ligne in lignes]

    def enregistrer_preparation(self, cle: str, texte: str, faite_le: str) -> None:
        """Stores a successful sheet (PREP-32); the status does not change."""
        with self._connexion:
            self._connexion.execute(
                "UPDATE candidatures SET preparation = ?, preparation_le = ? WHERE cle = ?",
                (texte, faite_le, cle),
            )

    def entreprises_connues(self) -> set[str]:
        lignes = self._connexion.execute("SELECT DISTINCT entreprise FROM candidatures").fetchall()
        return {normaliser(ligne["entreprise"]) for ligne in lignes}

    def set_config_links(self, links: Mapping[str, CompanyLinks]) -> None:
        """Replaces the links given by `config.toml` with the current ones (CONF-09)."""
        with self._connexion:
            self._connexion.execute("UPDATE entreprises SET site_config = '', linkedin_config = ''")
            for key, found in links.items():
                self._connexion.execute(
                    "INSERT INTO entreprises (cle, site_config, linkedin_config) VALUES (?, ?, ?)"
                    " ON CONFLICT (cle) DO UPDATE SET site_config = excluded.site_config,"
                    " linkedin_config = excluded.linkedin_config",
                    (key, found.site, found.linkedin),
                )

    def record_lookup(self, key: str, found: CompanyLinks, day: str) -> None:
        """Stores a lookup result, found or not, with its date (LNK-14)."""
        with self._connexion:
            self._connexion.execute(
                "INSERT INTO entreprises (cle, site_recherche, linkedin_recherche,"
                " recherchee_le) VALUES (?, ?, ?, ?) ON CONFLICT (cle) DO UPDATE SET"
                " site_recherche = excluded.site_recherche,"
                " linkedin_recherche = excluded.linkedin_recherche,"
                " recherchee_le = excluded.recherchee_le",
                (key, found.site, found.linkedin, day),
            )

    def company_lookups(self) -> dict[str, str]:
        """Date of the last lookup, by company key."""
        lignes = self._connexion.execute(
            "SELECT cle, recherchee_le FROM entreprises WHERE recherchee_le != ''"
        ).fetchall()
        return {ligne["cle"]: ligne["recherchee_le"] for ligne in lignes}

    def correct_links(self, application: str, company: str, found: CompanyLinks | None) -> bool:
        """Stores User's correction made on an application, or withdraws it when `found`
        is None (BASE-13). Returns true if something changed."""
        with self._connexion:
            if found is None or not (found.site or found.linkedin):
                curseur = self._connexion.execute(
                    "DELETE FROM liens_corriges WHERE candidature = ?", (application,)
                )
                return curseur.rowcount > 0
            curseur = self._connexion.execute(
                "INSERT INTO liens_corriges (candidature, entreprise, site, linkedin, ordre)"
                " VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(ordre), 0) + 1 FROM liens_corriges))"
                " ON CONFLICT (candidature) DO UPDATE SET entreprise = excluded.entreprise,"
                " site = excluded.site, linkedin = excluded.linkedin, ordre = excluded.ordre"
                " WHERE entreprise != excluded.entreprise OR site != excluded.site"
                " OR linkedin != excluded.linkedin",
                (application, company_key(company), found.site, found.linkedin),
            )
        return curseur.rowcount > 0

    def company_links(self) -> dict[str, CompanyLinks]:
        """Each company's links: correction, then config, then lookup (LNK-02)."""
        resultat: dict[str, CompanyLinks] = {}
        for ligne in self._connexion.execute("SELECT * FROM entreprises"):
            resultat[ligne["cle"]] = CompanyLinks(
                ligne["site_config"], ligne["linkedin_config"]
            ).over(CompanyLinks(ligne["site_recherche"], ligne["linkedin_recherche"]))
        corrections: dict[str, CompanyLinks] = {}
        # Most recent correction first: it wins, link by link.
        for ligne in self._connexion.execute(
            "SELECT entreprise, site, linkedin FROM liens_corriges ORDER BY ordre DESC"
        ):
            precedente = corrections.get(ligne["entreprise"], CompanyLinks())
            corrections[ligne["entreprise"]] = precedente.over(
                CompanyLinks(ligne["site"], ligne["linkedin"])
            )
        for key, correction in corrections.items():
            resultat[key] = correction.over(resultat.get(key, CompanyLinks()))
        return {key: links for key, links in resultat.items() if links.site or links.linkedin}
