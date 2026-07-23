# Python 3.8 Compatibility Evidence

- The repository has no packaging metadata or other machine-readable minimum Python declaration.
- The public README does not state a Python compatibility floor.
- CI currently exercises Windows on Python 3.10 and Linux on an unpinned current Python release, so
  neither job proves the requested lower bound.
- An isolated CPython 3.8 compile-only probe accepts every module under `scripts/` and `tests/`.
  Remaining risk is therefore runtime standard-library behavior and test parity rather than parser
  syntax.
- Importing the manifest command on Python 3.8 fails before argument handling because
  `domain/transitions.py` evaluates `tuple[str, str, str]` as a runtime type-alias expression.
  Built-in generic aliases are not subscriptable until Python 3.9; annotations postponed by
  `from __future__ import annotations` do not postpone ordinary assignment expressions.
- The repository already uses only the standard library at runtime. A direct Python 3.8 test run is
  the most faithful oracle and avoids a compatibility shim or speculative source rewrite.
