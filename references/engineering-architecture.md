# Architecture references

[Reference shelf](engineering.md)

## Boundaries

**When one change touches everything:** Parnas proposes organizing modules around
design decisions that can change, hiding those details behind interfaces. A module
is a responsibility, not merely a function or a stage in a processing pipeline.
This helps explain why splitting a large file into smaller files can leave the
same coupling intact. Source: D. L. Parnas, [On the Criteria To Be Used in Decomposing
Systems into Modules](https://ckrybus.com/static/papers/decomposing_systems_into_modules_1972.pdf)
(1972 original paper, hosted copy).

Application: for a job runner, separate the rules for selecting ready work from the
storage representation and process launcher. Ask who owns each state change and
which interface consumers actually need. If every Worker must edit the same dispatch
function, reconsider that boundary before labeling the work independent. File names
can follow these responsibilities; file count alone says little about modularity.

**When collaborators cannot picture the system:** C4 provides context, container,
component, and code views. Its author recommends using only levels that add value;
a context and container view often suffice. Source: Simon Brown's [C4 diagrams](https://c4model.com/diagrams).

Application: a small map naming the caller, service, data owner, and external systems
may expose a missing connection faster than a long list of layers. Add interaction
or deployment detail when it resolves a real question, not to fill a diagram set.

## Quality and decisions

**When the goal says only “fast”, “safe”, or “reliable”:** arc42 uses concrete quality
scenarios to connect conditions and stimuli to measurable responses. Source:
[arc42 quality requirements](https://docs.arc42.org/section-10/).

Application: “An interrupted import can resume without duplicate records” gives the
Designer a state and recovery problem to solve. A latency target needs a workload
and measurement context; obtain missing stakeholder expectations rather than invent
numbers. Different answers may justify different architectures.

**When several approaches are plausible:** Nygard's decision records retain the
context, choice, and consequences of consequential architectural decisions. This
helps later engineers avoid blindly accepting or reversing a choice. Source:
[Documenting Architecture Decisions](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

Application: explain the relevant alternative and tradeoff in the existing plan or
repository decision record. A separate ADR is useful only if the decision merits it;
Better Plan needs neither an extra document per Node nor a new approval workflow.
