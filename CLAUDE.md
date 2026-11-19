# Règles du dépôt

- `specs/` fait foi sur le comportement de l'outil (moteur B, page de suivi, tâches
  planifiées). Antoine relit les specs, pas le code.
- Pour tout changement de comportement : **modifier d'abord la spec** (nouvelle règle ou
  règle modifiée, identifiant stable, jamais renuméroté), la faire valider par Antoine,
  puis coder et tester. Le commit contient spec, code et tests.
- Chaque règle du moteur a au moins un test qui la cite avec
  `@pytest.mark.spec("XXX-NN")` ; `tests/test_specs.py` le vérifie. Une règle qu'on ne
  peut pas tester porte la mention *(non testé)*, avec la raison.
- Une modification de la page de suivi ou d'une tâche planifiée met aussi à jour
  `specs/page-suivi.md` ou `specs/taches-claude.md`.
- Les règles de `specs/identifiants.md` existent en double (Python et page) : ne jamais
  en changer un seul côté.
- Avant de committer : `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest`.
