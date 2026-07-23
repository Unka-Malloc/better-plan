# Current Agent Target Matrix Validation

| Requirement | Focused proof |
| --- | --- |
| `REQ-001` | Installer tests reject the retired target and cover atomic Antigravity plugin structure and Hook shape, Pi shared-skill resolution, all configured Craft workspaces, diagnosis, and uninstall. Hook tests prove first-invocation-only guidance and safe no-op behavior. Source scans confirm the removed adapter symbols and CLI flags are absent. |

Run only:

```sh
python3 -m unittest tests.test_install_tool tests.test_hook_tool tests.test_orchestration_workflow -v
python3 scripts/manifest_tool.py validate docs/plan --check-sources --no-git
python3 scripts/manifest_tool.py check-labels docs/plan
```
