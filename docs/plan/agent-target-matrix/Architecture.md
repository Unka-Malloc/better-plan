# Current Agent Target Matrix Architecture

`AGENTS` is the single supported-target inventory. Pi joins shared-skill resolution. Antigravity
owns one atomically replaced plugin directory containing `plugin.json`, `hooks.json`, and the
canonical Better Plan tree under `skills/better-plan`. Craft workspace discovery returns a
deterministically ordered tuple of directories that contain `config.json`; the canonical copier
updates each workspace skill independently.

The Antigravity protocol maps only invocation zero from `PreInvocation` to Better Plan's existing
session guidance. Later invocations are no-ops. The plugin has no `PreToolUse`, `PostToolUse`,
`PostInvocation`, or `Stop` handlers, so it cannot block tools or force execution to continue.

Installation, diagnosis, and uninstallation use the same target names and paths. Removed Gemini
adapter functions, flags, enablement state, tests, and documentation have no compatibility path.

