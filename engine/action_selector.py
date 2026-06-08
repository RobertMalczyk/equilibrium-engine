"""selector.select (M8) -- shared selector for BOTH paths + arbitration (spec sections 7/8).

In: potentials + urges + thresholds + mode + cooldowns + state' + traits + drives. Out: one
ActionSelection (action, kind, interrupted, post_effects, explanation). Reactive and
proactive paths differ only in their trigger; both resolve here against one state. Returns
deltas as post_effects; commits nothing and changes no mode itself -- simulation maps
(prev_mode, kind, interrupted) to mode/cooldown transitions.

Selection rule (spec section 7): a threshold gates "in play"; argmax picks "strongest of
the allowed". So cold_response@0.50 with potential 0.6 beats outburst@0.75 with 0.55.
"""

from __future__ import annotations

from engine.schema import (
    POTENTIAL_NAMES,
    ActionKind,
    ActionSelection,
    GlobalStateMap,
    Mode,
    PersonaConfig,
    PotentialVector,
    StateDelta,
)

_NEVER = (
    1.0 + 1.0
)  # absent threshold => effectively unreachable (potentials clamp to 1)


def _react_threshold(config: PersonaConfig, name: str) -> float:
    th = config.thresholds
    return th.get(f"react.{name}", th.get("react_default", _NEVER))


def _interrupt_threshold(config: PersonaConfig, name: str) -> float:
    th = config.thresholds
    return th.get(f"interrupt.{name}", th.get("interrupt_default", _NEVER))


def _argmax_reactive(
    config: PersonaConfig, potentials: PotentialVector
) -> tuple[str, float] | None:
    """Strongest potential that clears its own react threshold (deterministic tie-break)."""
    best: tuple[str, float] | None = None
    for name in POTENTIAL_NAMES:  # canonical order = stable tie-break
        p = potentials.get(name, 0.0)
        if p >= _react_threshold(config, name):
            if best is None or p > best[1]:
                best = (name, p)
    return best


def _post_effects(
    config: PersonaConfig, action: str, reaction_target: str | None
) -> StateDelta:
    """Reaction cost: global deltas, plus relational deltas booked on the reaction's target
    (the provoking source, e.g. outburst -> +resentment[source], spec section 8)."""
    params = config.action_params.get(action, {})
    pe = params.get("post_effects", {})
    glob = {k: float(v) for k, v in dict(pe.get("global", {})).items()}
    relations: dict[str, dict[str, float]] = {}
    src_rel = dict(pe.get("source_relations", {}))
    if src_rel and reaction_target is not None:
        relations[reaction_target] = {k: float(v) for k, v in src_rel.items()}
    return StateDelta(global_=glob, relations=relations)


def _best_drive(
    config: PersonaConfig, urges: dict[str, float]
) -> tuple[str, str, float] | None:
    """(drive_name, action, urge) with the strongest urge; deterministic by drive name."""
    best: tuple[str, str, float] | None = None
    for drive_name in sorted(config.drives):
        spec = config.drives[drive_name]
        urge_state = spec.get("urge")
        action = spec.get("action")
        u = urges.get(urge_state, 0.0)
        if best is None or u > best[2]:
            best = (drive_name, action, u)
    return best


def select(
    potentials: PotentialVector,
    urges: dict[str, float],
    global_state: GlobalStateMap,
    config: PersonaConfig,
    mode: Mode,
    active_action: str | None,
    reaction_target: str | None = None,
    reactive_allowed: bool = True,
) -> ActionSelection:
    th = config.thresholds
    # A reactive action is a REPLY -- it needs a recent provocation. reactive_allowed is False when no
    # event has occurred within the recency window (simulation computes it): from pure idle the ambient
    # fatigue->stress->anger drift must NOT fire a 'cold_response' at thin air (D5 step 1c / D2). Sustained
    # reactions after a real event still fire (the event is within the window).
    max_react = _argmax_reactive(config, potentials) if reactive_allowed else None

    if mode == Mode.BUSY:
        satiation = th.get("satiation", _NEVER)
        fatigue_end = th.get("fatigue_end", _NEVER)
        # END when sated / exhausted, OR when the NEED the activity serves is met (per-action
        # `end_when_below`, e.g. rest ends once fatigue is low -- "rested", not "tired"; spec section 8).
        end_below = config.action_params.get(active_action, {}).get(
            "end_when_below", {}
        )
        need_met = any(global_state.get(s, 0.0) <= thr for s, thr in end_below.items())
        if (
            global_state["satisfaction"] >= satiation
            or global_state["fatigue"] >= fatigue_end
            or need_met
        ):
            return ActionSelection(
                action=active_action or "neutral",
                score=0.0,
                kind=ActionKind.PROACTIVE,
                interrupted=False,
                post_effects=StateDelta(),
                explanation="END activity (satiation/fatigue) -> COOLDOWN",
            )
        if max_react is not None:
            name, score = max_react
            if score >= _interrupt_threshold(config, name):
                return ActionSelection(
                    action=name,
                    score=score,
                    kind=ActionKind.REACTIVE,
                    interrupted=True,
                    post_effects=_post_effects(config, name, reaction_target),
                    explanation=f"reactive '{name}' >= theta_interrupt -> INTERRUPT activity",
                )
            return ActionSelection(
                action=name,
                score=score,
                kind=ActionKind.REACTIVE,
                interrupted=False,
                post_effects=_post_effects(config, name, reaction_target),
                explanation=f"reactive '{name}' in passing; activity continues",
            )
        return ActionSelection(
            action=active_action or "neutral",
            score=0.0,
            kind=ActionKind.CONTINUE,
            interrupted=False,
            post_effects=StateDelta(),
            explanation="continue activity",
        )

    if mode == Mode.SLEEP:
        # M7.5 Part B: sleep on until the night is over (sleep_pressure discharged -> end_when_below), unless
        # a STRONG stimulus wakes (wake-on-threat = clears theta_interrupt). No "reaction in passing" -- a
        # mild stimulus is simply ignored (you don't cold-respond in your sleep); the fast-state reset is the
        # `sleep` action's per_tick (update.py).
        end_below = config.action_params.get(active_action, {}).get(
            "end_when_below", {}
        )
        rested = any(global_state.get(s, 0.0) <= thr for s, thr in end_below.items())
        if rested:
            return ActionSelection(
                action=active_action or "neutral",
                score=0.0,
                kind=ActionKind.PROACTIVE,
                interrupted=False,
                post_effects=StateDelta(),
                explanation="WAKE (rested: sleep_pressure low) -> COOLDOWN",
            )
        if max_react is not None:
            name, score = max_react
            if score >= _interrupt_threshold(config, name):
                return ActionSelection(
                    action=name,
                    score=score,
                    kind=ActionKind.REACTIVE,
                    interrupted=True,
                    post_effects=_post_effects(config, name, reaction_target),
                    explanation=f"WAKE on threat: reactive '{name}' >= theta_interrupt -> INTERRUPT sleep",
                )
        return ActionSelection(
            action=active_action or "sleep",
            score=0.0,
            kind=ActionKind.CONTINUE,
            interrupted=False,
            post_effects=StateDelta(),
            explanation="continue sleeping (mild stimulus ignored)",
        )

    if mode == Mode.COOLDOWN:
        if max_react is not None:
            name, score = max_react
            return ActionSelection(
                action=name,
                score=score,
                kind=ActionKind.REACTIVE,
                interrupted=False,
                post_effects=_post_effects(config, name, reaction_target),
                explanation=f"reactive '{name}' (works during cooldown)",
            )
        return ActionSelection(
            action="neutral",
            score=0.0,
            kind=ActionKind.IDLE,
            interrupted=False,
            post_effects=StateDelta(),
            explanation="cooldown: start blocked",
        )

    if mode == Mode.SEEKING:
        # M7 Step 2: looking for an activity, awaiting the world's confirmation. A provocation interrupts
        # the search; otherwise keep seeking (the engage-on-`activity` and the give-up timeout are handled
        # by the orchestrator, which sees the event + the clock).
        if max_react is not None:
            name, score = max_react
            return ActionSelection(
                action=name,
                score=score,
                kind=ActionKind.REACTIVE,
                interrupted=False,
                post_effects=_post_effects(config, name, reaction_target),
                explanation=f"reactive '{name}' interrupts seeking",
            )
        return ActionSelection(
            action=active_action or "seek_stimulus",
            score=0.0,
            kind=ActionKind.CONTINUE,
            interrupted=False,
            post_effects=StateDelta(),
            explanation="continue seeking (awaiting activity)",
        )

    # IDLE: world has priority, then proactive start.
    if max_react is not None:
        name, score = max_react
        return ActionSelection(
            action=name,
            score=score,
            kind=ActionKind.REACTIVE,
            interrupted=False,
            post_effects=_post_effects(config, name, reaction_target),
            explanation=f"reactive '{name}' (world first)",
        )
    drive = _best_drive(config, urges)
    if drive is not None:
        _, action, u = drive
        if u >= th.get("urge_start", _NEVER):
            # A proactive START books the action's configured post_effects too (self deltas; reaction_target
            # None -> no relational delta). seek_stimulus/rest carry none -> empty delta -> unchanged; an
            # INSTANTANEOUS action (command_other) discharges its drive state here (e.g. duty -= delta).
            return ActionSelection(
                action=action,
                score=u,
                kind=ActionKind.PROACTIVE,
                interrupted=False,
                post_effects=_post_effects(config, action, None),
                explanation=f"START proactive '{action}' (urge {u:.3f} >= theta_start)",
            )
    return ActionSelection(
        action="neutral",
        score=0.0,
        kind=ActionKind.IDLE,
        interrupted=False,
        post_effects=StateDelta(),
        explanation="idle: nothing above threshold",
    )
