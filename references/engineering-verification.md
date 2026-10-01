# Verification and acceptance references

[Reference shelf](engineering.md)

## Acceptance

Cucumber's [Gherkin reference](https://cucumber.io/docs/gherkin/reference/)
distinguishes initial context, an event, and an observable outcome. That is a useful
way to clarify acceptance even when the project does not use Gherkin or Cucumber.

Application: “Given saved settings, after restarting, the client uses those settings”
expresses an outcome. “Create the settings module” describes work but does not prove
that outcome. For an import, rejection behavior for a malformed record may matter as
much as the happy path. Choose examples from the user's requirements and actual risk;
the syntax and example count are not prescribed.

For performance, recovery, or maintainability claims, [arc42 quality scenarios](https://docs.arc42.org/section-10/)
help make the conditions and response assessable. Agree on relevant measures instead
of adding arbitrary budgets. A test passing under different conditions does not
establish the intended claim.

## Evidence

Ham Vocke's [Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
discusses fast narrow tests, integration and contract checks, and a smaller set of
end-to-end journeys. It emphasizes testing behavior and avoiding redundant coverage.
Use the boundary that can detect the defect; the pyramid is not a required numerical
ratio.

Application:

| Claim | Useful evidence |
| --- | --- |
| A scheduling rule preserves dependency order | Deterministic cases against the real scheduling implementation |
| A stored operation can resume | Persistence/restart test against the actual storage path |
| Two components agree on a protocol | Contract or integration check exercising both sides |
| The user can complete a critical journey | An appropriate end-to-end or authorized live check |

Test doubles can isolate a dependency, but agreement between two invented doubles
cannot demonstrate that production components connect. Keep deterministic engineering
checks distinct from claims that genuinely require a real service, Agent, or user
workflow; those follow the project's live-acceptance authorization.

Google's [review guidance](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
asks whether the overall design makes sense, functionality serves users, tests can
catch defects, and complexity is justified. Passing tests do not replace that judgment.

Application: the Reviewer can ask what user-visible failure a test would detect,
inspect the production connection, and challenge a faulty assumption in the plan.
Assertions tied to an internal call order or incidental wording may reject harmless
changes while missing the actual requirement. Conversely, a small test with a clear
behavioral claim may be enough; more tests are not automatically stronger evidence.
