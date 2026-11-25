# Applying with Claude

The skill `skills/postuler/SKILL.md` of the repository, installed in the Claude desktop
app, tells Claude how to send the applications User has approved, on the employers'
websites. Its rules guide a conversation and a browser, so none of them can be checked
by a test.

## What to send

- **APPLY-01** · The only source is the database of the tracking page (collection
  `candidatures`), never engine B (`propositions`, local database, `echange/` files).
  *(untested: behaviour of Claude)*
- **APPLY-02** · Only applications whose `statut` is `validee` (To send) are sent. An
  application in another status is not sent, even when User names it; Claude says so.
  *(untested: behaviour of Claude)*
- **APPLY-03** · Facts entered in forms come from `latex/commun/infos-candidature.md`
  (personal, ignored by Git; template `latex-exemple/commun/infos-candidature.exemple.md`),
  then `latex/commun/coordonnees.tex`,
  then the CV. Claude enters them without asking; a fact found nowhere is asked, and
  may then be added to the profile. *(untested: behaviour of Claude)*

## Accounts and blockers

- **APPLY-04** · When the site lets User apply without an account, Claude does not
  create one. *(untested: behaviour of Claude)*
- **APPLY-05** · When an account is required, Claude stops on the sign-up or sign-in
  page and waits for User to create it or sign in, then goes on. Claude never creates an
  account nor types a password. A CAPTCHA is left to User. A closed ad is reported; its
  status is not changed. *(untested: behaviour of Claude)*

## Filling the form

- **APPLY-06** · The CV (`cv_ref`) is always attached; the letter (`lettre_ref`) when the
  form has a letter field. A required letter that does not exist is asked.
  *(untested: behaviour of Claude)*
- **APPLY-07** · Every salary field is asked to User, even when a reference figure is in
  the profile (Claude may suggest it). *(untested: behaviour of Claude)*
- **APPLY-08** · Every free-text answer is drafted by Claude, shown to User, and entered
  only once validated, exactly as validated. *(untested: behaviour of Claude)*
- **APPLY-09** · Only consents required by the application are ticked; marketing and
  talent-pool boxes stay unticked unless User asks. *(untested: behaviour of Claude)*

## Sending and after

- **APPLY-10** · Before the final click, Claude shows a recap (files, salary, free texts,
  consents) and sends only after User agrees, then checks the confirmation.
  *(untested: behaviour of Claude)*
- **APPLY-11** · Once sent, the page's document gets `statut` `postulee`, and
  `date_postulee` and `date_maj` set to today; engine B is told through `decisions`
  when its tools are available. *(untested: behaviour of Claude)*
- **APPLY-12** · Claude writes `reponses-formulaire.md` in the application's folder: date,
  form address, account used (never a password), salary given, validated texts, other
  notable answers. *(untested: behaviour of Claude)*
- **APPLY-13** · The application's folder moves to `Candidatures/sent/`, and `cv_ref` /
  `lettre_ref` in the page follow the new paths. *(untested: behaviour of Claude)*
- **APPLY-14** · Claude ends with the applications sent, those waiting for User and
  those not sent, with the reason. *(untested: behaviour of Claude)*
