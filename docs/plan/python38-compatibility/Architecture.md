# Python 3.8 Compatibility Architecture

## Runtime contract

Python 3.8 becomes the single minimum supported runtime. The same source tree executes on every
supported Python version; there is no version-specific module, import fallback, or compatibility
branch. If the lower-bound regression identifies an unavailable API, the active implementation is
replaced once with the simplest Python 3.8 standard-library equivalent.

The README owns the user-facing runtime statement. CI owns the executable support matrix. The
source and tests remain the behavioral implementation and must pass unchanged across the matrix.
Runtime type aliases use their `typing` equivalents where Python evaluates the alias expression;
postponed function and variable annotations may retain the current built-in generic notation.

## Continuous integration matrix

The CI matrix contains:

- Linux with Python 3.8;
- Windows with Python 3.8;
- Linux with the current `3.x` runtime.

Both lower-bound jobs run the complete suite and CLI smoke checks already used by CI. The current
job protects against upper-end drift. No job is allowed to skip compatibility tests based on the
runtime version.

## Validation strategy

The focused regression for this capability is the complete repository suite under isolated
CPython 3.8 because the compatibility boundary spans every shipped module and command. A compile
probe detects parser and import-surface failures before behavioral tests. Contract tests verify the
README declaration and CI lower-bound jobs so compatibility cannot silently drift upward later.

After the Node passes its Python 3.8 regression and independent audit, the repository's ordinary
full regression runs exactly once on the current validation runtime.

## Design constraints

- Keep runtime dependencies standard-library-only.
- Do not add `typing_extensions`, `six`, vendored backports, or parallel old/new code paths.
- Replace the active `TransitionKey` alias with `typing.Tuple` rather than branching on the runtime
  version.
- Do not weaken or conditionally skip existing tests.
- Keep commands, state files, Hook protocols, installer targets, and public behavior unchanged.
- Persist only repository-relative evidence and bounded pass/fail receipts.
