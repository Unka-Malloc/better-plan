# Kimi Code Support Evidence

- Kimi Code documents user Skills under `$KIMI_CODE_HOME/skills/` and the shared
  `.agents/skills/` tree.
- Kimi Code stores Hooks as `[[hooks]]` tables in `$KIMI_CODE_HOME/config.toml`.
- The current lifecycle events include `SessionStart`, `UserPromptSubmit`, and `SubagentStop`;
  only the prompt event can affect the main flow, while the other two are observation-only.
- Hook failures are fail-open, so Better Plan returns exit code zero and never emits a denial.
