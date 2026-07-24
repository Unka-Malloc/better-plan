# Planning Work Activation Architecture

The activation predicate expands from coding or explicit implementation to planning, coding, or
explicit implementation. Static entry surfaces remain routing-only. `SKILL.md` and
`references/orchestration-main.md` adopt the same predicate so planning-only requests are not
accepted by the Hook and then rejected by the workflow.

No parser, classifier, state, cache, transition, Hook protocol, or role contract changes. Existing
progressive-disclosure tests extend their positive activation oracle with planning.
