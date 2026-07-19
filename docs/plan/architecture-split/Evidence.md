# Evidence

- `scripts/manifest_tool.py` currently combines schema, storage, graph validation,
  regression, acceptance orchestration, repair, reporting, and CLI responsibilities.
- `scripts/install.py` currently combines data models, skill copying, host targets,
  WSL probing, verification, and CLI responsibilities.
- Lifecycle helpers import the workflow monolith, so a lightweight Hook loads the
  complete command implementation.
- Existing tests provide strong behavioral seams for a complete internal migration;
  public executable paths can remain stable while internal imports move once.
