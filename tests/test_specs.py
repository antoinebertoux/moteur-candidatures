"""Every rule of `specs/` is checked by a test, and every test cites real rules.

A rule is written `- **FILT-03** · …`; a test cites it with
`@pytest.mark.spec("FILT-03")`. Exempt from tests: rules marked "(untested" and those of
the page and the scheduled tasks, outside this repository.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs"
OUTSIDE_REPO = {"tracking-page.md", "scheduled-tasks.md"}
_RULE = re.compile(r"^- \*\*([A-Z]+-\d{2})\*\*")


def blocks(text: str) -> list[tuple[str, str]]:
    """(identifier, full text) of each rule, continuation lines included."""
    found_links: list[tuple[str, list[str]]] = []
    for row in text.splitlines():
        start = _RULE.match(row)
        if start:
            found_links.append((start.group(1), [row]))
        elif not row.strip() or row.startswith(("#", "|", "- ")):
            found_links.append(("", []))
        elif found_links and found_links[-1][0]:
            found_links[-1][1].append(row)
    return [(rule, " ".join(rows)) for rule, rows in found_links if rule]


def rules() -> dict[str, bool]:
    """Identifier of each rule -> true if it must have a test."""
    found_ones: dict[str, bool] = {}
    for file in sorted(SPECS.glob("*.md")):
        for rule, text in blocks(file.read_text(encoding="utf-8")):
            assert rule not in found_ones, f"{rule} defined twice"
            found_ones[rule] = file.name not in OUTSIDE_REPO and "(untested" not in text
    return found_ones


def quotes() -> dict[str, set[str]]:
    """Rule -> tests citing it with `@pytest.mark.spec(...)`."""
    quoted: dict[str, set[str]] = {}
    for file in sorted((ROOT / "tests").glob("test_*.py")):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and ast.unparse(decorator.func) == "pytest.mark.spec"
                ):
                    for argument in decorator.args:
                        assert isinstance(argument, ast.Constant), node.name
                        quoted.setdefault(str(argument.value), set()).add(node.name)
    return quoted


def test_every_engine_rule_has_a_test() -> None:
    without_test = sorted(r for r, to_test in rules().items() if to_test and r not in quotes())
    assert without_test == [], f"Rules without a test: {', '.join(without_test)}"


def test_tests_cite_existing_rules() -> None:
    unknown = sorted(set(quotes()) - set(rules()))
    assert unknown == [], f"Rules cited but missing from specs/: {', '.join(unknown)}"


def test_rules_are_found() -> None:
    all_ = rules()
    assert {"ID-02", "FILT-04", "PAGE-30", "TACHE-05"} <= set(all_)
    assert not all_["PAGE-30"]
    assert not all_["CV-12"]
    assert all_["FILT-04"]
