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

- **CLI-01** · The commands above exist and chain the steps shown. *(untested)*
- **CLI-02** · `--config <file>` (default `config.toml` in the current folder) and `-v`
  (detail per source) can be written before or after the command.
- **CLI-03** · A configuration error, an unreadable export or a missing file prints
  "Erreur : …" and returns exit code 1, without a Python traceback. *(untested)*

## PDF server (`moteur servir`)

The page lives on claude.ai, where the browser blocks `file://` links. The CV and Lettre
buttons therefore point to this small server.

- **SRV-01** · It listens on `127.0.0.1` only, port 8765 by default (the page assumes
  8765). *(untested)*
- **SRV-02** · It only serves files under `/Candidatures/…`, read-only. Everything else
  (`config.toml`, `.env`, `latex/`, `..`, links leaving the folder) returns 404.
- **SRV-03** · Responses carry `Cache-Control: no-store`, so that a regenerated PDF shows
  up to date.
