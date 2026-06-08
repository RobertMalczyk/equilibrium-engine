"""calibration -- the derivative-free optimizer LOOP (spec sections 9, 16). The IMPURE half.

Closes the loop around the pure loss (loss.py): Morris screening (SALib) freezes inert
half-lives, then CMA-ES searches the active free-set to minimize loss.total within param_bounds.
cma / SALib / RNG live ONLY here -- they must not leak into loss/simulate/engine (same rule as
numpy stays out of the tick loop). See docs/diagrams/calibration.md (control/optimization-flow).

Layered (spec section 9): the loop is parameterized by a FREE-SET; **layer 1 is its first
instance** (free = half_lives). Later layers reuse this machinery with a different free-set /
weights -- do NOT tune gains here (time scales must be fixed first; the shifting-ground rule).

Acceptance (note: not just "loss dropped"): layer-1 success = weighted loss DOWN **and** the
monitored, unpenalized behavior/ranking components did NOT degrade sharply (they carry weight 0
in layer 1, so the optimizer could lower curve_loss while wrecking a contrast -- caught here).

Output: calibration/calibrated_layer1.yaml with RUN METADATA (seed, frozen params, per-component
breakdown baseline-vs-best, input-config provenance). NEVER overwrites defaults.yaml -- promotion
is a deliberate human step (spec section 16: human curates, doesn't run).

Soft constraints: range + ordering live in regularization_loss (declarative, in config). If the
optimizer keeps "cheating" (violating ordering), the knob is the stability/regularization WEIGHT,
NOT reparameterization (keep structure in the loss, not in a variable transform).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import cma
import numpy as np
import yaml
from SALib.analyze import morris as morris_analyze
from SALib.sample import morris as morris_sample

from engine.loss import loss
from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"


def _cma_seed(seed: int) -> int:
    """cma treats seed=0 (falsy) as 'RANDOMIZE' -> non-deterministic. Force a positive seed so runs are
    reproducible (determinism is a project pillar; a value you can't reproduce is a placeholder in disguise)."""
    return seed if isinstance(seed, int) and seed > 0 else 1


# --- free-set / param plumbing ------------------------------------------------------


def _bounds():
    """Layer-1 free-set = half_lives in param_bounds. Returns (keys, lo, hi, base_half_lives)."""
    cfg = load_persona(ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS)
    hb = (cfg.param_bounds or {}).get("half_lives", {})
    keys = list(hb.keys())
    lo = {k: float(hb[k][0]) for k in keys}
    hi = {k: float(hb[k][1]) for k in keys}
    return keys, lo, hi, dict(cfg.half_lives)


def _params(half_lives: dict) -> dict:
    return {"half_lives": {k: float(v) for k, v in half_lives.items()}}


def objective_total(half_lives: dict) -> float:
    """Pure adapter: the scalar the optimizer minimizes = loss.total for these half_lives."""
    return loss(_params(half_lives)).total


# --- (0) Morris screening -----------------------------------------------------------


def screen_morris(n_trajectories: int = 20, seed: int = 0) -> dict:
    """Elementary-effects sensitivity (mu_star) of loss.total to each half-life, over the bounds.
    Captures interactions (unlike one-at-a-time) -- needed because the states form a coupled loop.
    Cost ~ n_trajectories*(D+1) loss() calls."""
    keys, lo, hi, _ = _bounds()
    problem = {
        "num_vars": len(keys),
        "names": keys,
        "bounds": [[lo[k], hi[k]] for k in keys],
    }
    X = morris_sample.sample(problem, N=n_trajectories, seed=seed)
    Y = np.array([objective_total(dict(zip(keys, row))) for row in X])
    res = morris_analyze.analyze(problem, X, Y, seed=seed)
    return {k: float(mu) for k, mu in zip(keys, res["mu_star"])}


def freeze_inert(sensitivity: dict, rel_threshold: float = 0.05):
    """active = params whose mu_star >= rel_threshold * max(mu_star); rest frozen at baseline.
    If the loss is flat over the box (max mu_star ~ 0), keep everything active (don't freeze blind)."""
    mx = max(sensitivity.values(), default=0.0)
    if mx <= 0.0:
        return list(sensitivity), []
    active = [k for k, v in sensitivity.items() if v >= rel_threshold * mx]
    frozen = [k for k in sensitivity if k not in active]
    return active, frozen


# --- (1-3) CMA-ES optimize ----------------------------------------------------------


@dataclass
class OptResult:
    best_half_lives: dict  # full half_lives (active tuned, frozen at baseline)
    best_total: float
    start_total: float
    n_evals: int
    seed: int


def optimize(
    active_keys,
    x0_half_lives: dict | None = None,
    seed: int = 0,
    maxiter: int = 50,
    sigma0: float = 0.25,
) -> OptResult:
    """CMA-ES over the active half-lives, normalized to [0,1]^D and mapped to bounds (so the wildly
    different scales -- 10s vs 100000s -- don't break the single step size). Frozen keys stay at
    baseline. x0_half_lives lets a test start from a PERTURBED (bad) point to show real descent."""
    keys, lo, hi, base = _bounds()
    start = dict(base) if x0_half_lives is None else {**base, **x0_half_lives}
    act = list(active_keys)

    def to_unit(real):
        return [min(1.0, max(0.0, (real[k] - lo[k]) / (hi[k] - lo[k]))) for k in act]

    def full_from_unit(unit):
        # cast to plain float: CMA-ES yields np.float64, which is not YAML-serializable downstream.
        tuned = {
            k: float(lo[k] + float(u) * (hi[k] - lo[k])) for k, u in zip(act, unit)
        }
        return {**base, **{k: float(start[k]) for k in keys if k not in act}, **tuned}

    n = {"evals": 0}

    def obj(unit):
        n["evals"] += 1
        return loss(_params(full_from_unit(unit))).total

    x0_unit = to_unit(start)
    start_total = obj(list(x0_unit))
    es = cma.CMAEvolutionStrategy(
        list(x0_unit),
        sigma0,
        {"bounds": [0, 1], "seed": _cma_seed(seed), "maxiter": maxiter, "verbose": -9},
    )
    es.optimize(obj)
    best_full = full_from_unit(es.result.xbest)
    return OptResult(
        best_half_lives=best_full,
        best_total=loss(_params(best_full)).total,
        start_total=start_total,
        n_evals=n["evals"],
        seed=seed,
    )


# --- (4) acceptance -----------------------------------------------------------------


def accept(baseline, best, monitor_tol: float = 0.05):
    """Layer-1 success: weighted loss did not increase AND monitored (weight-0) behavior/ranking
    did not degrade beyond monitor_tol. Returns (ok, reasons)."""
    reasons = {"loss_not_increased": best.total <= baseline.total + 1e-12}
    ok = reasons["loss_not_increased"]
    for comp in ("behavior", "ranking"):
        not_degraded = (
            best.components.get(comp, 0.0)
            <= baseline.components.get(comp, 0.0) + monitor_tol
        )
        reasons[f"{comp}_not_degraded"] = not_degraded
        ok = ok and not_degraded
    return ok, reasons


# --- (5) run + emit -----------------------------------------------------------------


def _provenance() -> dict:
    data = DEFAULTS.read_bytes()
    return {
        "defaults_path": str(DEFAULTS.relative_to(ROOT)),
        "defaults_sha256": hashlib.sha256(data).hexdigest()[:16],
    }


def _bd(b) -> dict:
    return {"total": b.total, "components": b.components, "weighted": b.weighted}


def run_layer1(
    seed: int = 1,
    n_trajectories: int = 20,
    maxiter: int = 50,
    x0_half_lives: dict | None = None,
    out_path: str | Path | None = None,
) -> dict:
    """Full layer-1 pass: baseline -> Morris screen/freeze -> CMA-ES -> accept -> emit report.
    Returns the report dict; writes it to out_path (YAML) if given. Never touches defaults.yaml."""
    keys, _, _, _ = _bounds()
    baseline = loss(None)
    sensitivity = screen_morris(n_trajectories=n_trajectories, seed=seed)
    active, frozen = freeze_inert(sensitivity)
    opt = optimize(active, x0_half_lives=x0_half_lives, seed=seed, maxiter=maxiter)
    best = loss(_params(opt.best_half_lives))
    accepted, reasons = accept(baseline, best)

    report = {
        "layer": 1,
        "free_set": keys,
        "active": active,
        "frozen": frozen,
        "morris_mu_star": sensitivity,
        "optimizer": f"cma=={cma.__version__}",
        "seed": seed,
        "n_evals": opt.n_evals,
        "input_config": _provenance(),
        "baseline": _bd(baseline),
        "best": _bd(best),
        "calibrated_half_lives": opt.best_half_lives,
        "accepted": accepted,
        "acceptance_reasons": reasons,
        "note": "PLACEHOLDER->CALIBRATED candidate; promote to defaults.yaml only by a deliberate human step.",
    }
    if out_path is not None:
        Path(out_path).write_text(
            yaml.safe_dump(report, sort_keys=False), encoding="utf-8"
        )
    return report


# ============================ LAYER 2 optimizer (anger loop) ============================
from engine.loss import frozen_base, loss_layer2  # noqa: E402


def _layer2_free():
    """Layer-2 free-set = the 5 anger-loop gains + ONLY anger & stress half-lives (they enter the Jury
    bound and were never calibrated at layer 1 -- D7). satisfaction stays frozen; everything else frozen."""
    cfg = load_persona(ROOT / "data" / "personas" / "halgrim.yaml", DEFAULTS)
    pb = cfg.param_bounds or {}
    g = pb.get("layer2_gains", {})
    hl = pb.get("half_lives", {})
    keys = list(g.keys()) + ["half_lives.anger", "half_lives.stress"]
    lo = {k: float(g[k][0]) for k in g}
    hi = {k: float(g[k][1]) for k in g}
    for s in ("anger", "stress"):
        lo[f"half_lives.{s}"], hi[f"half_lives.{s}"] = float(hl[s][0]), float(hl[s][1])
    return keys, lo, hi


def _run_layer2_once(seed: int, maxiter: int = 20) -> dict:
    """One CMA run over the 5 anger-loop gains + co-freed anger/stress half-lives, with the renegotiation
    gate (flags: contrast / cooldown / margin / decoupling / tension / success). Returns the report; does
    NOT write -- the multi-start wrapper writes the chosen success."""
    keys, lo, hi = _layer2_free()

    def to_real(unit):
        # cast to plain float: CMA-ES yields np.float64, which is not YAML-serializable downstream.
        return {
            k: float(lo[k] + float(u) * (hi[k] - lo[k])) for k, u in zip(keys, unit)
        }

    def obj(unit):
        t = loss_layer2(to_real(unit)).total
        return (
            1e9 if t == float("inf") else t
        )  # hard-rejected -> large finite so CMA can rank

    x0 = []
    base_vals = {
        "couplings.anger.stress": 0.04,
        "couplings.stress.anger": 0.03,
        "couplings.anger.frustration": 0.05,
        "gains.anger.insult": 0.35,
        "gains.frustration.insult": 0.20,
        "half_lives.anger": 30.0,
        "half_lives.stress": 70.0,
    }
    for k in keys:
        x0.append(min(1.0, max(0.0, (base_vals[k] - lo[k]) / (hi[k] - lo[k]))))
    es = cma.CMAEvolutionStrategy(
        x0,
        0.25,
        {"bounds": [0, 1], "seed": _cma_seed(seed), "maxiter": maxiter, "verbose": -9},
    )
    es.optimize(obj)
    best = to_real(es.result.xbest)
    bd = loss_layer2(best)

    comp = bd.components
    {p["component"]: p["satisfied"] for p in bd.detail["predicates"]}
    contrast_repaired = comp.get("behavior", 1) == 0.0 and comp.get("ranking", 1) == 0.0
    cooldown_met = comp.get("cooldown", 1) == 0.0
    margin_ok = comp.get("stability_margin", 1) <= 1e-9
    decoupling_ok = comp.get("decoupling", 1) == 0.0
    tension_irreducible = not (
        contrast_repaired and cooldown_met
    )  # the HARD contracts conflict
    # A contrast won by DECOUPLING anger (anger inert, peak below floor) is hollow -> also blocks.
    success = contrast_repaired and cooldown_met and decoupling_ok

    if tension_irreducible:
        note = "BLOCKED: hard contracts (contrast AND cooldown) cannot both be met -> escalate (revisit anchor / re-open a layer)."
    elif not decoupling_ok:
        note = (
            "BLOCKED (decoupling): contrast+cooldown+margin met, but the optimizer GUTTED the "
            "anger<->stress 2-cycle to the floor for margin and propped the burst up with the DRIVERS -- "
            "peak_anger fell below the floor, anger is now an isolated counter, not stress-coupled. The "
            "lower coupling bound was insufficient. ESCALATE: raise the lower bound / decide whether the "
            "margin is worth decoupling anger."
        )
    else:
        note = (
            "accepted: hard contracts met, anger still coupled. If margin_ok is False, the soft margin "
            "could not reach target without breaking the burst -> the binding constraint is the frozen "
            "outburst threshold (a later threshold sub-layer), not a gain."
        )

    jury_before = round(
        loss_layer2(base_vals).detail["jury_margin"], 6
    )  # placeholder gains + anger30/stress70
    flags = {
        "contrast_repaired": contrast_repaired,
        "cooldown_met": cooldown_met,
        "margin_ok": margin_ok,
        "decoupling_ok": decoupling_ok,
        "tension_irreducible": tension_irreducible,
        "success": success,
    }
    # Status-marked calibrated values (CALIBRATED-AT-LAYER-2, NOT layer-1 placeholders).
    calibrated = {
        k: {
            "value": round(best[k], 5),
            "kind": ("half_life" if k.startswith("half_lives.") else "gain"),
            "status": "calibrated-at-layer-2",
        }
        for k in keys
    }
    report = {
        "layer": 2,
        "seed": seed,
        "optimizer": f"cma=={cma.__version__}",
        "reads_on_top_of": (
            f"calibrated_layer1.yaml (satisfaction={frozen_base()['half_lives'].get('satisfaction')}) "
            "+ defaults.yaml (placeholders); both untouched"
        ),
        "free_set": keys,
        "calibrated": calibrated,
        "provenance": {
            "flags": flags,
            "jury_margin_before": jury_before,
            "jury_margin_after": round(bd.detail["jury_margin"], 6),
            "spectral_radius": round(bd.detail["spectral_radius"], 6),
            "dt": round(bd.detail["dt"], 4),
            "components": {k: round(v, 4) for k, v in comp.items()},
        },
        "flags": flags,
        "written": False,
        "note": note,
    }
    return report


def _layer1_dt() -> float:
    """The dt of the layer-1 base (calibrated satisfaction + placeholders, no layer-2 anger/stress move)."""
    base = {
        "couplings.anger.stress": 0.04,
        "couplings.stress.anger": 0.03,
        "couplings.anger.frustration": 0.05,
        "gains.anger.insult": 0.35,
        "gains.frustration.insult": 0.20,
        "half_lives.anger": 30.0,
        "half_lives.stress": 70.0,
    }
    return loss_layer2(base).detail["dt"]


def run_layer2(
    seeds=(1, 2, 3, 4, 5),
    maxiter: int = 20,
    select: str = "first",
    out_path: str | Path | None = None,
) -> dict:
    """MULTI-START basin search. Layer 2 has a coupled-GOOD basin AND a decoupled-HOLLOW basin (the
    decoupling monitor blocks the latter); a single seed is a roulette, so try the seeds and collect the
    gate-SUCCESSES (coupled, mechanism-based). The successes are loss-equivalent, so SELECT among them:
      - 'first'      -> the first gate-success (basin-search default).
      - 'dt_neutral' -> the success whose dt is CLOSEST to the layer-1 base dt (least cross-layer
                        perturbation: keeps the frozen satisfaction anchor valid, no dt drift). RE-COMPUTED
                        here on the current base, not carried over.
    If none succeed, return the last (blocked) report. Writes the chosen iff success; never overwrites
    defaults. (cma seed=0 randomizes -> seeds must be positive; see _cma_seed.)"""
    if isinstance(seeds, int):
        seeds = (seeds,)
    tried, reports, last = [], [], None
    for s in seeds:
        last = _run_layer2_once(s, maxiter)
        tried.append(
            {
                "seed": s,
                "success": last["flags"]["success"],
                "dt": last["provenance"]["dt"],
                "anger": last["calibrated"]["half_lives.anger"]["value"],
            }
        )
        if last["flags"]["success"]:
            reports.append(last)
        if select == "first" and last["flags"]["success"]:
            break

    if not reports:
        chosen = last  # no basin succeeded -> blocked report
    elif select == "dt_neutral":
        ref_dt = _layer1_dt()
        chosen = min(reports, key=lambda r: abs(r["provenance"]["dt"] - ref_dt))
        chosen["selected_by"] = f"dt_neutral (ref layer-1 dt={round(ref_dt, 4)})"
    else:
        chosen = reports[0]
    chosen["seeds_tried"] = tried
    if chosen["flags"]["success"] and out_path is not None:
        chosen["written"] = True
        Path(out_path).write_text(
            yaml.safe_dump(chosen, sort_keys=False), encoding="utf-8"
        )
    return chosen
