# Commandes et serveur local

## Commandes

| Commande | Effet |
| --- | --- |
| `moteur collecter` | interroge et filtre, ajoute à la base (0 token) |
| `moteur noter` | note les offres en attente |
| `moteur exporter` | écrit `echange/pour-la-page.json` |
| `moteur quotidien` | collecter, noter, puis exporter |
| `moteur decisions <fichier>` | relit l'export de la page |
| `moteur generer` | dossiers des acceptées, lettres manquantes, puis export |
| `moteur lettre [id…]` | lettres seules, puis export |
| `moteur servir [--port N]` | sert les PDF à la page |

- **CLI-01** · Les commandes ci-dessus existent et enchaînent les étapes indiquées.
  *(non testé)*
- **CLI-02** · `--config <fichier>` (défaut `config.toml` du dossier courant) et `-v`
  (détail par source) s'écrivent avant ou après la commande.
- **CLI-03** · Une erreur de configuration, un export illisible ou un fichier manquant
  affiche « Erreur : … » et rend le code 1, sans trace Python. *(non testé)*

## Serveur des PDF (`moteur servir`)

La page est sur claude.ai : le navigateur y bloque les liens `file://`. Les boutons CV et
Lettre pointent donc vers ce petit serveur.

- **SRV-01** · Il écoute sur `127.0.0.1` uniquement, port 8765 par défaut (la page
  suppose 8765). *(non testé)*
- **SRV-02** · Il ne sert que les fichiers sous `/Candidatures/…`, en lecture seule. Tout
  le reste (`config.toml`, `.env`, `latex/`, `..`, liens qui sortent du dossier) répond
  404.
- **SRV-03** · Les réponses portent `Cache-Control: no-store`, pour qu'un PDF régénéré
  s'affiche à jour.
