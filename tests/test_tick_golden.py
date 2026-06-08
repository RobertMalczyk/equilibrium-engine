"""Golden-trace regression + determinism + good-day property test.

Golden traces are the frozen DebugTrace JSON (debug.py contract). Regenerate intentionally
with GOLDEN_REGEN=1 (e.g. after a conscious calibration re-baseline):

    GOLDEN_REGEN=1 python -m pytest tests/test_tick_golden.py
"""

import os
from pathlib import Path

import pytest

from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
DEFAULTS = ROOT / "calibration" / "defaults.yaml"

CASES = [
    ("food_given_single", "halgrim", None),
    ("same_soup_good_day", "halgrim", None),
    ("same_soup_bad_day", "halgrim", None),
    ("same_soup_bad_day", "wojslaw", None),
    # M2 relational channels: insult/help, social exposure, relational bias.
    ("insult_public", "wojslaw", 4),
    ("insult_private", "wojslaw", 4),
    ("prisoner_bias_resentful", "cichy", 8),
    ("prisoner_bias_neutral", "cichy", 8),
    # M3a cast expansion: recruit (group-A contrast) and poet (group-D third axis point).
    ("same_soup_bad_day", "branic", None),
    ("insult_public", "lutek", 4),
]


def _run(scenario_id: str, persona_id: str, n_ticks):
    cfg = load_persona(ROOT / "data" / "personas" / f"{persona_id}.yaml", DEFAULTS)
    sc = load_scenario(ROOT / "data" / "scenarios" / f"{scenario_id}.yaml")
    _, trace = run_scenario(cfg, sc, n_ticks=n_ticks)
    return trace


@pytest.mark.parametrize("scenario_id,persona_id,n_ticks", CASES)
def test_golden(scenario_id, persona_id, n_ticks):
    trace = _run(scenario_id, persona_id, n_ticks)
    actual = trace.to_json()
    golden_path = GOLDEN_DIR / f"{scenario_id}.{persona_id}.json"

    if os.environ.get("GOLDEN_REGEN") == "1":
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(actual + "\n", encoding="utf-8")
        pytest.skip(f"regenerated {golden_path.name}")

    assert golden_path.exists(), (
        f"missing golden {golden_path}; run with GOLDEN_REGEN=1"
    )
    expected = golden_path.read_text(encoding="utf-8").rstrip("\n")
    assert actual == expected, "trace diverged from golden (see debug.py contract)"


@pytest.mark.parametrize("scenario_id,persona_id,n_ticks", CASES)
def test_determinism_bit_for_bit(scenario_id, persona_id, n_ticks):
    a = _run(scenario_id, persona_id, n_ticks).to_json()
    b = _run(scenario_id, persona_id, n_ticks).to_json()
    assert a == b


def test_good_day_no_outburst():
    """Litmus (spec section 10): a fed, rested, trusting Halgrim never bursts on soup."""
    trace = _run("same_soup_good_day", "halgrim", None)
    actions = [tk.selection.action for tk in trace.ticks]
    assert "outburst" not in actions
    assert "hostile_action" not in actions


def test_persona_contrast_same_soup_bad_day():
    """Litmus (spec section 10) + interaction-feature validation: SAME elevated emotion
    (shared initial_overrides), traits differ -> different visible action."""
    halgrim = [
        tk.selection.action for tk in _run("same_soup_bad_day", "halgrim", None).ticks
    ]
    wojslaw = [
        tk.selection.action for tk in _run("same_soup_bad_day", "wojslaw", None).ticks
    ]

    # Wojslaw (low control, high pride) bursts; Halgrim (high stoicism/control) does not.
    assert "outburst" in wojslaw
    assert "outburst" not in halgrim
    # Halgrim suppresses into a cold response instead.
    assert "cold_response" in halgrim
    # Same scenario, different action -> they play differently.
    assert set(halgrim) != set(wojslaw)


def test_social_exposure_amplifies_insult():
    """Litmus (spec section D, public_vs_private_insult): the SAME insult from the SAME
    source lands harder in public. social_exposure scales the relational channel, so the
    outburst potential and the anger DEPOSIT at the insult tick are strictly higher when public.
    NB: measure the anger deposit (state_after_commit), NOT state_after_post -- once pride->insult-anger
    (the gain modulator) is wired, the public insult can FIRE Wojslaw's outburst, whose -0.30 discharge
    confounds the post-reaction anger. The deposit is the layer this litmus is about."""
    pub = _run("insult_public", "wojslaw", 4).ticks[0]
    prv = _run("insult_private", "wojslaw", 4).ticks[0]
    assert pub.potentials["outburst"] > prv.potentials["outburst"]
    assert (
        pub.state_after_commit.global_state["anger"]
        > prv.state_after_commit.global_state["anger"]
    )


def test_relational_bias_asymmetry_prisoner():
    """Litmus (spec section D, prisoner_bias): SAME persona (Cichy), SAME insult+help events;
    ONLY relations[guard] differs. A resented guard's insult is amplified and his help is
    damped -> resentful Cichy reads both asymmetrically vs the neutral baseline."""
    res = _run("prisoner_bias_resentful", "cichy", 8)
    neu = _run("prisoner_bias_neutral", "cichy", 8)

    # Insult (t=0) lands harder under resentment.
    assert (
        res.ticks[0].state_after_post.global_state["anger"]
        > neu.ticks[0].state_after_post.global_state["anger"]
    )

    # Help (t=4) is damped under resentment: it builds less trust than for the neutral guard.
    res_trust_gain = (
        res.ticks[-1].state_after_post.relations["guard"]["trust"]
        - res.ticks[0].snapshot.relations["guard"]["trust"]
    )
    neu_trust_gain = (
        neu.ticks[-1].state_after_post.relations["guard"]["trust"]
        - neu.ticks[0].snapshot.relations["guard"]["trust"]
    )
    assert res_trust_gain < neu_trust_gain

    # Different relation -> different visible action (resentful refuses; neutral does not).
    res_actions = {tk.selection.action for tk in res.ticks}
    neu_actions = {tk.selection.action for tk in neu.ticks}
    assert res_actions != neu_actions


def test_pride_modulates_insult_anger_deposit():
    """Gain modulator (spec section 14, pride->insult-anger): the insult-anger DEPOSIT
    (state_after_commit, PRE-discharge) rises monotonically with pride -- a proud persona feels an
    insult more, a low-pride one less, so the differentiated sting emerges from a TRAIT (not from
    output-side stoicism). Same persona + same public insult, vary ONLY pride. Magnitude is a
    believability placeholder; only this ORDERING is asserted (Rule 1 / spec section 14)."""

    def deposit(pride):
        cfg = load_persona(
            ROOT / "data" / "personas" / "wojslaw.yaml",
            DEFAULTS,
            param_overrides={"traits": {"pride": pride}},
        )
        sc = load_scenario(ROOT / "data" / "scenarios" / "insult_public.yaml")
        _, trace = run_scenario(cfg, sc, n_ticks=1)
        return trace.ticks[0].state_after_commit.global_state["anger"]

    deposits = [deposit(p) for p in (0.1, 0.3, 0.5, 0.7, 0.9)]
    assert deposits == sorted(deposits)  # non-decreasing in pride
    assert (
        deposits[0] < deposits[2] < deposits[-1]
    )  # real spread, anchored at the pride=0.5 midpoint


def _first_outburst_tick(actions):
    """Index of the first outburst, or +inf if it never fires (N_to_burst, spec section A)."""
    return next((i for i, a in enumerate(actions) if a == "outburst"), float("inf"))


def test_recruit_bursts_faster_than_veteran():
    """Litmus (spec section A, person contrast): SAME elevated state + SAME soup; the recruit
    (low control/stoicism) bursts, the veteran suppresses. N_to_burst[Branic] < [Halgrim]."""
    branic = [
        tk.selection.action for tk in _run("same_soup_bad_day", "branic", None).ticks
    ]
    halgrim = [
        tk.selection.action for tk in _run("same_soup_bad_day", "halgrim", None).ticks
    ]
    assert "outburst" in branic
    assert "outburst" not in halgrim  # veteran suppresses
    assert "cold_response" in halgrim
    assert _first_outburst_tick(branic) < _first_outburst_tick(halgrim)


def test_poet_shrugs_off_public_insult():
    """Litmus (spec section D, third axis point): the SAME public insult that most provokes
    Wojslaw leaves Lutek unmoved -- high stoicism/self_control, no burst (the stage-2 valence
    rewrite is out of MVP). outburst_fired[Lutek] == false; outburst_potential peaks lowest
    for the personas that don't burst, highest for Wojslaw."""
    woj = _run("insult_public", "wojslaw", 4)
    lut = _run("insult_public", "lutek", 4)
    lut_actions = [tk.selection.action for tk in lut.ticks]
    assert "outburst" not in lut_actions
    woj_peak = max(tk.potentials["outburst"] for tk in woj.ticks)
    lut_peak = max(tk.potentials["outburst"] for tk in lut.ticks)
    assert woj_peak > lut_peak
