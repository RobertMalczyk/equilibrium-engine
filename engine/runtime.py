"""PersonaRuntime.init (M1).

In: PersonaConfig + initial overrides (from a Scenario). Out: a fresh PersonaRuntime
with mode=IDLE, empty log, zero cooldowns, overrides applied and clamped. Processes NO
events -- only seeds mutable state.
"""

from __future__ import annotations

from engine.clamp import clamp01
from engine.schema import (
    GLOBAL_STATES,
    RELATION_DIMS,
    Mode,
    PersonaConfig,
    PersonaRuntime,
)


def init_runtime(
    config: PersonaConfig, overrides: dict | None = None
) -> PersonaRuntime:
    overrides = overrides or {}

    global_state = {
        name: config.initial_global_state.get(name, 0.0) for name in GLOBAL_STATES
    }
    for name, val in dict(overrides.get("global_state", {})).items():
        if name in global_state:
            global_state[name] = clamp01(float(val))

    relations: dict[str, dict[str, float]] = {
        src: dict(dims) for src, dims in config.initial_relations.items()
    }
    for src, dims in dict(overrides.get("relations", {})).items():
        row = relations.setdefault(str(src), {d: 0.0 for d in RELATION_DIMS})
        for d, val in dict(dims).items():
            if d in RELATION_DIMS:
                row[d] = clamp01(float(val))

    return PersonaRuntime(
        config=config,
        global_state=global_state,
        relations=relations,
        mode=Mode.IDLE,
        active_action=None,
        busy_target=None,
        history_log=[],
        cooldowns={},
    )
