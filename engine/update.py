"""update.compute (M6) -- the ONLY place state equations live.

In: snapshot + EffectiveInputVector + derived_pre + config + active_action. Out: StateDelta
(raw additive deltas; clamping belongs to commit, spec section 7 step 5). Every state is
the same generic integrator (spec section 14):

    new_raw = decay*old + (1-decay)*setpoint + drift
              + Sum gain[state][ch]*mod[state][ch]*eff[ch].value   (channels; mod = trait modulator, default 1)
              + Sum coupling[state][y]*snapshot.global[y]   (sparse state->state, spec section 8)
              + BUSY per-tick effects (relief / cost / reward) when active
              + idle_factor*idle_recovery[state] when IDLE & unprovoked (ambient homeostasis, D11;
                `recovering` flag; idle_factor = clamp01(1+k*(reactivity-ref)) -- reactive personas settle
                slower; never recovers below idle_recovery_floor[state]*resentment_max -- a standing grievance)

Reads the FROZEN snapshot only (synchronous). Selects no action, filters nothing, commits
nothing. self_control's setpoint is wired to the trait ``base_self_control`` (a wiring, not
a literal). Sums iterate sorted keys so equation order never changes the float result.
"""

from __future__ import annotations

from engine.clamp import clamp01
from engine.schema import (
    GLOBAL_STATES,
    RELATION_DIMS,
    EffectiveInputVector,
    Mode,
    PersonaConfig,
    Snapshot,
    StateDelta,
)


def _setpoint(config: PersonaConfig, state: str) -> float:
    if state == "self_control":
        return config.traits["base_self_control"]  # homeostat rests at base (wiring)
    return config.setpoints.get(state, 0.0)


_ACTIVITY_KINDS = frozenset(
    {"self_activity", "external"}
)  # M7 Step 2: world-confirmed activities


def _active_effect(
    config: PersonaConfig, active_action: str | None, state: str, engaged_novelty: float
) -> float:
    """Per-tick effect of the active action (M7 Step 2): applies in BUSY (engaged activity: relief) AND
    SEEKING (seek_stimulus: the frustration cost of looking). A confirmed activity's BOREDOM relief scales
    with the confirmed novelty (how stimulating it is)."""
    if active_action is None:
        return 0.0
    per_tick = config.action_params.get(active_action, {}).get("per_tick", {})
    val = float(per_tick.get(state, 0.0))
    if state == "boredom" and active_action in _ACTIVITY_KINDS:
        val *= engaged_novelty
    return val


def compute(
    snapshot: Snapshot,
    eff: EffectiveInputVector,
    config: PersonaConfig,
    active_action: str | None,
    engaged_novelty: float = 1.0,
    recovering: bool = False,
    burst_latched: bool = False,
) -> StateDelta:
    g = snapshot.global_state
    decay = config.decay
    drifts = config.drifts
    gains = config.gains
    gain_modulators = config.gain_modulators
    couplings = config.couplings
    # spec section 8 burst / section 14: a coupling edge MAY escalate with its own input's level,
    # g_eff = g*(1 + k_esc*y). Sparse; absent = 0 = the linear edge (bit-identical by construction).
    escalation = config.coupling_escalation
    # spec section 8 burst: while the latch is SET, an extinction term relaxes the loop states toward 0
    # (the self-extinguishing episode). Empty/unlatched = no term.
    extinction = config.burst_extinction if burst_latched else {}
    # per-tick effects apply while the persona is "active": BUSY (engaged activity), SEEKING (looking), or
    # SLEEP (M7.5 Part B -- the sleep reset is the `sleep` action's per_tick: fast states decay, fatigue/
    # sleep_pressure discharge, self_control recovers; the SLOW relations are absent so the grudge persists).
    active = snapshot.mode in (Mode.BUSY, Mode.SEEKING, Mode.SLEEP)
    # ambient idle homeostasis (D11): extra recovery toward calm when IDLE and unprovoked (the persona
    # settles when nothing is happening). simulation computes `recovering`; absent state => 0 (neutral).
    # The whole block is scaled by an optional trait modulator (factor in [0,1]): a high-reactivity persona
    # settles SLOWER, retaining its edge; calm personas recover at the full base rate (D11 round-2 fix).
    idle_recovery = config.idle_recovery
    irm = config.idle_recovery_modulator
    idle_factor = 1.0
    resentment_max = 0.0
    if recovering and irm:
        idle_factor = clamp01(
            1.0 + irm["k"] * (config.traits[irm["trait"]] - irm["ref"])
        )
    if recovering and config.idle_recovery_floor:
        # standing grievance floor: recovery stops at weight*resentment_max (a resentful persona idles wary).
        resentment_max = max(
            (dims.get("resentment", 0.0) for dims in snapshot.relations.values()),
            default=0.0,
        )

    delta_global: dict[str, float] = {}
    for x in GLOBAL_STATES:
        old = g[x]
        new = (
            decay[x] * old
            + (1.0 - decay[x]) * _setpoint(config, x)
            + drifts.get(x, 0.0)
        )

        gx = gains.get(x, {})
        gmx = gain_modulators.get(x, {})
        for ch in sorted(gx):
            sis = eff.get(ch)
            if sis:
                m = gmx.get(ch)
                # mod = 1 + k*(trait - ref), clamped >=0 (a gain can't flip sign); absent edge = identity.
                mod = (
                    max(0.0, 1.0 + m["k"] * (config.traits[m["trait"]] - m["ref"]))
                    if m
                    else 1.0
                )
                # M-MEM: a channel may carry MULTIPLE inputs in one tick (several sources firing the same
                # channel) -- sum their deposits (event order, deterministic). A single input reduces to the
                # exact prior product, so a <=1-event tick is byte-identical.
                for si in sis:
                    new += gx[ch] * mod * si.value

        cx = couplings.get(x, {})
        ex = escalation.get(x, {})
        for y in sorted(cx):
            # escalated edge: g*(1 + k_esc*y)*y -- local gain grows with the operating point (burst);
            # k_esc absent/0 reduces to the exact linear product (the frozen calibration).
            new += (
                cx[y] * (1.0 + ex.get(y, 0.0) * g[y]) * g[y]
            )  # snapshot (synchronous)

        if x in extinction:
            # burst extinction (latch SET): relax toward 0 at the configured rate -- the trajectory
            # comes off the ceiling and keeps descending (spike, plateau, slow cool).
            new += extinction[x] * (0.0 - g[x])

        if active:
            new += _active_effect(config, active_action, x, engaged_novelty)
        elif recovering:
            rec = idle_factor * idle_recovery.get(
                x, 0.0
            )  # IDLE & unprovoked: settle toward calm
            floor = config.idle_recovery_floor.get(x, 0.0) * resentment_max
            if (
                rec < 0.0 and floor > 0.0
            ):  # don't recover BELOW a standing-grievance floor
                new = new if new <= floor else max(new + rec, floor)
            else:
                new += rec

        delta_global[x] = new - old  # raw; commit clamps

    # Relational states: memory (slow decay toward setpoint) + relational channel deposits.
    # Booking CREATES the row for a previously-unknown source (spec section 5): a stranger's first
    # insult starts a real grudge -- iterate the union of seeded rows and this tick's relational
    # sources (sorted: deterministic). A fresh source's row starts at the neutral 0-vector.
    rel_gains = gains.get("relations", {})
    event_sources = {
        si.source for sis in eff.values() for si in sis if si.source is not None
    }
    delta_relations: dict[str, dict[str, float]] = {}
    for src in sorted(set(snapshot.relations) | event_sources):
        row = snapshot.relations.get(src, {})
        out_row: dict[str, float] = {}
        for dim in RELATION_DIMS:
            old = row.get(dim, 0.0)
            new = decay[dim] * old + (1.0 - decay[dim]) * config.setpoints.get(dim, 0.0)
            dim_gains = rel_gains.get(dim, {})
            for ch in sorted(dim_gains):
                # M-MEM: sum every input on this channel whose source is `src` (multi-source same tick).
                for si in eff.get(ch, ()):
                    if si.source == src:
                        new += dim_gains[ch] * si.value
            d = new - old
            if d != 0.0:
                out_row[dim] = d
        if out_row:
            delta_relations[src] = out_row

    return StateDelta(global_=delta_global, relations=delta_relations)
