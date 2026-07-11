# Validation Matrix

| Requirement | Automated proof |
| --- | --- |
| REQ-001 | Unit test mocks a detected WSL OpenCode runtime and asserts the WSL shared skill plus agent file are created and reference each other. |
| REQ-002 | Unit tests cover WSL `opencode agent list` success and absence/failure reporting; the command is executed against the local WSL runtime when available. |
| REQ-003 | Unit tests cover optional native command validation success, unavailable CLI warning behavior, and failed command behavior for Cursor and Copilot; Gemini must validate and list the installed extension when its CLI is available. |
| REQ-004 | Unit test asserts the generated Claude manifest has a semantic version; local `claude plugin validate` completes without a version warning. |
| REQ-005 | Existing installer tests for idempotent updates, native/shared resolution, duplicate removal, uninstall behavior, and CLI overrides remain green. |

Final validation runs `python -m unittest discover -s tests -v`, `python scripts/install.py doctor`, the available Claude validator, and WSL OpenCode's agent listing. Gemini's native check uses `gemini extensions validate` and `gemini extensions list` when available. It also checks the source tree and all generated skill roots for the same `SKILL.md` digest.
