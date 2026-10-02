# Delivery and decomposition references

[Reference shelf](engineering.md)

## Shared interfaces

Independent implementation needs shared knowledge of the interactions that cross
module boundaries. Parnas's [modularization paper](https://ckrybus.com/static/papers/decomposing_systems_into_modules_1972.pdf)
explains why those design decisions matter for parallel development.

Application: where Workers meet, useful information might include the input/output
meaning, state ownership, failure result, or ordering assumption. Put the facts in
the existing shared plan or interface definition so everyone reads the same source.
Describe what another contribution can rely on; implementation recipes and file
whitelists do not supply that missing agreement.

## Slices

Google's [Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
recommends coherent changes with related tests that leave the system working. It
describes horizontal, vertical, and combined decomposition, including explicit
ordering when one change depends on another. Smallness is conceptual, not a fixed
line count.

Application: a “save settings” outcome might include persistence, the command/API,
its caller, and observable verification in one Task. Its Nodes can follow real
implementation seams. Alternatively, two user-visible capabilities may proceed
independently once their shared interface is understood. Neither “one layer per
Task” nor “one Task per feature” is automatically the right answer.

A useful thought experiment is to implement one proposed Task after only its declared
prerequisites. What works then? If it needs an undeclared sibling, the dependency or
slice is incomplete. If every Node changes one shared registry, there is still a
coordination cost despite the parallel labels. Resolve the real join in the design;
adding Workers alone does not remove it.

Better Plan's use of Tasks for outcomes, Nodes for coherent contributions, and PRs
for reviewable delivery boundaries, with one accountable Reviewer, are project
conventions. Related Tasks may share a PR, and a Node's resulting revision may
contain multiple commits. Google's review staffing and process are not imported
with the decomposition advice.

## Refactoring

Fowler defines [refactoring](https://martinfowler.com/bliki/DefinitionOfRefactoring.html)
as changing internal structure while preserving observable behavior. This distinction
makes it possible to judge structural work separately from intentional behavior changes.

Application: establish the behavior that remains valid, change the structure, and
use that evidence to detect accidental differences. When fixing an incorrect design,
state the intended behavior change rather than calling every change a refactor.
Update related producers, consumers, tests, and documentation together. Published
contracts and stored user data need their actual support treatment; an unpublished
mistake alone is no reason to retain an obsolete implementation or compatibility path.
