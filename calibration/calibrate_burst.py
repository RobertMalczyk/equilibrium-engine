"""M20.1 burst calibration — staged, deterministic, provenance-tracked (plan §4).

STAGES C1–C5 (all here): C1 k_esc feasibility frontier (solve_c1) -> C2 extinction (solve_c2,
latched_cooldown) -> C3 latch geometry (solve_c3) -> C4 Loop-2 sign (solve_c4, loop2_contrast) ->
C5 displacement bar (solve_c5). All write calibration/calibrated_burst.yaml (overlay; defaults stay
neutral, goldens bit-identical until the overlay is wired at plan step 4). Remaining: turn the
refractory-edge weight ON, wire the overlay, run the 1400-scenario regression.

C1 detail — the k_esc feasibility frontier. Reads the frozen Layer-2 loop
(couplings + decays) and the MEASURED operating-point envelope (eval/burst_operating_points.json,
produced by eval/measure_operating_points.py) and chooses the per-edge escalation k_esc analytically:

  escalated 2-cycle Jury margin at (a*, s*):
      margin(k) = (1-d_s)(1-d_a) - g_as*(1+k*a*) * g_sa*(1+k*s*)
  stable iff margin >= 0. The escalation product (1+k*a*)(1+k*s*) may grow up to
      R = (1-d_s)(1-d_a) / (g_as*g_sa)
  before the loop goes locally unstable (the spiral = the burst).

KEY MEASURED FINDING (C1): the corpus >=3-way coincidences do NOT reach a higher (anger, stress)
operating point than the frequent <=2-way ones — BOTH top out near anger~0.70 / stress~0.52. So k_esc
CANNOT gate the burst on "coincidence count": there is no (anger,stress) threshold separating triples
from pairs. This is the plan §8 feasibility tension, now measured. Resolution (topology-now rule):
k_esc is set so the loop stays linearly stable across the ENTIRE observed operating envelope (every
frequent pair, up to the observed max) and only spirals once BOTH states are pushed into the
SATURATION BAND above that envelope (anger>=0.80, stress>=0.60). The latch band thresholds (stage C3)
therefore carry the "rare and earned" selectivity; k_esc only supplies the in-band spiral.

  feasible window:  k_lo = smallest k that spirals at the band entry (BAND_ENTRY)
                    k_hi = largest k that keeps the MAX observed frequent pair stable
  choice: the low end of the window (max stability margin at the frequent operating points).

Deterministic; no optimizer needed (closed-form). Run:
  PYTHONPATH=. python eval/measure_operating_points.py   # produce the envelope first
  PYTHONPATH=. python calibration/calibrate_burst.py     # choose k_esc, write calibrated_burst.yaml
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import yaml

from eval.calibrated import believable_day_layout, load_eval_persona

ROOT = Path(__file__).resolve().parents[1]
ENV_JSON = ROOT / "eval" / "burst_operating_points.json"
OUT = ROOT / "calibration" / "calibrated_burst.yaml"

# the saturation band the latch will sit on (stage C3 will pin these; C1 uses them as the spiral
# target). Chosen just ABOVE the measured frequent-pair ceiling (anger max ~0.70, stress max ~0.53).
BAND_ENTRY = {"anger": 0.80, "stress": 0.60}

# --- stage C2 (extinction) anchors -----------------------------------------------------------
# The single ABSOLUTE anchor for the burst layer's time axis: the believable cool-down duration.
# The design note calls a burst a self-extinguishing episode that comes off the ceiling in "about
# an hour" of game time. We express it in TICKS via the believable day layout (dt ~120s/tick).
T_COOL_HOURS = 1.0
# theta_burst_exit (anger) — the latch release hysteresis (stage C3), also the C2 cool-down return
# target (C2 and C3 share it: C2 sizes extinction to reach it within T_cool, C3 uses it as the latch
# exit). Anchored to the measured envelope: just BELOW the frequent <=2-way anger p99 (~0.4426), so
# the latch releases once acute anger has fallen back beneath the ordinary reactive ceiling and
# CANNOT re-arm from a normal provocation. Hysteresis gap to enter.anger (0.80) is 0.40 — chatter-free.
THETA_BURST_EXIT = 0.40
# the worst-case start of the cool-down: full saturation. If the latched loop returns from (1,1)
# within T_cool, it returns from any lower in-band plateau at least as fast.
CEILING = {"anger": 1.0, "stress": 1.0}


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def latched_cooldown(
    decay: dict[str, float],
    g_as: float,
    g_sa: float,
    k: float,
    ext_a: float,
    ext_s: float,
    a0: float = 1.0,
    s0: float = 1.0,
    n: int = 240,
) -> dict:
    """Simulate the latched anger<->stress loop with extinction, in the ABSENCE of fresh provocation
    (the self-extinguishing episode). Mirrors engine/update.py exactly for the loop states:
        a <- decay_a*a + g_sa*(1+k*s)*s - ext_a*a      (stress -> anger, escalated)
        s <- decay_s*s + g_as*(1+k*a)*a - ext_s*s      (anger  -> stress, escalated)
    setpoints/drifts/idle-recovery are 0 here (an active outburst episode, no external input). This
    is the analytic cool-down used to size extinction; the full-scenario check is G3* after the
    overlay is wired. Returns the trajectory, monotonicity, and tick of return below THETA_BURST_EXIT.
    Single source of the C2 cooling math (imported by tests/test_burst_calibration.py)."""
    a, s = a0, s0
    traj = [(a, s)]
    mono = True
    cross = None
    prev_a = a
    for i in range(1, n + 1):
        an = _clamp01(decay["anger"] * a + g_sa * (1.0 + k * s) * s - ext_a * a)
        sn = _clamp01(decay["stress"] * s + g_as * (1.0 + k * a) * a - ext_s * s)
        a, s = an, sn
        traj.append((a, s))
        if a > prev_a + 1e-9:
            mono = False
        prev_a = a
        if cross is None and a < THETA_BURST_EXIT:
            cross = i
    return {"traj": traj, "mono": mono, "cross": cross, "final": (a, s)}


def _t_cool_ticks() -> int:
    dt = float(believable_day_layout()["dt"])  # seconds per tick (believable timescale)
    return round(T_COOL_HOURS * 3600.0 / dt)


def _loop_constants():
    c = load_eval_persona(
        "wojslaw"
    )  # couplings/decays are persona-independent (frozen Layer-2)
    d = c.decay
    g_as = c.couplings["stress"]["anger"]  # anger -> stress
    g_sa = c.couplings["anger"]["stress"]  # stress -> anger
    bound = (1.0 - d["stress"]) * (1.0 - d["anger"])
    return bound, g_as, g_sa, d


def _factor(a: float, s: float, k: float) -> float:
    return (1.0 + k * a) * (1.0 + k * s)


def _k_for_factor(a: float, s: float, target: float) -> float:
    """Smallest k>=0 with (1+k a)(1+k s) = target. Solve the quadratic k^2(a s)+k(a+s)+(1-target)=0."""
    A, B, C = a * s, a + s, 1.0 - target
    disc = B * B - 4 * A * C
    return (-B + disc**0.5) / (2 * A)


def solve_c1() -> dict:
    bound, g_as, g_sa, d = _loop_constants()
    R = bound / (g_as * g_sa)  # max escalation factor before instability
    env = json.loads(ENV_JSON.read_text(encoding="utf-8"))

    # k_hi: keep the MAX observed frequent (<=2-way) pair linearly stable.
    a_pair, s_pair = env["le2_anger_max"], env["le2_stress_max"]
    k_hi = _k_for_factor(a_pair, s_pair, R)
    # k_lo: spiral at the saturation-band entry.
    k_lo = _k_for_factor(BAND_ENTRY["anger"], BAND_ENTRY["stress"], R)

    # choose the LOW end of [k_lo, k_hi] (max stability margin at the frequent operating points),
    # rounded to 2 dp toward the stable side. If the window is empty/inverted, flag it.
    feasible = k_lo <= k_hi
    import math

    k = (
        math.floor(k_lo * 100 + 0.5) / 100
    )  # round k_lo to 2dp; it already spirals at the band
    if k < k_lo:  # rounding dipped below the spiral floor -> nudge up one step
        k += 0.01
    if k > k_hi:
        k = round((k_lo + k_hi) / 2, 2)

    return {
        "bound": bound,
        "g_as": g_as,
        "g_sa": g_sa,
        "R": R,
        "pair": (a_pair, s_pair),
        "k_lo": k_lo,
        "k_hi": k_hi,
        "feasible": feasible,
        "k": k,
        "env": env,
    }


def _lambda_max(decay, g_as, g_sa, k, ext_a, ext_s, a, s) -> float:
    """Spectral radius of the extinction-damped escalated loop linearised at (a, s). With extinction
    the self-retention drops to (decay - ext); the burst is bounded iff this stays < 1."""
    da = decay["anger"] - ext_a
    ds = decay["stress"] - ext_s
    cross = g_sa * (1.0 + k * s) * g_as * (1.0 + k * a)
    return ((da + ds) + math.sqrt((da - ds) ** 2 + 4.0 * cross)) / 2.0


def solve_c2(k: float) -> dict:
    """C2 — extinction. Given k_esc (C1), choose the SMALLEST extinction (longest believable, still
    bounded, episode) that returns the fully-saturated latched loop below THETA_BURST_EXIT within T_cool.

    One scalar free parameter beta: ext_x = beta * (1 - decay_x). Splitting by each state's native
    decay rate makes anger relax faster than stress automatically (the design note's "anger falls
    fast, stress cools slower") WITHOUT inventing a ratio — the split is inherited from the frozen
    Layer-2 half-lives. beta is fixed by the single absolute anchor T_cool; everything else relative.
    """
    c = load_eval_persona("wojslaw")
    decay = c.decay
    g_as = c.couplings["stress"]["anger"]
    g_sa = c.couplings["anger"]["stress"]
    one_minus = {"anger": 1.0 - decay["anger"], "stress": 1.0 - decay["stress"]}
    t_cool = _t_cool_ticks()

    # smallest beta (0.01 grid) whose full-saturation cool-down returns below THETA_BURST_EXIT within
    # t_cool ticks and is monotone (stays down, no re-spiral).
    beta = None
    b = 0.0
    while b <= 3.0 + 1e-9:
        ext_a = b * one_minus["anger"]
        ext_s = b * one_minus["stress"]
        r = latched_cooldown(decay, g_as, g_sa, k, ext_a, ext_s)
        if r["mono"] and r["cross"] is not None and r["cross"] <= t_cool:
            beta = round(b, 2)
            break
        b = round(b + 0.01, 2)
    if beta is None:
        raise SystemExit("C2: no beta in [0,3] returns within T_cool — check k_esc / model")

    ext_a = round(beta * one_minus["anger"], 6)
    ext_s = round(beta * one_minus["stress"], 6)
    r = latched_cooldown(decay, g_as, g_sa, k, ext_a, ext_s)
    lam_ceiling = _lambda_max(decay, g_as, g_sa, k, ext_a, ext_s, 1.0, 1.0)
    return {
        "beta": beta,
        "ext_a": ext_a,
        "ext_s": ext_s,
        "t_cool": t_cool,
        "cross": r["cross"],
        "mono": r["mono"],
        "lam_ceiling": lam_ceiling,
        "decay": decay,
    }


def solve_c5(c3: dict, env: dict) -> dict:
    """C5 — theta_displace (the displacement bar) + the displaced relational discount.

      theta_displace = midpoint of the C3 latch hysteresis band [exit, enter.anger]. Displacement
        ("kicking the dog": a sourced event catches the spent fury while latched) fires only in the
        DEEP half of the episode — above typical reactive anger (the frequent <=2-way anger p99) and
        below the plateau where the latch arms (enter.anger). As anger cools through the lower half of
        the band the gate closes again, before the latch itself releases at exit.
      displaced_relational_discount = 0.0: the grudge booked on the INNOCENT target is fully transient
        ("snapped at her", no durable resentment) — the intended default (the fabricated-nemesis
        runaway is excluded by construction). Nonzero ONLY with a story/persona target that carries a
        provenance-backed partial grudge; none here, so it stays 0.
    """
    theta = round((c3["exit"] + c3["enter_a"]) / 2.0, 2)
    le2_a_p99 = env["le2_anger_p99"]
    assert c3["exit"] < theta < c3["enter_a"], "theta_displace must sit inside the latch band"
    assert theta > le2_a_p99, "theta_displace must be above typical reactive anger (frequent p99)"
    prov_theta = (
        f"displacement bar = {theta} = midpoint of the C3 latch band [exit {c3['exit']}, enter.anger "
        f"{c3['enter_a']}]. Displacement fires only in the DEEP half of the burst: above typical "
        f"reactive anger (frequent <=2-way anger p99 {le2_a_p99:.4f}) and below the plateau where the "
        f"latch arms ({c3['enter_a']}); the gate closes as anger cools through the band's lower half, "
        f"before the latch releases at exit. Validated by the existing G5 displacement tests."
    )
    prov_discount = (
        "displaced relational discount = 0.0: the discharge onto an INNOCENT bystander books NO "
        "durable grudge (fully transient — 'snapped at her'); the intended default that excludes the "
        "fabricated-nemesis runaway. Nonzero only for a story/persona target with a provenance-backed "
        "partial grudge (none here)."
    )
    return {"theta_displace": theta, "discount": 0.0, "prov_theta": prov_theta, "prov_discount": prov_discount}


def loop2_contrast(seek_cost: float, window: int = 15) -> dict:
    """Run the rich and barren mock-world scenarios (lutek, STRESSED start) with the given burst
    seek stress-cost and return the mean per-tick STRESS slope of each. Single source of the C4
    Loop-2 contrast (imported by tests). Rich world: the world confirms a self_activity (relief,
    stress -0.04/tick) -> stress descends. Barren world: fruitless seeking -> the seek stress-cost
    accumulates -> stress winds up. Deterministic (the mock world is seeded)."""
    from eval.burst_eval import STRESSED, Scenario, _cfg
    from eval.mock_world import MockWorld, run_with_world

    ov = {"action_params": {"seek_stimulus": {"per_tick": {"stress": seek_cost}}}}
    cfg = _cfg("lutek", ov)
    relief = abs(
        float(cfg.action_params.get("self_activity", {}).get("per_tick", {}).get("stress", 0.0))
    )

    def _slope(novelty_start: float, replenish: float) -> float:
        sc = Scenario(id="loop2", persona="lutek", initial_overrides=STRESSED, events=())
        tr = run_with_world(
            cfg, sc, MockWorld(novelty_start=novelty_start, replenish_per_tick=replenish), window
        )
        s = [tk.state_after_post.global_state["stress"] for tk in tr.ticks]
        return (s[-1] - s[0]) / len(s)

    rich = _slope(1.0, 0.02)
    barren = _slope(0.0, 0.0)
    return {"rich": rich, "barren": barren, "margin": barren - rich, "relief": relief}


def solve_c4() -> dict:
    """C4 — Loop 2 (relief-seeking through the world). Two free edges:
      B2 seek_stimulus.per_tick.stress: the FORWARD edge (fruitless looking wears you down). Set to
         HALF the calibrated rich-world relief rate |self_activity.stress| (a deliberate asymmetry:
         relief from engaging must DOMINATE the wind-up from looking, so a rich world resolves stress;
         the looking cost is 'small'). This is the operative Loop-2 knob.
      B1 derived_weights.urge_boredom.stress: the stress->seek RETURN edge. MEASURED FINDING: the
         rich/barren contrast does NOT identify it — boredom already drives seeking in every
         burst-relevant (wound-up) scenario, and making pure-stress (boredom 0) seek needs w_s ~ the
         seek threshold (~0.85), a large fragile hand-set value. Per topology-now / never-invent, the
         edge stays NEUTRAL (0); Loop 2 is carried by B2.
    Validated by the mock-world contrast: with B2 the rich slope is negative (relief) and the barren
    slope positive (wind-up into burst range); at cost 0 the barren world does not wind up.
    """
    probe = loop2_contrast(0.02)
    seek_cost = round(0.5 * probe["relief"], 4)  # half the relief rate (0.5 * 0.04 = 0.02)
    chosen = loop2_contrast(seek_cost)
    off = loop2_contrast(0.0)
    return {
        "seek_cost": seek_cost,
        "w_s": 0.0,
        "relief": probe["relief"],
        "rich": chosen["rich"],
        "barren": chosen["barren"],
        "margin": chosen["margin"],
        "barren_off": off["barren"],
    }


def solve_c3(env: dict, c2: dict, k: float) -> dict:
    """C3 — latch geometry (theta_burst_enter / theta_burst_exit / burst_confirm_ticks). Chosen from
    the operating-point envelope + the escalated-loop spiral boundary + the C2 trajectory, NOT free-
    optimised (the latch is the "rare and earned" selector once k_esc can't gate on coincidence count).

      enter = BAND_ENTRY (0.80, 0.60): just ABOVE the measured frequent <=2-way ceiling
              (anger {le2_anger_max}, stress {le2_stress_max}) AND at the escalated-loop spiral
              boundary (Jury margin ~0 there, < 0 above) — ordinary coinciding drives never arm it.
      exit  = THETA_BURST_EXIT (0.40): < enter.anger and just below the frequent anger p99
              ({le2_anger_p99}) — releases once acute anger rejoins the ordinary reactive range and
              cannot re-arm from a normal provocation. The hysteresis gap is enter.anger - exit.
      confirm = 2: the minimal dwell > 1 tick. A single in-band tick must NOT arm (the signature is a
              sustained LOOP plateau, not an instantaneous coincidence); 2 ticks ~ a few minutes at
              the believable dt, and short vs. the bad-day plateau (verified plateau-capable, step 1).
    """
    enter_a = BAND_ENTRY["anger"]
    enter_s = BAND_ENTRY["stress"]
    exit_th = THETA_BURST_EXIT
    confirm = 2
    le2_a_max, le2_s_max = env["le2_anger_max"], env["le2_stress_max"]
    le2_a_p99 = env["le2_anger_p99"]
    # geometry sanity (mirrors the engine yaml_io validation + the "rare and earned" intent)
    assert exit_th < enter_a, "hysteresis: exit must be < enter.anger"
    assert enter_a > le2_a_max and enter_s > le2_s_max, "enter band must clear the frequent ceiling"
    assert exit_th < le2_a_p99, "exit must be below the ordinary reactive anger p99 (chatter-free)"
    assert confirm >= 2, "confirm must reject a single in-band tick"
    prov_enter = (
        f"latch arm band, anger edge = {enter_a}. Set just ABOVE the measured frequent <=2-way anger "
        f"ceiling ({le2_a_max:.3f}) and at the escalated-loop (k_esc={k}) spiral boundary — the Jury "
        f"margin is ~0 at (0.80,0.60) and negative above, so the loop only spirals (=burst) once both "
        f"states clear the ordinary envelope. Carries the 'rare and earned' selectivity that k_esc "
        f"cannot (C1 finding: >=3-way pairs don't out-reach <=2-way pairs)."
    )
    prov_exit = (
        f"latch release hysteresis (anger) = {exit_th}. < enter.anger ({enter_a}) and just below the "
        f"frequent <=2-way anger p99 ({le2_a_p99:.4f}): the latch releases once acute anger has fallen "
        f"back beneath the ordinary reactive ceiling, so it cannot re-arm from a normal provocation. "
        f"Hysteresis gap {enter_a - exit_th:.2f}. Shared with C2: extinction (beta={c2['beta']:.2f}) "
        f"is sized so the fully-saturated cool-down reaches this exit within T_cool={c2['t_cool']} "
        f"ticks (return at tick {c2['cross']})."
    )
    prov_confirm = (
        f"latch confirm dwell = {confirm} ticks. The minimal value > 1: a single in-band tick must not "
        f"arm the latch — the burst signature is a sustained LOOP plateau (both states in-band), not an "
        f"instantaneous coincidence. {confirm} ticks ~ a few minutes at the believable dt, short vs the "
        f"bad-day plateau (step-1 benchmarks are plateau-capable). Matches the G4 discrimination tests."
    )
    return {
        "enter_a": enter_a,
        "enter_s": enter_s,
        "exit": exit_th,
        "confirm": confirm,
        "le2_s_max": le2_s_max,
        "prov_enter": prov_enter,
        "prov_exit": prov_exit,
        "prov_confirm": prov_confirm,
    }


def write_yaml(res: dict, c2: dict, c3: dict, c4: dict, c5: dict) -> None:
    k = res["k"]
    prov = (
        f"C1 feasibility frontier (calibration/calibrate_burst.py). Frozen Layer-2: "
        f"bound=(1-d_s)(1-d_a)={res['bound']:.6f}, g_as*g_sa={res['g_as'] * res['g_sa']:.6f}, "
        f"max escalation factor R={res['R']:.4f}. Measured envelope "
        f"(eval/burst_operating_points.json): max frequent <=2-way pair "
        f"(anger={res['pair'][0]:.3f}, stress={res['pair'][1]:.3f}); >=3-way operating points do NOT "
        f"exceed the pair ceiling, so k_esc cannot gate on coincidence count (the latch band does). "
        f"Feasible window [k_lo={res['k_lo']:.3f} (spiral at band entry "
        f"anger>={BAND_ENTRY['anger']}/stress>={BAND_ENTRY['stress']}), "
        f"k_hi={res['k_hi']:.3f} (max observed pair stays stable)]; chose the low end for max "
        f"stability margin at the frequent operating points."
    )
    doc = {
        "layer": "burst (M20.1)",
        "reads_on_top_of": (
            "calibrated_layer2.yaml + calibrated_recovery.yaml + defaults.yaml (all untouched)"
        ),
        "anchor": (
            "the frozen Layer-2 2-cycle Jury bound + the measured corpus operating-point envelope; "
            "every burst number is expressed RELATIVE to these, none chosen by hand"
        ),
        "free_set": [
            "coupling_escalation.anger.stress",
            "coupling_escalation.stress.anger",
            "burst_extinction.anger",
            "burst_extinction.stress",
            "thresholds.burst_enter.anger",
            "thresholds.burst_enter.stress",
            "thresholds.burst_exit",
            "thresholds.burst_confirm_ticks",
            "action_params.seek_stimulus.per_tick.stress",
            "derived_weights.urge_boredom.stress",
            "thresholds.theta_displace",
            "appraisal.displaced_relational_discount",
        ],
        "calibrated": {
            "coupling_escalation.anger.stress": {
                "value": k,
                "kind": "k_esc",
                "status": "calibrated-C1",
                "provenance": prov,
            },
            "coupling_escalation.stress.anger": {
                "value": k,
                "kind": "k_esc",
                "status": "calibrated-C1",
                "provenance": "symmetric with coupling_escalation.anger.stress (no data to split "
                "the two edges; one shared k, the absolute anchor for the burst layer)",
            },
            "burst_extinction.anger": {
                "value": c2["ext_a"],
                "kind": "extinction_rate",
                "status": "calibrated-C2",
                "provenance": (
                    f"C2 extinction (calibration/calibrate_burst.py). Absolute anchor = the "
                    f"believable cool-down T_cool={T_COOL_HOURS:.0f}h = {c2['t_cool']} ticks at the "
                    f"believable dt. ONE free scalar beta={c2['beta']:.2f} with ext_x=beta*(1-decay_x) "
                    f"(split inherited from the frozen Layer-2 decays => anger faster than stress, no "
                    f"invented ratio). beta is the SMALLEST value whose fully-saturated (1,1) latched "
                    f"cool-down returns below theta_burst_exit={THETA_BURST_EXIT} within T_cool and stays "
                    f"down (monotone). Result: return at tick {c2['cross']} ({c2['cross']}<= {c2['t_cool']}), "
                    f"spectral radius at the ceiling lambda_max={c2['lam_ceiling']:.4f}<1 (bounded). "
                    f"ext_anger=beta*(1-decay_anger)={c2['ext_a']}."
                ),
            },
            "burst_extinction.stress": {
                "value": c2["ext_s"],
                "kind": "extinction_rate",
                "status": "calibrated-C2",
                "provenance": (
                    f"C2 extinction, stress edge. Same scalar beta={c2['beta']:.2f}; "
                    f"ext_stress=beta*(1-decay_stress)={c2['ext_s']} < ext_anger ({c2['ext_a']}) by "
                    f"construction (stress cools slower than anger, per the design note)."
                ),
            },
            "thresholds.burst_enter.anger": {
                "value": c3["enter_a"],
                "kind": "latch_band",
                "status": "calibrated-C3",
                "provenance": c3["prov_enter"],
            },
            "thresholds.burst_enter.stress": {
                "value": c3["enter_s"],
                "kind": "latch_band",
                "status": "calibrated-C3",
                "provenance": (
                    f"latch arm band, stress edge = {c3['enter_s']}; same anchor as "
                    f"thresholds.burst_enter.anger (just above the measured frequent <=2-way stress "
                    f"ceiling {c3['le2_s_max']:.3f}; both states must be in-band for the loop plateau)."
                ),
            },
            "thresholds.burst_exit": {
                "value": c3["exit"],
                "kind": "latch_hysteresis",
                "status": "calibrated-C3",
                "provenance": c3["prov_exit"],
            },
            "thresholds.burst_confirm_ticks": {
                "value": c3["confirm"],
                "kind": "latch_dwell",
                "status": "calibrated-C3",
                "provenance": c3["prov_confirm"],
            },
            "action_params.seek_stimulus.per_tick.stress": {
                "value": c4["seek_cost"],
                "kind": "loop2_seek_cost",
                "status": "calibrated-C4",
                "provenance": (
                    f"C4 Loop-2 forward edge (fruitless looking wears you down). = half the calibrated "
                    f"rich-world relief rate |self_activity.stress|={c4['relief']:.3f} (deliberate "
                    f"asymmetry: engaging-relief must DOMINATE looking-windup so a rich world resolves "
                    f"stress; the cost is 'small'). Mock-world contrast (lutek, STRESSED): rich stress "
                    f"slope {c4['rich']:+.4f}/tick (relief), barren {c4['barren']:+.4f}/tick (wind-up "
                    f"into burst range); at cost 0 barren is {c4['barren_off']:+.4f} (no wind-up). The "
                    f"operative Loop-2 knob."
                ),
            },
            "derived_weights.urge_boredom.stress": {
                "value": c4["w_s"],
                "kind": "loop2_return_edge",
                "status": "measured-inert-C4",
                "provenance": (
                    "C4 MEASURED FINDING: the stress->seek return edge is NOT identified by the "
                    "rich/barren contrast — boredom already drives seeking in every burst-relevant "
                    "(wound-up) scenario, and making a pure-stress (boredom 0) character seek requires "
                    "w_s ~ the seek threshold (~0.85), a large, fragile hand-set value. Per "
                    "topology-now / never-invent-numbers, the edge stays NEUTRAL (0); Loop 2 is "
                    "carried by the seek stress-cost (B2). The topology edge exists, the weight is 0."
                ),
            },
            "thresholds.theta_displace": {
                "value": c5["theta_displace"],
                "kind": "displacement_bar",
                "status": "calibrated-C5",
                "provenance": c5["prov_theta"],
            },
            "appraisal.displaced_relational_discount": {
                "value": c5["discount"],
                "kind": "displaced_grudge_discount",
                "status": "default-C5",
                "provenance": c5["prov_discount"],
            },
        },
        "stages_pending": [
            "refractory edge weight (potential_weights.outburst.refractory_x_resent_src) — turn ON",
            "wire the burst overlay into the eval loader (plan step 4, opt-in)",
            "1400-scenario regression + sanity + cichy_multi_060 (plan step 5)",
        ],
    }
    OUT.write_text(
        "# GENERATED by calibration/calibrate_burst.py — do not hand-edit (provenance record).\n"
        "# Read ON TOP OF defaults.yaml; defaults stay neutral/placeholder. Wired into the eval\n"
        "# loader at plan step 4 (burst overlay, opt-in) — until then this is a provenance artifact.\n\n"
        + yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, width=100),
        encoding="utf-8",
    )


def main() -> None:
    if not ENV_JSON.exists():
        raise SystemExit(
            "missing eval/burst_operating_points.json — run "
            "`python eval/measure_operating_points.py` first"
        )
    res = solve_c1()
    print("C1 — k_esc feasibility frontier\n" + "=" * 50)
    print(
        f"frozen loop: bound={res['bound']:.6f}  g_as*g_sa={res['g_as'] * res['g_sa']:.6f}"
    )
    print(f"max escalation factor before instability R = {res['R']:.4f}")
    print(
        f"max observed frequent pair: anger={res['pair'][0]:.3f} stress={res['pair'][1]:.3f}"
    )
    print(
        f"feasible window: k_lo={res['k_lo']:.3f}  k_hi={res['k_hi']:.3f}  feasible={res['feasible']}"
    )
    print(f"CHOSEN k_esc = {res['k']:.2f} (both edges)\n")
    # show the margin table at the chosen k
    bound, g_as, g_sa = res["bound"], res["g_as"], res["g_sa"]
    pts = {
        "p99 pair": (res["env"]["le2_anger_p99"], res["env"]["le2_stress_p99"]),
        "MAX observed pair": res["pair"],
        f"band entry ({BAND_ENTRY['anger']},{BAND_ENTRY['stress']})": (
            BAND_ENTRY["anger"],
            BAND_ENTRY["stress"],
        ),
        "full saturation (1,1)": (1.0, 1.0),
    }
    for nm, (a, s) in pts.items():
        m = bound - g_as * g_sa * _factor(a, s, res["k"])
        print(f"  {nm:28s} margin={m:+.6f}  {'SPIRAL' if m < 0 else 'stable'}")

    # --- C2 extinction ---
    c2 = solve_c2(res["k"])
    print("\nC2 — extinction\n" + "=" * 50)
    print(f"anchor T_cool = {T_COOL_HOURS:.0f}h = {c2['t_cool']} ticks (believable dt)")
    print(f"chosen beta = {c2['beta']:.2f}  (ext_x = beta*(1-decay_x))")
    print(f"  burst_extinction.anger  = {c2['ext_a']}")
    print(f"  burst_extinction.stress = {c2['ext_s']}  (< anger: stress cools slower)")
    print(
        f"full-saturation (1,1) cool-down: anger<{THETA_BURST_EXIT} at tick {c2['cross']} "
        f"(<= {c2['t_cool']}), monotone={c2['mono']}, lambda_max@ceiling={c2['lam_ceiling']:.4f}"
    )

    # --- C3 latch geometry ---
    c3 = solve_c3(res["env"], c2, res["k"])
    print("\nC3 — latch geometry\n" + "=" * 50)
    print(
        f"burst_enter = (anger>={c3['enter_a']}, stress>={c3['enter_s']})  "
        f"[> frequent ceiling ({res['env']['le2_anger_max']:.2f},{res['env']['le2_stress_max']:.2f})]"
    )
    print(
        f"burst_exit  = {c3['exit']} (anger; < p99 {res['env']['le2_anger_p99']:.3f}, "
        f"gap {c3['enter_a'] - c3['exit']:.2f})   burst_confirm_ticks = {c3['confirm']}"
    )

    # --- C4 Loop-2 (relief vs wind-up) ---
    c4 = solve_c4()
    print("\nC4 — Loop-2 (relief-seeking through the world)\n" + "=" * 50)
    print(f"seek_stimulus.per_tick.stress = {c4['seek_cost']}  (= 0.5 * relief rate {c4['relief']:.3f})")
    print(f"  rich stress slope   = {c4['rich']:+.4f}/tick (relief)")
    print(f"  barren stress slope = {c4['barren']:+.4f}/tick (wind-up; at cost 0: {c4['barren_off']:+.4f})")
    print(f"  contrast margin     = {c4['margin']:+.4f}")
    print(f"derived_weights.urge_boredom.stress = {c4['w_s']} (measured-inert: boredom already seeks)")

    # --- C5 displacement bar + discount ---
    c5 = solve_c5(c3, res["env"])
    print("\nC5 — displacement bar\n" + "=" * 50)
    print(
        f"theta_displace = {c5['theta_displace']} (midpoint of latch band "
        f"[{c3['exit']},{c3['enter_a']}]; > reactive p99 {res['env']['le2_anger_p99']:.3f})"
    )
    print(f"displaced_relational_discount = {c5['discount']} (fully transient — no grudge on the innocent)")

    write_yaml(res, c2, c3, c4, c5)
    print(f"\nwrote -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
