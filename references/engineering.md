# Engineering reference shelf

Use this shelf when a design or implementation question would benefit from a concrete
engineering reference. Follow the relevant link, or skip it when existing evidence
is sufficient. These are practices to evaluate, not mandatory reading, a prescribed
architecture, or additional approval criteria. Repository rules and user needs give
them context; the sources are not all universal standards.

| Question | Start here |
| --- | --- |
| Where should module, file, and state boundaries go? | [Architecture: boundaries](engineering-architecture.md#boundaries) |
| Which qualities should determine the architecture? | [Architecture: quality and decisions](engineering-architecture.md#quality-and-decisions) |
| What information helps another Agent implement independently? | [Delivery: shared interfaces](engineering-delivery.md#shared-interfaces) |
| How can work run in parallel and still produce a working result? | [Delivery: slices](engineering-delivery.md#slices) |
| How do we change structure without preserving a design mistake? | [Delivery: refactoring](engineering-delivery.md#refactoring) |
| What would demonstrate that a user requirement is satisfied? | [Verification: acceptance](engineering-verification.md#acceptance) |
| Which tests are useful, and what do passing tests fail to prove? | [Verification: evidence](engineering-verification.md#evidence) |

The notes summarize selected ideas, link to their original sources, and give small
Better Plan applications. They can inform design and implementation, Verifier checks, and independent Reviewer
judgment; they do not require implementation-only Workers to produce acceptance proof.
For framework-specific choices, use the official guidance and maintained source/tests
for the version in the repository; a generic reference cannot choose its directory
layout or runtime semantics for it. Sources checked 2026-10-01.
