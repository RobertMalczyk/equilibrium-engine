# Block diagrams — index

Maintained schematics (spec §12): each dynamics/wiring subsystem keeps a versioned diagram, **before**
implementation and in sync with the code. Start with **`wiring.md`** for the whole "what is connected to
what" map; the per-subsystem files zoom in.

| Diagram | Subsystem | Class |
|---|---|---|
| **[wiring.md](wiring.md)** | **whole-system topology** (channels→states→derived→potentials→actions) | wiring map |
| [mapper.md](mapper.md) | M3 mapper (event → channels) | routing (combinational) |
| [relation_filter.md](relation_filter.md) | M4 filter pipeline (relation + affinity) | signal (combinational) |
| [affinity_filter.md](affinity_filter.md) | M4b affinity stage | → points to relation_filter.md |
| [derived.md](derived.md) | M5 derived read-outs (biases, urges) | combinational |
| [update.md](update.md) | M6 integrator core (decay+drift+gain+coupling) | **dynamics** (integrators) |
| [potentials.md](potentials.md) | M7 reactive potentials (term registry) | combinational |
| [action_selector.md](action_selector.md) | M8 shared selector + arbitration | **dynamics** (mode FF) |
| [simulation.md](simulation.md) | M9 tick orchestrator (freeze + write-back) | **dynamics** (the loop) |
| [orchestrator.md](orchestrator.md) | multi-agent cross-agent router (eval/orchestrator.py; stage-2 slice) | multi-agent flow |
| [sleep.md](sleep.md) | night & sleep — fast-state reset / slow-cause persistence (M7.5 Part B) | **dynamics** (mode + reset) |
| [history.md](history.md) | M2 history features | combinational |
| [calibration.md](calibration.md) | M4 harness optimizer loop (offline) | optimization-flow |

**No block diagram (pure functions / utilities — I/O contracts in their docstrings instead):**
`schema`, `yaml_io`, `clamp`, `debug`, `metrics`, `expectations`, `loss`, `stability`, `diagnostics`.

Rule: a structural change updates the relevant diagram **together with** the code (and the spec first).
A diagram drawn only in chat does not exist; if there is no file here, the subsystem has no diagram.
