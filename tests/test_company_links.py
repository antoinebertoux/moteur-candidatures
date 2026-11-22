"""Company website and LinkedIn page (specs/company-links.md)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from moteur import cli
from moteur.company_links import (
    LOOKUP_TOOLS,
    CompanyLinks,
    build_prompt,
    clean_linkedin,
    clean_website,
    company_key,
    config_links,
    look_up,
    parse_response,
    to_look_up,
)
from moteur.config import ConfigError
from moteur.decisions import apply
from moteur.exchange import decisions_from, for_the_page
from moteur.local_db import LocalDb
from moteur.models import JobAd, Rating
from tests.conftest import FakeAssistant, parsed

TODAY = date(2026, 11, 20)
NOTE = Rating(score=80, summary="Bon.", letter_requested=False, language="fr")
ACME_1 = JobAd("Acme", "Lead AI", location="Paris", url="https://jobs.lever.co/acme/1")
ACME_2 = JobAd("ACMÉ", "Staff AI", location="Lyon", url="https://jobs.lever.co/acme/2")
ZETA = JobAd("Zeta", "AI Engineer", location="Paris", url="https://zeta.io/jobs/3", salary="70 k€")
SITE = "https://acme.com/"
LINKEDIN = "https://www.linkedin.com/company/acme/"


@pytest.fixture
def base(tmp_path: Path) -> Iterator[LocalDb]:
    with LocalDb(tmp_path / "moteur.sqlite3") as opened:
        opened.add([ACME_1, ACME_2, ZETA])
        for ad in (ACME_1, ACME_2, ZETA):
            opened.record_score(ad.key, NOTE)
        yield opened


def answer(*entries: dict[str, str]) -> str:
    return json.dumps(list(entries))


def page_document(ad: JobAd, **fields: Any) -> dict[str, Any]:
    return {
        "id": ad.key,
        "statut": "a_traiter",
        "entreprise": ad.company,
        "poste": ad.title,
        **fields,
    }


@pytest.mark.spec("LNK-01", "ECH-04")
def test_one_record_per_company_shared_by_its_applications(base: LocalDb) -> None:
    base.record_lookup(company_key("Acme"), CompanyLinks(SITE, LINKEDIN), "2026-11-20")
    rows = for_the_page(base.for_the_page(), links=base.company_links())
    by_title = {row["poste"]: row for row in rows}
    for title in ("Lead AI", "Staff AI"):
        assert by_title[title]["site_entreprise"] == SITE
        assert by_title[title]["linkedin_entreprise"] == LINKEDIN
    assert "site_entreprise" not in by_title["AI Engineer"]
    assert "linkedin_entreprise" not in by_title["AI Engineer"]


@pytest.mark.spec("LNK-02")
def test_correction_beats_config_beats_lookup(base: LocalDb) -> None:
    key = company_key("Acme")
    base.record_lookup(key, CompanyLinks("https://lookup.com/", LINKEDIN), "2026-11-20")
    assert base.company_links()[key] == CompanyLinks("https://lookup.com/", LINKEDIN)
    base.set_config_links({key: CompanyLinks("https://config.com/", "")})
    # Each link on its own: the config has no LinkedIn, the lookup's stays.
    assert base.company_links()[key] == CompanyLinks("https://config.com/", LINKEDIN)
    base.correct_links(ACME_1.key, "Acme", CompanyLinks("", "https://linkedin.com/company/a"))
    assert base.company_links()[key] == CompanyLinks(
        "https://config.com/", "https://linkedin.com/company/a"
    )
    # A new lookup never replaces a stronger source.
    base.record_lookup(key, CompanyLinks("https://other.com/", ""), "2026-11-21")
    assert base.company_links()[key].site == "https://config.com/"


@pytest.mark.spec("LNK-02")
def test_config_links_are_replaced_at_each_start(base: LocalDb) -> None:
    key = company_key("Acme")
    base.set_config_links(config_links([("Acme", "https://acme.com", "")]))
    assert base.company_links()[key].site == "https://acme.com"
    base.set_config_links(config_links([]))
    assert key not in base.company_links()


@pytest.mark.spec("LNK-03")
def test_linkedin_link_form() -> None:
    assert clean_linkedin("https://fr.linkedin.com/company/acme-sas?trk=x#a") == (
        "https://www.linkedin.com/company/acme-sas/"
    )
    assert clean_linkedin("http://linkedin.com/company/acme/about/") == LINKEDIN
    assert clean_linkedin("https://www.linkedin.com/in/someone/") == ""
    assert clean_linkedin("https://www.linkedin.com/school/x/") == ""
    assert clean_linkedin("https://notlinkedin.com/company/acme") == ""
    assert clean_linkedin(None) == ""


@pytest.mark.spec("LNK-03")
def test_website_form() -> None:
    assert clean_website("https://www.Acme.com/fr/about?x=1") == "https://www.acme.com/"
    assert clean_website("http://acme.io") == "https://acme.io/"
    for refused in (
        "https://fr.linkedin.com/company/acme",
        "https://www.welcometothejungle.com/fr/companies/acme",
        "https://fr.indeed.com/cmp/acme",
        "https://www.glassdoor.fr/Overview/acme",
        "https://jobs.lever.co/acme",
        "https://acme.wd3.myworkdayjobs.com/Careers",
        "https://fr.wikipedia.org/wiki/Acme",
        "ftp://acme.com",
        "acme.com",
        "https://localhost/",
        "",
    ):
        assert clean_website(refused) == "", refused


@pytest.mark.spec("LNK-11")
def test_selection(base: LocalDb) -> None:
    assert [o.company for o in to_look_up(base, TODAY)] == ["Acme", "Zeta"]
    # Complete from any source: not sent again.
    base.set_config_links({company_key("Zeta"): CompanyLinks("https://zeta.io", LINKEDIN)})
    assert [o.company for o in to_look_up(base, TODAY)] == ["Acme"]
    # Looked up but not found: retried after 30 days only.
    base.record_lookup(company_key("Acme"), CompanyLinks(), "2026-11-01")
    assert to_look_up(base, TODAY) == []
    assert [o.company for o in to_look_up(base, date(2026, 12, 1))] == ["Acme"]


@pytest.mark.spec("LNK-11")
def test_selection_includes_accepted_but_not_refused(base: LocalDb) -> None:
    base.apply_decision(ACME_1.key, "acceptee")
    base.apply_decision(ACME_2.key, "refusee")
    base.apply_decision(ZETA.key, "refusee")
    assert [o.title for o in to_look_up(base, TODAY)] == ["Lead AI"]


@pytest.mark.spec("LNK-12", "CLA-04")
def test_the_call_sends_little_and_has_web_search_only(base: LocalDb) -> None:
    assistant = FakeAssistant(answer())
    look_up(base, assistant, model="haiku", today=TODAY)
    assert assistant.tools == [LOOKUP_TOOLS] == [("WebSearch",)]
    assert assistant.models == ["haiku"]
    sent = json.loads(assistant.prompts[0])
    assert sent == json.loads(build_prompt([ACME_1, ZETA]))
    assert sent[1] == {
        "entreprise": "Zeta",
        "offre": {"poste": "AI Engineer", "lieu": "Paris", "lien": "https://zeta.io/jobs/3"},
    }
    assert "70 k€" not in assistant.prompts[0]
    assert "Bon." not in assistant.prompts[0] + assistant.systems[0]


@pytest.mark.spec("LNK-14")
def test_reading_the_response() -> None:
    found = parse_response(
        answer(
            {"entreprise": "ACME", "site": "https://acme.com/fr", "linkedin": LINKEDIN},
            {"entreprise": "Zeta", "site": "https://fr.indeed.com/cmp/zeta", "linkedin": ""},
            {"entreprise": "Inconnue", "site": "https://inconnue.fr", "linkedin": ""},
        ),
        {"acme", "zeta"},
    )
    assert found == {"acme": CompanyLinks(SITE, LINKEDIN), "zeta": CompanyLinks()}


@pytest.mark.spec("LNK-14")
def test_every_company_of_the_batch_gets_a_lookup_date(base: LocalDb) -> None:
    assistant = FakeAssistant(answer({"entreprise": "Acme", "site": SITE, "linkedin": ""}))
    assert look_up(base, assistant, model="haiku", today=TODAY) == (2, 1)
    assert base.company_lookups() == {"acme": "2026-11-20", "zeta": "2026-11-20"}
    assert base.company_links() == {"acme": CompanyLinks(SITE, "")}


@pytest.mark.spec("LNK-14")
def test_a_failed_batch_records_nothing(base: LocalDb) -> None:
    assert look_up(base, FakeAssistant('{"pas": "un tableau"}'), model="haiku") == (0, 0)
    assert base.company_lookups() == {}


@pytest.mark.spec("LNK-15")
def test_daily_run_looks_up_links_between_scoring_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(Path("config.exemple.toml").read_text(encoding="utf-8"), encoding="utf-8")
    order: list[str] = []
    for step in ("collect", "score", "links", "export"):
        monkeypatch.setattr(cli, f"command_{step}", lambda *_args, step=step: order.append(step))
    assert cli.main(["daily", "--config", str(config)]) == 0
    assert order == ["collect", "score", "links", "export"]


@pytest.mark.spec("LNK-15")
def test_a_failed_lookup_does_not_stop_the_daily_run(base: LocalDb) -> None:
    class Failing:
        def ask(self, *_args: Any, **_kwargs: Any) -> str:
            from moteur.claude_cli import ClaudeError

            raise ClaudeError("claude introuvable")

    assert look_up(base, Failing(), model="haiku") == (0, 0)


@pytest.mark.spec("CAT-08")
def test_config_links_must_be_web_addresses() -> None:
    (acme,) = parsed(
        {"entreprises": [{"nom": "Acme", "site": "https://acme.com", "linkedin": LINKEDIN}]},
        Path(),
    ).companies
    assert (acme.site, acme.linkedin) == ("https://acme.com", LINKEDIN)
    with pytest.raises(ConfigError, match=r"Acme.*linkedin"):
        parsed({"entreprises": [{"nom": "Acme", "linkedin": "acme"}]}, Path())


@pytest.mark.spec("BASE-13", "ECH-11")
def test_page_correction_applies_to_the_whole_company(base: LocalDb, tmp_path: Path) -> None:
    corrected = page_document(
        ACME_1,
        liens_manuels=True,
        site_entreprise=" https://acme.fr ",
        linkedin_entreprise="",
    )
    apply(base, decisions_from([corrected]), tmp_path)
    assert base.company_links()["acme"] == CompanyLinks("https://acme.fr", "")
    # Values sent back without `liens_manuels` are the engine's own: no correction.
    other = page_document(ACME_2, site_entreprise="https://wrong.com")
    apply(base, decisions_from([corrected, other]), tmp_path)
    assert base.company_links()["acme"].site == "https://acme.fr"


@pytest.mark.spec("BASE-13")
def test_withdrawing_a_correction(base: LocalDb, tmp_path: Path) -> None:
    base.record_lookup("acme", CompanyLinks(SITE, ""), "2026-11-20")
    corrected = page_document(ACME_1, liens_manuels=True, site_entreprise="https://acme.fr")
    apply(base, decisions_from([corrected]), tmp_path)
    assert base.company_links()["acme"].site == "https://acme.fr"
    apply(base, decisions_from([page_document(ACME_1, liens_manuels=False)]), tmp_path)
    assert base.company_links()["acme"].site == SITE


@pytest.mark.spec("BASE-13")
def test_a_correction_that_is_not_a_web_address_is_ignored(base: LocalDb, tmp_path: Path) -> None:
    corrected = page_document(ACME_1, liens_manuels=True, site_entreprise="javascript:x")
    apply(base, decisions_from([corrected]), tmp_path)
    assert "acme" not in base.company_links()
