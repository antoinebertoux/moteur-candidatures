# Engine B local database

`moteur.sqlite3` keeps every application seen by engine B, with its score, its status
(see the table in the [README](README.md#statuses)) and the paths of its PDFs.

- **BASE-01** · Only unknown applications (identifier ID-02) are added; an ad already
  seen is never reinserted nor reset.
- **BASE-02** · An added ad is `a_noter`. An unsolicited application has nothing to
  score: it is directly `notee`, with a letter planned.
- **BASE-03** · A score is recorded only for an `a_noter` application, which becomes
  `notee`.
- **BASE-04** · What goes to the page: `notee` applications (proposals) and `generee`
  ones (files ready).
- **BASE-05** · Decisions from the page: `acceptee` → `acceptee`, `refusee` → `refusee`,
  `postulee` → `close`. The page's other statuses (`a_traiter`, `prete`, `validee`)
  change nothing. A decision identical to the current state does not count as a change.
- **BASE-06** · A `generee` file that the page still shows as "accepted" (not imported
  yet) **is not regenerated**, unless an edit instruction comes with it: it then goes
  back to `acceptee` with that instruction.
- **BASE-07** · An application accepted in the page but unknown to the database (manual
  entry, engine A) is added as `acceptee`, with the ad text provided by the page. For an
  application already known, only a missing ad text is filled in.
- **BASE-08** · The page's "letter yes / no" choice is stored in the database. A
  *missing letter* is a `generee` file with a letter planned but no letter PDF yet.
- **BASE-09** · A successful generation moves the file to `generee`, stores its PDFs and
  clears the edit instruction; a successful letter clears the letter instruction.
- **BASE-10** · A database created by an older version gets the columns added since, if
  needed, without data loss.
