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
- **BASE-11** · The page's refusal reason and detail (PAGE-10) are stored with a `refusee`
  application, and replaced when the page changes them; an unknown reason is stored as
  `autre`. Leaving `refusee` clears them.
- **BASE-12** · A preparation request from the page (PREP-01) is stored with its time,
  salary announced, interview details and instruction, whatever the application's state;
  an older or identical request changes nothing. A successful sheet stores its text and
  date (PREP-32). The application's status is never changed by a preparation.
- **BASE-13** · Company links (LNK-01): a document whose `liens_manuels` is true sets its
  company's website and LinkedIn page as User's correction (LNK-02), an empty field
  meaning "no correction" for that link. A document whose `liens_manuels` is false or
  missing removes a correction previously sent from that same application.
- **BASE-14** · The ad text is kept for every application, whatever its state, so that
  it can still be read once the employer has taken the ad down. A text is never erased
  nor replaced by an empty one. A text sent by the page (`texte_offre`, ECH-11) fills in
  a missing text of a known application whatever its status (not only an accepted one,
  BASE-07).
- **BASE-15** · User's choices about companies, sectors, sizes and sources (CAT-12) are
  kept in the local database, one per company (keyed by the normalised name, ID-01),
  sector, size or source. Going back to the default removes the choice. They are not
  applications: `propositions` and `pour-la-page.json` do not carry them.
- **BASE-16** · User's own companies (CAT-20) are kept in the local database, one per
  normalised name, with their fields and the date they were added or last updated.
  Removing one (CAT-25) deletes it. Like BASE-15, they are not applications.
- **BASE-10** · A database created by an older version gets the columns added since, if
  needed, without data loss.
