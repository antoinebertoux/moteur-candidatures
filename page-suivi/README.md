# Tracking page ("Application tracker")

`index.html` is the complete code of the tracking page, as published as a claude.ai
artifact. It is a single HTML file (styles and script included), with no dependency. Its
rules are described in [`specs/tracking-page.md`](../specs/tracking-page.md).

The interface is in English by default, and in French through the flag menu in the
header (PAGE-63). The choice is saved in the page's database and also kept in the
browser, so the page reopens in the same language.

The page only works when opened from Claude: it relies on these artifact capabilities,
provided by `window.claude.use(...)`:

| Capability | Use |
| --- | --- |
| `db` | database hosted by Claude: collection `candidatures` (one document per application) and document `reglages/page` (interface language) |
| `downloads` | "Export" button (`candidatures-export.json`) |
| `user` | declared on the published page |
| `mcp` | local server `host:moteur` (tools `propositions`, `decisions`): direct link with engine B, only in the PC's Claude desktop app |

Opened outside Claude (locally in a browser), it shows "The database is not available in
this view".

## Installing your own page

1. In a Claude conversation, ask: "Publish `page-suivi/index.html` as an artifact, with
   the capabilities `db`, `downloads`, `user` and `mcp` (`host:moteur`, tools
   `propositions` and `decisions`)". Claude creates a private artifact and gives you its
   link.
2. Note the artifact's **slug** (the UUID Claude gives you, or visible in its tools). The
   scheduled tasks need it (`<SLUG_DE_TA_PAGE>` in [`taches/`](../taches/)).
3. The database starts empty. To try it with fake data, ask Claude to write the content
   of [`exemple-base.json`](exemple-base.json) into the `candidatures` collection (one
   document per entry, identifier = the `id` field).
4. For the PDFs (CV and Letter buttons), run `uv run moteur serve` on your PC: the page
   opens `http://127.0.0.1:8765/<path>` (see SRV-01).

## Adding a language

All the interface texts are in the `I18N` object of the script, one dictionary per
language with the same keys. To add one:

1. add its dictionary to `I18N` (a missing key falls back to English);
2. add an entry to `LANGS`: code, its own name, date locale (`de-DE`…) and a flag
   function returning a small SVG;
3. update PAGE-63 and PAGE-64 in [`specs/tracking-page.md`](../specs/tracking-page.md)
   (accepted values of `langue`).

The stored data (statuses, field names, `lettre` = `oui` / `non`) never depend on the
language.

## Database

Collection `candidatures`, one document per application. Identifier:
`<type>_<company>_<title>` normalised (rule ID-02, see
[`specs/identifiers.md`](../specs/identifiers.md)). No special access rule: the default
rules (only the owner writes).

| Field | Type | Contents |
| --- | --- | --- |
| `type` | text | `offre` or `spontanee` |
| `entreprise`, `poste`, `lieu`, `url`, `source` | text | description of the ad |
| `moteur` | text | `A` (Claude tasks), `B` (local engine), `manuel` |
| `statut` | text | `a_traiter`, `acceptee`, `prete`, `validee`, `postulee`, `refusee` (see [`specs/README.md`](../specs/README.md#statuses)) |
| `score` | integer | fit from 0 to 100 |
| `resume` | text | 3 to 5 sentences |
| `lettre_demandee` | boolean | letter made by default |
| `lettre` | text | `oui` / `non`, manual choice that wins |
| `cv_ref`, `lettre_ref` | text | relative path or http(s) link of the PDFs |
| `contact`, `notes`, `texte_offre` | text | free |
| `consigne`, `retouche_le`, `lettre_consigne`, `lettre_refaire_le` | text | edit requests |
| `suite` | text | after sending: empty, `relance`, `entretien`, `refus`, `offre` |
| `motif_refus`, `motif_detail` | text | refusal reason (PAGE-10) |
| `preparation_demandee_le`, `pretentions`, `entretien_infos`, `preparation_consigne` | text | interview preparation request (PAGE-11) |
| `preparation`, `preparation_le` | text | preparation sheet (Markdown) and its date, written by engine B |
| `site_entreprise`, `linkedin_entreprise`, `liens_manuels` | text, boolean | company links (PAGE-41, PAGE-42) |
| `date_ajout`, `date_maj`, `date_postulee` | text | `YYYY-MM-DD` |

Document `reglages/page`: field `langue` (`en` or `fr`), the interface language (PAGE-64).

## Backup and restore

- **Back up**: the page's "Export" button, or ask Claude for an export of the
  collection. The file has the shape
  `{"exporte_le": "…", "candidatures": [{"id": "…", …fields}, …]}`.
- **Restore** into a new page: give this file to Claude and ask it to write each entry
  to `candidatures/<id>` (`set` operation). The page's "Import" button is meant for the
  local engine's file (`pour-la-page.json`) and does not recreate decisions.

The real data are not in the repository (see "Personal data" in the
[README](../README.md)): the database export is kept in `prive/`, ignored by Git.
