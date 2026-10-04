# Better Plan

**Keep long-running agent work aligned with what you asked for.**

Better Plan gives your coding agents a shared plan they can carry across sessions.
Main keeps requirements and dispatch moving. A light Designer shapes the architecture,
Workers implement in parallel, and a persistent Verifier independently checks,
integrates, tests, and repairs their work. A separate Reviewer closes each candidate
from requirements and code. An Adversary independently challenges explicitly assigned
agents, including the Reviewer, through opinions and messages. It works with any
collaboration structure, whether or not a plan exists.

![Main coordinates requirements and dispatch; Designer decomposes the work; functional-domain Workers implement; persistent Verifier checks and integrates; separate Reviewer closes immutable candidates. An explicitly assigned Adversary independently challenges any named role through messages.](docs/images/workflow.svg)

**[Explore the workflow](docs/guide.md#how-it-works)** ·
**[Read a fictional project story](docs/story.md)** ·
**[Get the interactive presentation](docs/presentations/better-plan-workflow.html)**

The presentation is a standalone HTML file: download it and open it in your browser.
It shows the workflow and the actual role prompts, with no setup or internet required.

## Why use it?

Agents make mistakes. Better Plan keeps implementation inexpensive and parallel where
resources allow, then checks actual changes independently instead of trusting reports.

- **Keep the goal in view.** Main preserves requirements, decisions, and real blockers
  while Designer supplies architecture and independently deliverable milestones.
- **Keep implementation focused.** Workers implement bounded contributions. They do
  not own QA, process, integration, or a mandatory proof package.
- **Check work continuously.** The default-on Verifier runs alongside Main, inspects
  every actual change, integrates it, tests it, and repairs defects as work arrives.
- **Question assumptions early.** An assigned Adversary immediately investigates its
  targets' actual work, the host environment, applicable rules, and relevant external
  guidance. It can flag infeasibility, waste, coupling, or privacy risks beyond a plan
  without taking over implementation or approval.
- **Close with a fresh view.** A separate Reviewer independently assesses immutable
  milestone candidates from requirements and code. Final review follows the Verifier's
  whole-plan regression and shutdown, and covers every requirement, including omissions.

Use it for multi-part features, migrations, and projects that span many sessions.
Small tasks can stay small. Parallelism stays within available resources and host
permissions; Better Plan does not change your model or reasoning configuration.

## Start using it

Requires Python 3.8+. Supports Codex, Claude Code, Cursor, Kilo Code, and DeepSeek Harness.

```sh
git clone https://github.com/Unka-Malloc/better-plan.git
cd better-plan
python3 scripts/install.py install --agents codex
```

Then tell your agent:

> Use Better Plan to plan and deliver this project: [describe your goal].

[Installation, updates, and other hosts →](docs/guide.md#install-and-update)

## Go deeper

[User guide](docs/guide.md) · [Agent instructions](SKILL.md) ·
[Tree tools](references/checkpoints-tree.md) · [Long-term programmes](references/programme.md)

## License

[Apache License 2.0](LICENSE). Bundled third-party components retain their
[own licenses](scripts/better_plan/_vendor/README.md).
