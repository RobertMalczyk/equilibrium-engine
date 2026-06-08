"""eval/calibrated.py -- load a persona config with the CALIBRATED dynamics stacked (M7.5 Part A).

The golden/litmus path runs on calibration/defaults.yaml (placeholders) ON PURPOSE -- frozen regression.
The EVAL / day path should run on the believable CALIBRATED dynamics: frozen Layer-1 (calibrated half-lives)
+ Layer-2 (anger<->stress loop gains, more margin) + the recovery re-pacing (calibrated_recovery.yaml:
hunger drift) that M7.5 Part A added to fix the long-day saturation (D10). This stacks all three into one
param_overrides dict for load_persona.
"""

from __future__ import annotations

import math
from pathlib import Path

import yaml

from engine.loss import nest_dotted
from engine.schema import PersonaConfig
from engine.yaml_io import load_persona

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
CAL = ROOT / "calibration"


def _merge(a: dict, b: dict) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in a.items()}
    for k, v in b.items():
        out[k] = (
            _merge(out[k], v)
            if isinstance(v, dict) and isinstance(out.get(k), dict)
            else v
        )
    return out


def recovery_overrides() -> dict:
    """param_overrides stacking calibrated Layer-1 (the calibrated half-lives) + Layer-2 (loop gains/half-lives)
    + the recovery re-pacing (hunger drift) -- the believable-day dynamics for the eval path."""
    l1 = yaml.safe_load((CAL / "calibrated_layer1.yaml").read_text(encoding="utf-8"))
    l2 = yaml.safe_load((CAL / "calibrated_layer2.yaml").read_text(encoding="utf-8"))
    rec = yaml.safe_load((CAL / "calibrated_recovery.yaml").read_text(encoding="utf-8"))
    ov = {
        "half_lives": {
            k: float(v["value"])
            for k, v in l1["half_lives"].items()
            if v.get("status") == "calibrated"
        }
    }
    ov = _merge(ov, nest_dotted({k: v["value"] for k, v in l2["calibrated"].items()}))
    ov = _merge(ov, nest_dotted({k: v["value"] for k, v in rec["calibrated"].items()}))
    return ov


def _drift_to_reach(level: float, t_sec: float, half_life: float, dt: float) -> float:
    """Per-tick drift for an accumulator (setpoint 0) to rise from 0 to `level` in `t_sec` real seconds, at a
    GIVEN half-life. Closed form of x_{t+1}=decay*x+drift: x(n)=x*(1-decay^n), x*=drift/(1-decay)."""
    decay = 2.0 ** (-dt / half_life)
    n = max(1.0, t_sec / dt)
    return level * (1.0 - decay) / (1.0 - decay**n)


def _accum_from(
    level: float, t_sec: float, ceiling: float, dt: float
) -> tuple[float, float]:
    """Derive BOTH (half_life, drift) so an accumulator rises to `level` in `t_sec` AND asymptotes at
    `ceiling`. From x*=ceiling=drift/(1-decay) and level=ceiling*(1-decay^n): decay=(1-level/ceiling)^(1/n)."""
    n = max(1.0, t_sec / dt)
    decay = (1.0 - level / ceiling) ** (1.0 / n)
    half_life = -dt / math.log2(decay)
    drift = ceiling * (1.0 - decay)
    return half_life, drift


def timescale_overrides() -> dict:
    """param_overrides for the BELIEVABLE timescale, DERIVED from calibrated_timescale.yaml's few inputs --
    ONE knob (time_scale, scales every half-life -> dt -> the whole emotional/relational world) + the day's
    physiological DURATIONS (rise times / night length, which the per-tick drifts/discharge/timeout are
    derived from) + 2 genuine coupling gains. No hand-tuned per-tick magic numbers. Stacked on
    recovery_overrides; the engine scales the half-lives from tick.time_scale (see engine/yaml_io).
    Verified by eval/timescale_keeper.py against calibration/timescale_ground_truth.yaml."""
    ts = yaml.safe_load((CAL / "calibrated_timescale.yaml").read_text(encoding="utf-8"))
    base = load_persona(
        ROOT / "data" / "personas" / "branic.yaml",
        DEFAULTS,
        param_overrides=recovery_overrides(),
    )  # the eval half-lives at time_scale 1 (Branic = ref)
    k = float(ts["time_scale"])
    dt = (
        min(base.half_lives.values()) * k / 10.0
    )  # dt after the knob scales every half-life (Nyquist 10)
    dur, ceil = ts["durations"], ts["ceilings"]

    # (a) THE KNOB scales every half-life (emotions, relations, boredom, sleep_pressure, duty) -- shape kept.
    hl = {s: v * k for s, v in base.half_lives.items()}
    # (b) hunger & fatigue: derive HL + drift from their RISE time and CEILING (so they cap believably, not
    #     run to 1.0 the way the uniform scale would -> a meal can still cut hunger back below half).
    hl["hunger"], hunger_drift = _accum_from(
        0.50, dur["hunger_to_half"], ceil["hunger"], dt
    )
    hl["fatigue"], fatigue_drift = _accum_from(
        0.70, dur["fatigue_to_high"], ceil["fatigue"], dt
    )
    # (c) boredom: seek FIRES when urge_boredom crosses urge_start; for the reference persona (fatigue ~0
    #     early) that is boredom level L_seek = urge_start/(w_boredom*nov_factor). Derive the drift to reach
    #     it in `boredom_to_seek` (HL scaled by the knob). who-bores-first stays trait-driven (the nov_factor).
    w = base.derived_weights.get("urge_boredom", {})
    nov_factor = max(
        0.0,
        1.0
        + w.get("boredom_novelty_k", 0.0)
        * (base.traits["novelty_seeking"] - w.get("boredom_novelty_ref", 0.5)),
    )
    l_seek = base.thresholds["urge_start"] / (w.get("boredom", 1.0) * nov_factor)
    boredom_drift = _drift_to_reach(l_seek, dur["boredom_to_seek"], hl["boredom"], dt)

    night_ticks = dur["night_length"] / dt  # sleep_pressure 1.0 -> 0.10 over the night
    ov = {
        "half_lives": {s: round(v, 3) for s, v in hl.items()},
        "drifts": {
            "boredom": round(boredom_drift, 6),
            "hunger": round(hunger_drift, 6),
            "fatigue": round(fatigue_drift, 6),
        },
        "action_params": {
            "sleep": {
                "per_tick": {
                    "sleep_pressure": round(-0.90 / night_ticks, 6),
                    "hunger": round(dur["wake_hunger"] / night_ticks, 6),
                }
            }
        },
        "thresholds": {
            "seeking_timeout_ticks": max(1, round(dur["seeking_giveup"] / dt))
        },
        "couplings": {
            s: {kk: float(vv) for kk, vv in row.items()}
            for s, row in ts["couplings"].items()
        },
    }
    return _merge(recovery_overrides(), ov)


def load_eval_persona_timescale(persona_id: str) -> PersonaConfig:
    """Eval persona with the believable per-dimension time constants (a believable DAY; see
    timescale_overrides). Use for the day corpus / story once the keeper passes."""
    return load_persona(
        ROOT / "data" / "personas" / f"{persona_id}.yaml",
        DEFAULTS,
        param_overrides=timescale_overrides(),
    )


def believable_day_layout() -> dict:
    """The day tick layout at the believable per-dimension dt -- shared by the generator, the corpus
    runner and the stories so they agree. day_ticks ~ 24 h, waking_ticks ~ 17 h (dawn->nightfall),
    the night fills the rest. (dt is universal across personas: the fast cluster sets it.)"""
    dt = load_eval_persona_timescale("branic").dt
    return {
        "dt": dt,
        "day_ticks": round(86400 / dt),
        "waking_ticks": round(17 * 3600 / dt),
    }


def load_eval_persona(persona_id: str, time_scale: float = 1.0) -> PersonaConfig:
    """A persona loaded with the calibrated + recovery dynamics (for the eval / day-corpus path).

    ``time_scale`` (default 1.0 = identity) uniformly slows ALL time constants so a believable DAY emerges
    from the placeholder-fast emotions (anger half-life 30s). It is a pure clock reparametrization: the
    tick-by-tick trace is bit-identical, only dt (seconds/tick) stretches (see engine/yaml_io). Eval-only --
    defaults stay at 1.0 so the frozen golden/litmus path is untouched."""
    ov = recovery_overrides()
    if time_scale != 1.0:
        ov = _merge(ov, {"tick": {"time_scale": float(time_scale)}})
    return load_persona(
        ROOT / "data" / "personas" / f"{persona_id}.yaml", DEFAULTS, param_overrides=ov
    )
