# Specs of the job application tool

These files describe **what** the tool does, not how it is coded. They are the
reference: when the code and a spec disagree, one of them is wrong and must be fixed.

## How to use them

- **One rule = one stable identifier** (`FILT-03`). It never changes and is never reused:
  a removed rule is struck through, not renumbered.
- **Every engine rule is checked by at least one test**, which cites it:
  `@pytest.mark.spec("FILT-03")`. `tests/test_specs.py` fails if a rule has no test or if
  a test cites an unknown rule.
- A rule marked *(untested)* deliberately has no automated test (instruction given to
  Claude, network behaviour…). Rules for the tracking page and the scheduled tasks live
  outside this repository: they are checked by hand.
- **Workflow**: change the spec first, User approves it, then code and test. The
  commit contains all three.

## Overview

```text
            ┌───────────── Engine A: scheduled tasks in Claude ──────────────┐
            │  search the web for job ads and write directly to the database  │
            └─────────────────────────────────┬──────────────────────────────┘
                                              ▼
 Engine B (this repo, on the PC)       "Application tracker" page
 collect → score                       (claude.ai artifact + its database)
 moteur mcp ── propositions ────────▶  imported at load and every minute
            ◀── decisions ───────────  sent after each change
                                        User sorts: yes / no, letter, edits
 generate / letter → PDFs in ../Candidatures/, picked up by the next "propositions"
 serve   ◀── CV / Letter links ───────  User reviews, approves, applies himself

 Fallback without the desktop app: export ─JSON─▶ Import, Export ─JSON─▶ decisions
```

Claude is only called to **score** (Haiku), to **write** (Sonnet) and to **prepare an
interview** (Sonnet, with web search), through
`claude -p` with User's subscription, never an API key. Everything else is plain
code, at 0 tokens.

## Statuses

| Page (`statut` field) | Step shown | Engine B local database |
| --- | --- | --- |
| — | — | `a_noter`: collected, not scored yet |
| `a_traiter` | To review (À traiter) | `notee`: proposed to the page |
| `acceptee` | To prepare (À préparer) | `acceptee`: CV (and letter) to generate |
| `prete` | To validate (À valider) | `generee`: PDFs ready |
| `validee` | To send (À envoyer) | `generee` |
| `postulee` | Applied (Postulée) | `close` |
| `refusee` | Rejected (Refusée) | `refusee` |

## Files

| File | Prefix | Subject |
| --- | --- | --- |
| [identifiers.md](identifiers.md) | `ID` | application identifier, rules shared with the page |
| [config.md](config.md) | `CONF` | `config.toml` and `.env` |
| [sources.md](sources.md) | `SRC` | job sites queried |
| [collection.md](collection.md) | `COL`, `FILT` | combining sources, filter, unsolicited applications |
| [local-database.md](local-database.md) | `BASE` | what engine B keeps and its transitions |
| [scoring.md](scoring.md) | `NOT`, `CLA` | scoring by Claude, `claude -p` calls |
| [generation.md](generation.md) | `CV`, `LET`, `GEN` | LaTeX CV and cover letter |
| [latex-repository.md](latex-repository.md) | `LTX` | format of the `latex/` folder, example shipped |
| [exchange.md](exchange.md) | `ECH` | files exchanged with the page |
| [interview-prep.md](interview-prep.md) | `PREP` | interview preparation sheet |
| [company-links.md](company-links.md) | `LNK` | company website and LinkedIn links |
| [cli.md](cli.md) | `CLI`, `SRV` | commands and local PDF server |
| [tracking-page.md](tracking-page.md) | `PAGE` | tracking page (claude.ai artifact) |
| [scheduled-tasks.md](scheduled-tasks.md) | `TACHE` | engine A: scheduled tasks |
| this file | `INV` | invariants of the whole tool |

## Invariants

- **INV-01** · Nothing is ever sent to an employer without User's approval: neither
  engine B nor engine A applies or sends a message. *(untested)*
- **INV-02** · The repository contains no personal data: `config.toml`, `.env`,
  `moteur.sqlite3` and `echange/` are ignored by Git; CVs, letters and applications stay
  outside the repository. *(untested)*
- **INV-03** · The salary floor is never sent to Claude nor written to the page's
  database. *(untested)*
- **INV-04** · Applications from the previous job search (before November 2026) are not
  brought into the tracking. *(untested)*
