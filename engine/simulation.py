"""simulation.run_scenario (M9) -- the ONLY runtime mutator.

In: PersonaConfig + Scenario. Out: (PersonaRuntime, DebugTrace). Runs the canonical tick
loop (spec section 7): freeze -> derived_pre -> [history/mapper/filters] -> update ->
commit+clamp -> derived_post -> potentials -> selector -> commit post_effects -> mode/
cooldown bookkeeping -> log -> debug.emit. Equations live in update; mode transitions are
derived here from (prev_mode, kind, interrupted).
"""

from __future__ import annotations

from dataclasses import replace

from engine import (
    action_selector,
    affinity_filter,
    derived,
    history,
    mapper,
    potentials,
    relation_filter,
    update,
)
from engine.clamp import clamp01
from engine.debug import DebugTrace, TickTrace
from engine.runtime import init_runtime
from engine.schema import (
    ActionKind,
    ActionSelection,
    Mode,
    PersonaConfig,
    PersonaRuntime,
    RawEvent,
    Scenario,
    StateDelta,
)


def _commit(runtime: PersonaRuntime, delta: StateDelta) -> None:
    for x, d in delta.global_.items():
        runtime.global_state[x] = clamp01(runtime.global_state[x] + d)
    for src, dims in delta.relations.items():
        row = runtime.relations.setdefault(src, {})
        for dim, d in dims.items():
            row[dim] = clamp01(row.get(dim, 0.0) + d)


def _event_is_provocation(event, eff: dict, snapshot, config: PersonaConfig) -> bool:
    """D11: an event PROVOKES (opens the reactive gate) iff the persona perceives it negatively. Two cases:
    (1) it directly adds anger or frustration -- an insult, an order, a DISLIKED dish (the eff inputs feed
        anger/frustration with a net positive contribution); OR
    (2) it is a gesture from a RESENTED source -- a kindness/meal from someone the persona blames still
        galls (resentment[source] >= theta_provocation). This is the relational valence the blind judge
        found for Cichy (a jailer's soup provokes) while Marta's soup to a non-resentful persona does not.
    A benign gesture (liked food / help) from a non-resented source is NOT a provocation -> no reply fires.

    A provocation needs a SOURCE -- someone to react TO. A sourceless world stressor (`weather`/`night`)
    raises the baseline (it wears at the temper, so a later real provocation lands harder) but per spec §5
    "opens no reactive reply": rain must NOT hold the reactive gate open and make the persona snap at nothing
    all day. So the gate keys on sourced events only; weather still feeds frustration/stress via `update`.
    """
    if event is None:
        return False
    src = event.source
    if src is None:  # sourceless world stressor (weather/night): baseline only
        return False
    contrib = 0.0
    for state in ("anger", "frustration"):
        gx = config.gains.get(state, {})
        for ch, si in eff.items():
            contrib += gx.get(ch, 0.0) * si.value
    if contrib > 0.0:  # raised anger/frustration from a SOURCE -> a direct provocation
        return True
    theta = config.thresholds.get(
        "provocation_resentment", float("inf")
    )  # (2) a gesture from a resented source still galls
    if snapshot.relations.get(src, {}).get("resentment", 0.0) >= theta:
        return True
    return False


def _event_is_stressor(event, eff: dict, config: PersonaConfig) -> bool:
    """A SOURCELESS world stressor (weather/etc.) that wears at the baseline (raises stress/frustration/anger).
    It opens NO reactive reply (it is not a provocation -- there is nobody to react to), but while it is
    active the persona is NOT idly recovering: you do not relax toward calm while cold and wet. So it gates
    `idle_recovery` (via a stressor window), letting rain wear a persona down so a LATER real provocation
    lands harder (spec §5: weather wears the temper). Sourced events go through the provocation path instead."""
    if event is None or event.source is not None:
        return False
    contrib = 0.0
    for state in ("anger", "frustration", "stress"):
        gx = config.gains.get(state, {})
        for ch, si in eff.items():
            contrib += gx.get(ch, 0.0) * si.value
    return contrib > 0.0


def _kindness_pressure(event, eff: dict, snapshot, config: PersonaConfig) -> float:
    """Theme A: the MIRROR of _event_is_provocation. A pro-social GESTURE (a `gesture_channels` channel is
    present in the filtered inputs -- food/help), appraised NON-negative (does not net anger/frustration --
    the same `contrib` the provocation check computes, here <= 0) from a NON-resented source, emits this
    tick's appraised kindness magnitude (config placeholder); 0 otherwise. It drives positive_response and,
    as a SIGNED edge, inhibits venting (spec section 8). Keeps Cichy intact BY CONSTRUCTION: a gesture from a
    RESENTED source is not kindness here -- it is a provocation (rule 2 above)."""
    if event is None:
        return 0.0
    gesture_channels = config.appraisal.get("gesture_channels", ())
    if not any(
        ch in eff for ch in gesture_channels
    ):  # not a pro-social gesture -> no kindness
        return 0.0
    contrib = 0.0
    for state in ("anger", "frustration"):
        gx = config.gains.get(state, {})
        for ch, si in eff.items():
            contrib += gx.get(ch, 0.0) * si.value
    if contrib > 0.0:  # a disliked dish / net-hostile gesture is NOT kindness
        return 0.0
    src = event.source
    if src is not None:
        theta = config.thresholds.get("provocation_resentment", float("inf"))
        if snapshot.relations.get(src, {}).get("resentment", 0.0) >= theta:
            return 0.0  # a gesture from a resented source galls (provocation)
    return float(config.appraisal.get("kindness_pressure", 0.0))


def _bystander_pressure(
    event, runtime, t: int, window: float, config: PersonaConfig
) -> float:
    """Target policy: a respect-based brake on venting at a source while you carry anger that source did NOT
    cause. It fires when this tick's event comes from a source S that is NOT the one who caused the lingering
    anger (`runtime.last_provocation_source`), while that residual anger is still inside the reactive window.
    Whether S's own act is itself a mild provocation (e.g. a routine command) is IRRELEVANT -- the part of the
    reaction being displaced onto S is what we damp (via `bystander_x_respect_src`, scaled by respect[S], so a
    respected commander is spared, a stranger less so). The `halgrim_068` flag: cold contempt at respected
    Edda's command while the anger is really Wojsław's. 0 otherwise -- the provoker themselves, the first
    provocation, or no residual anger -> bit-identical (the single-source litmus is untouched; the change only
    bites when a SECOND source interacts while anger from a FIRST still lingers)."""
    if event is None or event.source is None:
        return 0.0
    prov_src = runtime.last_provocation_source
    if (
        prov_src is None or event.source == prov_src
    ):  # no one to be displaced from / S IS the provoker
        return 0.0
    lp = runtime.last_provocation_t
    if (
        lp is None or (t - lp) > window
    ):  # no residual anger lingering -> nothing to displace
        return 0.0
    return float(config.appraisal.get("bystander_pressure", 0.0))


def _cooldown_ticks(config: PersonaConfig, action: str | None) -> int:
    if action is None:
        return 0
    return int(config.action_params.get(action, {}).get("cooldown", 0))


def _apply_transition(runtime: PersonaRuntime, prev_mode: Mode, sel, t: int) -> None:
    """Map (prev_mode, kind, interrupted) to mode/active_action/cooldown (spec section 7).
    M7 Step 2: a proactive START enters SEEKING (intent), not BUSY directly -- the engine engages only on
    the world's `activity` confirmation (handled in tick); a provocation interrupts the search."""
    if prev_mode == Mode.IDLE and sel.kind == ActionKind.PROACTIVE:
        params = runtime.config.action_params.get(sel.action, {})
        # An INSTANTANEOUS drive (command_other, the authority verb) fires ONCE -- its post_effects are
        # already booked (step 9) -- and goes straight to COOLDOWN; the cooldown rate-limits issuance. It is
        # not a dwell (no BUSY) and not a search (no SEEKING). active_action clears (nothing ongoing).
        if params.get("instantaneous", False):
            cd = _cooldown_ticks(runtime.config, sel.action)
            runtime.cooldowns["mode"] = cd
            runtime.active_action = None
            runtime.mode = Mode.COOLDOWN if cd > 0 else Mode.IDLE
            return
        # M7.5 Part B: a `sleep` drive enters the SLEEP mode (the night reset), not BUSY -- sleep changes the
        # rules of reactivity (only a strong stimulus wakes; handled in the selector's SLEEP branch).
        if params.get("sleep", False):
            runtime.mode = Mode.SLEEP
            runtime.active_action = sel.action
            return
        # A "seeking" drive (seek_stimulus) needs the world to confirm an activity -> SEEKING. Other drives
        # (rest) are self-supplied -> straight to BUSY, as before.
        if params.get("seeking", False):
            runtime.mode = Mode.SEEKING
            runtime.active_action = sel.action  # seek_stimulus (the looking)
            runtime.seeking_since = t
        else:
            runtime.mode = Mode.BUSY
            runtime.active_action = sel.action  # e.g. rest (self-supplied)
        return
    if prev_mode == Mode.SEEKING:
        if sel.kind == ActionKind.REACTIVE:  # a provocation interrupts the search
            runtime.mode = Mode.IDLE
            runtime.active_action = None
            runtime.seeking_since = None
        return  # CONTINUE: stay SEEKING (engage/timeout handled in tick)
    if prev_mode == Mode.SLEEP:
        # M7.5 Part B: WAKE -> COOLDOWN, whether rested (PROACTIVE end) or shaken awake (REACTIVE interrupt).
        if sel.kind == ActionKind.PROACTIVE or (
            sel.kind == ActionKind.REACTIVE and sel.interrupted
        ):
            runtime.cooldowns["mode"] = _cooldown_ticks(
                runtime.config, runtime.active_action
            )
            runtime.active_action = None
            runtime.mode = Mode.COOLDOWN
        return  # CONTINUE: stay asleep
    if prev_mode == Mode.BUSY:
        if sel.kind == ActionKind.PROACTIVE:  # END
            runtime.cooldowns["mode"] = _cooldown_ticks(
                runtime.config, runtime.active_action
            )
            runtime.active_action = None
            runtime.mode = Mode.COOLDOWN
            return
        if sel.kind == ActionKind.REACTIVE and sel.interrupted:  # INTERRUPT
            runtime.cooldowns["mode"] = _cooldown_ticks(
                runtime.config, runtime.active_action
            )
            runtime.active_action = None
            runtime.mode = Mode.COOLDOWN
            return
        # reactive-in-passing or continue: stay BUSY
        return
    # IDLE+reactive / COOLDOWN+anything / IDLE+idle: no mode change here.


def tick(runtime: PersonaRuntime, t: int, event: RawEvent | None) -> TickTrace:
    config = runtime.config

    # 1. freeze
    snapshot = runtime.freeze()
    prev_mode = snapshot.mode

    # 2. derived_pre
    derived_pre = derived.compute(snapshot.global_state, snapshot.relations, config)

    # 3. perception (only if an event fires this tick)
    eff: dict = {}
    command_pressure = (
        0.0  # transient: this tick's command channel (raw, pre-filter); 0 if no order
    )
    event_source = event.source if event is not None else None
    if event is not None:
        feats = history.analyze(runtime.history_log, event, t, config)
        raw = mapper.map_event(event, config, feats)
        command_pressure = raw["command"].value if "command" in raw else 0.0
        ctx = event.context
        eff = affinity_filter.apply(
            relation_filter.apply(raw, snapshot.relations, derived_pre, config, ctx),
            config.affinities,
            config,
            ctx,
        )

    # Recency / PROVOCATION gate (D5 step 1c + D11): a reactive REPLY needs a recent PROVOCATION -- not just
    # any recent event. A benign gesture (liked food / help from a non-resented source) is not a provocation,
    # so a calm-but-recently-fed persona does not "snap at a meal" (the D11 finding). Computed here (before
    # update) so it ALSO gates idle recovery. The provoking-event tick is tracked on the runtime.
    window = config.thresholds.get("reactive_window_ticks", float("inf"))
    is_provocation = _event_is_provocation(event, eff, snapshot, config)
    # Theme A: the appraised kindness of THIS tick's event (mirror of is_provocation). Transient, like
    # command_pressure: 0 unless a non-resented pro-social gesture. Drives positive_response + inhibits venting.
    kindness_pressure = _kindness_pressure(event, eff, snapshot, config)
    # Target policy: is this tick's source a respected BYSTANDER catching displaced anger? (uses last_provocation_source)
    bystander_pressure = _bystander_pressure(event, runtime, t, window, config)
    lp = runtime.last_provocation_t
    # A kindness is itself a valid trigger for a reactive REPLY (positive_response) -- it opens the gate even
    # with no recent provocation. On a kindness tick the hostile potentials are inhibited (the signed edge), so
    # opening the gate yields warmth, not a snap. (No gesture/resented source -> kindness_pressure 0 -> the gate
    # is governed by provocation exactly as before -> bit-identical.)
    # Burst gate extension (spec section 8 burst): while the latch is SET and anger has cleared the
    # displacement bar, ANY SOURCED event this tick is an admissible discharge trigger -- the gate opens
    # for it even though it provokes nothing (a kind gesture included; "kicking the dog"). A sourceless
    # event (weather) still never opens it: you cannot kick the rain. Reads the FROZEN snapshot (the
    # synchronous discipline) and the latch state carried over from the previous tick's end.
    theta_displace = config.thresholds.get("theta_displace", float("inf"))
    displaced_gate = (
        runtime.burst_latched
        and event_source is not None
        and snapshot.global_state["anger"] >= theta_displace
    )
    reactive_allowed = (
        is_provocation
        or kindness_pressure > 0.0
        or (lp is not None and (t - lp) <= window)
        or displaced_gate
    )
    # A sourceless world stressor (rain) opens no reply, but it WEARS the persona down -- so while it is active
    # he is not idly recovering (spec §5: weather wears the temper, so a later provocation lands harder).
    is_stressor = _event_is_stressor(event, eff, config)
    ls = runtime.last_stressor_t
    stressor_active = is_stressor or (ls is not None and (t - ls) <= window)
    # ambient idle homeostasis (D11): the character settles toward calm only when IDLE, unprovoked AND not
    # under an active environmental stressor (else idle_recovery would cancel the rain wearing him down).
    recovering = prev_mode == Mode.IDLE and not reactive_allowed and not stressor_active

    # 4. update (synchronous, raw deltas). engaged_novelty scales a confirmed activity's boredom relief.
    delta = update.compute(
        snapshot,
        eff,
        config,
        runtime.active_action,
        runtime.engaged_novelty,
        recovering=recovering,
        burst_latched=runtime.burst_latched,
    )

    # 5. commit + clamp -> state'
    _commit(runtime, delta)
    state_after_commit = runtime.freeze()

    # 6. derived_post
    derived_post = derived.compute(runtime.global_state, runtime.relations, config)

    # 7. potentials + urges (command_pressure + event_source feed the obedience potentials; spec §7)
    pots = potentials.compute(
        runtime.global_state,
        runtime.relations,
        config,
        derived_post,
        command_pressure,
        event_source,
        kindness_pressure,
        bystander_pressure,
    )
    urges = {
        "boredom": derived_post.urge_boredom,
        "fatigue": derived_post.urge_fatigue,
        "command": derived_post.urge_command,
        "sleep": derived_post.sleep_urge,
    }

    # 8. selector (shared path + arbitration). The reaction is aimed at the provoking
    # source (this tick's event source, if any) -- used to book relational post_effects.
    # reactive_allowed (recent-provocation gate) was computed before update (step 4) and is reused here.
    reaction_target = event.source if event is not None else None

    if prev_mode == Mode.SEEKING and event is not None and event.type == "activity":
        # M7 Step 2 ENGAGE: the world confirmed an activity -> start it (overrides normal selection).
        kind = str(event.context.get("kind", "self_activity"))
        runtime.engaged_novelty = float(event.context.get("novelty", 1.0))
        sel = ActionSelection(
            action=kind,
            score=0.0,
            kind=ActionKind.PROACTIVE,
            interrupted=False,
            post_effects=StateDelta(),
            explanation=f"ENGAGE '{kind}' (world confirmed, novelty={runtime.engaged_novelty:.2f}) -> BUSY",
        )
        runtime.mode = Mode.BUSY
        runtime.active_action = kind
        runtime.seeking_since = None
    else:
        sel = action_selector.select(
            pots,
            urges,
            runtime.global_state,
            config,
            prev_mode,
            runtime.active_action,
            reaction_target,
            reactive_allowed=reactive_allowed,
        )
        # Displaced discharge (spec section 8 burst): a reactive reply landing on someone who is NOT
        # the provocation's source, while the latch is SET and anger is over the displacement bar,
        # books its relational cost TRANSIENTLY (discounted by config, default 0 = fully transient) --
        # a flash of "snapped at her", never a durable grudge on the innocent (the fabricated-nemesis
        # runaway is excluded by construction). The expression seam reads the tag to frame it AS
        # displacement. Unlatched (the shipped default) -> this branch never runs -> bit-identical.
        if (
            displaced_gate
            and sel.kind == ActionKind.REACTIVE
            and reaction_target is not None
            and reaction_target != runtime.last_provocation_source
            and sel.post_effects.relations
        ):
            discount = float(config.appraisal.get("displaced_relational_discount", 0.0))
            relations = {
                src: {dim: v * discount for dim, v in dims.items()}
                for src, dims in sel.post_effects.relations.items()
            }
            sel = replace(
                sel,
                post_effects=StateDelta(
                    global_=sel.post_effects.global_, relations=relations
                ),
                explanation=sel.explanation
                + " [DISPLACED onto a bystander; relational cost transient]",
            )
        # 9. commit post_effects + mode/cooldown transition
        _commit(runtime, sel.post_effects)
        _apply_transition(runtime, prev_mode, sel, t)
        # M7 Step 2: give up if SEEKING too long with no `activity` confirmation (-> IDLE, keep frustration).
        if runtime.mode == Mode.SEEKING and runtime.seeking_since is not None:
            timeout = config.thresholds.get("seeking_timeout_ticks", float("inf"))
            if (t - runtime.seeking_since) >= timeout:
                runtime.mode = Mode.IDLE
                runtime.active_action = None
                runtime.seeking_since = None
    state_after_post = runtime.freeze()

    # 10. bookkeeping
    if event is not None:
        runtime.history_log.append(event)
    if is_provocation:
        runtime.last_provocation_t = (
            t  # the reactive gate keys on the last PROVOKING event (D11)
        )
        runtime.last_provocation_source = (
            event.source if event is not None else runtime.last_provocation_source
        )
    if is_stressor:
        runtime.last_stressor_t = (
            t  # suppresses idle recovery while a world stressor (rain) is active
        )
    if runtime.cooldowns.get("mode", 0) > 0:
        runtime.cooldowns["mode"] -= 1
        if runtime.cooldowns["mode"] <= 0 and runtime.mode == Mode.COOLDOWN:
            runtime.mode = Mode.IDLE

    # Burst latch transitions (spec section 8 burst), evaluated on the END-of-tick committed state.
    # ENTER: BOTH loop states in the saturation band for burst_confirm_ticks (the LOOP plateau is the
    # signature -- a single-state spike must not arm it). EXIT (hysteresis): anger back below burst_exit.
    # All three thresholds must be configured or the latch is disabled (the shipped default).
    enter_a = config.thresholds.get("burst_enter.anger")
    enter_s = config.thresholds.get("burst_enter.stress")
    exit_th = config.thresholds.get("burst_exit")
    if enter_a is not None and enter_s is not None and exit_th is not None:
        if runtime.burst_latched:
            if runtime.global_state["anger"] <= exit_th:
                runtime.burst_latched = False
                runtime.burst_armed_since = None
        else:
            in_band = (
                runtime.global_state["anger"] >= enter_a
                and runtime.global_state["stress"] >= enter_s
            )
            if in_band:
                if runtime.burst_armed_since is None:
                    runtime.burst_armed_since = t
                confirm = int(config.thresholds.get("burst_confirm_ticks", 1))
                if (t - runtime.burst_armed_since) + 1 >= confirm:
                    runtime.burst_latched = True
            else:
                runtime.burst_armed_since = None

    return TickTrace(
        t=t,
        event=event,
        snapshot=snapshot,
        derived_pre=derived_pre,
        eff_inputs=eff,
        delta=delta,
        state_after_commit=state_after_commit,
        derived_post=derived_post,
        potentials=pots,
        urges=urges,
        selection=sel,
        state_after_post=state_after_post,
        burst_latched=runtime.burst_latched,
    )


def run_scenario(
    config: PersonaConfig, scenario: Scenario, n_ticks: int | None = None
) -> tuple[PersonaRuntime, DebugTrace]:
    runtime = init_runtime(config, scenario.initial_overrides)
    events_by_t: dict[int, RawEvent] = {ev.t: ev for ev in scenario.events}

    if n_ticks is None:
        last_t = max((ev.t for ev in scenario.events), default=0)
        n_ticks = last_t + 1

    trace = DebugTrace(persona=config.id, scenario=scenario.id, dt=config.dt)
    for t in range(n_ticks):
        trace.emit(tick(runtime, t, events_by_t.get(t)))
    return runtime, trace
