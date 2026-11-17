"""Base SQLite locale : ce que le moteur a déjà vu, noté, et ce qu'il doit générer."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import Self

from moteur.modeles import Candidature, Note, Offre, normaliser

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

# Colonnes ajoutées après coup : créées au besoin dans les bases existantes.
_COLONNES_AJOUTEES = {"consigne_lettre": "TEXT NOT NULL DEFAULT ''"}

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
    )


class BaseLocale:
    def __init__(self, chemin: Path | str) -> None:
        self._connexion = sqlite3.connect(str(chemin))
        self._connexion.row_factory = sqlite3.Row
        with self._connexion:
            self._connexion.execute(_SCHEMA)
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
        """Ce que la page de suivi doit connaître : propositions notées et dossiers générés."""
        return self._par_statut(NOTEE, GENEREE)

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
        with self._connexion:
            curseur = self._connexion.execute(
                "UPDATE candidatures SET statut = ?, consigne = ?"
                " WHERE cle = ? AND (statut != ? OR consigne != ?)" + condition,
                (statut, consigne, cle, statut, consigne, *parametres),
            )
        return curseur.rowcount > 0

    def completer_depuis_la_page(self, cle: str, offre: Offre, lettre_demandee: bool) -> bool:
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
                    ACCEPTEE,
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

    def entreprises_connues(self) -> set[str]:
        lignes = self._connexion.execute("SELECT DISTINCT entreprise FROM candidatures").fetchall()
        return {normaliser(ligne["entreprise"]) for ligne in lignes}
