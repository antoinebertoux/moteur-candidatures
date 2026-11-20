import json

import pytest

from moteur.claude_cli import ClaudeError
from moteur.local_db import LocalDb
from moteur.models import JobAd, Rating
from moteur.scoring import (
    DESCRIPTION_LENGTH,
    build_scoring_prompt,
    parse_answer,
    score_ads,
    system,
)
from tests.conftest import FakeAssistant

A = JobAd("Acme", "Data Scientist", description="x" * 5000)
B = JobAd("Bolt", "AI Engineer")


def answer(*entries: dict[str, object]) -> str:
    return json.dumps(list(entries))


@pytest.mark.spec("NOT-03")
def test_prompt_truncates_description_and_carries_key() -> None:
    (entry,) = json.loads(build_scoring_prompt([A]))
    assert entry["cle"] == A.key
    assert len(entry["description"]) == DESCRIPTION_LENGTH


@pytest.mark.spec("NOT-04")
def test_systeme_contient_le_profil() -> None:
    assert system("Vise un poste de Lead AI").endswith("Vise un poste de Lead AI")


@pytest.mark.spec("NOT-06")
def test_analyser_reponse_borne_et_filtre() -> None:
    text = answer(
        {"cle": A.key, "score": 140, "resume": "Bien.", "lettre_demandee": True, "langue": "en"},
        {"cle": B.key, "score": 61.4},
        {"cle": "inconnue", "score": 50},
        {"cle": A.key + "x", "score": True},
    )
    notes = parse_answer(text, {A.key, B.key})
    assert notes == {
        A.key: Rating(100, "Bien.", True, "en"),
        B.key: Rating(61, "", False, "fr"),
    }


@pytest.mark.spec("NOT-06")
def test_analyser_reponse_refuse_autre_chose_qu_un_tableau() -> None:
    with pytest.raises(ClaudeError):
        parse_answer('{"cle": "a"}', {"a"})


@pytest.mark.spec("NOT-01", "NOT-02")
def test_score_in_batches_and_keep_failures_waiting() -> None:
    assistant = FakeAssistant(answer({"cle": A.key, "score": 70}), "illisible")
    with LocalDb(":memory:") as base:
        base.add([A, B])
        scored_count = score_ads(base, assistant, profile="p", model="haiku", batch_size=1)
        assert scored_count == 1
        assert base.to_score() == [B]
        assert [c.score for c in base.for_the_page()] == [70]
    assert assistant.models == ["haiku", "haiku"]


@pytest.mark.spec("NOT-04", "NOT-08")
def test_system_prompt_lists_past_refusals() -> None:
    from moteur.refusal import Refusal

    assert "refusées" not in system("profil")
    text = system(
        "profil",
        [Refusal("Capgemini", "Data Scientist", "conseil", "ESN"), Refusal("X", "Y", "lieu")],
    )
    assert "profil" in text
    assert "- Capgemini — Data Scientist : Conseil / ESN (ESN)" in text
    assert "- X — Y : Lieu / télétravail" in text


@pytest.mark.spec("NOT-08")
def test_scoring_sends_the_refusals_from_the_database() -> None:
    from moteur.local_db import LocalDb
    from tests.conftest import FakeAssistant

    spy = FakeAssistant("[]")
    systems = spy.systems

    with LocalDb(":memory:") as base:
        refusee, new_one = JobAd("Sopra", "Data Scientist"), JobAd("Acme", "Lead AI")
        base.add([refusee, new_one])
        base.apply_decision(refusee.key, "refusee")
        base.set_refusal_reason(refusee.key, "conseil", "")
        score_ads(base, spy, profile="p", model="haiku", batch_size=8)
        assert "Sopra — Data Scientist : Conseil / ESN" in systems[0]
