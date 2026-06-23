# AI Usage Policy

This project uses AI-assisted development tools, including [Claude Code](https://claude.com/claude-code),
as part of the implementation workflow. This document states plainly how that assistance is used and
where responsibility lies: **AI is an implementation accelerator; the model, the decisions, and the final
content are human-owned.**

## What AI assistance may be used for

- drafting implementation code from explicit specifications,
- generating test scaffolding,
- refactoring,
- documentation drafts,
- exploratory prototypes.

## What remains human-owned

AI assistance is **not** treated as a source of truth. The maintainer remains responsible for:

- the conceptual model,
- architecture decisions,
- acceptance criteria,
- review and validation,
- test coverage,
- licensing and maintainability,
- final repository content.

## How AI-assisted output is handled

All AI-assisted output is treated as an **untrusted implementation draft** until it is reviewed, tested,
and aligned with the project specification. It is not merged on the strength of looking plausible.

This is enforced by how the project is built. Development is organised around explicit specifications
(`docs/rpg_persona_dynamics_spec_v1.md` is the source of truth), block diagrams, per-tick traces,
scenario-based validation, and a substantial automated test suite (currently around 300 automated tests,
including property, persona-contrast, order-invariance, stability, and golden-trace determinism checks).
AI may assist with implementation, but the model must remain explainable, testable, and auditable: a
change that cannot be reviewed against the spec and validated by tests does not land, regardless of how
it was drafted.

---

In short: **AI-assisted, human-owned, spec-driven, and test-validated.**
