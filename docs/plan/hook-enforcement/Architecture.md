# Hook Enforcement Architecture

> Completed delivery record. The current session/task alignment contract is defined by `../task-plan-alignment/`; this Plan's terminal Nodes are not reopened.

## Module map

### Workflow domain — `scripts/manifest_tool.py`

Owns the canonical Node schema, platform normalization, active-node discovery, regression contract validation, deterministic tested-path fingerprinting, command execution, receipt persistence, and state transitions. It has no dependency on Codex, Cursor, or Claude event schemas.

### Hook protocol adapter — `scripts/hook_tool.py`

Reads one host Stop event JSON object from standard input, resolves the event working root, calls public workflow-domain functions, and serializes the host-specific continuation response. It does not mutate state except through the workflow-domain regression API and never persists host session identifiers or command output.

### Hook configuration adapter — `scripts/hook_config.py`

Builds, merges, inspects, and removes Better Plan entries in each host's supported configuration shape. It owns managed-entry identification and atomic JSON updates but knows nothing about Node state.

### Delivery infrastructure — `scripts/install.py`

Selects the installed skill root, delegates configuration work to `hook_config.py`, and surfaces install/update/doctor/uninstall results. Existing skill-copy and client-resolution behavior remains the only delivery path.

### Documentation — `SKILL.md`, `references/state-files.md`, `README.md`

Defines operator workflow, contract semantics, host support, trust/restart notes, and direct CLI fallback.

## Dependency direction

`install.py -> hook_config.py`

`host process -> hook_tool.py -> manifest_tool.py -> state files / local regression commands`

The workflow domain never imports installation or host adapters. The configuration adapter only receives a resolved script path and agent name.

## Contracts

### Node regression contract

```json
{
  "regression": {
    "scope": "focused",
    "commands": ["python3 -m unittest tests.test_example"],
    "criteria": [0],
    "paths": ["src/example.py", "tests/test_example.py"]
  }
}
```

After a passing run, the domain adds `last_pass` containing a UTC timestamp, contract digest, and tested-path fingerprint. `commands`, `criteria`, and `paths` are non-empty; indexes are unique and in range; paths are unique, repository-relative, and confined to the project root.

### Platform gate

`any` matches every normalized platform. Otherwise the Node platform must equal the runtime platform. The same predicate is used by `next`, `start`, completion/regression, and Stop-time regression checks.

### Stop Hook

- No valid workspace or no active Node: return an empty success object.
- More than one active Node: return an empty success response without running commands.
- One active Node with incompatible platform: request continuation and do not run commands.
- One active Node with fresh receipt: request that the agent finish remaining criteria and complete the Node.
- One active Node without a fresh receipt: run the contract. Pass records a receipt; failure records nothing. Either result requests continuation while the Node remains active.

## Deliberate patterns

- **Functional core with thin adapters:** one platform predicate and regression implementation prevent host-specific correctness drift; adapters only translate protocols.
- **Strategy by data, not subclasses:** host response shapes are small deterministic functions keyed by agent name. Class hierarchies would add indirection without state or behavior reuse.
- **Read-modify-write ownership marker:** configuration merge removes only handlers whose command contains the stable Better Plan marker, then appends one current handler per event. This makes install idempotent and uninstall scoped.
- **Content-addressed receipt:** sorted relative paths plus file contents, entry type, and symlink target produce a deterministic digest. Hashing is linear in declared tested content and avoids scanning unrelated dependency/build trees.
- **Fail on ambiguity:** stop-time discovery never selects an arbitrary Node; correctness is worth one explicit continuation.

## Risks and controls

- Host hooks may be disabled, untrusted, unsupported, or fail to launch. The manifest `start` and `complete` gates remain authoritative.
- Tests may modify declared files while running. The domain fingerprints immediately before and after the commands and refuses a receipt if the content changed.
- A contract may omit a relevant file. Requirements and review keep `paths` aligned with the Node's single declared closure; the tool can only guarantee declared scope.
- Command output may contain sensitive runtime data. It is captured, discarded, and excluded from errors and evidence.
- Global Hook configuration may contain unknown structures. The adapter validates only the portions it mutates and preserves all unrelated fields and handlers.
