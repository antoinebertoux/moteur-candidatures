# Moteur A : tâches planifiées dans Claude

Le texte des quatre tâches planifiées qui alimentent la page de suivi. Leurs règles sont
décrites dans [`specs/scheduled-tasks.md`](../specs/scheduled-tasks.md).

| Fichier | Tâche | Quand (heure de Paris) |
| --- | --- | --- |
| `emploi-2-grands-groupes.md` | offres de l'État et des grands groupes | mardi 19 h 44 |
| `emploi-4-startups.md` | offres de start-ups et scale-ups | lundi 19 h 53 |
| `emploi-3-relances.md` | réponses reçues et brouillons de relance | vendredi 19 h 38 |
| `emploi-5-boite-mail.md` | lecture et classement des e-mails reçus | mercredi et dimanche 19 h 44 |

Les fichiers sont des **gabarits** : le profil, le nom, les salaires et le slug de la
page sont remplacés par des repères entre chevrons (`<PRÉNOM>`, `<PROFIL : …>`,
`<SALAIRE PLANCHER>`, `<SLUG_DE_TA_PAGE>`…). Les versions remplies sont gardées dans
`prive/taches/`, ignoré par Git.

## Créer les tâches

1. Remplace tous les repères `<…>` (sauf `<type>_<entreprise>_<poste>`,
   `<identifiant>` et `<id du document>`, qui font partie des consignes).
   Adapte aussi les cibles, sources et critères de calibrage à ton profil.
2. Dans une conversation Claude, demande : « Crée une tâche planifiée nommée
   “Emploi 2 – Grands groupes et administration”, chaque mardi à 19 h 44 heure de
   Paris, avec ce texte », puis colle le fichier.
3. Connecteurs utilisés : Gmail (alertes LinkedIn, réponses, brouillons) et les outils
   de base de données d'artefact. Le navigateur du PC est facultatif.
4. Réglage d'approbation : les tâches n'envoient jamais rien et n'écrivent que dans la
   base ; l'approbation automatique est donc adaptée.
