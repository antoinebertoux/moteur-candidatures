# Interview preparation

When a company answers an application, User clicks "Prepare the interview" in the page.
Engine B then gathers everything that was sent for this application, has Claude research
the company on the web, and writes a ready-to-read preparation sheet in French.

There are two kinds of sheet, one per interview step (PAGE-08): the **HR sheet** for the
first interview (recruiter or HR, follow-up `entretien`), and the **technical / manager
sheet** for the next ones (follow-up `entretien_technique`), deeper and centred on the
job itself (PREP-50 to PREP-55). Unless a rule says otherwise, a rule applies to both.

## Request

- **PREP-01** · The request comes from the page (PAGE-11): `preparation_demandee_le`
  (time of the click) for the HR sheet, `preparation_technique_demandee_le` for the
  technical / manager sheet, with optional `pretentions` (salary User announced, free
  text), `entretien_infos` (date, format, interviewers…), `preparation_consigne` (an
  instruction, e.g. "insiste sur le RAG") and, for the technical sheet,
  `retour_entretien_rh` (what was said in the earlier interviews). These fields are shared
  by both kinds: the latest request sets them. Engine B stores them with the application
  (BASE-12).
- **PREP-02** · A request is *pending* when it is more recent than the current sheet of
  its kind (or there is no such sheet). Clicking again after a sheet exists asks for a
  new one, which replaces the previous sheet of the same kind only: the HR sheet stays
  when the technical one is written.
- **PREP-03** · An application unknown to engine B (manual entry, engine A) is added from
  the page's document, like BASE-07, so that it can be prepared.

## What Claude receives

- **PREP-10** · Everything about the application: company, title, location, link, type,
  sent date, follow-up and notes from the page (replies, follow-ups), the ad text
  (`offre.md` or the page's text), the CV and letter as sent (`cv.tex`, `lettre.tex` of
  the folder, when they exist), `pretentions`, `entretien_infos` and the instruction,
  marked as taking priority.
- **PREP-11** · User's background, as material for answers: the `profil` from
  `config.toml`, the CV bank of the CV's language and the letter paragraph bank.
- **PREP-12** · From `latex/commun/infos-candidature.md`, only the *Situation* (except
  the sorting criterion line), *Préférences* and *Réponses types* sections. **The salary
  floor is never sent** (INV-03), nor identity or contact details.

## The call

- **PREP-20** · One `claude -p` call per sheet with the writing model of
  `[modeles] preparation` (default `sonnet`; technical sheet: PREP-52). Unlike CLA-01, this call may use the
  **WebSearch and WebFetch** tools only (no files, no shell, no MCP), for the company
  research. No answer within 15 minutes is a failure.
- **PREP-21** · A failed sheet is reported and stays pending; the others carry on.

## The sheet

- **PREP-30** · Instructions given to Claude *(untested: instruction to the model)*. The
  sheet is in French and has, in this order:
  1. **À retenir** (a few lines): role, company, sent date, interview details, salary
     announced (or "non renseigné : à décider avant l'entretien"), notice period, what
     the letter promised.
  2. **À relire en priorité**: each project or claim of the CV and letter likely to be
     probed, with the figures and facts to have in mind, taken from the banks.
  3. **L'entreprise**: creation date, headcount, revenue or last funding round (start-ups:
     amount, date, investors), leaders, products, recent news (last 12 months),
     competitors, and for a public body its mission and attachment. Each figure gives its
     source and date; what is not found is written "non trouvé", never guessed.
  4. **Le poste**: what the ad really asks, matching points, gaps and how to answer them.
  5. **Questions probables**: about ten, each with a suggested answer or a story
     (situation, action, result) built only from User's real experience; in the
     interview's language when the ad is in English.
  6. **Questions à poser**: five to eight, specific to the company and the role.
- **PREP-31** · No invented experience, figure or fact about User: anything not in the
  material of PREP-10 to PREP-12 is left out. *(untested: instruction to the model)*
- **PREP-32** · The sheet is written to `preparation-entretien.md` in the application's
  folder (CV-01, created if missing, with its `offre.md`), replacing a previous sheet. It
  is also stored in engine B's database with its date and sent to the page (ECH-03),
  where it is read (PAGE-11). A sheet longer than 40,000 characters is cut, with a
  final line saying so.

## Running it

- **PREP-40** · `moteur prepare [id…]` prepares the given applications, or otherwise
  every pending request of both kinds, then exports for the page. Given identifiers get
  an HR sheet, or a technical / manager sheet with `--technical`.
- **PREP-41** · **Automatic start**: when the `decisions` tool (ECH-22) records at least
  one new pending request, it starts `moteur prepare` in the background, detached, and
  answers at once without waiting for it (ECH-26).
- **PREP-42** · Only one `moteur prepare` runs at a time, whatever the kind (lock file next to the
  database). A run started while another is going stops at once; the running one checks
  for new pending requests before it ends, so no request is left behind. A lock left by
  a process that no longer exists is ignored.
- **PREP-43** · The background run writes its output to `echange/preparation.log`
  (replaced at each run), so that a failure can be read afterwards.

## Technical / manager interview

- **PREP-50** · The technical / manager sheet is asked for once the follow-up is
  `entretien_technique` (PAGE-11). It is a separate request, with its own time, sheet and
  date (PREP-01, PREP-02); it is meant for an interview with the future manager or the
  team — some technique, much about past projects and about the job itself — or a
  technical test, so it goes much further than the HR sheet.
- **PREP-51** · Claude receives everything of PREP-10 to PREP-12, plus
  `retour_entretien_rh` and the HR sheet when there is one, given as already known: the
  technical sheet builds on it instead of repeating it.
- **PREP-52** · The call uses the model of `[modeles] preparation_technique` (default
  `opus`), with the same tools as PREP-20 (WebSearch and WebFetch only). No answer within
  30 minutes is a failure.
- **PREP-53** · Instructions given to Claude *(untested: instruction to the model)*. The
  sheet is in French and has, in this order:
  1. **À retenir**: role, interview details, interlocutors (their public professional
     background when they are named: role, career, talks, publications; nothing
     private), what the earlier interviews said and what remains to prove.
  2. **L'équipe et le contexte technique**: the team and where it sits, products and
     users, technical stack and practices (engineering blog, public repositories, talks,
     other ads of the company), data and regulatory context, the challenges the team
     likely faces now. Sources and dates as in PREP-30; "non trouvé" when not found.
  3. **Ce que je ferai sur place**: the likely missions and deliverables of the first
     months, how User's experience maps onto each, and a 30-60-90 day outline to suggest.
  4. **Mes projets à raconter**: three to five projects of the CV chosen for this role,
     each with context, User's own role, technical choices and trade-offs, results with
     their figures, what was learnt, and the deep-dive questions to expect with answers.
  5. **Questions techniques probables**: the concepts of the ad and the stack likely to
     be asked, each with a short, correct answer and the link to User's experience; the
     likely exercise (case study, system design, live coding, take-home) and how to
     approach it.
  6. **Questions du manager**: way of working, autonomy, priorities, disagreement,
     collaboration with product and business, failure — answers built as stories
     (situation, action, result) from User's real experience.
  7. **Points de vigilance**: the gaps the interviewer may probe and an honest way to
     answer each; the salary if it comes up again.
  8. **Questions à poser**: eight to twelve, for the manager and the team (missions,
     success criteria, team, stack, roadmap, decision-making).
  Answers are in the interview's language when the ad is in English. PREP-31 applies.
- **PREP-54** · The sheet is written to `preparation-entretien-technique.md` in the
  application's folder, replacing a previous technical sheet, stored in engine B's
  database with its date and sent to the page as `preparation_technique` and
  `preparation_technique_le` (ECH-03). A sheet longer than 60,000 characters is cut, with
  a final line saying so.
- **PREP-55** · A pending technical request whose model call fails stays pending, like
  PREP-21; the HR sheet is never touched by a technical request.
