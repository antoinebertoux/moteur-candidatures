# Commands and local server

## Commands

| Command | Effect |
| --- | --- |
| `moteur collecter` | queries and filters, adds to the database (0 tokens) |
| `moteur noter` | scores the waiting ads |
| `moteur exporter` | writes `echange/pour-la-page.json` |
| `moteur quotidien` | collecter, noter, then exporter |
| `moteur decisions <file>` | reads the page's export |
| `moteur generer` | folders of accepted applications, missing letters, then export |
| `moteur lettre [id…]` | letters only, then export |
| `moteur servir [--port N]` | serves the PDFs to the page |
| `moteur mcp` | direct link with the page (ECH-20), started by the Claude desktop app |
| `moteur detecter <address…> [--nom N]` | recognises the recruiting tool of career pages and prints the `[[entreprises]]` block to paste |

- **CLI-01** · The commands above exist and chain the steps shown. *(untested)*
- **CLI-02** · `--config <file>` (default `config.toml` in the current folder) and `-v`
  (detail per source) can be written before or after the command.
- **CLI-03** · A configuration error, an unreadable export or a missing file prints
  "Erreur : …" and returns exit code 1, without a Python traceback. *(untested)*
- **CLI-04** · `moteur detecter` first reads the address itself: `job-boards.greenhouse.io/<id>`
  or `boards.greenhouse.io/<id>`, `jobs.lever.co/<id>`, `jobs.ashbyhq.com/<id>`,
  `jobs.smartrecruiters.com/<id>`, `<id>.recruitee.com`, `<id>.teamtailor.com`,
  `apply.workable.com/<id>` give the tool and identifier; a `myworkdayjobs.com` address
  gives `workday` with the address as identifier (SRC-40).
- **CLI-05** · Any other address (the company's own career page) is downloaded once and
  the first link matching CLI-04 found in it is used. None found: the address is reported
  as "outil non reconnu", and the other addresses carry on.
- **CLI-06** · For each recognised address, the command prints a ready-to-paste
  `[[entreprises]]` block (`nom` from `--nom` when a single address is given, otherwise
  derived from the identifier; `ats`; `identifiant`; `site` = the address given). It never
  writes `config.toml` and never calls Claude.

## PDF server (`moteur servir`)

The page lives on claude.ai, where the browser blocks `file://` links. The CV and Lettre
buttons therefore point to this small server.

- **SRV-01** · It listens on `127.0.0.1` only, port 8765 by default (the page assumes
  8765). *(untested)*
- **SRV-02** · It only serves files under `/Candidatures/…`, read-only. Everything else
  (`config.toml`, `.env`, `latex/`, `..`, links leaving the folder) returns 404.
- **SRV-03** · Responses carry `Cache-Control: no-store`, so that a regenerated PDF shows
  up to date.
