# Base locale du moteur B

`moteur.sqlite3` retient chaque candidature vue par le moteur B, avec sa note, son
statut (voir le tableau du [README](README.md#statuts)) et les chemins de ses PDF.

- **BASE-01** · Seules les candidatures inconnues (identifiant ID-02) sont ajoutées ; une
  offre déjà vue n'est jamais réinsérée ni remise à zéro.
- **BASE-02** · Une offre ajoutée est `a_noter`. Une spontanée n'a rien à noter : elle
  est directement `notee`, avec une lettre prévue.
- **BASE-03** · Une note n'est enregistrée que pour une candidature `a_noter`, qui
  devient `notee`.
- **BASE-04** · Ce qui part vers la page : les candidatures `notee` (propositions) et
  `generee` (dossiers prêts).
- **BASE-05** · Décisions venues de la page : `acceptee` → `acceptee`, `refusee` →
  `refusee`, `postulee` → `close`. Les autres statuts de la page (`a_traiter`, `prete`,
  `validee`) ne changent rien. Une décision identique à l'état actuel ne compte pas
  comme un changement.
- **BASE-06** · Un dossier `generee` que la page montre encore « acceptée » (l'import
  n'a pas encore été fait) **n'est pas régénéré**, sauf si une consigne de retouche
  l'accompagne : il repasse alors `acceptee` avec cette consigne.
- **BASE-07** · Une candidature acceptée dans la page mais inconnue de la base (ajout
  manuel, moteur A) y est ajoutée en `acceptee`, avec le texte de l'offre fourni par la
  page. Pour une candidature déjà connue, seul un texte d'offre manquant est complété.
- **BASE-08** · Le choix « lettre oui / non » de la page est reporté dans la base. Une
  *lettre manquante* est un dossier `generee` avec une lettre prévue mais pas encore de
  PDF de lettre.
- **BASE-09** · Une génération réussie passe le dossier `generee`, enregistre ses PDF et
  efface la consigne de retouche ; une lettre réussie efface la consigne de lettre.
- **BASE-10** · Une base créée par une version plus ancienne reçoit au besoin les
  colonnes ajoutées depuis, sans perte.
