# Contributing

Thanks for your interest in the Equilibrium Engine — a deterministic, debuggable engine for NPC
character tensions, modelled like a control system (visible behaviour *emerges* from the dynamics of
internal states, not from scripts).

Contributions are welcome. To keep `main` stable and reviewable, **all changes land through pull
requests** — direct pushes to `main` are disabled, and a maintainer merges after CI passes.

## Workflow

1. **Fork** the repository and create a branch from `main`:
   `git checkout -b my-change`
2. **Make your change.** Match the surrounding style; keep commits focused.
3. **Run the checks locally** (see below) — CI runs the same ones and a PR cannot merge until they pass.
4. **Open a pull request** against `main`. Describe *what* changed and *why*; link any related issue.
5. A maintainer reviews and merges. Only maintainers can merge to `main`.

## Local checks (must pass)

```bash
pip install -e .            # installs ruff + pytest
ruff check .                # lint
ruff format --check .       # formatting
pytest -q                   # test suite
```

`ruff format .` auto-fixes formatting. The test suite must stay green.

## Project conventions

- **Spec first.** Structural decisions (states, channels, equations, couplings) are described before
  they are coded. If a change alters the model's structure, update the spec/diagram together with the
  code — a diagram detached from the code is worse than none. See `docs/`.
- **Topology now, constants from calibration.** Decide *what connects to what* deliberately; do not
  hand-pick gains/thresholds/half-lives — those come out of calibration as config parameters.
- **No numeric literals in engine code** — everything comes from config; defaults are neutral.
- **Determinism is a pillar.** Changes must preserve bit-for-bit determinism; prefer property and
  persona-contrast tests over hard-coded numbers.
- **Less is more.** The MVP contains only what does something; name and defer the rest.

## Reporting issues

Use GitHub Issues for bugs, questions, and proposals. For behavioural claims, a small reproducing
scenario (an `eval/scenarios` YAML or a short script) helps a lot.

## License

By contributing you agree your contributions are licensed under the repository's
[Apache-2.0 License](LICENSE).
