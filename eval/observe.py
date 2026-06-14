"""eval/observe.py -- read-only observability helpers over a DebugTrace.

Lightweight summaries that make it easy to VERIFY whether a run's behavioral dynamics are plausible:
state trajectories, per-state min/max/final, action histograms, mode timelines, boundedness and
monotonicity checks. These are PURE functions that only READ a trace -- they never touch the engine,
never mutate state, and change no runtime behavior (so goldens, determinism, and the sanity gates are
untouched). They live in eval/ (the believability/observability layer), not in engine/.

The contract everywhere: a "trace" is the DebugTrace returned as run_scenario(...)[1]; its `ticks` are
TickTrace records (see engine/debug.py). State is read from `state_after_post` (the final per-tick state).
"""

from __future__ import annotations

from typing import Iterable


def trajectory(tr, state: str) -> list[float]:
    """The per-tick trajectory of one global state (post-selector value), in tick order."""
    return [tk.state_after_post.global_state[state] for tk in tr.ticks]


def relation_trajectory(tr, source: str, dim: str) -> list[float]:
    """The per-tick trajectory of one relational dimension toward `source` (0.0 when no row yet)."""
    return [
        tk.state_after_post.relations.get(source, {}).get(dim, 0.0) for tk in tr.ticks
    ]


def state_summary(tr, state: str) -> dict:
    """min / max / first / last / net change for one global state over the whole trace."""
    xs = trajectory(tr, state)
    return {
        "min": min(xs),
        "max": max(xs),
        "first": xs[0],
        "last": xs[-1],
        "net": xs[-1] - xs[0],
    }


def action_counts(tr) -> dict[str, int]:
    """Histogram of selected actions over the trace (action name -> count)."""
    counts: dict[str, int] = {}
    for tk in tr.ticks:
        counts[tk.selection.action] = counts.get(tk.selection.action, 0) + 1
    return counts


def mode_timeline(tr) -> list[str]:
    """The per-tick mode value (IDLE / SEEKING / BUSY / SLEEP / COOLDOWN), in tick order."""
    return [tk.state_after_post.mode.value for tk in tr.ticks]


def first_tick_with_action(tr, action: str) -> int | None:
    """The tick number where `action` is first selected, or None if it never is."""
    return next((tk.t for tk in tr.ticks if tk.selection.action == action), None)


def is_bounded(tr, lo: float = 0.0, hi: float = 1.0) -> bool:
    """True iff every global state AND every relational dimension stays within [lo, hi] for all ticks."""
    for tk in tr.ticks:
        for v in tk.state_after_post.global_state.values():
            if not (lo <= v <= hi):
                return False
        for row in tk.state_after_post.relations.values():
            for v in row.values():
                if not (lo <= v <= hi):
                    return False
    return True


def is_nondecreasing(xs: Iterable[float], eps: float = 1e-9) -> bool:
    """True iff a sequence never steps DOWN by more than eps (monotone-up within tolerance)."""
    xs = list(xs)
    return all(b >= a - eps for a, b in zip(xs, xs[1:]))


def is_deterministic(run_a, run_b) -> bool:
    """True iff two traces are bit-identical (compares the canonical JSON serialization)."""
    return run_a.to_json() == run_b.to_json()
