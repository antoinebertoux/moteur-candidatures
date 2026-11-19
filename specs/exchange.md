# Files exchanged with the page

The page is a claude.ai artifact: it cannot call the PC (the platform blocks every
`fetch()` to another host, `127.0.0.1` included). Both sides therefore exchange JSON files
that User drops in by hand.

## Engine B → page: `echange/pour-la-page.json`

- **ECH-01** · Array of entries with: `type`, `entreprise`, `poste`, `lieu`, `url`,
  `source`, `moteur` = `B`, `resume`, `lettre_demandee`, and `score` if the ad is scored.
  **No identifier**: the page recomputes it (ID-02).
- **ECH-02** · A generated folder adds `cv_ref` and `genere_le` (modification date of the
  CV PDF), and if it has a letter `lettre_ref` and `lettre_generee_le`. Dates use the
  format `2026-11-17T21:45:48.123Z`, comparable with the page's.

## Page → engine B: `candidatures-export.json`

- **ECH-10** · Accepted as `{"candidatures": [...]}` or directly as the array. A file that
  is not JSON or has no array is rejected with a message. Entries without `id` or
  `statut` are ignored.
- **ECH-11** · Fields read: `id`, `statut`, `consigne`, `lettre_demandee`, `lettre`
  (`oui` / `non` or boolean; missing = no choice), `lettre_refaire_le`,
  `lettre_consigne`, and enough to rebuild the ad if `entreprise` and `poste` are
  present (`type`, `lieu`, `url`, `source`, `texte_offre`).
- **ECH-12** · `moteur decisions <file>` applies, in this order: adding unknown accepted
  applications (BASE-07); letter choice of accepted, ready or approved applications
  (BASE-08); status decisions (BASE-05, BASE-06); letter regenerations (LET-07). It then
  prints the summary and what is left to generate. *(untested)*
