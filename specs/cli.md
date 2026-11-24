# Commands and local server

## Commands

| Command | Effect |
| --- | --- |
| `moteur collect` | queries and filters, adds to the database (0 tokens) |
| `moteur score` | scores the waiting ads |
| `moteur export` | writes `echange/pour-la-page.json` |
| `moteur links` | looks up the missing company links (LNK-10) |
| `moteur daily` | collect, score, links, then export |
| `moteur decisions <file>` | reads the page's export |
| `moteur generate` | folders of accepted applications, missing letters, then export |
| `moteur letter [id…]` | letters only, then export |
| `moteur prepare [id…] [--technical]` | interview preparation sheets (PREP-40), then export |
| `moteur init-latex` | copies the LaTeX example to `latex/` (LTX-03) |
| `moteur serve [--port N]` | serves the PDFs to the page |
| `moteur mcp` | direct link with the page (ECH-20), started by the Claude desktop app |
| `moteur companies` | lists the companies followed and the sources, with what is searched (CLI-09) |
| `moteur detect <address…>` | recognises the recruiting tool of career pages and prints it |
| `moteur import-companies` | turns the `[[entreprises]]` of an older `config.toml` into own companies (CLI-10) |

- **CLI-01** · The commands above exist and chain the steps shown. *(untested)*
- **CLI-02** · `--config <file>` (default `config.toml` in the current folder) and `-v` /
  `--verbose` (detail per source) can be written before or after the command.
- **CLI-03** · A configuration error, an unreadable export or a missing file prints
  "Error: …" and returns exit code 1, without a Python traceback. *(untested)*
- **CLI-04** · `moteur detect` first reads the address itself: `job-boards.greenhouse.io/<id>`
  or `boards.greenhouse.io/<id>`, `jobs.lever.co/<id>`, `jobs.ashbyhq.com/<id>`,
  `jobs.smartrecruiters.com/<id>`, `<id>.recruitee.com`, `<id>.teamtailor.com`,
  `job-boards.eu.greenhouse.io/<id>` (identifier `eu:<id>`, SRC-33),
  `apply.workable.com/<id>` give the tool and identifier; a `myworkdayjobs.com` address
  gives `workday` with the address as identifier (SRC-40); `<x>.taleez.com` gives
  `taleez` with that host as identifier (SRC-103), and
  `careers.werecruit.io/<language>/<company>` gives `werecruit` with that address as
  identifier, without what follows the company (SRC-106); a `<x>.csod.com/ux/ats/careersite/<n>/home?c=<x>` address
  gives `cornerstone` with that address as identifier (SRC-111), and
  `ats.rippling.com/<board>/jobs` gives `rippling` with that address as identifier
  (SRC-116), and `join.com/companies/<company>` gives `join` with that address as
  identifier (SRC-122).
- **CLI-05** · Any other address (the company's own career page) is downloaded once and
  the first link matching CLI-04 found in it is used. None found: the address is reported
  as "unrecognised tool", and the other addresses carry on.
- **CLI-06** · For each recognised address, the command prints the address, `ats` and
  `identifiant`. It never writes anything and never calls Claude.
- **CLI-07** · Everything the command line shows is in English: command and option names,
  help, progress lines, warnings and errors. What is written for the user or a recruiter
  (CV, cover letter, preparation sheet) and the stored data (statuses, field names,
  `config.toml` keys, files exchanged with the page) are unchanged.
- **CLI-08** · The former French command names (`collecter`, `noter`, `exporter`, `liens`,
  `quotidien`, `generer`, `lettre`, `preparer`, `servir`, `detecter`, and `--verbeux`,
  `--nom`) are no longer accepted: argparse rejects them with its usual message listing
  the valid commands.
- **CLI-09** · `moteur companies` prints every company followed, grouped by sector, with
  its origin (catalogue or own), its size, whether it is searched and, if not, why (User's
  choice, sector, size, country), and whether its unsolicited application is on; then
  every keyword source and whether it is searched. It only reads.
- **CLI-10** · `moteur import-companies` reads the `[[entreprises]]` of `config.toml`
  and keeps each one as an own company (BASE-16), checked by CAT-08 and CAT-20 but
  without querying its board (CAT-22). An entry with `spontanee = true` also records
  that choice (BASE-15), unless User already made one. An own company of the same
  normalised name is replaced (CAT-24). Each refused entry is printed with its reason;
  the others are kept. It never rewrites `config.toml`, and ends by saying to delete the
  `[[entreprises]]` from it. Running it twice changes nothing the second time.

## PDF server (`moteur serve`)

The page lives on claude.ai, where the browser blocks `file://` links. The CV and Lettre
buttons therefore point to this small server.

- **SRV-01** · It listens on `127.0.0.1` only, port 8765 by default (the page assumes
  8765). *(untested)*
- **SRV-02** · It only serves files under `/Candidatures/…`, read-only. Everything else
  (`config.toml`, `.env`, `latex/`, `..`, links leaving the folder) returns 404.
- **SRV-03** · Responses carry `Cache-Control: no-store`, so that a regenerated PDF shows
  up to date.
