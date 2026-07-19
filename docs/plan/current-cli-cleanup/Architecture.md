# Architecture

This plan changes no production interface. The current `edit-node` implementation
already accepts repeated `--criterion` values as one complete replacement and
atomically invalidates stale preparation and regression proof.

The implementation Node owns only `tests/test_manifest_tool_cli.py` and removes the
obsolete negative-test function. Adjacent current-interface tests remain the durable
contract. A Node-local linear scan of active documentation, source, and tests is the
one-time migration oracle; completed Plan history is excluded and remains immutable.

The final Node owns no implementation work. It runs the complete suite once for its
reviewed fingerprint, validates current source paths, and cross-checks REQ-001 before
a fresh auditor decides completion.
