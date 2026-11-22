# Tracking page ("Application tracker")

Private claude.ai artifact (slug `34e12927-7588-4297-9860-6ed2374e9e20`), with its
database hosted by Claude: collection `candidatures`, one document per application, whose
identifier follows ID-02. Its code is [`page-suivi/index.html`](../page-suivi/index.html). The interface is in English by default and in French on request (PAGE-63); labels below
are quoted in English. These rules are checked by hand.

## Document fields

`type`, `entreprise`, `poste`, `lieu`, `url`, `source`, `moteur` (`A`, `B`, `manuel`;
missing = `manuel`), `statut`, `score`, `resume`, `lettre_demandee`, `lettre`
(`oui`/`non`), `cv_ref`, `lettre_ref`, `contact`, `notes`, `texte_offre`, `consigne`,
`retouche_le`, `lettre_refaire_le`, `lettre_consigne`, `suite`, `motif_refus`,
`motif_detail`, `date_ajout`, `date_maj`, `date_postulee`, `preparation_demandee_le`,
`pretentions`, `entretien_infos`, `preparation_consigne`, `preparation`,
`preparation_le`, `site_entreprise`, `linkedin_entreprise`, `liens_manuels`.

## Workflow

- **PAGE-01** · Six steps, each with its counter (according to the active filters): To
  review, To prepare, To validate, To send, Applied, Rejected (statuses: see the
  [README](README.md#statuses)).
- **PAGE-02** · Actions per step:

  | Step | Actions |
  | --- | --- |
  | To review | **Yes** → To prepare · **No** → Rejected |
  | To prepare | "CV and letter to generate"; "CV ready, move to validation" (manual) |
  | To validate | **Validate** → To send · edit request (PAGE-05) |
  | To send | **Mark as applied** → Applied, sent date = today · edit request |
  | Applied | follow-up (PAGE-08) |
  | Rejected | **Back to review** |

  Except in To review and Rejected: **Drop** → Rejected. Everywhere: **Delete**,
  with confirmation.
- **PAGE-03** · To review is sorted by descending score; the other steps by last change,
  most recent first.
- **PAGE-04** · Filters: type (ads / unsolicited), engine (A, B, manual) and free search
  on company, title and location (accents ignored).
- **PAGE-05** · Edit request: in To validate or To send, User writes an instruction
  then clicks "Request again with this instruction"; the application goes back to To prepare with
  the time of the request. Without an instruction, the page refuses.
- **PAGE-06** · Letter: as long as no letter is made (from To review to To send), a
  "Letter: yes / no" toggle shows and changes the choice; without a choice, the letter
  is planned if the ad asks for one or according to ID-04. Once the letter exists, a
  "Regenerate the letter" button (with an optional instruction; empty = rewritten from
  scratch) records the time of the request. Chips show "Letter to regenerate" and "Letter
  to generate".
- **PAGE-07** · In To prepare, for an ad (not an unsolicited application) that does not
  come from engine B and has no text, the page asks to paste the ad text, otherwise the
  CV will be generic.
- **PAGE-08** · Applied: the follow-up is Waiting, Followed up, Interview, Rejected by
  the company or Offer received, and shows as a chip.
- **PAGE-10** · Refusal reason: **No** (To review) and **Drop** open a short choice
  of reasons before moving the application to Rejected: Skills mismatch, Too senior,
  Too junior, Salary, Location / remote, Sector or mission, Consulting firm, Too pure ML,
  Company, Duplicate, Other — stored as `motif_refus`
  (`competences`, `trop_senior`, `trop_junior`, `salaire`, `lieu`, `secteur`, `conseil`,
  `ml_pur`, `entreprise`, `doublon`, `autre`), with an optional free-text detail
  (`motif_detail`, at most 200 characters). "Reject without a reason" stays possible. In
  Rejected the reason shows as a chip and can be changed; **Back to review** clears it.
- **PAGE-11** · Interview preparation ([interview-prep.md](interview-prep.md)): on a
  Applied application whose follow-up is Interview, a "Prepare the interview" button
  opens a short form — salary announced, interview details (date, format,
  interviewers), instruction, all optional and kept from one request to the next — and
  records `preparation_demandee_le`. While the request is more recent than the sheet, a
  "Preparation in progress" chip shows. Once `preparation` has arrived, a "Preparation"
  button opens the sheet (Markdown shown formatted, readable on mobile) with its date,
  and the request button becomes "Redo the preparation".
- **PAGE-12** · Ad text: every application whose `texte_offre` is not empty shows a
  small, discreet "View ad text" link (French: "Voir le texte de l'offre"), smaller than
  the action buttons, whatever its step. It is read-only: it opens a window showing the
  stored text as Markdown (headings, lists, bold; plain text shows as is), readable on
  mobile, with a "Copy" button and the ad link when it is http(s); nothing can be
  edited there. The text is kept in
  the page's database, so it stays readable after the employer removes the ad.
- **PAGE-09** · Every change sets `date_maj` to today; a failed save shows a message
  without losing the input.

## Manual entry

- **PAGE-20** · Form: type, company (required), title or target role, location, link,
  company website and LinkedIn page (optional; filled in = `liens_manuels`), contact, starting status (Applied by default, with today as sent date), notes, ad text
  (at most 20,000 characters). Engine = `manuel`.
- **PAGE-21** · An entry already present (same identifier) is rejected.

## Import and export

- **PAGE-30** · The engine B file is imported with the button or by dropping it anywhere
  on the page. An unknown entry is created in To review (engine `A` if the file says so,
  otherwise `B`). An entry without a company is ignored. A summary is shown (added,
  updated, ignored).
- **PAGE-31** · A known entry only receives updates to `cv_ref`, `lettre_ref`, `resume`,
  `score`, `lettre_demandee`, `preparation` and `preparation_le`, and to `site_entreprise`
  and `linkedin_entreprise` unless `liens_manuels` is true, and to `texte_offre` only when
  the page has none (ECH-05). User's decisions are never overwritten. An entry marked
  `archive` (ECH-06) only fills in a missing `texte_offre` of a known document; an
  unknown one is ignored, never created.
- **PAGE-32** · When a CV arrives for an application in To prepare, it moves to To validate
  and its instruction is cleared — unless an edit was requested after that CV was
  generated (PDF older than the request).
- **PAGE-33** · A letter regeneration request is cleared as soon as a letter more recent
  than the request arrives.
- **PAGE-34** · Export: downloads `candidatures-export.json`
  (`{"exporte_le": …, "candidatures": [all documents]}`); if downloading is not possible,
  the content is shown for copying.

## Direct link with engine B

- **PAGE-35** · The page declares the MCP server `host:moteur` (tools `propositions`,
  `decisions`, `entreprises` and `selection`, ECH-20). When it answers, an "Engine B: connected" chip shows, with the time
  of the last synchronisation; otherwise "Engine B: not connected" and the import and
  export buttons stay the way to exchange (PAGE-30 to PAGE-34).
- **PAGE-36** · Engine B → page: at load, then every minute while the page is visible,
  and on the "Sync" button, the page reads `propositions` and imports them with
  the rules PAGE-30 to PAGE-33, without a summary when nothing changed.
- **PAGE-37** · Page → engine B (the ad text is sent whatever the status, BASE-14): after the first successful read, then a few seconds
  after any change in the database (a decision, a letter choice, an edit request, a
  scheduled task adding an entry), the page sends all its documents to `decisions`.
  Changes made in quick succession are sent together, one call at a time.
- **PAGE-38** · A failed call does not block the page: the chip says why (engine not
  running, access refused in the app) and the next synchronisation tries again; a
  refused access is not asked again in a loop.

## Links

- **PAGE-40** · The CV and Letter buttons open `cv_ref` / `lettre_ref`: an http(s) link as
  is, a relative path through `http://127.0.0.1:8765/<path>` (SRV-01), any other scheme is
  ignored. The ad link is shown only if it is http(s).
- **PAGE-41** · Company links: next to the ad link, every application with a company
  shows two links, opening in a new tab. Each uses the stored address
  (`site_entreprise`, `linkedin_entreprise`, [company-links.md](company-links.md)) when
  it is http(s); otherwise it is computed from the company name (nothing stored, so older
  applications get them too):
  - "Company LinkedIn" → LinkedIn's company search,
    `https://www.linkedin.com/search/results/companies/?keywords=<company>`;
  - "Company website" → a web search that opens the first result directly,
    `https://duckduckgo.com/?q=!ducky+<company>`.

  The company name is URL-encoded. For an unsolicited application, whose link is already
  the company website (COL-03), that link is labelled "Company
  website" and no search link is added for the site.
- **PAGE-42** · Correcting the links: the detail of an application has two fields "Company
  website" and "Company LinkedIn" (http(s) only, otherwise the page
  refuses with a message). Saving a changed value sets `liens_manuels` to true, so that
  the engine's links no longer replace it (PAGE-31) and the engine applies it to the
  whole company (BASE-13). Emptying both fields and saving sets `liens_manuels` to false:
  the engine's links come back at the next synchronisation.

## Engine comparison

- **PAGE-50** · A table counts, for A, B and manual: proposed, to process, accepted (To
  prepare, To validate, To send or Applied), rejected, applied, and the acceptance rate
  = accepted / (accepted + rejected).

## Search options

- **PAGE-70** · An "Options" button in the header opens the "Search options" panel.
  It reads the tool `entreprises` (ECH-27) when it opens. When engine B is not connected
  (PAGE-35), the panel says the choices need engine B running and shows nothing else.
- **PAGE-71** · The panel shows, from top to bottom: the search criteria (PAGE-75); the
  keyword sources (PAGE-76); the sizes; the sectors, each
  with its number of companies (a sector with none is not shown); then the companies, grouped by sector, with a search
  field. Each company shows its name, a "catalogue" or "mine" badge, a "searched" box
  and an "unsolicited" box. A company ticked but left out by its sector or size is shown
  greyed out with the reason. A line says that the choices apply to engine B, not to the
  scheduled tasks.
- **PAGE-72** · Each tick calls `selection` (ECH-28) at once and redraws the panel from
  its answer. A failed call puts the box back and says why, as PAGE-38.
- **PAGE-73** · A company, a group, a source or a criterion whose state differs from the
  default shows a "default" link that sends `null` for it. A "Back to defaults" button,
  after a confirmation, does it for every choice, criteria included.
- **PAGE-74** · The page keeps none of these choices in its own database: engine B holds
  them (BASE-15, BASE-17), on the PC.
- **PAGE-75** · Search criteria (CONF-13), in this order: keywords, exclusions,
  locations, countries, search terms. Each list shows its values as chips with a ×, and a
  field where Enter or a comma adds what is typed. Each addition or removal calls
  `selection` at once (PAGE-72); a value refused (CONF-14) is left in the field with the
  reason. A line under each list says how it is used:
  - keywords: the title must contain at least one; empty = no filter;
  - exclusions: a title containing one is rejected;
  - locations: an ad's location must contain one of them (e.g. "lyon", "69", "remote");
    empty = anywhere; an ad without location always passes;
  - countries: two-letter codes (fr, gb, be…); used by the sites that search by country
    and to pick the catalogue companies by default; empty = every country;
  - search terms: typed in the search box of the sites that cannot list all their ads;
    each term costs one search per company on those sites, so keep a few broad terms.
  A line says that the changes apply from the next collection, and that the ads already
  in the list stay.
- **PAGE-76** · Each keyword source shows a box: ticked if it is turned on (CAT-15).
  France Travail without its credentials is greyed out, "credentials missing (.env)". A
  source with its own search terms in `config.toml` says so (CONF-15).

## Robustness and display

- **PAGE-60** · The list updates live when the database changes (scheduled tasks, another
  device).
- **PAGE-61** · Database unavailable or disconnected: a message says so; with no answer
  after 10 s, a waiting message is shown.
- **PAGE-62** · Light or dark theme following the system; on mobile, steps wrap onto
  three columns.

## Interface language

- **PAGE-63** · The interface is in English by default; French is also available. A
  language menu in the header shows the current language's flag (🇬🇧 English,
  🇫🇷 Français, drawn as small images so that they look the same on every system); it
  opens a short list of the languages, each with its flag and its own name. Choosing one
  translates the whole page at once — labels, buttons, chips, messages, placeholders,
  tooltips, the tab title and dates and times — without reloading and without losing
  what is being typed.
- **PAGE-64** · The choice is saved in the page's database (collection `reglages`,
  document `page`, field `langue`: `en` or `fr`), so it is the same at the next opening,
  on every device. It is also kept in the browser so that the page opens directly in the
  right language before the database answers. An unknown or missing value means English.
  If the choice cannot be saved, the page still switches and says the choice will not be
  remembered.
- **PAGE-65** · Only the interface is translated. The data (company, title, summary,
  notes, preparation sheet), the stored values (statuses, reasons, `lettre` = `oui` /
  `non`) and the files exchanged with engine B do not change with the language.
- **PAGE-66** · Every text of the interface comes from one dictionary per language, with
  the same keys. Adding a language means adding its dictionary and its flag; a key missing
  from a language falls back to English.
