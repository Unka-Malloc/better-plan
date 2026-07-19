# Windows Test Portability Validation

## Selected observation dimensions

The executable cases use `success` for the corrected test paths, `boundary` for Python-version
and operating-system floors, and `negative` for strict CLI parsing and blocked host discovery.
`replay`, `privacy`, and `fingerprint` do not add a distinct observable contract for this Node;
machine-specific output must not be retained in Plan evidence.

## Executable acceptance cases

### WIN-S01 — Node subprocess helpers preserve the documented positional grammar

- `path`: `tests/test_acceptance_state_machine.py`, `tests/test_agent_completion.py`
- Observation target: each helper that invokes a node command and the production
  `manifest_cli.build_parser` grammar.
- Preconditions: a complete temporary workspace exists on the Windows runner's drive; a second
  parse-only fixture supplies a syntactically valid UNC workspace string without contacting a
  network share.
- Action: invoke the existing state-machine and Agent-completion scenarios with argument vectors
  shaped as `command`, `node-id`, `workspace`, then options. Parse the equivalent drive and UNC
  vectors directly, and submit one misspelled option after the valid positionals.
- Observable result: drive-backed scenarios reach their expected lifecycle states; the parser
  preserves the complete drive or UNC value as `root`; the misspelled option exits nonzero.
- False-positive-resistant oracle: assert the expected state/output of the real scenario, exact
  parsed `root` equality for both path forms, and byte-for-byte unchanged workspace state after
  the misspelled-option call. Merely avoiding an `argparse` error is not a pass.
- Maps to: REQ-WIN-001; criterion 0; decision `composition`; seams `node command positional
  ordering`; strict `dispatch`/`advance` parser interfaces.

### WIN-B01 — Architecture analysis selects only AST node classes exposed by the runtime

- `path`: `tests/test_architecture_layers.py`
- Observation target: `TRY_NODE_TYPES: tuple[type[ast.AST], ...]` and every architecture walk
  that recognizes exception-handling statements.
- Preconditions: the test runs once under Python 3.10 and once under a current Python runtime;
  synthetic source contains an ordinary `try`, and the newer runtime fixture also contains
  `try*` source parsed at run time.
- Action: run `python -m unittest tests.test_architecture_layers -v` in both environments.
- Observable result: `ast.Try` is always recognized; `ast.TryStar` is included and recognized
  exactly when the runtime exposes it; importing the test module succeeds on Python 3.10.
- False-positive-resistant oracle: assert the exact version-derived tuple and require fault
  fixtures containing the supported syntax to be visited by the same architecture analyzer.
  Skipping the analyzer, swallowing `AttributeError`, or merely compiling the module cannot pass.
- Maps to: REQ-WIN-002; criterion 1; symbol `TRY_NODE_TYPES`; decisions `algorithms` and
  `data_structures`; seam `Python 3.10 AST analysis`.

### WIN-N01 — Installer tests cannot observe optional host integrations by accident

- `path`: `tests/test_install_tool.py`
- Observation target: `run_command(*args, env=...)`, optional-client lookup, and WSL discovery.
- Scope: this isolation contract applies only to `tests/test_install_tool.py`; it does not change
  production installer discovery behavior or impose isolation rules on unrelated test modules.
- Preconditions: subprocess fixtures receive a copied explicit environment; optional-client
  absence uses an empty executable search path; lifecycle smoke exposes only the directory of
  the current Python executable. General installer cases replace WSL discovery with an empty
  result. Dedicated optional-client and WSL cases retain only their controlled fakes.
- Action: run `python -m unittest tests.test_install_tool -v`, including absent/success/failure
  optional-client cases and the two controlled WSL cases.
- Observable result: general and absence cases produce deterministic results regardless of tools
  installed on the host; lifecycle commands still find Python; only dedicated fixtures record
  optional-client or `wsl.exe` invocations.
- False-positive-resistant oracle: fail on any unexpected command through a recording fake, assert
  the exact controlled command list in integration cases, and assert absence fixtures return WARN
  without creating an external-execution marker. A passing exit code alone is insufficient.
- Maps to: REQ-WIN-003; criterion 2; interface `portable_test_runtime`; symbol `run_command`;
  decisions `state` and `isolation`; seams `optional CLI absence` and `controlled WSL discovery`.

### WIN-B02 — One CI contract covers the supported Windows floor and current Linux

- `path`: `.github/workflows/ci.yml`
- Observation target: the CI matrix and completed job results for the reviewed commit.
- Preconditions: the workflow runs for a commit containing these changes.
- Action: execute the same complete-suite and portable CLI smoke steps in matrix entries
  `windows-latest` / Python `3.10` and `ubuntu-latest` / Python `3.x` (the current stable release
  selected by `setup-python`). Shell-specific output redirection is not part of the smoke oracle.
- Observable result: both jobs run `python -m unittest discover -s tests -v`; both run UUID,
  transition, Plan schema, and Node schema smoke commands; both jobs complete successfully.
- False-positive-resistant oracle: require exactly the two declared OS/Python combinations, the
  same behavioral commands in each, and successful job conclusions for the same commit. YAML text
  presence without both completed jobs is not acceptance evidence.
- Maps to: REQ-WIN-004; criterion 3; dependency `.github/workflows/ci.yml -> tests`; decision
  `concurrency`; seam `Windows CI matrix`.

### WIN-S02 — Focused, complete, workspace, and installed-Codex checks agree

- `path`: `docs/plan/windows-test-portability/Validation.md`
- Observation target: repository behavior and the locally installed Codex adapter.
- Preconditions: run from the repository root; for the supported-floor proof, use Python 3.10 on
  Windows. Updating the local Codex installation is an explicit operator action outside the test
  fixtures.
- Action, in order:
  1. `python -m unittest tests.test_acceptance_state_machine tests.test_agent_completion tests.test_architecture_layers tests.test_install_tool -v`
  2. `python -m unittest discover -s tests -v`
  3. `python scripts/manifest_tool.py validate docs/plan --check-sources --no-git`
  4. `python scripts/manifest_tool.py check-labels docs/plan --plan windows-test-portability`
  5. `python scripts/install.py update --agents codex`
  6. `python scripts/install.py doctor --agents codex`
- Observable result: every command exits zero, the doctor reports no `FAIL`, and no earlier command
  is skipped because a later command passed.
- False-positive-resistant oracle: bind the six exit codes to one reviewed repository fingerprint;
  retain only bounded command receipts, not stdout, absolute installation paths, discovered host
  tools, or machine identity. The focused suite alone cannot satisfy the complete-suite or local
  installation criteria.
- Maps to: REQ-WIN-001 through REQ-WIN-004; criteria 0–3; all declared symbols, interface, and test
  seams.

## Coverage mapping

| Requirement / criterion | Primary cases | Independent guard |
| --- | --- | --- |
| REQ-WIN-001 / criterion 0 | WIN-S01 | WIN-S02 focused and complete suites |
| REQ-WIN-002 / criterion 1 | WIN-B01 | WIN-B02 Windows 3.10 and current-Linux jobs |
| REQ-WIN-003 / criterion 2 | WIN-N01 | WIN-S02 focused and complete suites |
| REQ-WIN-004 / criterion 3 | WIN-B02 | WIN-S02 workspace, label, install, and doctor sequence |

## Design gaps

- Criterion 3 requires updating and diagnosing the local Codex installation, but the Node's focused
  regression commands contain only the complete suite, workspace validation, and label checks.
  WIN-S02 therefore treats install/doctor as explicit operator evidence; it cannot become an
  automatic regression receipt without a main-owned regression-contract revision.
- Successful GitHub job conclusions are external evidence and cannot be produced by local
  execution. Static matrix inspection is intentionally insufficient for WIN-B02.
