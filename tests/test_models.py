import pytest

from moteur.models import MAX_KEY_LENGTH, JobAd, contains_expression, normalise


@pytest.mark.spec("ID-01")
def test_normalise_removes_accents_and_punctuation() -> None:
    assert normalise("  Ingénieur·e IA (H/F) — Défense ") == "ingenieur-e-ia-h-f-defense"


@pytest.mark.spec("ID-02")
def test_key_same_as_the_tracking_page() -> None:
    ad = JobAd(company="ÉTÉ (Études Techniques Européennes)", title="Chef de projet IA")
    assert ad.key == "offre_ete-etudes-techniques-europeennes_chef-de-projet-ia"


@pytest.mark.spec("ID-02")
def test_key_tells_ad_from_unsolicited() -> None:
    ad = JobAd(company="Acme", title="Lead AI")
    unsolicited = JobAd(company="Acme", title="Lead AI", type="spontanee")
    assert ad.key != unsolicited.key
    assert unsolicited.key.startswith("spontanee_")


@pytest.mark.spec("ID-02")
def test_key_truncated() -> None:
    assert len(JobAd(company="x" * 200, title="y").key) == MAX_KEY_LENGTH


@pytest.mark.spec("ID-03")
def test_expression_on_whole_words() -> None:
    assert contains_expression("Ingénieur IA senior", "ia")
    assert contains_expression("Head of AI (F/H)", "head of ai")
    assert not contains_expression("Commercial terrain", "ia")
    assert not contains_expression("Data Scientist", "")
