"""Company website and LinkedIn page (specs/company-links.md)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from moteur import cli
from moteur.base_locale import BaseLocale
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
from moteur.config import ErreurConfig, analyser
from moteur.decisions import appliquer
from moteur.echange import decisions_depuis, pour_la_page
from moteur.modeles import Note, Offre
from tests.conftest import FauxAssistant

TODAY = date(2026, 11, 20)
NOTE = Note(score=80, resume="Bon.", lettre_demandee=False, langue="fr")
ACME_1 = Offre("Acme", "Lead AI", lieu="Paris", url="https://jobs.lever.co/acme/1")
ACME_2 = Offre("ACMÉ", "Staff AI", lieu="Lyon", url="https://jobs.lever.co/acme/2")
ZETA = Offre("Zeta", "AI Engineer", lieu="Paris", url="https://zeta.io/jobs/3", salaire="70 k€")
SITE = "https://acme.com/"
LINKEDIN = "https://www.linkedin.com/company/acme/"


@pytest.fixture
def base(tmp_path: Path) -> Iterator[BaseLocale]:
    with BaseLocale(tmp_path / "moteur.sqlite3") as ouverte:
        ouverte.ajouter([ACME_1, ACME_2, ZETA])
        for offre in (ACME_1, ACME_2, ZETA):
            ouverte.enregistrer_note(offre.cle, NOTE)
        yield ouverte


def answer(*entries: dict[str, str]) -> str:
    return json.dumps(list(entries))


def page_document(offre: Offre, **fields: Any) -> dict[str, Any]:
    return {
        "id": offre.cle,
        "statut": "a_traiter",
        "entreprise": offre.entreprise,
        "poste": offre.poste,
        **fields,
    }


@pytest.mark.spec("LNK-01", "ECH-04")
def test_one_record_per_company_shared_by_its_applications(base: BaseLocale) -> None:
    base.record_lookup(company_key("Acme"), CompanyLinks(SITE, LINKEDIN), "2026-11-20")
    lignes = pour_la_page(base.pour_la_page(), liens=base.company_links())
    par_poste = {ligne["poste"]: ligne for ligne in lignes}
    for poste in ("Lead AI", "Staff AI"):
        assert par_poste[poste]["site_entreprise"] == SITE
        assert par_poste[poste]["linkedin_entreprise"] == LINKEDIN
    assert "site_entreprise" not in par_poste["AI Engineer"]
    assert "linkedin_entreprise" not in par_poste["AI Engineer"]


@pytest.mark.spec("LNK-02")
def test_correction_beats_config_beats_lookup(base: BaseLocale) -> None:
    key = company_key("Acme")
    base.record_lookup(key, CompanyLinks("https://lookup.com/", LINKEDIN), "2026-11-20")
    assert base.company_links()[key] == CompanyLinks("https://lookup.com/", LINKEDIN)
    base.set_config_links({key: CompanyLinks("https://config.com/", "")})
    # Each link on its own: the config has no LinkedIn, the lookup's stays.
    assert base.company_links()[key] == CompanyLinks("https://config.com/", LINKEDIN)
    base.correct_links(ACME_1.cle, "Acme", CompanyLinks("", "https://linkedin.com/company/a"))
    assert base.company_links()[key] == CompanyLinks(
        "https://config.com/", "https://linkedin.com/company/a"
    )
    # A new lookup never replaces a stronger source.
    base.record_lookup(key, CompanyLinks("https://other.com/", ""), "2026-11-21")
    assert base.company_links()[key].site == "https://config.com/"


@pytest.mark.spec("LNK-02")
def test_config_links_are_replaced_at_each_start(base: BaseLocale) -> None:
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
def test_selection(base: BaseLocale) -> None:
    assert [o.entreprise for o in to_look_up(base, TODAY)] == ["Acme", "Zeta"]
    # Complete from any source: not sent again.
    base.set_config_links({company_key("Zeta"): CompanyLinks("https://zeta.io", LINKEDIN)})
    assert [o.entreprise for o in to_look_up(base, TODAY)] == ["Acme"]
    # Looked up but not found: retried after 30 days only.
    base.record_lookup(company_key("Acme"), CompanyLinks(), "2026-11-01")
    assert to_look_up(base, TODAY) == []
    assert [o.entreprise for o in to_look_up(base, date(2026, 12, 1))] == ["Acme"]


@pytest.mark.spec("LNK-11")
def test_selection_includes_accepted_but_not_refused(base: BaseLocale) -> None:
    base.appliquer_decision(ACME_1.cle, "acceptee")
    base.appliquer_decision(ACME_2.cle, "refusee")
    base.appliquer_decision(ZETA.cle, "refusee")
    assert [o.poste for o in to_look_up(base, TODAY)] == ["Lead AI"]


@pytest.mark.spec("LNK-12", "CLA-04")
def test_the_call_sends_little_and_has_web_search_only(base: BaseLocale) -> None:
    assistant = FauxAssistant(answer())
    look_up(base, assistant, model="haiku", today=TODAY)
    assert assistant.outils == [LOOKUP_TOOLS] == [("WebSearch",)]
    assert assistant.modeles == ["haiku"]
    sent = json.loads(assistant.prompts[0])
    assert sent == json.loads(build_prompt([ACME_1, ZETA]))
    assert sent[1] == {
        "entreprise": "Zeta",
        "offre": {"poste": "AI Engineer", "lieu": "Paris", "lien": "https://zeta.io/jobs/3"},
    }
    assert "70 k€" not in assistant.prompts[0]
    assert "Bon." not in assistant.prompts[0] + assistant.systemes[0]


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
def test_every_company_of_the_batch_gets_a_lookup_date(base: BaseLocale) -> None:
    assistant = FauxAssistant(answer({"entreprise": "Acme", "site": SITE, "linkedin": ""}))
    assert look_up(base, assistant, model="haiku", today=TODAY) == (2, 1)
    assert base.company_lookups() == {"acme": "2026-11-20", "zeta": "2026-11-20"}
    assert base.company_links() == {"acme": CompanyLinks(SITE, "")}


@pytest.mark.spec("LNK-14")
def test_a_failed_batch_records_nothing(base: BaseLocale) -> None:
    assert look_up(base, FauxAssistant('{"pas": "un tableau"}'), model="haiku") == (0, 0)
    assert base.company_lookups() == {}


@pytest.mark.spec("LNK-15")
def test_daily_run_looks_up_links_between_scoring_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(Path("config.exemple.toml").read_text(encoding="utf-8"), encoding="utf-8")
    order: list[str] = []
    for step in ("collecter", "noter", "liens", "exporter"):
        monkeypatch.setattr(cli, f"commande_{step}", lambda *_args, step=step: order.append(step))
    assert cli.main(["quotidien", "--config", str(config)]) == 0
    assert order == ["collecter", "noter", "liens", "exporter"]


@pytest.mark.spec("LNK-15")
def test_a_failed_lookup_does_not_stop_the_daily_run(base: BaseLocale) -> None:
    class Failing:
        def demander(self, *_args: Any, **_kwargs: Any) -> str:
            from moteur.claude_cli import ErreurClaude

            raise ErreurClaude("claude introuvable")

    assert look_up(base, Failing(), model="haiku") == (0, 0)


@pytest.mark.spec("CONF-09")
def test_config_links_must_be_web_addresses() -> None:
    (acme,) = analyser(
        {"entreprises": [{"nom": "Acme", "site": "https://acme.com", "linkedin": LINKEDIN}]},
        Path(),
    ).entreprises
    assert (acme.site, acme.linkedin) == ("https://acme.com", LINKEDIN)
    with pytest.raises(ErreurConfig, match=r"Acme.*linkedin"):
        analyser({"entreprises": [{"nom": "Acme", "linkedin": "acme"}]}, Path())


@pytest.mark.spec("BASE-13", "ECH-11")
def test_page_correction_applies_to_the_whole_company(base: BaseLocale, tmp_path: Path) -> None:
    corrected = page_document(
        ACME_1,
        liens_manuels=True,
        site_entreprise=" https://acme.fr ",
        linkedin_entreprise="",
    )
    appliquer(base, decisions_depuis([corrected]), tmp_path)
    assert base.company_links()["acme"] == CompanyLinks("https://acme.fr", "")
    # Values sent back without `liens_manuels` are the engine's own: no correction.
    other = page_document(ACME_2, site_entreprise="https://wrong.com")
    appliquer(base, decisions_depuis([corrected, other]), tmp_path)
    assert base.company_links()["acme"].site == "https://acme.fr"


@pytest.mark.spec("BASE-13")
def test_withdrawing_a_correction(base: BaseLocale, tmp_path: Path) -> None:
    base.record_lookup("acme", CompanyLinks(SITE, ""), "2026-11-20")
    corrected = page_document(ACME_1, liens_manuels=True, site_entreprise="https://acme.fr")
    appliquer(base, decisions_depuis([corrected]), tmp_path)
    assert base.company_links()["acme"].site == "https://acme.fr"
    appliquer(base, decisions_depuis([page_document(ACME_1, liens_manuels=False)]), tmp_path)
    assert base.company_links()["acme"].site == SITE


@pytest.mark.spec("BASE-13")
def test_a_correction_that_is_not_a_web_address_is_ignored(
    base: BaseLocale, tmp_path: Path
) -> None:
    corrected = page_document(ACME_1, liens_manuels=True, site_entreprise="javascript:x")
    appliquer(base, decisions_depuis([corrected]), tmp_path)
    assert "acme" not in base.company_links()
