# Compiled Plan repair

Use the supplied repair brief exactly as given. Treat `Design.md` as read-only source material and
complete `Plan.json` directly. Map every valid in-scope Designer meaning into an appropriate Plan
field, including valid unmapped content. Do not promote content conflicting with explicit user
decisions, out-of-scope suggestions, or rejected alternatives into implementation requirements.
Record each non-adoption reason and its Design line reference in `spec.architecture.notes`; the
unchanged live and pristine drafts retain the original content. Do not freely rewrite valid design
choices or use exclusion to conceal missing requirements.
Use each issue's supplied Design line or line range and canonical Plan field directly; do not repeat
the compiler's parsing work merely to locate the defect.

Do not change or delete `Design.md`, and do not redispatch the Designer. Keep the repair inside the
authorized intent and the existing v3 Plan schema.

After completing the Plan run:

```sh
python3 scripts/manifest_tool.py compile-design --plan <PLAN-CODE> --apply
```

The command verifies the repaired Plan, confirms that the archived draft is unchanged, and closes
the conversion receipt. It never recompiles over the main thread's repair.
