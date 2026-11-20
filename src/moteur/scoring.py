"""Scoring ads in batches: one short call to Claude for several ads."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from moteur.claude_cli import Assistant, ClaudeError, extract_json
from moteur.local_db import LocalDb
from moteur.models import JobAd, Rating
from moteur.refusal import Refusal

log = logging.getLogger(__name__)

DESCRIPTION_LENGTH = 1500
SUMMARY_LENGTH = 400
REFUSALS_SHOWN = 40

_INSTRUCTIONS_BLOCK = """Tu tries des offres d'emploi pour le candidat décrit ci-dessous.
Pour chaque offre reçue, réponds par un objet JSON avec exactement ces champs :
- "cle" : la clé reçue, recopiée telle quelle ;
- "score" : entier de 0 à 100, adéquation entre l'offre et ce que cherche le candidat ;
- "resume" : deux phrases en français, ce qu'est le poste puis le point fort ou le point bloquant ;
- "lettre_demandee" : true seulement si l'offre demande une lettre de motivation ;
- "langue" : "en" si l'offre est rédigée en anglais, sinon "fr".
Réponds uniquement par un tableau JSON, sans texte autour.

Candidat :
"""


_REFUSALS = """

Offres que le candidat a récemment refusées, avec son motif. Baisse nettement la note \
des offres semblables pour le même motif :
"""


def system(profile: str, refusals: Sequence[Refusal] = ()) -> str:
    """Scoring instructions, the profile, then past refusals when there are some (NOT-08)."""
    text = _INSTRUCTIONS_BLOCK + profile
    if refusals:
        text += _REFUSALS + "\n".join(refusal.line() for refusal in refusals)
    return text


def build_scoring_prompt(ads: Sequence[JobAd]) -> str:
    return json.dumps(
        [
            {
                "cle": ad.key,
                "entreprise": ad.company,
                "poste": ad.title,
                "lieu": ad.location,
                "salaire": ad.salary,
                "description": ad.description[:DESCRIPTION_LENGTH],
            }
            for ad in ads
        ],
        ensure_ascii=False,
    )


def parse_answer(text: str, expected_keys: set[str]) -> dict[str, Rating]:
    """Extracts the valid ratings; ignores unknown or malformed entries."""
    data = extract_json(text)
    if not isinstance(data, list):
        raise ClaudeError("The scoring must be a JSON array")
    notes: dict[str, Rating] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        key = entry.get("cle")
        score = entry.get("score")
        if (
            key not in expected_keys
            or isinstance(score, bool)
            or not isinstance(score, int | float)
        ):
            continue
        notes[key] = Rating(
            score=max(0, min(100, round(score))),
            summary=str(entry.get("resume", ""))[:SUMMARY_LENGTH],
            letter_requested=entry.get("lettre_demandee") is True,
            language="en" if entry.get("langue") == "en" else "fr",
        )
    return notes


def score_ads(
    base: LocalDb, assistant: Assistant, *, profile: str, model: str, batch_size: int
) -> int:
    """Scores every waiting ad. A failed batch stays to be scored on the next run."""
    ads = base.to_score()
    instructions = system(profile, base.recent_refusals(REFUSALS_SHOWN))
    scored_count = 0
    for start in range(0, len(ads), batch_size):
        batch = ads[start : start + batch_size]
        try:
            answer = assistant.ask(build_scoring_prompt(batch), system=instructions, model=model)
            notes = parse_answer(answer, {ad.key for ad in batch})
        except ClaudeError as error:
            log.warning("Batch of %d ads not scored: %s", len(batch), error)
            continue
        for key, rating in notes.items():
            base.record_score(key, rating)
        scored_count += len(notes)
    return scored_count
