# A small project, from requirements to closure

[Back to Better Plan](../README.md) · [Workflow guide](guide.md#how-it-works) ·
[Interactive presentation](presentations/better-plan-workflow.html)

This is a fictional example of ordinary software development. The application,
requirements, people, and events below are invented.

## The request

A small browser-based reading-list application already stores books locally. Its user asks for
three outcomes: fix an existing bug that drops a book's notes when its title changes,
make storage easier to extend without changing current behavior, and add portable
JSON export and import. An exported list must import without losing notes or tags.
Existing saved lists must continue to open.

Main records these requirements and keeps the original wording accessible. It starts
a persistent Verifier alongside itself. For this project, Main also explicitly assigns
an Adversary to the named agents `main` and `architecture`, serving as Main and
Designer. The assignment is to question their
actual choices, not merely to check a plan. Designer begins examining the application.

## Questions begin before the plan is ready

The Adversary starts immediately. It reads what Main and Designer are actually doing,
examines the browser application and the development host's available tools and sandbox,
checks project and organization guidance plus local repository rules, and consults
relevant browser API documentation and software guidance on importing untrusted data.
No completed plan is available or needed.

Designer is considering a native filesystem service to simplify import. The Adversary
notices that the application runs entirely in a browser and that the proposed service
would add a runtime and deployment burden the project does not have. It messages
Designer directly: “What requires a native service here? The existing browser file
picker can read a user-selected file. A new service adds a deployment dependency before
we have established a need for it.” It also asks Main why service deployment work is
already being queued. Following a draft plan would not settle either concern.

Designer checks the observation and chooses the existing browser boundary. Main removes
the unnecessary queued work. The Adversary has offered opinions, not edited their design
or plan. A host without direct agent messaging would have Main relay those same messages
unchanged. This role could challenge the same choices in a team with no formal plan.

Designer now proposes three independently deliverable milestones:

1. **Existing bug fix:** preserve notes when a title changes. This improves the current
   application on its own and can ship without import or export.
2. **Necessary refactor:** isolate storage access behind one repository interface while
   preserving saved-data compatibility and existing behavior. This leaves a runnable,
   useful application and prepares a consistent boundary for import and export.
3. **New feature:** add complete JSON export and import, including the interface,
   validation, persistence, and round-trip behavior. It depends on the storage boundary.

These are complete outcomes, not separate “backend,” “UI,” and “tests” milestones.
Designer defines the shared interface and real dependencies, then hands off. It does
not enumerate every implementation branch or guess every future bug.

## Work arrives; verification keeps going

Main groups Workers by functional domain: storage ownership covers the title-update
fix and storage boundary, while transfer ownership covers import/export behavior. It
dispatches independent contributions with clear write ownership. Transfer Workers can
study the agreed format while the refactor completes, but do not integrate code against
an unfinished boundary. Domain needs and actual host resources determine how many
Workers are useful. Neither work nor adversarial coverage uses fixed-size groups.

Main explicitly updates the Adversary's assignment: `storage-owner` belongs to the
storage domain, `transfer-owner` to the transfer domain, and `verification` is the
Verifier. It can question a proposed
cross-domain shortcut or a Verifier's unproductive retry loop while those agents retain
implementation, testing, and integration ownership.

A storage Worker submits a title-update change and a short location-and-result handoff. It is
not asked to certify quality, run the delivery process, integrate other work, or build
a proof package. The Verifier reads the actual diff and discovers that blank titles
still overwrite notes through a second update path. It fixes that path, tests both
cases independently, integrates the correction, and checks the resulting application.
A convincing Worker report would not have replaced that inspection.

The storage refactor finishes next. Verifier inspects its actual changes, notices a
saved-data compatibility regression, repairs it, and checks old saved lists. Neither
ordinary repair restarts the entire architecture exercise.

## A milestone closes while other work continues

The bug-fix candidate is captured at an immutable revision. Main gives a separate
Reviewer the relevant requirements and that code snapshot. The Reviewer independently
reads the implementation and reproduces the required behavior; it does not accept the
Worker's report or the Verifier's passing checks as proof. It closes this candidate
when its own inspection and verification justify the result.

While that review runs, the persistent Verifier continues integrating the storage
refactor outside the frozen candidate. The Reviewer is not observing a moving target,
and unrelated work does not wait. The completed refactor later receives the same
independent milestone closure. Main can resume the same Reviewer for each milestone
and final review; independence means separation from implementation and persistent
verification, not a mandatory new agent session for every candidate.

## A feature error stays inside the feature

A transfer Worker implements export and import. Verifier discovers that import drops
empty tags and incorrectly decodes a note containing a line break. It repairs those
problems directly or sends a bounded implementation repair through Main, then independently
inspects the returned changes and tests them. These are errors in the new feature,
not additional “bug-fix milestones.” The feature remains open until its complete
outcome works. A repaired candidate replaces the old revision and is verified afresh.

The independent Reviewer checks the stable feature candidate from its requirements
and code. It can find and repair more defects, then retest; review is not merely a
pass/fail vote. Any corrected revision returns to the persistent Verifier, which
inspects and incorporates the correction into the ongoing whole-plan candidate.
Persistent verification of other work can continue in parallel.

## The Reviewer can be challenged too

Main explicitly adds `milestone-review`, the Reviewer, to the Adversary's targets. The Adversary reads
the Reviewer's actual inspection and sees it preparing to close the feature after
successful round trips. It asks: “What happens to an existing list when an import file
is valid JSON but has the wrong structure? Could a failed import erase the user's data
before validation finishes?” Neither the plan nor the original request spells out that
failure case, but the risk to existing data is reason enough to question the conclusion.

The Reviewer independently investigates. It reproduces an early-clear path, repairs the
candidate so rejected input leaves the list untouched, and verifies the fix and affected
behavior. The persistent Verifier then inspects and integrates that corrected revision.
The Adversary did not change the code, add a plan entry, demand an evidence package, or
veto closure. Its message prompted the responsible agents to exercise their own judgment.

## The last handoff is deliberately different

Main confirms every Worker has finished and stopped writing, milestone-review repair
writes have ended, and corrected milestone revisions have been incorporated. The persistent Verifier
then runs final whole-plan regression on the integrated application: title updates,
old saved lists, the storage boundary, import, export, and their interactions. It
repairs any defects and repeats the necessary checks, then notifies Main.

Main stops the Verifier and confirms its writes have ended. Only then does a separate
final Reviewer take the final candidate. It reads the complete requirements and code
with fresh judgment, independently validates the application, and repairs any remaining
problem. It does not inherit the earlier verification as proof.

The final Reviewer notices that the original round-trip requirement applies to an
entire reading list, although the plan's examples focused on individual books. It
checks complete lists, finds an ordering mistake, repairs it, and verifies the changed
candidate and affected behavior. All requirement closure includes this omission; three
closed milestones alone would not establish that the original request was fulfilled.

If further implementation is needed, Main coordinates a scoped rework cycle and the
changed candidate receives fresh verification. Ordinary host messages and stable
revisions support these handoffs, without a new enforcement or approval system.
Delivery, publication, and installation still follow the project's authorization.

The result is a working application with each requested outcome accounted for: the
old bug is fixed, the necessary refactor preserves behavior, and the complete new
feature meets its round-trip requirement.
