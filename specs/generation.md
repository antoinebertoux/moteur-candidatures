# Génération du CV et de la lettre

`moteur generer` prépare un dossier pour chaque candidature `acceptee`, à partir du dépôt
`../latex/` : modèle de CV, banque de blocs (fr ou en), squelette de lettre, banque de
paragraphes et `compiler.sh`. Rédaction par Claude (Sonnet par défaut).

## Dossier

- **CV-01** · Chaque candidature a son dossier `Candidatures/<Entreprise> - <Poste>/`
  (`<Entreprise> - spontanée/` pour une spontanée), sans caractère interdit dans un nom
  de fichier, 100 caractères au plus. Le nom ne dépend que de l'entreprise, du type et
  du poste : une régénération réutilise le même dossier.
- **CV-02** · Le dossier contient `offre.md` (entreprise, poste, lien, source, texte de
  l'offre), écrit à la première génération et jamais écrasé ensuite. *(non testé)*
- **CV-03** · Langue : celle détectée à la notation (NOT-05) ; elle choisit la banque
  `banque-fr` ou `banque-en`. Les fichiers générés pointent vers `../../latex/` pour
  compiler depuis leur dossier.

## CV

- **CV-10** · Point de départ : le modèle de CV du dépôt. S'il y a une consigne de
  retouche et qu'un `cv.tex` existe déjà, on repart de ce CV-là.
- **CV-11** · Claude reçoit : l'offre (entreprise, poste, lieu, résumé, mention
  « candidature spontanée » le cas échéant, 6 000 premiers caractères du texte), la
  langue, le fichier de départ, la banque, et la consigne d'Antoine marquée prioritaire.
- **CV-12** · Consignes données à Claude pour le CV *(non testé : consigne au modèle)* :
  - il ne fait que choisir des macros de la banque : aucun texte libre, aucune
    expérience ni macro inventée, préambule et structure conservés ;
  - une seule accroche, celle dont l'usage correspond le mieux à l'offre ;
  - Eurofins : toutes les puces sauf celles vraiment hors sujet (au moins 7), de la plus
    à la moins pertinente ;
  - les deux projets académiques, le plus pertinent en premier ;
  - centres d'intérêt : escalade et jeux ; géopolitique seulement pour un poste axé
    défense (DGSE, Armées, DGA, AID, industriel de défense), jamais ailleurs.
- **CV-13** · La réponse doit être un fichier LaTeX complet (`\documentclass` …
  `\end{document}`), sinon le dossier échoue.
- **CV-14** · **Le CV tient sur une page et la remplit.** Le programme compile la version
  complète, puis retire d'abord le second projet, puis les dernières puces Eurofins (il
  en garde au moins 5) jusqu'à tenir sur une page. Ensuite il essaie de remettre, dans
  l'ordre, les éléments retirés plus courts que le premier, et garde chacun s'il tient.
- **CV-15** · Si même la version la plus courte dépasse une page, le dossier est généré
  quand même et un avertissement « à reprendre » est affiché.

## Lettre

- **LET-01** · Une lettre est faite avec le CV si elle est prévue (choix de la page, sinon
  offre qui la demande, sinon règle ID-04) ou s'il s'agit d'une spontanée ; sinon le
  dossier n'a pas de lettre.
- **LET-02** · Le choix fait avec l'interrupteur de la page l'emporte toujours sur la
  demande de l'offre et sur la règle par défaut.
- **LET-03** · Consignes données à Claude pour la lettre *(non testé : consigne au
  modèle)* :
  - squelette conservé ; seuls le contenu et le nom de l'entreprise changent ;
  - dans la langue de l'offre ; en anglais, « Dear Hiring Manager, » ;
  - quatre paragraphes : accroche (poste exact, pourquoi cette entreprise) ; une ou deux
    réalisations Eurofins qui répondent à l'offre ; l'apport au-delà du technique ;
    pourquoi eux, avec des éléments concrets ;
  - aucun fait inventé, tout vient de la banque de paragraphes ; jamais « certifié en IA
    générative » ; aucun salaire ni prétention ; géopolitique ou Le Collimateur
    seulement pour un poste axé défense ;
  - spontanée : propose le rôle indiqué ;
  - style direct, sans formules creuses, 250 à 350 mots, une page.
- **LET-04** · `moteur lettre` ajoute une lettre à un dossier déjà généré **sans toucher
  au CV** : pour les identifiants donnés, ou à défaut pour toutes les lettres manquantes
  (BASE-08).
- **LET-05** · Une lettre existante sert de point de départ seulement si une consigne de
  lettre l'accompagne ; sinon elle est réécrite depuis le squelette.
- **LET-06** · Une lettre de plus d'une page est un échec : le dossier reste sans lettre
  enregistrée. Un identifiant inconnu de la base est un échec.
- **LET-07** · « Régénérer la lettre » dans la page n'est pris en compte que si la demande
  est plus récente que le PDF de lettre actuel ; la lettre repasse alors manquante, avec
  la consigne de lettre éventuelle.

## Compilation et résultat

- **GEN-01** · Chaque fichier est compilé par `latex/compiler.sh <dossier> <fichier>`.
  Un échec de compilation fait échouer le dossier avec la fin du journal. `compiler.sh`
  signale un dépassement par « `<nom>.pdf fait N pages` ».
- **GEN-02** · Un dossier réussi passe `generee` avec les chemins de ses PDF, relatifs au
  dossier racine (`Candidatures/…/cv.pdf`). Un dossier en échec est listé avec la
  raison, reste `acceptee`, et n'empêche pas les suivants.
- **GEN-03** · Après les dossiers, `generer` ajoute les lettres manquantes puis exporte
  automatiquement le fichier pour la page. *(non testé)*
