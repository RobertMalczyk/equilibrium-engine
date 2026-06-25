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
    EffectiveInputVector,
    LieRecord,
    Mode,
    PersonaConfig,
    PersonaRuntime,
    RawEvent,
    Scenario,
    StateDelta,
)


def _update_ledger(
    runtime: PersonaRuntime, action: str, target: str | None, t: int
) -> None:
    """M-J.4.1: decay existing LieRecords (mini-integrators) and book a create/reinforce for a lie-type
    action (its `action_params[action].ledger` config). Repeated lies to the SAME target accrue debt on the
    EXISTING record (keyed by target) -- never spawn a fresh one (spec 3.5). Mutates the ledger in the
    post_effects phase ONLY (the sanctioned second mutation site). Inert for legacy personas (no ledger
    config -> no decay key, no action ledger block)."""
    config = runtime.config
    led = runtime.moral_ledger
    decay = float(config.ledger_params.get("lie_decay", 1.0))
    if (
        decay != 1.0
    ):  # stale lies fade (a record not reinforced this tick relaxes toward 0)
        for rid in sorted(
            led.lies
        ):  # sorted: deterministic regardless of creation order
            rec = led.lies[rid]
            rec.consistency_debt *= decay
            rec.maintenance_load *= decay
            rec.detected_risk *= decay
    spec = config.action_params.get(action, {}).get("ledger")
    if not spec or target is None:
        return
    rid = f"lie:{target}"
    rec = led.lies.get(rid)
    if spec.get(
        "resolves"
    ):  # M-J.4: a CONFESSION clears the lie to this target (spec 3.5 lie_confessed) --
        if (
            rec is not None
        ):  # reduce its debt/load toward 0 (negative increments); never create a record
            rec.consistency_debt = clamp01(
                rec.consistency_debt + float(spec.get("consistency_debt", 0.0))
            )
            rec.maintenance_load = clamp01(
                rec.maintenance_load + float(spec.get("maintenance_load", 0.0))
            )
            rec.last_reinforced_at = t
        return
    if (
        rec is None
    ):  # first lie to this target -> create; later lies REINFORCE this same record
        rec = LieRecord(
            id=rid,
            liar_id=config.id,
            target_id=target,
            lie_type=str(spec.get("lie_type", "denial")),
        )
        led.lies[rid] = rec
    rec.consistency_debt = clamp01(
        rec.consistency_debt + float(spec.get("consistency_debt", 0.0))
    )
    rec.maintenance_load = clamp01(
        rec.maintenance_load + float(spec.get("maintenance_load", 0.0))
    )
    rec.complexity = clamp01(max(rec.complexity, float(spec.get("complexity", 0.0))))
    rec.last_reinforced_at = t


def _book_detection(runtime: PersonaRuntime, eff: EffectiveInputVector, t: int) -> None:
    """M-J.4.2: a detected lie (`betrayal` channel from source S) hits the CAUGHT liar -- the persona holding
    a LieRecord keyed to S (lie:S). On the record: detected_risk jumps. On the liar's felt state: exposure_
    anxiety and guilt spike (the caught-out dread + remorse). BOTH are GATED on the record existing, so a
    betrayed TARGET (no record) gets none of this -- only the relational damage booked by update's gains.
    Runs in the post_effects phase. Inert for legacy personas (no detected_risk_on_detect config)."""
    lp = runtime.config.ledger_params
    bump = float(lp.get("detected_risk_on_detect", 0.0))
    if bump <= 0.0:
        return
    exp_bump = float(lp.get("detected_exposure", 0.0))
    guilt_bump = float(lp.get("detected_guilt", 0.0))
    gs = runtime.global_state
    for si in eff.get("betrayal", ()):
        if si.source is None:
            continue
        rec = runtime.moral_ledger.lies.get(f"lie:{si.source}")
        if rec is None:
            continue
        rec.detected_risk = clamp01(rec.detected_risk + bump * si.value)
        rec.last_reinforced_at = t
        # the caught liar FEELS it: exposure_anxiety + guilt spike (gated on being the liar, i.e. the record)
        if exp_bump and "exposure_anxiety" in gs:
            gs["exposure_anxiety"] = clamp01(
                gs["exposure_anxiety"] + exp_bump * si.value
            )
        if guilt_bump and "guilt" in gs:
            gs["guilt"] = clamp01(gs["guilt"] + guilt_bump * si.value)


def _secret_active(secret, unresolved_floor: float) -> bool:
    """M-J.4.3 (spec 3.4): a secret is ACTIVE while the owner is still hiding it from someone OR it remains
    unresolved. Inactive (hidden_from empty AND unresolvedness low) -> it stays in the ledger/trace but no
    longer drives salience/stress."""
    return bool(secret.hidden_from) or secret.unresolvedness >= unresolved_floor


def _update_secrets(runtime: PersonaRuntime, events: list[RawEvent], t: int) -> None:
    """M-J.4.3: the Secret lifecycle, booked in the post_effects phase. Decays salience; a `secret_cued`
    reminder raises salience (gated to 0 for an inactive secret); `secret_exposed` fills `known_by` with the
    witnesses and EMPTIES `hidden_from` (publicly known -> no longer hiding) -> inactivation; an ACTIVE
    secret's salience then weighs as stress. Inert when the ledger holds no secrets (legacy byte-identical)."""
    led = runtime.moral_ledger
    if not led.secrets:
        return
    lp = runtime.config.ledger_params
    sal_decay = float(lp.get("salience_decay", 1.0))
    cue_gain = float(lp.get("secret_cue_salience", 0.0))
    floor = float(lp.get("inactive_unresolved_floor", 0.0))
    stress_gain = float(lp.get("secret_salience_to_stress", 0.0))
    guilt_gain = float(
        lp.get("secret_weight_to_guilt", 0.0)
    )  # A3: moral_weight sustains guilt
    gs = runtime.global_state
    ids = sorted(
        led.secrets
    )  # sorted: deterministic order for the stress accumulation (clamp is sequential)
    if sal_decay != 1.0:  # salience fades between reminders
        for sid in ids:
            led.secrets[sid].salience *= sal_decay
    for ev in events:
        if ev.type == "secret_cued":
            for sid in ids:
                s = led.secrets[sid]
                if (ev.topic is None or ev.topic == s.topic) and _secret_active(
                    s, floor
                ):
                    s.salience = clamp01(s.salience + cue_gain * ev.intensity)
        elif ev.type == "secret_exposed":
            for sid in ids:
                s = led.secrets[sid]
                if ev.topic is None or ev.topic == s.topic:
                    for w in list(ev.context.get("witnesses", [])):
                        if w not in s.known_by:
                            s.known_by.append(w)
                    s.hidden_from = []  # public knowledge -> no longer ACTIVELY hiding -> inactivation
    for sid in ids:  # an ACTIVE secret weighs (stress) AND, by its moral_weight, keeps GUILT alive (A3:
        s = led.secrets[
            sid
        ]  # the minor/serious split -- a serious unconfessed wrong lingers, a minor fades;
        if _secret_active(
            s, floor
        ):  # confession/exposure inactivates it -> both drips stop -> relief.
            if stress_gain and "stress" in gs:
                gs["stress"] = clamp01(gs["stress"] + stress_gain * s.salience)
            if guilt_gain and "guilt" in gs:
                gs["guilt"] = clamp01(
                    gs["guilt"] + guilt_gain * s.moral_weight * s.salience
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
        for (
            ch,
            sis,
        ) in (
            eff.items()
        ):  # M-MEM: a channel may carry several inputs (multi-source tick)
            for si in sis:
                contrib += gx.get(ch, 0.0) * si.value
    if contrib > 0.0:  # raised anger/frustration from a SOURCE -> a direct provocation
        return True
    theta = config.thresholds.get(
        "provocation_resentment", float("inf")
    )  # (2) a gesture from a resented source still galls
    if snapshot.relations.get(src, {}).get("resentment", 0.0) >= theta:
        return True
    return False


def _provocation_score(event, ev_eff: dict, snapshot, config: PersonaConfig) -> float:
    """M-MEM.1: how strongly ONE event provokes (its OWN filtered inputs `ev_eff`), used to pick the primary
    provoker when several events land on a tick. > 0 iff `_event_is_provocation` would be True for that event
    alone: case (1) it adds anger/frustration (the contribution magnitude); case (2) it is a gesture from a
    resented source (ranked by that resentment). 0 for a sourceless stressor or a benign non-resented gesture.
    Reduces to the existing single-event provocation test, so a <=1-event tick is unaffected."""
    if event is None or event.source is None:
        return 0.0
    contrib = 0.0
    for state in ("anger", "frustration"):
        gx = config.gains.get(state, {})
        for ch, si in ev_eff.items():
            contrib += gx.get(ch, 0.0) * si.value
    if contrib > 0.0:
        return contrib
    theta = config.thresholds.get("provocation_resentment", float("inf"))
    resent = snapshot.relations.get(event.source, {}).get("resentment", 0.0)
    return resent if resent >= theta else 0.0


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
        for (
            ch,
            sis,
        ) in (
            eff.items()
        ):  # M-MEM: a channel may carry several inputs (multi-source tick)
            for si in sis:
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
        for (
            ch,
            sis,
        ) in (
            eff.items()
        ):  # M-MEM: a channel may carry several inputs (multi-source tick)
            for si in sis:
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


def _refractory_pressure(
    event, runtime, is_provocation: bool, config: PersonaConfig
) -> float:
    """Spent-fury refractory edge (spec §8, the FOURTH inhibitory edge), DECOUPLED from the burst latch.
    Once a character has already erupted at a source, a FRESH provocation from the SAME source while the
    fury is still hot no longer mints a new full-intensity outburst each tick -- the spent fury yields to
    cold contempt / numbed withdrawal (the `refractory_x_resent_src` term is read with a negative weight by
    `outburst`). The arming signature is the SPENT-FURY state, NOT the latch: the latch is the
    stress-saturation vent for a multi-loop COINCIDENCE, which a single relentless provoker (one
    individually-stable loop) never reaches -- so a latch-gated brake could never help exactly the
    relentless-cluster case it is for. Fires iff this tick's event is a provocation, its source IS the
    remembered provoker (`last_provocation_source`, the PREVIOUS provoker at this point), AND the carried
    anger is at/above `refractory_anger` (the heat of a recent eruption at that source). It naturally also
    covers the genuinely-latched multi-loop case (anger is high there too) -- a superset of the old latch
    gate. The FIRST eruption is a NEW source (`last_provocation_source` not yet this one), so it is
    unchanged. 0 otherwise -> bit-identical: `refractory_anger` unset (the shipped default), anger below it,
    a different/new provoker (full ordinary reaction, like the displacement gate's `target != provoker`),
    or a non-provocation."""
    theta = config.thresholds.get("refractory_anger")
    if theta is None:  # disabled (shipped default) -> bit-identical
        return 0.0
    if event is None or event.source is None or not is_provocation:
        return 0.0
    if event.source != runtime.last_provocation_source:
        return 0.0
    if (
        runtime.global_state["anger"] < theta
    ):  # not still hot from a recent eruption here
        return 0.0
    return float(config.appraisal.get("refractory_pressure", 0.0))


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


def tick(
    runtime: PersonaRuntime,
    t: int,
    events: RawEvent | list[RawEvent] | None = None,
) -> TickTrace:
    config = runtime.config
    # M-MEM: 0, 1, or MANY events this tick (idle = empty). A bare RawEvent or None is accepted and
    # normalized (backward-compatible with single-event callers); run_scenario passes the per-tick list.
    if isinstance(events, RawEvent):
        events = [events]
    events = events or []
    # The PRIMARY event drives the per-source reactive signals (provocation / kindness / reaction_target /
    # bookkeeping). It is the STRONGEST provoker on the tick (M-MEM.1); with no provoker it falls back to the
    # first event (a benign gesture / sourceless stressor / activity). EVERY event's deposits are merged into
    # `eff` regardless. For a <=1-event tick this is exactly the single event -> byte-identical.
    primary = events[0] if events else None

    # 1. freeze
    snapshot = runtime.freeze()
    prev_mode = snapshot.mode

    # 2. derived_pre
    derived_pre = derived.compute(snapshot.global_state, snapshot.relations, config)

    # 3. perception: map + filter EACH event, MERGE into channel -> list of inputs (M-MEM). A single event
    # yields one-element lists, so update/derived/the reactive gates are byte-identical for a <=1-event tick.
    eff: EffectiveInputVector = {}
    command_pressure = (
        0.0  # transient: this tick's command channel (raw, pre-filter); 0 if no order
    )
    best_provoke = 0.0  # M-MEM.1: track the strongest provoker to elect as `primary`
    for ev in events:
        feats = history.analyze(runtime.history_log, ev, t, config)
        raw = mapper.map_event(ev, config, feats)
        if "command" in raw:
            command_pressure = max(command_pressure, raw["command"].value)
        ctx = ev.context
        ev_eff = affinity_filter.apply(
            relation_filter.apply(raw, snapshot.relations, derived_pre, config, ctx),
            config.affinities,
            config,
            ctx,
        )
        for ch, si in ev_eff.items():
            eff.setdefault(ch, []).append(si)
        # elect the primary provoker: STRICTLY-greater so ties keep the earlier (scenario-order) event.
        score = _provocation_score(ev, ev_eff, snapshot, config)
        if score > best_provoke:
            best_provoke = score
            primary = ev
    event_source = primary.source if primary is not None else None

    # Recency / PROVOCATION gate (D5 step 1c + D11): a reactive REPLY needs a recent PROVOCATION -- not just
    # any recent event. A benign gesture (liked food / help from a non-resented source) is not a provocation,
    # so a calm-but-recently-fed persona does not "snap at a meal" (the D11 finding). Computed here (before
    # update) so it ALSO gates idle recovery. The provoking-event tick is tracked on the runtime.
    window = config.thresholds.get("reactive_window_ticks", float("inf"))
    is_provocation = _event_is_provocation(primary, eff, snapshot, config)
    # Theme A: the appraised kindness of THIS tick's event (mirror of is_provocation). Transient, like
    # command_pressure: 0 unless a non-resented pro-social gesture. Drives positive_response + inhibits venting.
    kindness_pressure = _kindness_pressure(primary, eff, snapshot, config)
    # Target policy: is this tick's source a respected BYSTANDER catching displaced anger? (uses last_provocation_source)
    bystander_pressure = _bystander_pressure(primary, runtime, t, window, config)
    # Spent-fury refractory (spec §8, 4th inhibitory edge, DECOUPLED from the latch): a fresh provocation
    # from the SAME source while still hot (anger >= refractory_anger) inhibits a new outburst -> the spent
    # fury goes cold instead. 0 when refractory_anger unset / anger below it / different source / non-provoke.
    refractory_pressure = _refractory_pressure(primary, runtime, is_provocation, config)
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
    # M3 source-valence gate (spec section 8, config `appraisal.displace_valence_gate`, default off ->
    # bit-identical): a GENUINE kindness is not a discharge target. `positive_valence` reuses the existing
    # kindness appraisal exactly -- kindness_pressure > 0 means a pro-social gesture from a NON-resented
    # source (a "kindness" from a resented source is kindness_pressure 0, it galls -> still a target, so
    # Cichy is unaffected). When enabled, such an event does not open the displaced gate, so its
    # kindness_pressure survives below and the appraisal route wins (warmth, not a lash-out at the giver).
    valence_gate_on = bool(config.appraisal.get("displace_valence_gate", False))
    positive_valence = kindness_pressure > 0.0
    displaced_gate = (
        runtime.burst_latched
        and event_source is not None
        and snapshot.global_state["anger"] >= theta_displace
        and not (valence_gate_on and positive_valence)
    )
    # Above the bar, displacement OVERRIDES the appraisal route (spec section 8 burst, decided
    # 2026-06-12): while the displaced gate is open, this tick's kindness is suppressed -- fury past
    # theta_displace no longer HEARS the kindness ("even someone kind, even at their kindness").
    # Below the bar (or unlatched) the appraisal route wins completely unchanged. Without this gate
    # the kindness inhibitory edge vetoed the displaced discharge at every weight (measured), so the
    # spec'd behaviour was unrealizable by calibration -- a topology gap, not a tuning task.
    if displaced_gate:
        kindness_pressure = 0.0
    reactive_allowed = (
        is_provocation
        or kindness_pressure > 0.0
        or (lp is not None and (t - lp) <= window)
        or displaced_gate
    )
    # A sourceless world stressor (rain) opens no reply, but it WEARS the persona down -- so while it is active
    # he is not idly recovering (spec §5: weather wears the temper, so a later provocation lands harder).
    is_stressor = _event_is_stressor(primary, eff, config)
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
        refractory_pressure,
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
    reaction_target = primary.source if primary is not None else None

    if prev_mode == Mode.SEEKING and primary is not None and primary.type == "activity":
        # M7 Step 2 ENGAGE: the world confirmed an activity -> start it (overrides normal selection).
        kind = str(primary.context.get("kind", "self_activity"))
        runtime.engaged_novelty = float(primary.context.get("novelty", 1.0))
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
        # A discharge is DISPLACED only if ALL hold (corner-case review, 2026-06-12):
        #   (1) the displaced gate is what could admit it (latch SET + anger over the bar);
        #   (2) this tick's event is NOT itself a provocation -- a direct reply to the provoking
        #       event (even a brand-new provoker) is an ORDINARY reply and books its full cost;
        #   (3) the reply is HOSTILE (books positive resentment) -- a warm positive_response that
        #       happens while latched is an appraisal reply, not a lash-out: never tagged/discounted;
        #   (4) the target is not the remembered provocation source.
        if (
            displaced_gate
            and not is_provocation
            and sel.kind == ActionKind.REACTIVE
            and reaction_target is not None
            and reaction_target != runtime.last_provocation_source
            and any(
                dims.get("resentment", 0.0) > 0.0
                for dims in sel.post_effects.relations.values()
            )
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
    # M-J.4: ledger writes (post_effects phase) -- run on EVERY tick (incl. the SEEKING->BUSY ENGAGE branch),
    # so a lie/secret decays and a detection lands even on a tick the persona starts an activity. Inert for
    # legacy / no-ledger personas.
    _update_ledger(runtime, sel.action, reaction_target, t)  # book/decay lie records
    _book_detection(
        runtime, eff, t
    )  # M-J.4.2: a caught lie raises its record's detected_risk
    _update_secrets(
        runtime, events, t
    )  # M-J.4.3: secret salience / lifecycle (cue, exposure, weight)
    state_after_post = runtime.freeze()

    # 10. bookkeeping
    for ev in events:  # M-MEM: every event this tick enters history (order preserved)
        runtime.history_log.append(ev)
    if is_provocation:
        runtime.last_provocation_t = (
            t  # the reactive gate keys on the last PROVOKING event (D11)
        )
        runtime.last_provocation_source = (
            primary.source if primary is not None else runtime.last_provocation_source
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
        event=primary,
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
    # M-MEM: group ALL events sharing a tick into a list (scenario order preserved) instead of a dict that
    # silently dropped same-tick collisions. A single event per tick reduces to a one-element list.
    events_by_t: dict[int, list[RawEvent]] = {}
    for ev in scenario.events:
        events_by_t.setdefault(ev.t, []).append(ev)

    if n_ticks is None:
        last_t = max((ev.t for ev in scenario.events), default=0)
        n_ticks = last_t + 1

    trace = DebugTrace(persona=config.id, scenario=scenario.id, dt=config.dt)
    for t in range(n_ticks):
        trace.emit(tick(runtime, t, events_by_t.get(t, [])))
    return runtime, trace
