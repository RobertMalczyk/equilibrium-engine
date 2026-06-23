"""metrics.compute (M.metrics) -- trace -> metrics extractor (spec section 15/16).

Pure, deterministic. In: a DebugTrace (one persona x one scenario run). Out: a flat dict of
named metrics (scalars, bools, and curves) for the predicate DSL (expectations.py). Does NOT
evaluate predicates. Adding a metric = one pure function here (spec scenarios file).

Exposes the RAW reactive potentials and drive urges (peak_<potential>, peak_<urge>, and the
curves), not only the discretized action -- so that threshold-crossing goals (outburst_fired,
"seek fires", interrupts) can be scored on the smooth underlying quantity, giving a
derivative-free optimizer a gradient instead of a flat 0/1 (calibration note, M4).

Namespace
---------
scalars/bools : outburst_fired, final_action, interrupt_count, time_to_interrupt,
                proactive_start_count, first_start_tick, drive_switch_tick
sequence      : action_sequence
per global state (8) : peak_<state>, <state>_delta, <state>_curve
per potential (5)    : peak_<potential>, <potential>_curve
per urge (2)         : peak_urge_<urge>, urge_<urge>_curve
per relation src/dim : <dim>_delta__<src>, peak_<dim>__<src>, <dim>_curve__<src>
"""

from __future__ import annotations

from engine.schema import GLOBAL_STATES, POTENTIAL_NAMES, RELATION_DIMS, Mode

URGE_NAMES: tuple[str, ...] = ("boredom", "fatigue")


def compute(trace) -> dict:
    """trace: a DebugTrace (has .ticks). Returns the flat metric namespace above."""
    ticks = trace.ticks
    m: dict = {}

    actions = [tk.selection.action for tk in ticks]
    m["action_sequence"] = actions
    m["final_action"] = actions[-1] if actions else None
    m["outburst_fired"] = "outburst" in actions
    m["interrupt_count"] = sum(1 for tk in ticks if tk.selection.interrupted)
    m["time_to_interrupt"] = next(
        (tk.t for tk in ticks if tk.selection.interrupted), None
    )

    # proactive start = entering SEEKING from IDLE (M7 Step 2: the seek INTENT begins). Engagement
    # (SEEKING->BUSY) happens later, only if the world confirms an `activity`; counted separately.
    starts = [
        tk
        for tk in ticks
        if tk.state_after_post.mode == Mode.SEEKING and tk.snapshot.mode == Mode.IDLE
    ]
    m["proactive_start_count"] = len(starts)
    m["first_start_tick"] = starts[0].t if starts else None
    engagements = [
        tk
        for tk in ticks
        if tk.state_after_post.mode == Mode.BUSY and tk.snapshot.mode == Mode.SEEKING
    ]
    m["activity_engage_count"] = len(engagements)

    # drive switch = first change of the BUSY activity action (e.g. seek_stimulus -> rest).
    busy = [
        (tk.t, tk.selection.action)
        for tk in ticks
        if tk.state_after_post.mode == Mode.BUSY
    ]
    switch = next((t for (_, pa), (t, a) in zip(busy, busy[1:]) if a != pa), None)
    m["drive_switch_tick"] = switch

    # Game-time variants of the timing metrics (tick * dt). dt = min(half_life)/10 changes with
    # the time-constant params, so timing TARGETS must be read in game-time to stay comparable
    # across candidates (calibration note, M4); predicates use these, not the raw tick numbers.
    dt = trace.dt
    m["time_to_interrupt_seconds"] = (
        None if m["time_to_interrupt"] is None else m["time_to_interrupt"] * dt
    )
    m["drive_switch_seconds"] = None if switch is None else switch * dt
    m["first_start_seconds"] = (
        None if m["first_start_tick"] is None else m["first_start_tick"] * dt
    )

    init_global = ticks[0].snapshot.global_state
    for s in GLOBAL_STATES:
        if s not in init_global:
            continue  # opt-in moral state absent for this persona (overlay off) -> no curve to build
        series = [tk.state_after_post.global_state[s] for tk in ticks]
        m[f"{s}_curve"] = series
        m[f"peak_{s}"] = max(series)
        m[f"{s}_delta"] = series[-1] - init_global[s]

    # Raw reactive potentials (smooth substrate for threshold-crossing goals, M4 note).
    for p in POTENTIAL_NAMES:
        series = [tk.potentials.get(p, 0.0) for tk in ticks]
        m[f"{p}_curve"] = series
        m[f"peak_{p}"] = max(series)

    # Raw drive urges (smooth substrate for "seek fires" goals).
    for u in URGE_NAMES:
        series = [tk.urges.get(u, 0.0) for tk in ticks]
        m[f"urge_{u}_curve"] = series
        m[f"peak_urge_{u}"] = max(series)

    # Relational metrics per (source, dim) present in the run.
    sources = sorted({src for tk in ticks for src in tk.state_after_post.relations})
    for src in sources:
        init_rel = ticks[0].snapshot.relations.get(src, {})
        for dim in RELATION_DIMS:
            series = [
                tk.state_after_post.relations.get(src, {}).get(dim, 0.0) for tk in ticks
            ]
            m[f"{dim}_curve__{src}"] = series
            m[f"peak_{dim}__{src}"] = max(series)
            m[f"{dim}_delta__{src}"] = series[-1] - init_rel.get(dim, 0.0)

    # Settle time (game-time seconds) for each state: from its peak, how long until it falls to
    # <= settle_frac * peak. LEVEL-INDEPENDENT (a fraction of the state's OWN peak), so it measures
    # the time constant (decay), not the level -- the level depends on the frozen channel gains, so
    # a level metric would test the wrong calibration layer. If it never settles within the run, the
    # value is the elapsed game-time from the peak to the end (a long, comparable "did not settle").
    for s in GLOBAL_STATES:
        if s not in init_global:
            continue  # opt-in moral state absent -> skip
        m[f"settle_seconds_{s}"] = _settle_seconds(
            [tk.state_after_post.global_state[s] for tk in ticks], dt
        )
    for src in sources:
        for dim in RELATION_DIMS:
            m[f"settle_seconds_{dim}__{src}"] = _settle_seconds(
                [
                    tk.state_after_post.relations.get(src, {}).get(dim, 0.0)
                    for tk in ticks
                ],
                dt,
            )

    return m


def decay_time(series: list, dt: float, frac: float = 0.5) -> tuple[float, bool]:
    """From the series peak, the game-time until it first falls to <= frac*peak, and whether that
    was REACHED within the series. (sec, reached). peak<=0 (no excitation) -> (0.0, False). Not
    reached -> (elapsed game-time from peak to the end, False). The `reached` flag lets a contract
    test WHETHER a state decays in the horizon (e.g. resentment never halves) without measuring an
    unreachable TIME -- robust to the coupling FLOOR states decay toward (not zero)."""
    if not series:
        return 0.0, False
    peak = max(series)
    if peak <= 0.0:
        return 0.0, False
    k = series.index(peak)
    threshold = frac * peak
    for i in range(k, len(series)):
        if series[i] <= threshold:
            return (i - k) * dt, True
    return (len(series) - 1 - k) * dt, False


def _settle_seconds(series: list, dt: float, settle_frac: float = 0.10) -> float:
    return decay_time(series, dt, settle_frac)[0]
