from collections.abc import Mapping

import pytest

from moteur.detection import detect, find_tool, report
from moteur.sources.base import ErreurSource
from tests.conftest import FauxClient


@pytest.mark.spec("CLI-04")
@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("https://job-boards.greenhouse.io/helsing", ("greenhouse", "helsing")),
        ("https://boards.greenhouse.io/acme/jobs/123", ("greenhouse", "acme")),
        ("https://jobs.lever.co/safran-ai/abc-123", ("lever", "safran-ai")),
        ("https://jobs.ashbyhq.com/mistral", ("ashby", "mistral")),
        ("https://jobs.smartrecruiters.com/Acme1/744", ("smartrecruiters", "Acme1")),
        ("https://kayrros.recruitee.com/o/data", ("recruitee", "kayrros")),
        ("https://qevlar.teamtailor.com/jobs", ("teamtailor", "qevlar")),
        ("https://apply.workable.com/giskard/j/1/", ("workable", "giskard")),
        (
            "https://thales.wd3.myworkdayjobs.com/fr-FR/Careers/job/1",
            ("workday", "https://thales.wd3.myworkdayjobs.com/fr-FR/Careers"),
        ),
    ],
)
def test_address_gives_tool_and_identifier(address: str, expected: tuple[str, str]) -> None:
    assert find_tool(address) == expected
    detection = detect(address, FauxClient({}))
    assert (detection.ats, detection.identifier) == expected


@pytest.mark.spec("CLI-05")
def test_company_page_is_read_for_the_first_tool_link() -> None:
    page = (
        '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>'
        '<a href="https://jobs.ashbyhq.com/acme-ai">Postuler</a>'
        '<a href="https://jobs.lever.co/autre">x</a>'
    )
    client = FauxClient({"https://acme.ai/careers": page})
    detection = detect("acme.ai/careers", client)
    assert (detection.ats, detection.identifier) == ("ashby", "acme-ai")


@pytest.mark.spec("CLI-05")
def test_unrecognised_or_unreachable_page_is_reported_and_others_carry_on() -> None:
    class Failing(FauxClient):
        def get_texte(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
            if "panne" in url:
                raise ErreurSource(f"{url} : HTTP 503")
            return "<p>Pas d'outil</p>"

    text = report(["https://panne.fr", "https://rien.fr", "jobs.ashbyhq.com/dust"], Failing({}))
    assert "# https://panne.fr : https://panne.fr : HTTP 503" in text
    assert "# https://rien.fr : outil non reconnu" in text
    assert 'identifiant = "dust"' in text


@pytest.mark.spec("CLI-06")
def test_block_to_paste() -> None:
    client = FauxClient({})
    assert report(["https://jobs.ashbyhq.com/comand-ai"], client, "Comand AI") == (
        "[[entreprises]]\n"
        'nom = "Comand AI"\n'
        'ats = "ashby"\n'
        'identifiant = "comand-ai"\n'
        'site = "https://jobs.ashbyhq.com/comand-ai"\n'
    )
    two = report(["https://jobs.ashbyhq.com/alta-ares", "https://jobs.lever.co/x"], client, "N")
    assert 'nom = "Alta Ares"' in two  # --nom only applies to a single address
    assert client.appels == []  # known addresses need no download
