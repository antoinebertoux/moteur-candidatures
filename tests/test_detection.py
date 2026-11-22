from collections.abc import Mapping

import pytest

from moteur.detection import detect, find_tool, report
from moteur.sources.base import SourceError
from tests.conftest import FakeClient


@pytest.mark.spec("CLI-04")
@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("https://job-boards.greenhouse.io/helsing", ("greenhouse", "helsing")),
        ("https://boards.greenhouse.io/acme/jobs/123", ("greenhouse", "acme")),
        ("https://jobs.lever.co/safran-ai/abc-123", ("lever", "safran-ai")),
        (
            "https://job-boards.eu.greenhouse.io/sifflet/jobs/4327975101",
            ("greenhouse", "eu:sifflet"),
        ),
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
    detection = detect(address, FakeClient({}))
    assert (detection.ats, detection.identifier) == expected


@pytest.mark.spec("CLI-05")
def test_company_page_is_read_for_the_first_tool_link() -> None:
    page = (
        '<script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>'
        '<a href="https://jobs.ashbyhq.com/acme-ai">Postuler</a>'
        '<a href="https://jobs.lever.co/autre">x</a>'
    )
    client = FakeClient({"https://acme.ai/careers": page})
    detection = detect("acme.ai/careers", client)
    assert (detection.ats, detection.identifier) == ("ashby", "acme-ai")


@pytest.mark.spec("CLI-05")
def test_unrecognised_or_unreachable_page_is_reported_and_others_carry_on() -> None:
    class Failing(FakeClient):
        def get_text(self, url: str, *, params: Mapping[str, str] | None = None) -> str:
            if "panne" in url:
                raise SourceError(f"{url}: HTTP 503")
            return "<p>Pas d'outil</p>"

    text = report(["https://panne.fr", "https://rien.fr", "jobs.ashbyhq.com/dust"], Failing({}))
    assert text.splitlines() == [
        "https://panne.fr: https://panne.fr: HTTP 503",
        "https://rien.fr: unrecognised tool",
        "jobs.ashbyhq.com/dust: ats = ashby, identifiant = dust",
    ]


@pytest.mark.spec("CLI-06")
def test_detect_prints_the_tool_and_identifier_without_downloading_known_addresses() -> None:
    client = FakeClient({})
    assert report(["https://jobs.ashbyhq.com/comand-ai"], client) == (
        "https://jobs.ashbyhq.com/comand-ai: ats = ashby, identifiant = comand-ai"
    )
    assert client.calls == []  # known addresses need no download
