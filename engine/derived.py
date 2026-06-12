"""derived.compute (M5).

In: GlobalState + Relations + Traits (from one snapshot). Out: DerivedSnapshot (incl.
urge_boredom, urge_fatigue). Pure; NOT state. Called twice per tick: ``pre`` (how the
character interprets a stimulus) and ``post`` (what it is now inclined to do). All forms
are linear-with-clamp; weights come from config (neutral default 0). The saturation
option for effective_self_control is intentionally deferred (spec section 4 / MVP).

affective_bias and negative_bias are computed explicitly per source from relations[src].
"""

from __future__ import annotations

from engine.clamp import clamp01, clamp_signed
from engine.schema import (
    DerivedSnapshot,
    GlobalStateMap,
    PersonaConfig,
    Relations,
)


def compute(
    global_state: GlobalStateMap, relations: Relations, config: PersonaConfig
) -> DerivedSnapshot:
    g = global_state
    dw = config.derived_weights

    w_esc = dw.get("effective_self_control", {})
    effective_self_control = clamp01(
        g["self_control"]
        - w_esc.get("fatigue", 0.0) * g["fatigue"]
        - w_esc.get("stress", 0.0) * g["stress"]
    )

    w_irr = dw.get("irritability", {})
    irritability = clamp01(
        w_irr.get("stress", 0.0) * g["stress"]
        + w_irr.get("frustration", 0.0) * g["frustration"]
        + w_irr.get("hunger", 0.0) * g["hunger"]
    )

    w_dis = dw.get("dissatisfaction", {})
    dissatisfaction = clamp01(
        w_dis.get("frustration", 0.0) * g["frustration"]
        - w_dis.get("satisfaction", 0.0) * g["satisfaction"]
    )

    # Proactive boredom urge reads the boredom STATE directly (drive = state in its second
    # role, spec section 4/8) -- NOT via frustration, so an idle character seeks stimulus
    # rather than complaining at thin air. fatigue brakes it. Topology (which states feed the
    # urge) is fixed here; the weights are config placeholders owned by calibration (section 9).
    # novelty_seeking modulates the boredom term -> per-persona TEMPO (D5): a novelty-seeker acts
    # on boredom sooner, a stoic later/never. nov_factor = 1 + k*(novelty - ref), default identity.
    w_urb = dw.get("urge_boredom", {})
    nov = config.traits.get("novelty_seeking", 0.5)
    nov_factor = max(
        0.0,
        1.0
        + w_urb.get("boredom_novelty_k", 0.0)
        * (nov - w_urb.get("boredom_novelty_ref", 0.5)),
    )
    # Relief-seeking (spec section 4 / section 8 burst, Loop 2's return edge): the urge ALSO reads
    # `stress` with a small positive weight -- a stressed character looks for something to take its
    # mind off. Weight 0 (the neutral default) = today's behaviour; the loop this closes runs THROUGH
    # the world (rich world: engaged relief, negative feedback; barren world: fruitless looking winds up).
    urge_boredom = clamp01(
        w_urb.get("boredom", 0.0) * g["boredom"] * nov_factor
        + w_urb.get("stress", 0.0) * g["stress"]
        - w_urb.get("fatigue", 0.0) * g["fatigue"]
    )

    w_urf = dw.get("urge_fatigue", {})
    urge_fatigue = clamp01(w_urf.get("fatigue", 1.0) * g["fatigue"])

    # Proactive AUTHORITY urge -- the exact mirror of urge_boredom: reads the `duty` STATE in its second
    # role (drive = state in its second role, spec §4/§8), with need_for_control as the per-persona TEMPO
    # modulator (nfc_factor = 1 + k*(need_for_control - ref), default identity -- the novelty_seeking->boredom
    # precedent, D5). duty is 0 for non-authority personas (drift 0), so urge_command is 0 -> command_other
    # never fires for them. Topology fixed here; weights are config placeholders owned by calibration.
    w_urc = dw.get("urge_command", {})
    nfc = config.traits.get("need_for_control", 0.5)
    nfc_factor = max(
        0.0,
        1.0
        + w_urc.get("command_nfc_k", 0.0) * (nfc - w_urc.get("command_nfc_ref", 0.5)),
    )
    urge_command = clamp01(w_urc.get("duty", 0.0) * g["duty"] * nfc_factor)

    # Night/sleep (M7.5 Part B). arousal is a BLOCKER (a wound-up character is slow to drop off); sleep_urge
    # reads the sleep_pressure STATE in its second role (drive = state in 2nd role, §8), + fatigue, − arousal,
    # so high stress/anger DELAY onset (not prevent it -- sleep_pressure/fatigue eventually dominate). States
    # only (no trait). Sparse: sleep_pressure is 0 unless the world sent `nightfall`, so sleep_urge <= 0 -> the
    # sleep drive stays dormant in ordinary (single-day) runs.
    w_ar = dw.get("arousal", {})
    arousal = clamp01(
        w_ar.get("stress", 0.0) * g["stress"]
        + w_ar.get("anger", 0.0) * g["anger"]
        + w_ar.get("frustration", 0.0) * g["frustration"]
    )
    w_su = dw.get("sleep_urge", {})
    sleep_urge = clamp01(
        w_su.get("sleep_pressure", 0.0) * g["sleep_pressure"]
        + w_su.get("fatigue", 0.0) * g["fatigue"]
        - arousal
    )

    # Per-source relational biases (explicit, spec section 7).
    w_ab = dw.get("affective_bias", {})
    affective_bias: dict[str, float] = {}
    negative_bias: dict[str, float] = {}
    for src in sorted(relations):
        rel = relations[src]
        bias = clamp_signed(
            w_ab.get("trust", 0.0) * rel.get("trust", 0.0)
            + w_ab.get("respect", 0.0) * rel.get("respect", 0.0)
            - w_ab.get("resentment", 0.0) * rel.get("resentment", 0.0)
        )
        affective_bias[src] = bias
        negative_bias[src] = clamp01(-bias)

    return DerivedSnapshot(
        affective_bias=affective_bias,
        negative_bias=negative_bias,
        irritability=irritability,
        effective_self_control=effective_self_control,
        dissatisfaction=dissatisfaction,
        urge_boredom=urge_boredom,
        urge_fatigue=urge_fatigue,
        urge_command=urge_command,
        arousal=arousal,
        sleep_urge=sleep_urge,
    )
