# Using Better Plan

[Back to Better Plan](../README.md) · [Interactive presentation](presentations/better-plan-workflow.html)

## How it works

Describe the outcome you want. Better Plan carries that intent through architecture,
parallel implementation, continuous verification, and fresh independent closure.

| Role | What it does |
| --- | --- |
| Main | Owns requirements, dispatch, coordination, blockers, user questions, and the workflow handoff. |
| Designer | Provides light architecture and decomposition into independently deliverable milestones with real dependencies. |
| Workers | Grouped by functional domain, implement assigned contributions and scoped repairs; their output is untrusted until independently inspected. |
| Verifier | Runs persistently alongside Main by default; independently inspects every actual change, integrates, tests, and repairs continuously. |
| Reviewer | Independently validates and repairs a stable candidate against requirements and code, then closes its scope. |
| Adversary | Independently challenges one or more explicitly named target agents through opinions and messages; works in any collaboration structure, with or without a plan. |

### Independent challenge, with or without a plan

A coordinator explicitly assigns the Adversary one or more named targets. In Better
Plan the coordinator is Main, and targets can include Main itself, Designer, Workers,
Verifier, or Reviewer. For Workers, group assignments by **functional domain** such
as storage or import/export, naming the actual agents in that domain. Do not partition
Workers into arbitrary groups of a fixed size. The same role can be used in other
collaboration structures without adopting Better Plan's delivery workflow.

Once assigned, the Adversary investigates immediately. It examines what its targets
are actually doing and trying to accomplish, the actual host environment and available
capabilities, applicable project, organization, and local rules, and relevant external
documentation and software best practices. It does not wait for a completed plan,
implementation, report, or request to review. Plans and requirements can inform its
judgment, but are neither prerequisites nor the sole authority on correctness.

Independent common sense matters: a plan can be internally consistent yet infeasible
in the real environment. A target can follow its instructions while doing wasteful or
odd work, creating unnecessary coupling, or exposing private data. The Adversary
questions these choices and explains concrete concerns to the responsible target.
It messages that target directly when the host supports it; otherwise the coordinator
relays its message unchanged. Useful uncertainty should be stated, not disguised as a
confirmed defect.

Its only outputs are opinions and messages. It never edits code, documents, or plan
artifacts, performs repairs, or integrates work. Targets retain their responsibilities
and judgment, and the coordinator handles decisions and coordination. There is no
Adversary veto, mandatory evidence pack, runtime service, schema, or scheduler. An
installed profile does not assign targets or start an agent.

### Continuous work and milestone closure

Main starts the persistent Verifier and dispatches ready work. Designer hands off once
architecture, boundaries, and dependencies are clear; it does not predict every runtime
bug. Workers choose implementation details and resolve ordinary implementation problems.
They have no QA, process, integration, or mandatory evidence-pack duty. Their reports
locate work, but are not proof of correctness. The Verifier inspects the actual changes,
including repairs, and independently establishes whether the integrated result works.

Group Workers by functional domain and use inexpensive Workers in parallel where
useful, within available resources and host permissions. Domain boundaries, real
dependencies, and shared writes determine what can run together, not a fixed headcount.
Nothing here assumes unlimited or free compute or changes host-owned settings.

When a milestone candidate is ready, a separate Reviewer receives its requirements
and immutable code snapshot. Prior Worker or Verifier conclusions are not its proof.
It independently validates and repairs the candidate, rerunning affected checks after
changes. Meanwhile the persistent Verifier continues other work outside that candidate.
Only the reviewed candidate is held stable; unrelated work does not stop. Reviewer
corrections return to the persistent Verifier for inspection and integration into
the ongoing whole-plan candidate.

### Final handoff

1. Main establishes that all Workers are done, milestone-review repair writes have
   ended, and corrected milestone revisions have been incorporated.
2. The persistent Verifier runs final whole-plan regression on the integrated result,
   repairs defects, and repeats affected verification as needed.
3. Verifier notifies Main when that work is complete.
4. Main stops the Verifier and confirms its writes have ended.
5. A separate final Reviewer independently validates and repairs the final candidate
   from requirements and code, closing every requirement, including missing plan work.

This is a simple host handoff: all Workers done → Verifier final regression → notify
Main → Main stops Verifier → separate final Reviewer. Earlier test results and milestone
closure are not substitutes for final independent judgment. Rework cycles are allowed;
changed candidates need fresh verification. There is no added enforcement or human
approval framework. Material questions go through Main, and only dependent work waits
for an answer. Existing authorization and repository rules still apply.

Independently deliverable existing bug fixes, necessary refactors, and new features
have distinct milestone boundaries. Ordinary errors introduced while implementing a
feature remain within that feature. See the [fictional project story](story.md) for
an example of all three, early adversarial investigation, continuous repair, a
challenge to the Reviewer, and final closure.

The package includes five native specialist profiles: Designer, Worker, Verifier,
Reviewer, and Adversary. New Codex Verifier profiles use GPT-6 Luna / max; new
Codex Adversary profiles use GPT-6.1 Sol / high. Other hosts inherit their settings,
and existing host-owned configuration stays unchanged. Main starts the Verifier through
the host during the default workflow; installing a profile does not launch an agent.
The independent Reviewer may resume across milestones and final review while remaining
separate from the persistent Verifier.

The [presentation](presentations/better-plan-workflow.html) includes the actual
shared instructions and all role prompts. GitHub displays HTML as source; download the
file and open it locally to use the slides, role tabs, and keyboard navigation.

## Install and update

From a checkout of this repository:

```sh
python3 scripts/install.py install --agents codex
```

Choose your host with `--agents`:

| Host | Target |
| --- | --- |
| Codex | `codex` |
| Claude Code | `claude` |
| Cursor | `cursor` |
| Kilo Code | `kilo` |
| DeepSeek Harness | `dsh` |

You can name several targets, or use `--agents all`. The installer requires
Python 3.8 or newer; it needs no third-party Python packages.

To update an installation from the current checkout and check it:

```sh
python3 scripts/install.py update --agents codex
python3 scripts/install.py doctor --agents codex
```

Updates refresh the skill and role prompts while preserving existing model, tool,
permission, and sandbox configuration. A narrow migration adds only missing
Verifier and Adversary profiles to recognized older installations; same-name custom
roles or uncertain ownership are reported without replacement. The installed package includes this guide,
the offline presentation, and the license. See [host configuration](../references/host-configuration.md)
for installation locations, receipts, and Doctor diagnostics.

## Working with a plan

You describe the goal; the agents maintain the plan through the skill's tools.
Current requirements, architecture, open decisions, dependencies, and results are
shared directly. Relevant source conversations remain available as on-demand history.

A Task describes a deliverable outcome; a Node describes a coherent contribution.
A Draft PR marks a reviewable delivery boundary and may cover related Tasks. A Node's
resulting revision may contain multiple commits. Keep these relationships explicit
and useful for review rather than forcing one-to-one mappings. Longer programmes
keep future work as outlines until it is ready to design in detail. A milestone is
one independently deliverable unit: a feature or a module's rework, not a layer or a
partial slice.

For inspection from the command line, replace `<plan>` with the plan directory:

```sh
python3 scripts/manifest_tool.py tree status <plan> --json
python3 scripts/manifest_tool.py tree export <plan>
```

The [tree contract](../references/checkpoints-tree.md) documents stored files,
commands, dependency updates, checks, recovery, and delivery states. The
[programme guide](../references/programme.md) covers milestones and requirement
coverage. Agents load [SKILL.md](../SKILL.md) and the relevant role guide; the
human-facing presentation is not injected into their prompts.

Engineering delivery leaves PRs Draft by default. Publication, merge, installation,
and live acceptance follow your project's authorization.

## Engineering references

The [reference shelf](../references/engineering.md) offers optional, problem-oriented
notes on architecture, decomposition, tests, and acceptance, with links to original
industry sources. Agents choose what helps; it is not a required reading list.

## Process references

Alongside the role guides, five references carry the shared process mechanics:

- [Glossary](../references/glossary.md) — canonical terms so briefs and records do
  not drift.
- [Lifecycle](../references/lifecycle.md) — one phase model: who acts, who stays
  quiet, and what is frozen at each step.
- [Authority](../references/authority.md) — per-role May/Must/Must not/never-decides
  matrix for cross-role questions and dispatch.
- [Route review](../references/route-review.md) — event-triggered re-decision of the
  route (repeated failure, empty rounds, scope growth, cost growth) with a Round DoD:
  every round names the uncertainty it removed.
- [Exceptions](../references/exceptions.md) — recovery from interrupted checks,
  stale state, phase mismatches, and persistent blockers.

These are process guidance, not new gates: they add no approval mechanism, no
runtime enforcement, and no extra status system.

## Development

Maintaining Better Plan itself uses the ordinary repository workflow, without
creating a local plan workspace. Run relevant focused tests while editing. After
editing canonical role guidance, refresh the offline presentation's prompt data with
`python3 scripts/generate_workflow_presentation.py`; pass `--check` to detect drift
without writing. Prompt hygiene gate: every "Must not" in the authority matrix cites
its source guide; terms in role guides come from the glossary; new reference files
are added to `CURRENT_SKILL_FILES` in
`scripts/better_plan/installation/models.py` so installers ship them. After
implementation, source review, and repairs are complete, run the full suite:

```sh
python3 scripts/run_tests.py
```

[Repository rules](https://github.com/Unka-Malloc/better-plan/blob/nightly/AGENTS.md) govern development. [Design principles](../references/design-principles.md)
explain the product's choices.
