<!-- Thanks for contributing! See CONTRIBUTING.md. main is protected: CI must pass and a maintainer merges. -->

## What & why

<!-- What does this change, and why? Link any related issue (e.g. Closes #123). -->

## Type of change

- [ ] Bug fix
- [ ] New behaviour / feature
- [ ] Calibration (constants only, topology unchanged)
- [ ] Topology / structural change (spec + diagram updated below)
- [ ] Docs / tests / tooling

## Checks

- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `pytest -q` passes
- [ ] Determinism preserved (no new numeric literals in engine code; constants stay in config)
- [ ] If structure changed: the spec and `docs/diagrams/` were updated **together** with the code

## Notes for the reviewer

<!-- Anything that needs a closer look: a flagged scenario, a trade-off, a follow-up. -->
