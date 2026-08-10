# Compiled Plan repair

Use the supplied repair brief exactly as given. Treat `Design.md` as read-only source material and
complete `Plan.json` directly. Preserve every unmapped Designer line in an appropriate Plan field.
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
