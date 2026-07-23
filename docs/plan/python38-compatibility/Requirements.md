# Python 3.8 Compatibility Requirements

Better Plan currently has no declared minimum Python version, while continuous integration begins
above the requested lower bound. The delivery must make Python 3.8 the explicit, executable
compatibility floor without creating a second implementation path.

- **REQ-001 — Public runtime floor:** user-facing installation and development guidance states that
  Better Plan supports Python 3.8 and newer.
- **REQ-002 — Lower-bound execution:** every shipped Python entry point, package module, and test
  module compiles and executes on an isolated CPython 3.8 runtime.
- **REQ-003 — Complete behavioral parity:** the complete repository test suite passes on Python 3.8
  without skipping behavior or retaining a newer-runtime fallback.
- **REQ-004 — Continuous compatibility:** CI exercises the Python 3.8 lower bound on Linux and
  Windows and retains a current-Python job so the supported range is tested at both ends.

## Non-goals

- Packaging Better Plan as a Python distribution.
- Supporting Python 3.7 or older.
- Maintaining parallel implementations for old and new Python versions.
- Changing workflow, installer, Hook, or planning semantics.
