# Engine A: scheduled tasks in Claude

Claude scheduled tasks search the web for job ads and write directly to the page's
database. Their full prompt is in each task's settings, with an anonymised template in
[`taches/`](../taches/README.md); these rules state the contract.
Checked by hand.

## Tasks

| Task | When | Role |
| --- | --- | --- |
| Emploi 2 – Grands groupes et administration | Tuesday 19:44 | public sector and large companies |
| Emploi 4 – Start-ups offres publiées | Monday 19:53 | start-ups and scale-ups |
| Emploi 3 – Relances candidatures | Friday 19:38 | replies received and follow-ups |

## Job search (Emploi 2 and 4)

- **TACHE-01** · Before searching, the task reads the whole database. It never proposes
  an ad already present (same link, or same company and same title), nor an ad from a
  rejected company, unless the role is clearly better, which the summary points out.
- **TACHE-02** · Ads published less than 3 weeks ago, still open, checked on the original
  ad (never an aggregator).
- **TACHE-03** · Sources. Emploi 2: Choisir le service public, the organisations' own
  sites, beta.gouv, large companies' career sites, Welcome to the Jungle, LinkedIn alerts
  received in Gmail. Emploi 4: Welcome to the Jungle, Station F, career pages on ATSs,
  Licorne Society, Cyberjobs, LinkedIn alerts, and a light look at LinkedIn Jobs in the
  PC's browser when reachable (no clicking around, no applying, no messages).
- **TACHE-04** · Calibration: keep senior applied-AI or GenAI roles, lead, head, technical
  project manager, architect, AI expert in a government service; reject consulting firms
  and IT services companies, research or pure ML, junior roles, more than 5 years of
  required experience, displayed salary above €250k, group-level executive roles, 100 %
  on-site, internships. Floor €65k gross (€70k ideally) for the private sector, none for
  French public administration; it is never written to the database. Better 3 excellent
  proposals than 10 average ones, or none.
- **TACHE-07** · Calibration from refusals: the task reads `motif_refus` and `motif_detail`
  of `refusee` documents (except `doublon`) and avoids proposing ads that would be refused
  for the same reason.
- **TACHE-05** · Each ad is written as a new document `candidatures/<identifier ID-02>`
  with `moteur` = `A`, `statut` = `a_traiter`, a score from 0 to 100, a 3–5 sentence
  summary and `lettre_demandee`. **An existing document is never changed nor deleted.**
- **TACHE-06** · The summary starts with "Attention : déjà N candidatures récentes."
  when the organisation has already received, within 6 months, 3 or more applications
  (large company, ministry, scale-up) or 2 or more (start-up).

## Follow-ups (Emploi 3)

- **TACHE-10** · For each Postulée application waiting or followed up, the task looks in
  Gmail for a reply from the company since the sent date. Reply found → `suite` =
  interview, rejection or offer (a mere acknowledgement changes nothing) and a dated line
  appended to the notes.
- **TACHE-11** · No reply after 10 days: a short follow-up draft is prepared (Gmail draft
  if an address is known) and appended to the notes. Nothing is ever sent; User sets
  the follow-up to "Relancée" himself.
- **TACHE-12** · Already followed up and no news for 14 days: flagged as a candidate for
  dropping, without a new follow-up.
- **TACHE-13** · The task only changes `suite`, `notes` (appending only, never erasing)
  and `date_maj`; it never changes the status, and never creates or deletes a document.

## Common

- **TACHE-20** · If the database is unavailable, the task says so on the first line and,
  for job ads, gives them as JSON importable with the "Importer" button.
- **TACHE-21** · Each task sends User a short report (number of additions or checks,
  one line per item); approval happens in the page.
