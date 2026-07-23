# Kimi Code Support Architecture

Kimi joins the existing supported-target inventory and shared/native Skill resolver. Its native
root is derived from `KIMI_CODE_HOME`, with the current default selected only by the installer;
generated Hook commands contain no concrete machine path.

The Hook configuration adapter owns three complete TOML `[[hooks]]` tables marked inside their
portable commands. Installation first removes only marked tables and then appends the canonical
`SessionStart`, `UserPromptSubmit`, and `SubagentStop` set. Hook-only uninstall removes those
tables without parsing, serializing, or exposing unrelated provider and runtime configuration.

Kimi's protocol encoder returns plain text because its Hook contract consumes stdout directly.
An unrelated or invalid event returns empty stdout. `UserPromptSubmit` supplies bounded intent
guidance. `SessionStart` is detector-gated observation, and `SubagentStop` invokes the existing
correlated completion reducer; neither observation-only event is treated as a control channel.
