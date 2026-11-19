# Page « Suivi des candidatures »

`index.html` est le code complet de la page de suivi, telle qu'elle est publiée comme
artefact claude.ai. C'est un seul fichier HTML (styles et script inclus), sans
dépendance. Ses règles sont décrites dans [`specs/tracking-page.md`](../specs/tracking-page.md).

La page ne fonctionne qu'ouverte depuis Claude : elle s'appuie sur ces capacités de
l'artefact, fournies par `window.claude.use(...)` :

| Capacité | Usage |
| --- | --- |
| `db` | base hébergée par Claude, collection `candidatures` (un document par candidature) |
| `downloads` | bouton « Exporter » (`candidatures-export.json`) |
| `user` | déclarée sur la page publiée |
| `mcp` | serveur local `host:moteur` (outils `propositions`, `decisions`) : liaison directe avec le moteur B, seulement dans l'app Claude desktop du PC |

Ouverte hors de Claude (en local dans un navigateur), elle affiche « La base n'est pas
disponible dans cette vue ».

## Installer sa propre page

1. Dans une conversation Claude, demande : « Publie `page-suivi/index.html` comme
   artefact, avec les capacités `db`, `downloads`, `user` et `mcp` (`host:moteur`, outils
   `propositions` et `decisions`) ». Claude crée un artefact privé
   et te donne son lien.
2. Note le **slug** de l'artefact (l'identifiant UUID que Claude te donne, ou visible
   dans ses outils). Les tâches planifiées en ont besoin (`<SLUG_DE_TA_PAGE>` dans
   [`taches/`](../taches/)).
3. La base est vide au départ. Pour essayer avec des données fictives, demande à Claude
   d'écrire le contenu de [`exemple-base.json`](exemple-base.json) dans la collection
   `candidatures` (un document par entrée, identifiant = champ `id`).
4. Pour les PDF (boutons CV et Lettre), lance `uv run moteur servir` sur ton PC : la
   page ouvre `http://127.0.0.1:8765/<chemin>` (voir SRV-01).

## Base de données

Collection `candidatures`, un document par candidature. Identifiant :
`<type>_<entreprise>_<poste>` normalisé (règle ID-02, voir
[`specs/identifiers.md`](../specs/identifiers.md)). Aucune règle d'accès
particulière : les règles par défaut (seul le propriétaire écrit).

| Champ | Type | Contenu |
| --- | --- | --- |
| `type` | texte | `offre` ou `spontanee` |
| `entreprise`, `poste`, `lieu`, `url`, `source` | texte | description de l'offre |
| `moteur` | texte | `A` (tâches Claude), `B` (moteur local), `manuel` |
| `statut` | texte | `a_traiter`, `acceptee`, `prete`, `validee`, `postulee`, `refusee` (voir [`specs/README.md`](../specs/README.md#statuses)) |
| `score` | entier | adéquation de 0 à 100 |
| `resume` | texte | 3 à 5 phrases |
| `lettre_demandee` | booléen | lettre faite d'office |
| `lettre` | texte | `oui` / `non`, choix manuel qui l'emporte |
| `cv_ref`, `lettre_ref` | texte | chemin relatif ou lien http(s) des PDF |
| `contact`, `notes`, `texte_offre` | texte | libre |
| `consigne`, `retouche_le`, `lettre_consigne`, `lettre_refaire_le` | texte | demandes de retouche |
| `suite` | texte | après envoi : vide, `relance`, `entretien`, `refus`, `offre` |
| `motif_refus`, `motif_detail` | texte | motif du refus (PAGE-10) |
| `preparation_demandee_le`, `pretentions`, `entretien_infos`, `preparation_consigne` | texte | demande de préparation d'entretien (PAGE-11) |
| `preparation`, `preparation_le` | texte | fiche de préparation (Markdown) et sa date, écrites par le moteur B |
| `date_ajout`, `date_maj`, `date_postulee` | texte | `AAAA-MM-JJ` |

## Sauvegarde et restauration

- **Sauvegarder** : bouton « Exporter » de la page, ou demander à Claude un export de
  la collection. Le fichier a la forme
  `{"exporte_le": "…", "candidatures": [{"id": "…", …champs}, …]}`.
- **Restaurer** dans une nouvelle page : donner ce fichier à Claude et lui demander
  d'écrire chaque entrée dans `candidatures/<id>` (opération `set`). Le bouton
  « Importer » de la page, lui, est fait pour le fichier du moteur local
  (`pour-la-page.json`) et ne recrée pas les décisions.

Les vraies données ne sont pas dans le dépôt (voir « Données personnelles » dans le
[README](../README.md)) : l'export de la base est gardé dans `prive/`, ignoré par Git.
