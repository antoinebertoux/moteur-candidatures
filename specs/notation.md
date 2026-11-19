# Notation et appels à Claude

## Notation

`moteur noter` attribue à chaque offre `a_noter` un score, un résumé et deux indices
(lettre demandée, langue), en un appel court à Claude par lot.

- **NOT-01** · Les offres `a_noter` sont envoyées par lots de `taille_lot`, un appel par
  lot, avec le modèle de notation (Haiku par défaut).
- **NOT-02** · Un lot en échec (appel raté, réponse illisible) est signalé et reste
  `a_noter` : il sera retenté au prochain passage. Les autres lots continuent.
- **NOT-03** · Pour chaque offre, Claude reçoit seulement : identifiant, entreprise,
  intitulé, lieu, libellé de salaire et les 1 500 premiers caractères du texte.
- **NOT-04** · Le prompt système contient les consignes de notation suivies du `profil`
  de `config.toml`, et rien d'autre (pas le plancher salarial).
- **NOT-05** · Claude répond par un tableau JSON. Pour chaque entrée : identifiant
  recopié ; score de 0 à 100 ; résumé de deux phrases (le poste, puis le point fort ou
  bloquant) ; `lettre_demandee` vrai seulement si l'offre demande une lettre ; langue
  `en` si l'offre est en anglais, sinon `fr`. *(non testé : consigne au modèle ; la
  lecture de la réponse est vérifiée par NOT-06)*
- **NOT-06** · Lecture de la réponse : une entrée à l'identifiant inconnu ou au score non
  numérique est ignorée (l'offre reste `a_noter`) ; le score est arrondi et ramené entre
  0 et 100 ; le résumé est coupé à 400 caractères ; toute langue autre que `en` vaut
  `fr`. Une réponse qui n'est pas un tableau fait échouer le lot.
- **NOT-07** · La commande affiche le nombre d'offres notées et le nombre encore en
  attente. *(non testé)*

## Appel à Claude

- **CLA-01** · Claude est appelé par `claude -p` avec l'abonnement d'Antoine, jamais par
  clé API. Chaque appel part sans outils, sans serveurs MCP, sans session conservée, avec
  le modèle et le prompt système demandés ; le prompt passe par l'entrée standard et la
  sortie est lue en JSON.
- **CLA-02** · Sont des échecs : `claude` introuvable, pas de réponse en 10 minutes, code
  de sortie non nul, sortie non JSON, erreur signalée par Claude, réponse vide.
- **CLA-03** · Dans une réponse, on prend le contenu du premier bloc ` ``` ` s'il y en a
  un ; un JSON est retrouvé même entouré de texte.
