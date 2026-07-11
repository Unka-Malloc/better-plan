# Evidence and Gap Analysis

## Observed behavior

- `scripts/install.py` resolves all install paths from the invoking process's `Path.home()`; a Windows run therefore cannot write a WSL user's configuration by itself.
- `discover_wsl_opencode()` discovers only running WSL distributions with OpenCode. `check_opencode()` reports the discovery as a warning when Windows lacks an OpenCode executable; it does not read the WSL agent configuration or run `opencode agent list` there.
- `check_shared_scan_agent()` validates the skill tree and duplicate removal for Codex, Cursor, and Copilot. `check_gemini()` validates extension files, enablement JSON, and the generated context reference. Neither invokes an optional client CLI.
- `install_claude_plugin()` generates a plugin manifest without `version`; local `claude plugin validate` accepts it with a warning.
- The local audit verified that Windows-side adapters are structurally valid and a separately installed WSL OpenCode adapter is loaded. The separate WSL install proves the missing automatic deployment path.

## Design decision

Add an explicit WSL runtime abstraction rather than embedding WSL shell fragments throughout installation and validation. It will retain the distro name, resolved OpenCode path, and Linux home directory. Windows installation will use this information to copy the current source to the WSL shared skill root and generate the WSL OpenCode agent file. Validation will use the same abstraction to query the WSL runtime.

For native validation, use a small command-spec table keyed by client. It keeps client-specific commands and expected output isolated from shared skill-tree checks, avoids making absent optional CLIs a failure, and lets tests mock one command runner at the boundary.

## External constraints

WSL commands must be passed as argument arrays, not composed from untrusted values. Distro names are obtained from `wsl -l -v` and shell paths should be safely quoted before inclusion in a remote shell script. The source tree may be on a Windows-mounted drive, so copying uses the already-available WSL shell and Python rather than assuming a fixed mount prefix.
