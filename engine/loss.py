"""loss -- pure calibration loss over the benchmark (spec sections 9, 16). NOT the optimizer.

``loss(params)`` is a PURE, deterministic function of the tuned parameters. It runs the
benchmark through the param-injection seam (``simulate``), extracts metrics (``metrics.compute``),
evaluates the predicate set (``expectations.evaluate``), and aggregates a weighted scalar plus a
per-component breakdown. The derivative-free optimizer LOOP (``calibration.py``, step 3) only
CALLS this -- it cannot dirty it (same separation as ``update`` pure vs ``simulation`` mutator).

Layered calibration (spec section 9): a "layer" = which params are free + which loss components
carry WEIGHT. Layer 1 = time constants (``half_lives``). Weighted: stability, curve/timing,
regularization. ``behavior``/``ranking`` are COMPUTED AND LOGGED from the start (diagnostics) but
carry WEIGHT ZERO in layer 1 -- so if tuning half_lives accidentally worsens a behavioral
contrast we SEE it in the breakdown, even though we do not penalize it here (it belongs to a
later layer).

dt note (spec section 2): ``dt = min(half_life)/10`` changes with the time constants, so the
benchmark horizon is given in GAME-TIME and ``n_ticks`` is derived per candidate; timing metrics
are read in game-time (the ``_seconds`` variants in metrics.py). Event timelines are still
tick-based -- making event SPACING dt-invariant is a later scenario-format change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from engine.expectations import evaluate
from engine.metrics import compute as compute_metrics
from engine.metrics import decay_time
from engine.simulation import run_scenario
from engine.stability import jury_margin, spectral_radius
from engine.yaml_io import load_persona, load_scenario

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
CALIBRATED_L1 = ROOT / "calibration" / "calibrated_layer1.yaml"

# Component weights (spec section 16.4). Layer 1: behavior/ranking logged at weight 0.
LAYER1_WEIGHTS: dict[str, float] = {
    "stability": 100.0,  # hard constraint: poles inside the unit circle
    "timing": 2.0,  # the anchor + decay orderings (the primary layer-1 signal)
    "curve": 1.0,
    "regularization": 1.0,
    "behavior": 0.0,  # computed + logged, NOT penalized in layer 1
    "ranking": 0.0,  # computed + logged, NOT penalized in layer 1
}


# Benchmark = pure data (spec section 16): named runs + predicates tagged by component.
# Predicate persona/a/b fields index RUN LABELS (a persona may appear in several runs). The TIMING
# contracts are built from the config time-scale ANCHOR (the one absolute number); everything else
# is RELATIVE (orderings the optimizer fits). settle_seconds is level-independent (decay, not level
# -- level depends on the frozen channel gains, the wrong layer).
def layer1_benchmark(anchor_seconds: float) -> dict:
    H = 180.0  # game-time horizon for the impulse/control runs
    return {
        "runs": {
            "control": {
                "persona": "halgrim",
                "scenario": "quiet_control",
                "horizon_seconds": H,
            },
            "food_imp": {
                "persona": "halgrim",
                "scenario": "food_impulse",
                "horizon_seconds": H,
            },
            "insult_imp": {
                "persona": "halgrim",
                "scenario": "insult_impulse",
                "horizon_seconds": H,
            },
            "stoic_idle": {
                "persona": "halgrim",
                "scenario": "idle_watch",
                "horizon_seconds": 180.0,
            },
            "wojslaw_bad": {
                "persona": "wojslaw",
                "scenario": "same_soup_bad_day",
                "horizon_seconds": 75.0,
            },
            "halgrim_bad": {
                "persona": "halgrim",
                "scenario": "same_soup_bad_day",
                "horizon_seconds": 75.0,
            },
        },
        # Impulse-response: (impulse - control) isolates an event's contribution from the ambient
        # idle drift; half-decay on that contribution measures the time constant, floor-robustly.
        "contributions": {
            "glow": {
                "impulse": "food_imp",
                "control": "control",
                "states": ["satisfaction"],
            },
            "grudge": {
                "impulse": "insult_imp",
                "control": "control",
                "states": ["anger"],
                "relations": [["player", "resentment"]],
            },
        },
        "predicates": [
            # ANCHOR (single absolute, two-sided >= / <= at anchor_seconds): a pleasant moment's glow
            # half-decays on the ~minutes scale. On SATISFACTION, whose half-decay the half-life steers.
            {
                "component": "timing",
                "type": "threshold",
                "persona": "glow",
                "metric": "half_decay_seconds_satisfaction",
                "op": "<=",
                "value": anchor_seconds,
                "scale": anchor_seconds,
            },
            {
                "component": "timing",
                "type": "threshold",
                "persona": "glow",
                "metric": "half_decay_seconds_satisfaction",
                "op": ">=",
                "value": anchor_seconds,
                "scale": anchor_seconds,
            },
            # C1 REACHABILITY (NOT resentment's unreachable time; provenance: common qualitative
            # observation / design -- a grudge outlasts a flash of temper): within the horizon anger
            # reaches half-decay while resentment does NOT. Guards, satisfied at baseline.
            {
                "component": "timing",
                "type": "boolean",
                "persona": "grudge",
                "metric": "half_decay_reached_anger",
                "equals": True,
            },
            {
                "component": "timing",
                "type": "boolean",
                "persona": "grudge",
                "metric": "half_decay_reached_resentment__player",
                "equals": False,
            },
            # C4: idle boredom rises (drift active); slow-accumulator ordering held by param_bounds. Uses a
            # LOW-novelty persona (halgrim) that does NOT seek from idle (D5) -- so boredom drifts up cleanly;
            # a fast-borer (welf) now seeks, which relieves boredom (correct, but not a monotonic-drift check).
            {
                "component": "curve",
                "type": "shape",
                "persona": "stoic_idle",
                "metric": "boredom_curve",
                "shape": "monotonic_up",
            },
            # behavior/ranking: weight 0 in layer 1, computed + logged as diagnostics.
            {
                "component": "behavior",
                "type": "boolean",
                "persona": "wojslaw_bad",
                "metric": "outburst_fired",
                "equals": True,
            },
            {
                "component": "ranking",
                "type": "comparative",
                "metric": "peak_outburst",
                "a": "wojslaw_bad",
                "b": "halgrim_bad",
                "op": ">",
            },
        ],
    }


def _contribution_metrics(impulse, control, states, relations, frac) -> dict:
    """impulse-response metrics: half_decay (time + reached) of (impulse - control) per state/relation."""
    dt = impulse.dt
    out: dict = {}
    for s in states:
        diff = [
            i.state_after_post.global_state[s] - c.state_after_post.global_state[s]
            for i, c in zip(impulse.ticks, control.ticks)
        ]
        sec, reached = decay_time(diff, dt, frac)
        out[f"half_decay_seconds_{s}"] = sec
        out[f"half_decay_reached_{s}"] = reached
    for src, dim in relations:
        diff = [
            i.state_after_post.relations.get(src, {}).get(dim, 0.0)
            - c.state_after_post.relations.get(src, {}).get(dim, 0.0)
            for i, c in zip(impulse.ticks, control.ticks)
        ]
        sec, reached = decay_time(diff, dt, frac)
        out[f"half_decay_seconds_{dim}__{src}"] = sec
        out[f"half_decay_reached_{dim}__{src}"] = reached
    return out


@dataclass
class LossBreakdown:
    total: float
    components: dict  # component -> summed raw penalty
    weighted: dict  # component -> weight * penalty
    detail: dict  # diagnostics (spectral_radius, per-predicate results, ...)


def simulate(
    params: dict | None, persona_id: str, scenario_id: str, horizon_seconds: float
):
    """Pure function of params (spec section 16.1): override config, re-derive dt/decay, derive
    n_ticks from a game-time horizon (dt-invariant horizon), run. Returns (config, trace)."""
    cfg = load_persona(
        ROOT / "data" / "personas" / f"{persona_id}.yaml",
        DEFAULTS,
        param_overrides=params,
    )
    sc = load_scenario(ROOT / "data" / "scenarios" / f"{scenario_id}.yaml")
    n_ticks = max(1, round(horizon_seconds / cfg.dt))
    _, trace = run_scenario(cfg, sc, n_ticks=n_ticks)
    return cfg, trace


def _reference_config(params: dict | None):
    """A representative config for the param-space components. half_lives and couplings are
    GLOBAL (shared across personas), so any persona yields the same decay/bounds."""
    return load_persona(
        ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS, param_overrides=params
    )


def _stability_penalty(cfg) -> tuple[float, dict]:
    rho = spectral_radius(cfg.decay, cfg.couplings)
    jm = jury_margin(cfg.decay, cfg.couplings)
    penalty = max(0.0, rho - 1.0) + max(
        0.0, -jm
    )  # poles outside circle + Jury violation
    return penalty, {"spectral_radius": rho, "jury_margin": jm}


def _regularization_penalty(cfg) -> tuple[float, dict]:
    """Half-lives within bounds + non-decreasing ordering chains. Margins normalized (range
    width / relative gap) so magnitudes are comparable to the [0..1] predicate penalties."""
    bounds = cfg.param_bounds or {}
    hls = cfg.half_lives
    penalty = 0.0
    detail: dict = {}
    for key, rng in bounds.get("half_lives", {}).items():
        hl = hls.get(key)
        if hl is None:
            continue
        lo, hi = float(rng[0]), float(rng[1])
        width = max(hi - lo, 1e-9)
        over = max(0.0, (lo - hl) / width) + max(0.0, (hl - hi) / width)
        if over > 0.0:
            penalty += over
            detail[f"range:{key}"] = over
    for chain in bounds.get("half_life_ordering", []):
        for a, b in zip(chain, chain[1:]):
            ha, hb = hls.get(a), hls.get(b)
            if ha is None or hb is None:
                continue
            if ha > hb:  # must be non-decreasing (fast -> slow)
                v = (ha - hb) / max(hb, 1e-9)
                penalty += v
                detail[f"order:{a}>{b}"] = v
    return penalty, detail


def loss(
    params: dict | None = None,
    benchmark: dict | None = None,
    weights: dict | None = None,
) -> LossBreakdown:
    """Pure weighted loss + breakdown. params=None means 'baseline placeholders'."""
    weights = weights or LAYER1_WEIGHTS
    components = {k: 0.0 for k in weights}
    detail: dict = {}

    # --- param-space components (no run needed) ---
    ref = _reference_config(params)
    if benchmark is None:
        anchor = float(ref.calibration.get("satisfaction_halfdecay_seconds", 45.0))
        benchmark = layer1_benchmark(anchor)
    sp, sdet = _stability_penalty(ref)
    components["stability"] += sp
    detail["stability"] = sdet
    rp, rdet = _regularization_penalty(ref)
    components["regularization"] += rp
    detail["regularization"] = rdet

    # --- run-based components: simulate every run once, key metrics by run label ---
    metrics_by_run: dict = {}
    traces: dict = {}
    for label, run in benchmark["runs"].items():
        _, trace = simulate(
            params, run["persona"], run["scenario"], run["horizon_seconds"]
        )
        traces[label] = trace
        metrics_by_run[label] = compute_metrics(trace)

    # impulse-response contributions (synthetic run labels): (impulse - control) half-decay metrics.
    frac = float(ref.calibration.get("halfdecay_frac", 0.5))
    for label, spec in benchmark.get("contributions", {}).items():
        metrics_by_run[label] = _contribution_metrics(
            traces[spec["impulse"]],
            traces[spec["control"]],
            spec.get("states", []),
            [tuple(r) for r in spec.get("relations", [])],
            frac,
        )

    preds_detail = []
    for pred in benchmark["predicates"]:
        component = pred["component"]
        res = evaluate(
            pred, metrics_by_run
        )  # extra "component" key is ignored by evaluate
        components.setdefault(component, 0.0)
        components[component] += res.penalty
        preds_detail.append(
            {
                "component": component,
                "satisfied": res.satisfied,
                "penalty": res.penalty,
                "explanation": res.explanation,
            }
        )
    detail["predicates"] = preds_detail

    weighted = {k: weights.get(k, 0.0) * v for k, v in components.items()}
    total = sum(weighted.values())
    return LossBreakdown(
        total=total, components=components, weighted=weighted, detail=detail
    )


# ============================ LAYER 2 (anger-loop gains) ============================
# Frozen base = the layer-1 result, but ONLY the CALIBRATED half-lives (satisfaction); the rest stay
# placeholders (defaults). Layer 2 frees the 5 anger-loop GAINS. Stability is a HARD REJECT (poles
# computed with the calibrated/placeholder half-lives), not a weighted term -- Layer 2 tunes the only
# feedback loop, so a candidate can genuinely make it unstable.

# behavior/ranking carry weight (repair the contrast); 'cooldown' = the ORDERING contract anger>glow;
# 'stability_margin' = a SOFT objective rewarding Jury headroom (atop the hard reject). MONITORED (weight 0):
# satisfaction-anchor + curve (frozen half-lives -> should stay satisfied) and 'decoupling' (anger must still
# respond -- the contrast must not be won by anger going inert).
LAYER2_WEIGHTS: dict[str, float] = {
    "behavior": 2.0,
    "ranking": 2.0,
    "cooldown": 1.0,
    "stability_margin": 1.0,
    "regularization": 1.0,
    "timing": 0.0,
    "curve": 0.0,
    "decoupling": 0.0,
}


def layer2_benchmark(anchor_seconds: float) -> dict:
    """Layer-2 contracts. Reuses the layer-1 runs/contributions; reweights to the burst contrast + the
    cooldown ORDERING (anger lingers longer than the glow, no absolute number) + a decoupling MONITOR."""
    bm = layer1_benchmark(anchor_seconds)
    bm["predicates"] = [
        # CONTRAST repair (weighted): the recruit/veteran burst-vs-suppress litmus.
        {
            "component": "behavior",
            "type": "boolean",
            "persona": "wojslaw_bad",
            "metric": "outburst_fired",
            "equals": True,
        },
        {
            "component": "ranking",
            "type": "comparative",
            "metric": "peak_outburst",
            "a": "wojslaw_bad",
            "b": "halgrim_bad",
            "op": ">",
        },
        # COOLDOWN = ORDER only (anger contribution half-decay > satisfaction glow half-decay); the scale is
        # already pinned by the glow anchor, so anger gets NO absolute number. Provenance: design, candidate
        # for dataset-grounding. Guarded by reachability (anger must actually halve -- else vacuous).
        {
            "component": "cooldown",
            "type": "boolean",
            "persona": "grudge",
            "metric": "half_decay_reached_anger",
            "equals": True,
        },
        {
            "component": "cooldown",
            "type": "comparative",
            "a": "grudge",
            "b": "glow",
            "metric_a": "half_decay_seconds_anger",
            "metric_b": "half_decay_seconds_satisfaction",
            "op": ">",
            "scale": anchor_seconds,
        },
        # MONITORED (weight 0): satisfaction anchor (frozen -> should hold), idle curve, and DECOUPLING --
        # anger must still respond to the scenario (peak_anger floor), or the contrast is hollow.
        {
            "component": "timing",
            "type": "threshold",
            "persona": "glow",
            "metric": "half_decay_seconds_satisfaction",
            "op": "<=",
            "value": anchor_seconds,
            "scale": anchor_seconds,
        },
        {
            "component": "curve",
            "type": "shape",
            "persona": "stoic_idle",
            "metric": "boredom_curve",
            "shape": "monotonic_up",
        },
        {
            "component": "decoupling",
            "type": "threshold",
            "persona": "wojslaw_bad",
            "metric": "peak_anger",
            "op": ">=",
            "value": None,
        },
    ]
    return bm


def frozen_base() -> dict:
    """Layer-2 base = ONLY the CALIBRATED half-lives from calibrated_layer1.yaml (placeholders excluded,
    so a noise value never enters the Jury gate as if it were measured)."""
    raw = yaml.safe_load(CALIBRATED_L1.read_text(encoding="utf-8"))
    return {
        "half_lives": {
            k: float(v["value"])
            for k, v in raw["half_lives"].items()
            if v.get("status") == "calibrated"
        }
    }


def nest_dotted(dotted: dict) -> dict:
    """{'couplings.anger.stress': 0.06} -> {'couplings': {'anger': {'stress': 0.06}}}."""
    out: dict = {}
    for path, val in dotted.items():
        d = out
        parts = path.split(".")
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = float(val)
    return out


def _merge(a: dict, b: dict) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in a.items()}
    for k, v in b.items():
        out[k] = (
            _merge(out[k], v)
            if isinstance(v, dict) and isinstance(out.get(k), dict)
            else v
        )
    return out


def layer2_params(gain_overrides: dict) -> dict:
    """Full param-injection for a layer-2 candidate: frozen base (calibrated half-lives) + the 5 gains."""
    return _merge(frozen_base(), nest_dotted(gain_overrides))


def layer2_stable(gain_overrides: dict) -> tuple[bool, float, float]:
    """The HARD gate, with the calibrated/placeholder half-lives + candidate couplings. Stable iff the
    anger<->stress 2-cycle JURY margin > 0 AND the full spectral radius < 1. The Jury 2-cycle is the
    PRECISE loop criterion (the full radius is dominated by the slow accumulators hunger/fatigue, decay
    ~0.999, not the loop). Drivers (insult gains) are inputs -> not in the matrix. Returns (stable, rho, jury)."""
    ref = _reference_config(layer2_params(gain_overrides))
    rho = spectral_radius(ref.decay, ref.couplings)
    jm = jury_margin(ref.decay, ref.couplings)
    return (jm > 0.0 and rho < 1.0), rho, jm


def _gain_regularization(gain_overrides: dict, bounds: dict) -> float:
    pen = 0.0
    for key, val in gain_overrides.items():
        rng = bounds.get(key)
        if not rng:
            continue
        lo, hi = float(rng[0]), float(rng[1])
        width = max(hi - lo, 1e-9)
        pen += max(0.0, (lo - val) / width) + max(0.0, (val - hi) / width)
    return pen


def loss_layer2(gain_overrides: dict, weights: dict | None = None) -> LossBreakdown:
    """Pure layer-2 loss. STABILITY IS A HARD REJECT computed FIRST: if |pole| >= 1 the candidate is
    rejected (inf) before any run. Otherwise behavior/ranking (weighted) + gain regularization, with the
    satisfaction anchor / curve MONITORED. (The anger-cooldown 'cooldown' contract is wired after GATE 2.)"""
    weights = weights or LAYER2_WEIGHTS
    stable, rho, jm = layer2_stable(gain_overrides)
    if not stable:
        return LossBreakdown(
            total=float("inf"),
            components={"stability_REJECT": rho},
            weighted={},
            detail={"rejected": True, "spectral_radius": rho, "jury_margin": jm},
        )

    params = layer2_params(gain_overrides)
    ref = _reference_config(params)
    bounds = (ref.param_bounds or {}).get("layer2_gains", {})
    reg = _gain_regularization(gain_overrides, bounds)
    # half-life ORDERING (fast emotion -> slow): the co-freed anger/stress must not break it (e.g. stress
    # dropping below the frozen frustration). Same chains as layer 1; relative gap, normalized.
    hls = ref.half_lives
    for chain in (ref.param_bounds or {}).get("half_life_ordering", []):
        for a, b in zip(chain, chain[1:]):
            ha, hb = hls.get(a), hls.get(b)
            if ha is not None and hb is not None and ha > hb:
                reg += (ha - hb) / max(hb, 1e-9)
    components: dict = {"regularization": reg}
    detail: dict = {"spectral_radius": rho, "jury_margin": jm, "dt": ref.dt}

    # SOFT stability-margin objective: reward Jury headroom up to the target (0 once margin >= target).
    target = float(ref.calibration.get("stability_margin_target", 0.0))
    components["stability_margin"] = (
        max(0.0, (target - jm) / target) if target > 0 else 0.0
    )

    anchor = float(ref.calibration.get("satisfaction_halfdecay_seconds", 45.0))
    benchmark = layer2_benchmark(anchor)
    floor = float(ref.calibration.get("decoupling_peak_anger_floor", 0.0))
    for p in benchmark["predicates"]:
        if p.get("component") == "decoupling" and p.get("value") is None:
            p["value"] = floor  # inject the decoupling floor from config
    metrics_by_run, traces = {}, {}
    for label, run in benchmark["runs"].items():
        _, tr = simulate(
            params, run["persona"], run["scenario"], run["horizon_seconds"]
        )
        traces[label] = tr
        metrics_by_run[label] = compute_metrics(tr)
    frac = float(ref.calibration.get("halfdecay_frac", 0.5))
    for label, spec in benchmark.get("contributions", {}).items():
        metrics_by_run[label] = _contribution_metrics(
            traces[spec["impulse"]],
            traces[spec["control"]],
            spec.get("states", []),
            [tuple(r) for r in spec.get("relations", [])],
            frac,
        )

    preds = []
    for pred in benchmark["predicates"]:
        comp = pred["component"]
        res = evaluate(pred, metrics_by_run)
        components.setdefault(comp, 0.0)
        components[comp] += res.penalty
        preds.append(
            {
                "component": comp,
                "satisfied": res.satisfied,
                "penalty": res.penalty,
                "explanation": res.explanation,
            }
        )
    detail["predicates"] = preds

    weighted = {k: weights.get(k, 0.0) * v for k, v in components.items()}
    return LossBreakdown(
        total=sum(weighted.values()),
        components=components,
        weighted=weighted,
        detail=detail,
    )


# ===================== CONTRAST GATE (min-margin / max-penalty) =====================
# For a CONTRAST sub-block (e.g. the prisoner per-persona cold_response threshold) the predicates are
# aggregated by MIN-MARGIN -- maximize the SMALLEST slack, i.e. MINIMIZE the MAX shortfall -- NOT by a
# weighted sum. A sum NEGOTIATES: Layer 2's first attempt gutted the anger loop because the SUM fell
# (big slack elsewhere masked the broken contrast); only a hard gate caught it. min-margin cannot be
# gamed that way -- the only thing that lowers the loss is improving the WORST contrast. This is the
# non-negotiability the three-way prisoner gate needs. loss = -min_margin; feasible iff every slack >= 0.


@dataclass
class ContrastResult:
    min_margin: float  # smallest slack across predicates (the optimizer MAXIMIZES this)
    loss: float  # = -min_margin (the scalar the optimizer MINIMIZES)
    feasible: bool  # every margin >= 0  -> every contrast holds (admissibility)
    margins: dict  # predicate -> signed slack (>=0 satisfied with room, <0 violated)
    binding: str  # the predicate with the SMALLEST slack (what's holding the gate back)


def contrast_gate(margins: dict[str, float]) -> ContrastResult:
    """MIN-MARGIN aggregation, NOT a weighted sum. `margins` maps each contrast predicate to its
    SIGNED slack (>=0 satisfied with room, <0 violated). The gate score is the SMALLEST slack; the
    loss is -min_margin, so minimizing it pushes the WORST contrast's slack up -- the optimizer cannot
    buy one contrast by sacrificing another (a sum could let a large slack hide a violation; max(-slack)
    cannot). feasible iff every slack >= 0 (admissibility: ALL contrasts hold simultaneously)."""
    name, m = min(margins.items(), key=lambda kv: kv[1])
    return ContrastResult(
        min_margin=m,
        loss=-m,
        feasible=all(v >= 0.0 for v in margins.values()),
        margins=dict(margins),
        binding=name,
    )


def _sim_ticks(params: dict | None, persona_id: str, scenario_id: str, n_ticks: int):
    """Tick-count sim (not the game-time horizon): the contrast windows are scenario-fixed (the golden
    tick counts), and a threshold override does not change dt, so a fixed n_ticks is exact + comparable."""
    cfg = load_persona(
        ROOT / "data" / "personas" / f"{persona_id}.yaml",
        DEFAULTS,
        param_overrides=params,
    )
    sc = load_scenario(ROOT / "data" / "scenarios" / f"{scenario_id}.yaml")
    _, trace = run_scenario(cfg, sc, n_ticks=n_ticks)
    return trace


def _cold_from_overture(trace) -> list[float]:
    """cold_response from the OVERTURE tick (the first event -- the provocation) to window-end. Before
    the overture the persona has no reason to be cold, so 'fire EVERY tick' means every tick the grudge
    is LIVE, not every tick of the sim; demanding cold from t0 would mis-state the predicate."""
    start = next((i for i, tk in enumerate(trace.ticks) if tk.event is not None), 0)
    return [tk.potentials["cold_response"] for tk in trace.ticks[start:]]


def _cold_all(trace) -> list[float]:
    return [tk.potentials["cold_response"] for tk in trace.ticks]


def _peak(trace, name: str) -> float:
    return max(tk.potentials[name] for tk in trace.ticks)


def prisoner_margins(theta_cichy: float) -> dict[str, float]:
    """The three-way prisoner contrast as SIGNED MARGINS for contrast_gate. Cichy uses the candidate
    per-persona react.cold_response (theta); Lutek/Halgrim/Wojslaw keep the GLOBAL 0.50 -- a PRIVATE
    threshold decouples the prisoner from the burst litmus BY CONSTRUCTION, so those three are slack
    (REGRESSION GUARDS: assert they didn't move, but theta can't touch them)."""
    th_global = 0.50
    ov = {"thresholds": {"react.cold_response": theta_cichy}}
    res = _sim_ticks(ov, "cichy", "prisoner_bias_resentful", 8)
    neu = _sim_ticks(ov, "cichy", "prisoner_bias_neutral", 8)
    lut = _sim_ticks(None, "lutek", "insult_public", 5)
    woj = _sim_ticks(None, "wojslaw", "same_soup_bad_day", 25)
    hal = _sim_ticks(None, "halgrim", "same_soup_bad_day", 25)
    return {
        # BINDING pair (theta-dependent): resentful crosses EVERY tick from the overture; neutral NEVER does.
        "cichy_resentful_crosses": min(_cold_from_overture(res)) - theta_cichy,
        "cichy_neutral_stays": theta_cichy - max(_cold_all(neu)),
        # REGRESSION guards (theta-INDEPENDENT under a private threshold -> slack by construction):
        "lutek_stays": th_global - max(_cold_all(lut)),
        "wojslaw_bursts": _peak(woj, "outburst")
        - _peak(woj, "cold_response"),  # outburst wins (ordering)
        "halgrim_suppresses": _peak(hal, "cold_response")
        - _peak(hal, "outburst"),  # cold wins (ordering)
    }
