# Requirements

## REQ-WIN-001 Current CLI ordering

State-machine and Agent-completion tests must invoke node commands using the documented
`command node-id [workspace] --options` order. Lifecycle scenarios must execute against a local
Windows drive path, and parser coverage must preserve UNC path syntax without contacting a real
network share. No permissive production parser fallback may be added.

## REQ-WIN-002 Python 3.10 architecture analysis

Architecture tests must analyze `try` statements on Python 3.10 and include `try*` statements
when the running Python version exposes that AST node.

## REQ-WIN-003 Hermetic installer tests

Tests in `tests/test_install_tool.py` must not discover or execute optional host CLIs or WSL
distributions unless a test explicitly supplies a controlled fixture for that integration.

## REQ-WIN-004 Windows regression coverage

Continuous integration and local acceptance must run the complete suite on Windows with the
oldest supported Python version as well as the current Linux runtime.
