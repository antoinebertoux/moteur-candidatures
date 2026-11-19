# Moteur A : tâches planifiées dans Claude

Des tâches planifiées de Claude cherchent des offres sur le web et écrivent directement
dans la base de la page. Leur texte complet est dans les réglages de chaque tâche ; ces
règles en donnent le contrat. Vérifiées à la main.

## Tâches

| Tâche | Quand | Rôle |
| --- | --- | --- |
| Emploi 2 – Grands groupes et administration | mardi 19 h 44 | offres de l'État et des grands groupes |
| Emploi 4 – Start-ups offres publiées | lundi 19 h 53 | offres de start-ups et scale-ups |
| Emploi 3 – Relances candidatures | vendredi 19 h 38 | réponses reçues et relances |

## Recherche d'offres (Emploi 2 et 4)

- **TACHE-01** · Avant de chercher, la tâche lit toute la base. Elle ne propose jamais
  une offre déjà présente (même lien, ou même entreprise et même intitulé), ni une offre
  d'une entreprise refusée, sauf poste nettement meilleur, signalé dans le résumé.
- **TACHE-02** · Offres publiées depuis moins de 3 semaines, encore actives, vérifiées
  sur l'offre d'origine (jamais un agrégateur).
- **TACHE-03** · Sources. Emploi 2 : Choisir le service public, sites des organismes,
  beta.gouv, sites carrières des grands groupes, Welcome to the Jungle, alertes LinkedIn
  reçues dans Gmail. Emploi 4 : Welcome to the Jungle, Station F, pages carrières sur les
  ATS, Licorne Society, Cyberjobs, alertes LinkedIn, et une consultation légère de
  LinkedIn Jobs dans le navigateur du PC s'il est joignable (sans cliquer, postuler ni
  écrire).
- **TACHE-04** · Calibrage : garder les postes d'IA appliquée ou GenAI senior, lead,
  responsable, chef de projet technique, architecte, expert IA de l'État ; écarter
  conseil et ESN, recherche ou ML pur, juniors, plus de 5 ans d'expérience exigés,
  salaire affiché au-delà de 250 k€, postes de direction groupe, 100 % sur site, stages.
  Plancher 65 k€ brut (70 k€ idéal) pour le privé, aucun pour l'administration ; il n'est
  jamais écrit dans la base. Mieux vaut 3 excellentes propositions que 10 moyennes, ou
  aucune.
- **TACHE-05** · Chaque offre est écrite en document neuf `candidatures/<identifiant
  ID-02>` avec `moteur` = `A`, `statut` = `a_traiter`, un score de 0 à 100, un résumé de
  3 à 5 phrases et `lettre_demandee`. **Un document existant n'est jamais modifié ni
  supprimé.**
- **TACHE-06** · Le résumé commence par « Attention : déjà N candidatures récentes. »
  quand l'organisme a déjà reçu en 6 mois 3 candidatures ou plus (grand groupe,
  ministère, scale-up) ou 2 ou plus (start-up).

## Relances (Emploi 3)

- **TACHE-10** · Pour chaque candidature Postulée en attente ou relancée, la tâche
  cherche dans Gmail une réponse de l'entreprise depuis la date d'envoi. Réponse trouvée
  → `suite` = entretien, refus ou proposition (un simple accusé de réception ne change
  rien) et une ligne datée ajoutée aux notes.
- **TACHE-11** · Sans réponse après 10 jours : un brouillon de relance court est préparé
  (brouillon Gmail si une adresse est connue) et ajouté aux notes. Rien n'est jamais
  envoyé ; Antoine passe lui-même la suite à « Relancée ».
- **TACHE-12** · Déjà relancée et sans nouvelle depuis 14 jours : signalée comme
  candidate à l'abandon, sans nouvelle relance.
- **TACHE-13** · La tâche ne modifie que `suite`, `notes` (ajout à la fin, jamais
  d'effacement) et `date_maj` ; elle ne change jamais le statut, ne crée ni ne supprime
  de document.

## Commun

- **TACHE-20** · Si la base est indisponible, la tâche le dit en première ligne et, pour
  les offres, les donne en JSON importable par le bouton « Importer ».
- **TACHE-21** · Chaque tâche envoie à Antoine un rapport court (nombre d'ajouts ou de
  vérifications, une ligne par élément) ; la validation se fait dans la page.
