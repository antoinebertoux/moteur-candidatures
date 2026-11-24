"""Local SQLite database: what the engine has seen, scored, and must generate."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import Literal, Self, cast

from moteur.company_links import CompanyLinks, company_key
from moteur.config import AtsType, TargetCompany
from moteur.models import Application, JobAd, PrepKind, PrepRequest, Rating, normalise
from moteur.refusal import DUPLICATE, Refusal
from moteur.selection import Choice, Choices

TO_SCORE = "a_noter"
SCORED = "notee"
ACCEPTED = "acceptee"
GENERATED = "generee"
REJECTED = "refusee"
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
    # User's choices of companies, sectors, sizes and sources (BASE-15).
    """
CREATE TABLE IF NOT EXISTS choix (
    objet TEXT NOT NULL,
    cle TEXT NOT NULL,
    champ TEXT NOT NULL,
    valeur INTEGER NOT NULL,
    PRIMARY KEY (objet, cle, champ)
)
""",
    # The search criteria User replaced in the page (BASE-17); `valeurs` is a JSON list.
    """
CREATE TABLE IF NOT EXISTS criteres (
    cle TEXT PRIMARY KEY,
    valeurs TEXT NOT NULL
)
""",
    # User's own companies (BASE-16); `pays` holds the codes separated by commas.
    """
CREATE TABLE IF NOT EXISTS entreprises_perso (
    cle TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    ats TEXT NOT NULL,
    identifiant TEXT NOT NULL,
    site TEXT NOT NULL DEFAULT '',
    linkedin TEXT NOT NULL DEFAULT '',
    secteur TEXT NOT NULL,
    taille TEXT NOT NULL,
    pays TEXT NOT NULL DEFAULT '',
    modifiee_le TEXT NOT NULL
)
""",
)

# Columns added later: created when missing in existing databases.
_ADDED_COLUMNS = {
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
    "preparation_technique_demandee_le": "TEXT NOT NULL DEFAULT ''",
    "retour_entretien_rh": "TEXT NOT NULL DEFAULT ''",
    "preparation_technique": "TEXT NOT NULL DEFAULT ''",
    "preparation_technique_le": "TEXT NOT NULL DEFAULT ''",
}

# Columns of each kind of sheet: request time, sheet, sheet time (PREP-50).
_PREP_COLUMNS: dict[PrepKind, tuple[str, str, str]] = {
    "rh": ("preparation_demandee_le", "preparation", "preparation_le"),
    "technique": (
        "preparation_technique_demandee_le",
        "preparation_technique",
        "preparation_technique_le",
    ),
}


def _pending(kind: PrepKind) -> str:
    """A request is pending while it is more recent than the sheet of its kind, or there
    is no such sheet (PREP-02). Both times use the `toISOString()` format, so they compare
    as text."""
    requested, _, made = _PREP_COLUMNS[kind]
    return f"{requested} != '' AND {requested} > {made}"


SaveOutcome = Literal["added", "updated", "unchanged"]

# Tracking page status -> local status. Missing statuses change nothing.
_DECISIONS = {"acceptee": ACCEPTED, "refusee": REJECTED, "postulee": CLOSE}


def _application(row: sqlite3.Row) -> Application:
    return Application(
        ad=JobAd(
            company=row["entreprise"],
            title=row["poste"],
            type="spontanee" if row["type"] == "spontanee" else "offre",
            location=row["lieu"],
            url=row["url"],
            source=row["source"],
            description=row["description"],
            salary=row["salaire"],
            published_on=row["date_publication"],
        ),
        status=row["statut"],
        score=row["score"],
        summary=row["resume"],
        letter_requested=bool(row["lettre_demandee"]),
        language="en" if row["langue"] == "en" else "fr",
        instruction=row["consigne"],
        cv_ref=row["cv_ref"],
        letter_ref=row["lettre_ref"],
        letter_instruction=row["consigne_lettre"],
        preparation=row["preparation"],
        preparation_le=row["preparation_le"],
        technical_preparation=row["preparation_technique"],
        technical_preparation_le=row["preparation_technique_le"],
    )


class LocalDb:
    def __init__(self, path: Path | str) -> None:
        self._connection = sqlite3.connect(str(path))
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.execute(_SCHEMA)
            for schema in _COMPANY_SCHEMA:
                self._connection.execute(schema)
            existing = {
                row["name"] for row in self._connection.execute("PRAGMA table_info(candidatures)")
            }
            for column, definition in _ADDED_COLUMNS.items():
                if column not in existing:
                    self._connection.execute(
                        f"ALTER TABLE candidatures ADD COLUMN {column} {definition}"
                    )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def add(self, ads: Iterable[JobAd]) -> int:
        """Adds the unknown ads and returns how many.

        An unsolicited application has nothing to score: it is proposed as is.
        """
        added = 0
        with self._connection:
            for ad in ads:
                cursor = self._connection.execute(
                    "INSERT OR IGNORE INTO candidatures (cle, type, entreprise, poste, lieu, url,"
                    " source, description, salaire, date_publication, statut, lettre_demandee,"
                    " date_ajout) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ad.key,
                        ad.type,
                        ad.company,
                        ad.title,
                        ad.location,
                        ad.url,
                        ad.source,
                        ad.description,
                        ad.salary,
                        ad.published_on,
                        SCORED if ad.type == "spontanee" else TO_SCORE,
                        int(ad.type == "spontanee"),
                        date.today().isoformat(),
                    ),
                )
                added += cursor.rowcount
        return added

    def _by_status(self, *statuses: str) -> list[Application]:
        marks = ", ".join("?" for _ in statuses)
        rows = self._connection.execute(
            f"SELECT * FROM candidatures WHERE statut IN ({marks}) ORDER BY date_ajout, cle",
            statuses,
        ).fetchall()
        return [_application(row) for row in rows]

    def to_score(self) -> list[JobAd]:
        return [c.ad for c in self._by_status(TO_SCORE)]

    def record_score(self, key: str, rating: Rating) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE candidatures SET statut = ?, score = ?, resume = ?, lettre_demandee = ?,"
                " langue = ? WHERE cle = ? AND statut = ?",
                (
                    SCORED,
                    rating.score,
                    rating.summary,
                    int(rating.letter_requested),
                    rating.language,
                    key,
                    TO_SCORE,
                ),
            )

    def for_the_page(self) -> list[Application]:
        """What the page must know: scored proposals, ready folders (BASE-04) and every
        application with a preparation sheet, whatever its status (ECH-03)."""
        rows = self._connection.execute(
            "SELECT * FROM candidatures WHERE statut IN (?, ?) OR preparation != ''"
            " OR preparation_technique != ''"
            " ORDER BY date_ajout, cle",
            (SCORED, GENERATED),
        ).fetchall()
        return [_application(row) for row in rows]

    def archived_ad_texts(self) -> list[Application]:
        """Applied applications with an ad text that `for_the_page` does not already send:
        their text goes to the page so that it can still be read (ECH-06)."""
        rows = self._connection.execute(
            "SELECT * FROM candidatures WHERE statut = ? AND description != ''"
            " AND preparation = '' AND preparation_technique = ''"
            " ORDER BY date_ajout, cle",
            (CLOSE,),
        ).fetchall()
        return [_application(row) for row in rows]

    def complete_ad_text(self, key: str, text: str) -> bool:
        """Fills in a missing ad text, whatever the status (BASE-14). Returns true if the
        database changed; an existing text is never replaced."""
        if not text:
            return False
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE candidatures SET description = ? WHERE cle = ? AND description = ''",
                (text, key),
            )
        return cursor.rowcount > 0

    def to_generate(self) -> list[Application]:
        return self._by_status(ACCEPTED)

    def apply_decision(self, key: str, page_status: str, instruction: str = "") -> bool:
        """Records a decision made in the page. Returns true if the database changed.

        A folder already generated that the page still shows as accepted (export not
        imported yet) is only regenerated if an edit instruction comes with it.
        """
        status = _DECISIONS.get(page_status)
        if status is None:
            return False
        if status == ACCEPTED and not instruction:
            condition = " AND statut != ?"
            parameters: tuple[str, ...] = (GENERATED,)
        else:
            condition, parameters = "", ()
        # Leaving `refusee` clears the reason; entering it records the day (BASE-11).
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE candidatures SET"
                " motif_refus = CASE WHEN ? = ? THEN motif_refus ELSE '' END,"
                " motif_detail = CASE WHEN ? = ? THEN motif_detail ELSE '' END,"
                " refusee_le = CASE WHEN ? != ? THEN '' WHEN statut != ? THEN ?"
                " ELSE refusee_le END,"
                " statut = ?, consigne = ?"
                " WHERE cle = ? AND (statut != ? OR consigne != ?)" + condition,
                (
                    status,
                    REJECTED,
                    status,
                    REJECTED,
                    status,
                    REJECTED,
                    REJECTED,
                    date.today().isoformat(),
                    status,
                    instruction,
                    key,
                    status,
                    instruction,
                    *parameters,
                ),
            )
        return cursor.rowcount > 0

    def set_refusal_reason(self, key: str, reason: str, detail: str) -> bool:
        """Stores the page's refusal reason of a `refusee` application (BASE-11)."""
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE candidatures SET motif_refus = ?, motif_detail = ?"
                " WHERE cle = ? AND statut = ? AND (motif_refus != ? OR motif_detail != ?)",
                (reason, detail, key, REJECTED, reason, detail),
            )
        return cursor.rowcount > 0

    def recent_refusals(self, limit: int) -> list[Refusal]:
        """Most recent refusals that have a reason, duplicates excepted (NOT-08)."""
        rows = self._connection.execute(
            "SELECT entreprise, poste, motif_refus, motif_detail FROM candidatures"
            " WHERE statut = ? AND motif_refus NOT IN ('', ?)"
            " ORDER BY refusee_le DESC, date_ajout DESC, cle LIMIT ?",
            (REJECTED, DUPLICATE, limit),
        ).fetchall()
        return [Refusal(*row) for row in rows]

    def complete_from_the_page(
        self, key: str, ad: JobAd, letter_requested: bool, status: str = ACCEPTED
    ) -> bool:
        """Adds an application accepted in the page but unknown to the database.

        This is the case of ads added by hand or found by engine A. For an application
        already known, only completes the ad text if it was missing.
        Returns true if the database changed.
        """
        with self._connection:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO candidatures (cle, type, entreprise, poste, lieu, url,"
                " source, description, statut, lettre_demandee, date_ajout)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    ad.type,
                    ad.company,
                    ad.title,
                    ad.location,
                    ad.url,
                    ad.source,
                    ad.description,
                    status,
                    int(letter_requested),
                    date.today().isoformat(),
                ),
            )
            if cursor.rowcount:
                return True
        return self.complete_ad_text(key, ad.description)

    def set_letter(self, key: str, with_letter: bool) -> bool:
        """Records the page's "letter yes / no" choice. Returns true if the database changed."""
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE candidatures SET lettre_demandee = ?"
                " WHERE cle = ? AND lettre_demandee != ?",
                (int(with_letter), key, int(with_letter)),
            )
        return cursor.rowcount > 0

    def missing_letters(self) -> list[Application]:
        """Generated folders for which a letter is planned but not made yet."""
        return [c for c in self._by_status(GENERATED) if c.letter_requested and not c.letter_ref]

    def find(self, key: str) -> Application | None:
        row = self._connection.execute(
            "SELECT * FROM candidatures WHERE cle = ?", (key,)
        ).fetchone()
        return _application(row) if row else None

    def request_letter_again(self, key: str, instruction: str = "") -> bool:
        """Puts the letter of a generated folder back in the "to generate" queue."""
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE candidatures SET lettre_ref = '', lettre_demandee = 1,"
                " consigne_lettre = ? WHERE cle = ? AND statut = ?",
                (instruction, key, GENERATED),
            )
        return cursor.rowcount > 0

    def mark_letter(self, key: str, letter_ref: str) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE candidatures SET lettre_ref = ?, lettre_demandee = 1,"
                " consigne_lettre = '' WHERE cle = ?",
                (letter_ref, key),
            )

    def mark_generated(self, key: str, cv_ref: str, letter_ref: str) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE candidatures SET statut = ?, cv_ref = ?, lettre_ref = ?, consigne = ''"
                " WHERE cle = ?",
                (GENERATED, cv_ref, letter_ref, key),
            )

    def request_preparation(self, key: str, request: PrepRequest) -> bool:
        """Stores a preparation request (BASE-12); an older or identical request of the
        same kind changes nothing.

        Returns true if the request is new. The status is never changed.
        """
        requested = _PREP_COLUMNS[request.kind][0]
        with self._connection:
            cursor = self._connection.execute(
                f"UPDATE candidatures SET {requested} = ?, pretentions = ?,"
                " entretien_infos = ?, preparation_consigne = ?, contexte_page = ?,"
                f" retour_entretien_rh = ? WHERE cle = ? AND {requested} < ?",
                (
                    request.requested_at,
                    request.salary_expectations,
                    request.interview_details,
                    request.instruction,
                    request.context,
                    request.hr_feedback,
                    key,
                    request.requested_at,
                ),
            )
        return cursor.rowcount > 0

    def prep_request(self, key: str, kind: PrepKind = "rh") -> PrepRequest | None:
        """The last preparation request of a kind, or None if there is none."""
        requested = _PREP_COLUMNS[kind][0]
        row = self._connection.execute(
            f"SELECT {requested}, pretentions, entretien_infos, preparation_consigne,"
            f" contexte_page, retour_entretien_rh FROM candidatures"
            f" WHERE cle = ? AND {requested} != ''",
            (key,),
        ).fetchone()
        if not row:
            return None
        requested_at, salary, details, instruction, context, feedback = row
        return PrepRequest(requested_at, salary, details, instruction, context, kind, feedback)

    def pending_preparations(self, kind: PrepKind = "rh") -> list[str]:
        """Identifiers of the applications whose preparation of a kind is pending
        (PREP-02)."""
        requested = _PREP_COLUMNS[kind][0]
        rows = self._connection.execute(
            f"SELECT cle FROM candidatures WHERE {_pending(kind)} ORDER BY {requested}, cle"
        ).fetchall()
        return [row["cle"] for row in rows]

    def record_preparation(self, key: str, text: str, made_at: str, kind: PrepKind = "rh") -> None:
        """Stores a successful sheet in the columns of its kind (PREP-32, PREP-54); the
        status and the other kind's sheet do not change."""
        _, sheet, made = _PREP_COLUMNS[kind]
        with self._connection:
            self._connection.execute(
                f"UPDATE candidatures SET {sheet} = ?, {made} = ? WHERE cle = ?",
                (text, made_at, key),
            )

    def known_companies(self) -> set[str]:
        rows = self._connection.execute("SELECT DISTINCT entreprise FROM candidatures").fetchall()
        return {normalise(row["entreprise"]) for row in rows}

    def set_config_links(self, links: Mapping[str, CompanyLinks]) -> None:
        """Replaces the links given by `config.toml` with the current ones (CONF-09)."""
        with self._connection:
            self._connection.execute(
                "UPDATE entreprises SET site_config = '', linkedin_config = ''"
            )
            for key, found in links.items():
                self._connection.execute(
                    "INSERT INTO entreprises (cle, site_config, linkedin_config) VALUES (?, ?, ?)"
                    " ON CONFLICT (cle) DO UPDATE SET site_config = excluded.site_config,"
                    " linkedin_config = excluded.linkedin_config",
                    (key, found.site, found.linkedin),
                )

    def record_lookup(self, key: str, found: CompanyLinks, day: str) -> None:
        """Stores a lookup result, found or not, with its date (LNK-14)."""
        with self._connection:
            self._connection.execute(
                "INSERT INTO entreprises (cle, site_recherche, linkedin_recherche,"
                " recherchee_le) VALUES (?, ?, ?, ?) ON CONFLICT (cle) DO UPDATE SET"
                " site_recherche = excluded.site_recherche,"
                " linkedin_recherche = excluded.linkedin_recherche,"
                " recherchee_le = excluded.recherchee_le",
                (key, found.site, found.linkedin, day),
            )

    def company_lookups(self) -> dict[str, str]:
        """Date of the last lookup, by company key."""
        rows = self._connection.execute(
            "SELECT cle, recherchee_le FROM entreprises WHERE recherchee_le != ''"
        ).fetchall()
        return {row["cle"]: row["recherchee_le"] for row in rows}

    def correct_links(self, application: str, company: str, found: CompanyLinks | None) -> bool:
        """Stores User's correction made on an application, or withdraws it when `found`
        is None (BASE-13). Returns true if something changed."""
        with self._connection:
            if found is None or not (found.site or found.linkedin):
                cursor = self._connection.execute(
                    "DELETE FROM liens_corriges WHERE candidature = ?", (application,)
                )
                return cursor.rowcount > 0
            cursor = self._connection.execute(
                "INSERT INTO liens_corriges (candidature, entreprise, site, linkedin, ordre)"
                " VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(ordre), 0) + 1 FROM liens_corriges))"
                " ON CONFLICT (candidature) DO UPDATE SET entreprise = excluded.entreprise,"
                " site = excluded.site, linkedin = excluded.linkedin, ordre = excluded.ordre"
                " WHERE entreprise != excluded.entreprise OR site != excluded.site"
                " OR linkedin != excluded.linkedin",
                (application, company_key(company), found.site, found.linkedin),
            )
        return cursor.rowcount > 0

    def company_links(self) -> dict[str, CompanyLinks]:
        """Each company's links: correction, then config, then lookup (LNK-02)."""
        result: dict[str, CompanyLinks] = {}
        for row in self._connection.execute("SELECT * FROM entreprises"):
            result[row["cle"]] = CompanyLinks(row["site_config"], row["linkedin_config"]).over(
                CompanyLinks(row["site_recherche"], row["linkedin_recherche"])
            )
        corrections: dict[str, CompanyLinks] = {}
        # Most recent correction first: it wins, link by link.
        for row in self._connection.execute(
            "SELECT entreprise, site, linkedin FROM liens_corriges ORDER BY ordre DESC"
        ):
            previous = corrections.get(row["entreprise"], CompanyLinks())
            corrections[row["entreprise"]] = previous.over(
                CompanyLinks(row["site"], row["linkedin"])
            )
        for key, correction in corrections.items():
            result[key] = correction.over(result.get(key, CompanyLinks()))
        return {key: links for key, links in result.items() if links.site or links.linkedin}

    def choices(self) -> Choices:
        """User's choices (BASE-15), those about vanished companies included (CAT-16)."""
        rows = self._connection.execute("SELECT objet, cle, champ, valeur FROM choix")
        return Choices.of(
            Choice(row["objet"], row["cle"], row["champ"], bool(row["valeur"])) for row in rows
        )

    def record_choices(self, choices: Iterable[Choice]) -> None:
        """Records the choices at once; a None value goes back to the default (BASE-15)."""
        with self._connection:
            for choice in choices:
                if choice.value is None:
                    self._connection.execute(
                        "DELETE FROM choix WHERE objet = ? AND cle = ? AND champ = ?",
                        (choice.subject, choice.key, choice.field),
                    )
                else:
                    self._connection.execute(
                        "INSERT INTO choix (objet, cle, champ, valeur) VALUES (?, ?, ?, ?)"
                        " ON CONFLICT (objet, cle, champ) DO UPDATE SET valeur = excluded.valeur",
                        (choice.subject, choice.key, choice.field, int(choice.value)),
                    )

    def criteria(self) -> dict[str, tuple[str, ...]]:
        """The search criteria User replaced in the page (BASE-17), by list name."""
        rows = self._connection.execute("SELECT cle, valeurs FROM criteres")
        return {row["cle"]: tuple(json.loads(row["valeurs"])) for row in rows}

    def record_criteria(self, criteria: Mapping[str, tuple[str, ...] | None]) -> None:
        """Records the lists at once; None goes back to `config.toml` (BASE-17)."""
        with self._connection:
            for key, values in criteria.items():
                if values is None:
                    self._connection.execute("DELETE FROM criteres WHERE cle = ?", (key,))
                else:
                    self._connection.execute(
                        "INSERT INTO criteres (cle, valeurs) VALUES (?, ?)"
                        " ON CONFLICT (cle) DO UPDATE SET valeurs = excluded.valeurs",
                        (key, json.dumps(list(values), ensure_ascii=False)),
                    )

    def own_companies(self) -> tuple[TargetCompany, ...]:
        """User's own companies (BASE-16), in the order they were first added."""
        rows = self._connection.execute("SELECT * FROM entreprises_perso ORDER BY rowid")
        return tuple(
            TargetCompany(
                name=row["nom"],
                ats=cast(AtsType, row["ats"]),
                identifier=row["identifiant"],
                site=row["site"],
                linkedin=row["linkedin"],
                sector=row["secteur"],
                size=row["taille"],
                countries=tuple(code for code in row["pays"].split(",") if code),
                origin="perso",
            )
            for row in rows
        )

    def save_own_company(self, company: TargetCompany, day: str) -> SaveOutcome:
        """Adds an own company or replaces its fields (CAT-24, BASE-16).

        The same fields saved again change nothing, not even the date (CLI-10).
        """
        key = normalise(company.name)
        values = (
            company.name,
            company.ats,
            company.identifier,
            company.site,
            company.linkedin,
            company.sector,
            company.size,
            ",".join(company.countries),
        )
        with self._connection:
            current = self._connection.execute(
                "SELECT nom, ats, identifiant, site, linkedin, secteur, taille, pays"
                " FROM entreprises_perso WHERE cle = ?",
                (key,),
            ).fetchone()
            if current is not None and tuple(current) == values:
                return "unchanged"
            self._connection.execute(
                "INSERT INTO entreprises_perso (cle, nom, ats, identifiant, site, linkedin,"
                " secteur, taille, pays, modifiee_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (cle) DO UPDATE SET nom = excluded.nom, ats = excluded.ats,"
                " identifiant = excluded.identifiant, site = excluded.site,"
                " linkedin = excluded.linkedin, secteur = excluded.secteur,"
                " taille = excluded.taille, pays = excluded.pays,"
                " modifiee_le = excluded.modifiee_le",
                (key, *values, day),
            )
        return "added" if current is None else "updated"

    def remove_own_companies(self, keys: Iterable[str]) -> None:
        """Stops following these own companies; User's choices stay (CAT-25)."""
        with self._connection:
            self._connection.executemany(
                "DELETE FROM entreprises_perso WHERE cle = ?", [(key,) for key in keys]
            )
