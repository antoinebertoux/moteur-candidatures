"""Applies the page's decisions to the local database (file export or direct link)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from moteur import exchange
from moteur.local_db import ACCEPTED, CLOSE, LocalDb


@dataclass(frozen=True, slots=True)
class Outcome:
    """What a batch of decisions changed, and what is left to do."""

    decisions: int
    completed: int
    letters: int
    to_generate: int
    letters_to_add: int
    preparations: int = 0
    """New interview preparation requests recorded (PREP-01)."""

    def as_dict(self) -> dict[str, int]:
        return asdict(self)

    def sentence(self) -> str:
        return (
            f"{self.decisions} decisions recorded, {self.completed} ads added or completed"
            f" from the page, {self.letters} letter choices or regenerations,"
            f" {self.to_generate} folders to generate, {self.letters_to_add} letters to add,"
            f" {self.preparations} interview preparations requested"
        )


def letters_to_redo(decisions: list[exchange.Decision], base: LocalDb, root: Path) -> int:
    """Letters the page asked to regenerate since they were last generated."""
    requested_again = 0
    for decision in decisions:
        if not decision.letter_redo_at:
            continue
        application = base.find(decision.key)
        if application is None or not application.letter_ref:
            continue
        made_at = exchange.file_date(root / application.letter_ref)
        if made_at is None or made_at < decision.letter_redo_at:
            requested_again += base.request_letter_again(
                decision.key, decision.letter_instruction_page
            )
    return requested_again


def requested_preparations(base: LocalDb, decisions: list[exchange.Decision]) -> int:
    """Stores the page's preparation requests (BASE-12); returns how many are new.

    An application unknown to engine B is first added from the page's document (PREP-03).
    """
    new_ones = 0
    for decision in decisions:
        if decision.preparation is None:
            continue
        if decision.ad is not None and base.find(decision.key) is None:
            status = ACCEPTED if decision.status == "acceptee" else CLOSE
            base.complete_from_the_page(decision.key, decision.ad, decision.with_letter, status)
        new_ones += base.request_preparation(decision.key, decision.preparation)
    return new_ones


def apply(base: LocalDb, decisions: list[exchange.Decision], root: Path) -> Outcome:
    """ECH-12 order: unknown accepted ones, letter choices, statuses, letter
    regenerations, then interview preparation requests and company link corrections."""
    completed = sum(
        base.complete_from_the_page(d.key, d.ad, d.with_letter)
        for d in decisions
        if d.status == "acceptee" and d.ad is not None
    )
    # BASE-14: the page's ad text fills in a missing one, whatever the status.
    completed += sum(
        base.complete_ad_text(d.key, d.ad.description)
        for d in decisions
        if d.status != "acceptee" and d.ad is not None
    )
    letters = sum(
        base.set_letter(d.key, d.with_letter)
        for d in decisions
        if d.status in ("acceptee", "prete", "validee") and d.ad is not None
    )
    changed = sum(base.apply_decision(d.key, d.status, d.instruction) for d in decisions)
    changed += sum(
        base.set_refusal_reason(d.key, d.refusal_reason, d.reason_detail)
        for d in decisions
        if d.status == "refusee"
    )
    letters += letters_to_redo(decisions, base, root)
    preparations = requested_preparations(base, decisions)
    # BASE-13: corrections of company links; changes nothing else, so not counted.
    for decision in decisions:
        if decision.ad is not None:
            base.correct_links(decision.key, decision.ad.company, decision.links)
    return Outcome(
        changed,
        completed,
        letters,
        len(base.to_generate()),
        len(base.missing_letters()),
        preparations,
    )
