# Using Better Plan

[Back to Better Plan](../README.md) · [Interactive presentation](presentations/better-plan-workflow.html)

## How it works

Describe the outcome you want. Better Plan helps the agents carry that intent through
planning, parallel implementation, and independent review.

| Role | What it does |
| --- | --- |
| Main | Understands and conveys your needs, relays questions, resumes interrupted work, and starts the next ready work. |
| Designer | Independently designs the solution and a shared plan with useful parallel work. |
| Workers | Read the shared plan and repository, implement their assigned contributions, and record results. |
| Reviewer | Independently checks the result and the plan, fixes defects, then integrates and verifies the delivery. |

One Designer owns the design. Workers run in parallel where the work allows it.
After the other writers finish, one Reviewer stays responsible through repair and
closure. Questions that require your decision come back through Main; dependent
work waits for clarity.

The [presentation](presentations/better-plan-workflow.html) includes the actual
shared instructions and role prompts. GitHub displays HTML as source; download the
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
permission, and sandbox configuration. The installed package includes this guide,
the offline presentation, and the license. See [host configuration](../references/host-configuration.md)
for installation locations, receipts, and Doctor diagnostics.

## Working with a plan

You describe the goal; the agents maintain the plan through the skill's tools.
Current requirements, architecture, open decisions, dependencies, and results are
shared directly. Relevant source conversations remain available as on-demand history.

A Task groups an independently deliverable change into a Draft PR. Its Nodes are
coherent contributions, each represented by a commit. The Reviewer handles final
integration after the other writers finish. Longer programmes keep future work as
outlines until it is ready to design in detail.

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

## Development

Maintaining Better Plan itself uses the ordinary repository workflow, without
creating a local plan workspace. Run relevant focused tests while editing. After
implementation, source review, and repairs are complete, run the full suite:

```sh
python3 scripts/run_tests.py
```

[Repository rules](https://github.com/Unka-Malloc/better-plan/blob/nightly/AGENTS.md) govern development. [Design principles](../references/design-principles.md)
explain the product's choices.
