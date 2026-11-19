# Sources

Chaque source rend une liste d'offres (entreprise, intitulé, lieu, lien, source, texte,
salaire, date de publication), sans appel à Claude. Un champ que la source ne donne pas
reste vide.

## Général

- **SRC-01** · Une réponse inattendue d'un site (champ manquant, mauvais type, flux
  illisible) ne fait pas planter la source : les entrées inexploitables sont ignorées, et
  une offre sans intitulé n'est jamais gardée.
- **SRC-02** · Le texte HTML des offres est converti en texte brut, entités HTML (même
  échappées deux fois) décodées, espaces resserrés.
- **SRC-03** · Les appels HTTP s'identifient comme `moteur-candidatures/0.1 (usage
  personnel)`, suivent les redirections et abandonnent au bout de 20 s. Une erreur HTTP
  devient une erreur de source qui cite le code et le début de la réponse.
  *(non testé)*

## France Travail

- **SRC-10** · Active seulement si `[france_travail] actif = true` **et** si
  `FRANCE_TRAVAIL_ID` et `FRANCE_TRAVAIL_SECRET` sont définis ; sinon elle est ignorée
  avec un avertissement. *(non testé)*
- **SRC-11** · Obtient un jeton OAuth, puis lance une recherche par mot-clé et par
  département (ou une seule par mot-clé si aucun département), limitée aux offres
  publiées depuis `publiee_depuis` jours, 150 résultats au plus par recherche. Sans jeton
  dans la réponse, la source échoue.
- **SRC-12** · Entreprise absente → « Entreprise non précisée ». Lien : l'offre d'origine
  si l'API la donne, sinon la page de l'offre sur France Travail. Le libellé de salaire
  est conservé tel quel pour le filtre.

## Choisir le service public

- **SRC-20** · Pas d'identifiants. Chaque mot-clé est cherché sur tout le site, puis de
  nouveau chez les seuls employeurs suivis (la recherche générale est triée par
  pertinence et pourrait les manquer). Les domaines, s'il y en a, filtrent les deux.
- **SRC-21** · L'adresse de recherche suit l'ordre imposé par le site :
  `mot-cles/…/domaine/…/organisme/…/page/n/`.
- **SRC-22** · Pagination : 20 offres par page ; arrêt dès qu'une page est incomplète,
  que le total annoncé est atteint ou que `pages_max` est lu.
- **SRC-23** · Sur une carte de résultat : employeur (« Fonction publique » s'il manque),
  lieu, date « En ligne depuis le 16 novembre 2026 » convertie en `2026-11-16`. Une même
  offre (même lien) n'est gardée qu'une fois.
- **SRC-24** · Les résultats n'ont pas le texte de l'offre : la page de chaque offre
  **retenue** est ouverte pour récupérer les missions et le profil, un paragraphe par
  ligne.

## Pages carrières (ATS)

- **SRC-30** · Adresse interrogée selon l'outil, à partir de l'identifiant :

  | ATS | Adresse |
  | --- | --- |
  | greenhouse | `boards-api.greenhouse.io/v1/boards/<id>/jobs?content=true` |
  | lever | `api.lever.co/v0/postings/<id>?mode=json` |
  | ashby | `api.ashbyhq.com/posting-api/job-board/<id>` |
  | smartrecruiters | `api.smartrecruiters.com/v1/companies/<id>/postings?limit=100` |
  | recruitee | `<id>.recruitee.com/api/offers/` |
  | teamtailor | `<id>.teamtailor.com/jobs.rss` (flux RSS) |

  Une entreprise sans ATS pris en charge ne peut pas devenir une source.
- **SRC-31** · Chaque ATS fournit intitulé, lieu, lien et, quand il l'a, le texte et la
  date de publication (AAAA-MM-JJ). SmartRecruiters ne donne pas le texte ; son lien est
  reconstruit en `jobs.smartrecruiters.com/<id>/<offre>` et son lieu en « Ville, PAYS ».

## Workday

- **SRC-40** · L'identifiant est l'adresse de la page carrières telle qu'affichée
  (`https://<tenant>.wdN.myworkdayjobs.com/[fr-FR/]<site>`) ; le segment de langue est
  ignoré. Une adresse hors `myworkdayjobs.com` est refusée.
- **SRC-41** · Workday ne liste pas tout : chaque mot-clé de l'entreprise (par défaut
  « machine learning », « intelligence artificielle », « data scientist ») est cherché,
  20 offres par page, 5 pages au plus. Une offre trouvée par plusieurs mots-clés n'est
  gardée qu'une fois. Workday ne donne pas le texte de l'offre.
