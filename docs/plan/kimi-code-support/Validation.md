# Kimi Code Support Validation

| Requirement | Focused proof |
| --- | --- |
| `REQ-001` | Installer tests cover target selection, Skill placement, portable canonical TOML Hooks, idempotent merge, unrelated-config preservation, Doctor, CLI paths, full uninstall, and Hook-only uninstall. Hook tests cover native plain-text guidance, silent no-op behavior, and the exact event inventory. |

Run only:

```sh
python3 -m unittest tests.test_install_tool tests.test_hook_tool tests.test_orchestration_workflow tests.test_agent_completion -v
python3 scripts/manifest_tool.py validate docs/plan --plan kimi-code-support --check-sources --no-git
python3 scripts/manifest_tool.py check-labels docs/plan --plan kimi-code-support
```
