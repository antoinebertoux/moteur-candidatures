# Repository rules

- Specs are written in English.
- `specs/` is the reference for the tool's behaviour (engine B, tracking page, scheduled
  tasks). The user reviews the specs, not the code.
- For any change in behaviour: **change the spec first** (new or modified rule, stable
  identifier, never renumbered), get the user's approval, then code and test. The commit
  contains spec, code and tests.
- Every engine rule has at least one test citing it with `@pytest.mark.spec("XXX-NN")`;
  `tests/test_specs.py` checks this. A rule that cannot be tested is marked
  *(untested)*, with the reason.
- A change to the tracking page or to a scheduled task also updates
  `specs/tracking-page.md` or `specs/scheduled-tasks.md`.
- The published page and `page-suivi/index.html` stay identical: any change to one is
  carried over to the other. Likewise, a change to a scheduled task's text is carried
  over to its template in `taches/` (filled-in version in `prive/taches/`, ignored by
  Git). No personal data in the templates.
- The rules in `specs/identifiers.md` exist twice (Python and page): never change only
  one side.
- Before committing: `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest`.
