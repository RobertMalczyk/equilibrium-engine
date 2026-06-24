"""PersonaRuntime.init (M1).

In: PersonaConfig + initial overrides (from a Scenario). Out: a fresh PersonaRuntime
with mode=IDLE, empty log, zero cooldowns, overrides applied and clamped. Processes NO
events -- only seeds mutable state.
"""

from __future__ import annotations

import dataclasses

from engine.clamp import clamp01
from engine.schema import (
    MORAL_RELATION_DIMS,
    RELATION_DIMS,
    Mode,
    MoralLedger,
    PersonaConfig,
    PersonaRuntime,
    Secret,
)

_SECRET_FIELDS = {f.name for f in dataclasses.fields(Secret)}


def init_runtime(
    config: PersonaConfig, overrides: dict | None = None
) -> PersonaRuntime:
    overrides = overrides or {}

    # Copy the loader's initial map verbatim (it already conditionally OMITS opt-in moral states when the
    # moral overlay is absent) -- do NOT re-iterate GLOBAL_STATES, which would re-inject moral keys at 0.0
    # into every legacy runtime and diverge the goldens. Canonical order is preserved (the loader built it
    # in GLOBAL_STATES order).
    global_state = dict(config.initial_global_state)
    for name, val in dict(overrides.get("global_state", {})).items():
        if name in global_state:
            global_state[name] = clamp01(float(val))

    relations: dict[str, dict[str, float]] = {
        src: dict(dims) for src, dims in config.initial_relations.items()
    }
    for src, dims in dict(overrides.get("relations", {})).items():
        # OPT-IN moral dim (suspicion) seeds a new row ONLY when moral is enabled (its half_life -> decay key);
        # otherwise omitted so a legacy override row carries exactly the canonical dims (byte-identical).
        row = relations.setdefault(
            str(src),
            {
                d: 0.0
                for d in RELATION_DIMS
                if d not in MORAL_RELATION_DIMS or d in config.decay
            },
        )
        for d, val in dict(dims).items():
            if d in RELATION_DIMS and (
                d not in MORAL_RELATION_DIMS or d in config.decay
            ):
                row[d] = clamp01(float(val))

    # M-J.4.3: seed authored Secrets into the ledger (scenario `secrets:` overrides). Empty for legacy ->
    # ledger stays empty -> byte-identical. Unknown keys are ignored (forward-compatible authoring).
    ledger = MoralLedger()
    for sd in list(overrides.get("secrets", [])):
        d = {k: v for k, v in dict(sd).items() if k in _SECRET_FIELDS}
        ledger.secrets[str(d["id"])] = Secret(**d)

    return PersonaRuntime(
        config=config,
        global_state=global_state,
        relations=relations,
        mode=Mode.IDLE,
        active_action=None,
        busy_target=None,
        history_log=[],
        cooldowns={},
        moral_ledger=ledger,
    )
