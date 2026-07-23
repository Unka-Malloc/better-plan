# Current Agent Target Matrix Evidence

- Antigravity officially packages skills and Hooks inside a global plugin. Its first model call is
  observable through `PreInvocation`, which can inject an ephemeral guidance step.
- Pi implements Agent Skills and scans the shared `.agents/skills` location.
- Craft Agents isolates skills under each configured workspace and has no documented global skill
  directory.
- The existing installer already centralizes target selection, atomic skill copying, diagnosis, and
  uninstallation, so the migration belongs in those boundaries rather than in parallel scripts.

