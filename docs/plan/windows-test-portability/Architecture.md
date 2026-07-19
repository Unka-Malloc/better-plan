# Architecture

This correction changes no production interface. The manifest CLI keeps its strict documented
positionals, and the affected subprocess test helpers insert the workspace immediately after the
node ID. This avoids a broad `parse_known_args` recovery path that could hide misspelled options.

The architecture oracle defines one version-aware tuple of supported `try` AST node classes.
Python 3.10 contributes `ast.Try`; newer runtimes additionally contribute `ast.TryStar`.

Installer subprocess tests receive an explicit environment. Optional-client warning coverage uses
an empty executable search path, while lifecycle smoke coverage exposes only the current Python
directory. General installer tests suppress real WSL discovery by default; the dedicated WSL tests
retain their controlled mocks.

CI uses a small operating-system and Python matrix: Windows with Python 3.10 catches the supported
floor, and Ubuntu with the current Python release retains forward coverage. Both execute the same
complete suite and portable CLI smoke commands.
