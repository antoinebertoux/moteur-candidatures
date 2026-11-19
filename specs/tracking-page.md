# "Suivi des candidatures" page

Private claude.ai artifact (slug `34e12927-7588-4297-9860-6ed2374e9e20`), with its
database hosted by Claude: collection `candidatures`, one document per application, whose
identifier follows ID-02. Its code is [`page-suivi/index.html`](../page-suivi/index.html). The interface is in French; labels below are quoted as they
appear. These rules are checked by hand.

## Document fields

`type`, `entreprise`, `poste`, `lieu`, `url`, `source`, `moteur` (`A`, `B`, `manuel`;
missing = `manuel`), `statut`, `score`, `resume`, `lettre_demandee`, `lettre`
(`oui`/`non`), `cv_ref`, `lettre_ref`, `contact`, `notes`, `texte_offre`, `consigne`,
`retouche_le`, `lettre_refaire_le`, `lettre_consigne`, `suite`, `motif_refus`,
`motif_detail`, `date_ajout`, `date_maj`, `date_postulee`, `preparation_demandee_le`,
`pretentions`, `entretien_infos`, `preparation_consigne`, `preparation`,
`preparation_le`.

## Workflow

- **PAGE-01** · Six steps, each with its counter (according to the active filters): À
  traiter, À préparer, À valider, À envoyer, Postulée, Refusée (statuses: see the
  [README](README.md#statuses)).
- **PAGE-02** · Actions per step:

  | Step | Actions |
  | --- | --- |
  | À traiter | **Oui** → À préparer · **Non** → Refusée |
  | À préparer | "CV et lettre à générer"; "CV prêt, passer à valider" (manual) |
  | À valider | **Valider** → À envoyer · edit request (PAGE-05) |
  | À envoyer | **Marquer comme postulée** → Postulée, sent date = today · edit request |
  | Postulée | follow-up (PAGE-08) |
  | Refusée | **Remettre à traiter** |

  Except in À traiter and Refusée: **Abandonner** → Refusée. Everywhere: **Supprimer**,
  with confirmation.
- **PAGE-03** · À traiter is sorted by descending score; the other steps by last change,
  most recent first.
- **PAGE-04** · Filters: type (ads / unsolicited), engine (A, B, manual) and free search
  on company, title and location (accents ignored).
- **PAGE-05** · Edit request: in À valider or À envoyer, User writes an instruction
  then clicks "Redemander avec la consigne"; the application goes back to À préparer with
  the time of the request. Without an instruction, the page refuses.
- **PAGE-06** · Letter: as long as no letter is made (from À traiter to À envoyer), a
  "Lettre : oui / non" toggle shows and changes the choice; without a choice, the letter
  is planned if the ad asks for one or according to ID-04. Once the letter exists, a
  "Régénérer la lettre" button (with an optional instruction; empty = rewritten from
  scratch) records the time of the request. Chips show "Lettre à régénérer" and "Lettre à
  générer".
- **PAGE-07** · In À préparer, for an ad (not an unsolicited application) that does not
  come from engine B and has no text, the page asks to paste the ad text, otherwise the
  CV will be generic.
- **PAGE-08** · Postulée: the follow-up is En attente, Relancée, Entretien, Refus de
  l'entreprise or Proposition reçue, and shows as a chip.
- **PAGE-10** · Refusal reason: **Non** (À traiter) and **Abandonner** open a short choice
  of reasons before moving the application to Refusée: Compétences inadaptées, Trop
  senior, Trop junior, Salaire, Lieu / télétravail, Secteur ou mission, Conseil / ESN,
  Trop ML pur, Entreprise, Doublon, Autre — stored as `motif_refus`
  (`competences`, `trop_senior`, `trop_junior`, `salaire`, `lieu`, `secteur`, `conseil`,
  `ml_pur`, `entreprise`, `doublon`, `autre`), with an optional free-text detail
  (`motif_detail`, at most 200 characters). "Refuser sans motif" stays possible. In
  Refusée the reason shows as a chip and can be changed; **Remettre à traiter** clears it.
- **PAGE-11** · Interview preparation ([interview-prep.md](interview-prep.md)): on a
  Postulée application whose follow-up is Entretien, a "Préparer l'entretien" button
  opens a short form — salary announced, interview details (date, format,
  interviewers), instruction, all optional and kept from one request to the next — and
  records `preparation_demandee_le`. While the request is more recent than the sheet, a
  "Préparation en cours" chip shows. Once `preparation` has arrived, a "Préparation"
  button opens the sheet (Markdown shown formatted, readable on mobile) with its date,
  and the request button becomes "Refaire la préparation".
- **PAGE-09** · Every change sets `date_maj` to today; a failed save shows a message
  without losing the input.

## Manual entry

- **PAGE-20** · Form: type, company (required), title or target role, location, link,
  contact, starting status (Postulée by default, with today as sent date), notes, ad text
  (at most 20,000 characters). Engine = `manuel`.
- **PAGE-21** · An entry already present (same identifier) is rejected.

## Import and export

- **PAGE-30** · The engine B file is imported with the button or by dropping it anywhere
  on the page. An unknown entry is created in À traiter (engine `A` if the file says so,
  otherwise `B`). An entry without a company is ignored. A summary is shown (added,
  updated, ignored).
- **PAGE-31** · A known entry only receives updates to `cv_ref`, `lettre_ref`, `resume`,
  `score`, `lettre_demandee`, `preparation` and `preparation_le`. User's decisions are never overwritten.
- **PAGE-32** · When a CV arrives for an application in À préparer, it moves to À valider
  and its instruction is cleared — unless an edit was requested after that CV was
  generated (PDF older than the request).
- **PAGE-33** · A letter regeneration request is cleared as soon as a letter more recent
  than the request arrives.
- **PAGE-34** · Export: downloads `candidatures-export.json`
  (`{"exporte_le": …, "candidatures": [all documents]}`); if downloading is not possible,
  the content is shown for copying.

## Direct link with engine B

- **PAGE-35** · The page declares the MCP server `host:moteur` (tools `propositions` and
  `decisions`, ECH-20). When it answers, a "Moteur B : connecté" chip shows, with the time
  of the last synchronisation; otherwise "Moteur B : non connecté" and the import and
  export buttons stay the way to exchange (PAGE-30 to PAGE-34).
- **PAGE-36** · Engine B → page: at load, then every minute while the page is visible,
  and on the "Synchroniser" button, the page reads `propositions` and imports them with
  the rules PAGE-30 to PAGE-33, without a summary when nothing changed.
- **PAGE-37** · Page → engine B: after the first successful read, then a few seconds
  after any change in the database (a decision, a letter choice, an edit request, a
  scheduled task adding an entry), the page sends all its documents to `decisions`.
  Changes made in quick succession are sent together, one call at a time.
- **PAGE-38** · A failed call does not block the page: the chip says why (engine not
  running, access refused in the app) and the next synchronisation tries again; a
  refused access is not asked again in a loop.

## Links

- **PAGE-40** · The CV and Lettre buttons open `cv_ref` / `lettre_ref`: an http(s) link as
  is, a relative path through `http://127.0.0.1:8765/<path>` (SRV-01), any other scheme is
  ignored. The ad link is shown only if it is http(s).

## Engine comparison

- **PAGE-50** · A table counts, for A, B and manual: proposed, to process, accepted (À
  préparer, À valider, À envoyer or Postulée), rejected, applied, and the acceptance rate
  = accepted / (accepted + rejected).

## Robustness and display

- **PAGE-60** · The list updates live when the database changes (scheduled tasks, another
  device).
- **PAGE-61** · Database unavailable or disconnected: a message says so; with no answer
  after 10 s, a waiting message is shown.
- **PAGE-62** · Light or dark theme following the system; on mobile, steps wrap onto
  three columns.
