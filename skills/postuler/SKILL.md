---
name: postuler
description: Apply on employers' websites to the job applications User has already approved (status "To send" / "À envoyer" in the tracking page). Use when User asks to apply, send applications or fill application forms ("postule aux offres validées", "envoie la candidature Alstom", "candidate pour moi").
---

# Applying to approved applications

User has already chosen, prepared and approved these applications. Your job is only to
fill and send each employer's form, with User's files and facts, asking User whenever a
choice is theirs. Rules: [`specs/applying.md`](../../specs/applying.md), APPLY-01 to
APPLY-14.

Talk to User in their language (French, usually). Work on one application at a time.

## 1. Where the applications are (APPLY-01, APPLY-02)

The **only** source is the database of the tracking page, the claude.ai artifact titled
"Application tracker" (its slug is in `specs/tracking-page.md`; otherwise find it with
`list_artifacts`). Collection `candidatures`.

- Query `statut == "validee"` (shown as "To send" / "À envoyer"). Nothing else.
- Never use engine B for this (`propositions`, the local SQLite database, `echange/`
  files): it does not know which applications User approved.
- Never apply to another status (`a_traiter`, `acceptee`, `prete`, `postulee`,
  `refusee`), even when User names that company: say it is not in To send and that User
  can validate it in the page first.

Show the list (company, title, letter yes / no) and confirm which ones to send, unless
User already said which ("toutes", "Alstom").

## 2. User's files and facts (APPLY-03)

The work folder is the one holding `Candidatures/`, `latex/` and `moteur/` (for the
original user: `~/Téléchargements/Recherche emploi/`). If it is not connected, ask for it
with `device_request_folder_access`.

- CV: `cv_ref`, path relative to the work folder. Letter: `lettre_ref` (may be empty).
- Facts for the forms, in this order: `moteur/prive/profil-candidature.md` (template:
  [`profil-candidature.exemple.md`](profil-candidature.exemple.md)), then
  `latex/commun/coordonnees.tex`, then the CV itself.
- If `profil-candidature.md` does not exist, create it from the template with what the
  other files give, ask User for the rest, and save it.

Facts found there may be entered without asking: identity, contact details, address,
nationality, gender, diversity survey answers, languages, degrees, experience, current
job, notice period, work authorisation, links. A factual question the files do not
answer: ask User, then offer to add the answer to `profil-candidature.md`.

## 3. Open the form and accounts (APPLY-04, APPLY-05)

Open the ad's `url` in the browser (User's preferred one), find "Postuler" / "Apply".

- **Account optional** (guest apply, "postuler sans compte", "continue without an
  account"): apply without an account. Never create one "to be safe".
- **Account required**: stop on the sign-up or sign-in page, tell User ("compte
  obligatoire sur <site> : crée-le, puis dis-moi de continuer") and wait. Then go on
  from where the form is. Never create the account, never type or generate a password,
  never choose "Sign in with Google / LinkedIn" for User.
- Already signed in (the browser keeps its sessions): continue.
- CAPTCHA or "are you human" check: ask User to solve it, then continue.
- Ad closed, expired or unreachable: tell User; do not change the application's status
  yourself (User may Drop it in the page).

## 4. Fill the form (APPLY-06 to APPLY-09)

- Factual fields: from section 2. Check fields the site pre-fills from the CV (name,
  dates, employer, title) and correct them.
- Files: upload the CV from `cv_ref`; the letter from `lettre_ref` when there is a letter
  field. A letter required but `lettre_ref` empty: ask User. Upload with the browser's
  file-upload tool when it has one; otherwise use computer use on the file dialog, or ask
  User to pick the file, giving its full path.
- **Salary: always ask User** (expected, current, range, "package"), even when a figure
  is in the files: you may suggest it, never enter it unapproved.
- **Free text: always propose, User validates.** Every free-text answer (motivation,
  "why us", "why this role", cover letter box, additional information, open questions):
  draft it from the ad (`texte_offre`), the letter, the CV and the rules of
  `profil-candidature.md`; show it; enter exactly the validated version. Invent no fact
  about User.
- Choice questions that are not facts in the files (relocation, travel, availability
  date, sponsorship…): answer from `profil-candidature.md` when it covers them,
  otherwise ask.
- Ask everything an application needs **in one message** (salary, every free text,
  missing facts), not one question per message.
- Consents: tick only what the application requires (processing of the application's
  data); leave marketing, newsletters and "talent pool" boxes unticked unless User asks.

## 5. Send (APPLY-10)

Before the final click, show a short recap: files attached, salary entered, free texts,
consents ticked, anything unusual. Send only after User's yes. Then check the
confirmation (page or message) before going on.

## 6. After sending (APPLY-11 to APPLY-13)

1. Tracking page: `db_get` the document, then `db_write` `update` with its version:
   `statut: "postulee"`, `date_postulee` and `date_maj` = today (`YYYY-MM-DD`).
2. Engine B: if the `moteur` tools are there, call `decisions` with the updated document
   (`{"candidatures": [<data with its id>]}`) so that it closes it; otherwise the page
   does it at its next sync.
3. Notes: write `candidature.md` in the application's folder: date sent, address of the
   form, account used (site and e-mail, never a password), salary given, the validated
   free texts, the other notable answers.
4. Folder: move it from `Candidatures/` to `Candidatures/sent/`, then update `cv_ref`
   and `lettre_ref` in the page to the new paths (same `update`, or a second one with the
   new version).

## 7. Report (APPLY-14)

At the end: applications sent, those waiting for User (account to create, question
unanswered) and those not sent, with the reason.
