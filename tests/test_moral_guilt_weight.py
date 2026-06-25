"""M-J.4.4 follow-up (A3) -- minor vs serious guilt via the Secret's moral_weight.

The engine has ONE `guilt` state with ONE half-life, but the spec (section 11) wants a minor(18h)/serious(72h)
split and the blind multi-day judge confirmed it (18h reads "too tidy for a serious wrong"). Rather than two
guilt states, an ACTIVE secret RE-INJECTS guilt each tick proportional to its authored `moral_weight` x
`salience`: a SERIOUS unconfessed secret (high moral_weight) keeps the guilt alive against decay -> it lingers
(the 72h feel); a MINOR one barely does -> it fades (the 18h feel). Confession/exposure inactivates the secret
-> the drip stops -> relief. Magnitudes are calibration placeholders; only the ORDERING is asserted.
"""

from __future__ import annotations

from pathlib import Path

from engine.schema import RawEvent, Scenario
from engine.simulation import run_scenario
from engine.yaml_io import load_persona
from eval.moral import moral_overrides
from eval.observe import trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
MORAL = {"guilt_proneness": 0.6}
CALM = {
    "fatigue": 0.05,
    "boredom": 0.05,
    "stress": 0.05,
    "frustration": 0.05,
    "anger": 0.05,
}


def _run(moral_weight: float, n: int = 14, expose_at: int | None = None):
    secret = [
        {
            "id": "s_theft",
            "owner_id": "self",
            "topic": "theft",
            "category": "crime",
            "hidden_from": ["guard"],
            "moral_weight": moral_weight,
        }
    ]
    events = [
        RawEvent(type="secret_cued", t=t, topic="theft", intensity=1.0)
        for t in range(n)
    ]
    if expose_at is not None:
        events.append(
            RawEvent(
                type="secret_exposed",
                t=expose_at,
                topic="theft",
                intensity=1.0,
                context={"witnesses": ["guard", "warden"]},
            )
        )
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(MORAL))
    sc = Scenario(
        id="gw",
        persona="halgrim",
        initial_overrides={"global_state": dict(CALM), "secrets": secret},
        events=tuple(events),
    )
    return run_scenario(cfg, sc, n_ticks=n)


def test_serious_secret_sustains_guilt_minor_fades():
    """The minor/serious split: a SERIOUS secret (high moral_weight) keeps guilt weighing; a MINOR one barely."""
    g_serious = trajectory(_run(0.9)[1], "guilt")
    g_minor = trajectory(_run(0.1)[1], "guilt")
    assert (
        g_serious[-1] > g_minor[-1]
    )  # the weight of the wrong decides how heavily it sits
    assert g_serious[-1] > 0.1  # a serious unconfessed wrong keeps weighing
    assert all(0.0 <= v <= 1.0 for v in g_serious)  # bounded


def test_resolved_secret_stops_the_guilt_drip():
    """Exposure inactivates the secret -> the moral_weight guilt drip stops -> guilt no longer sustained."""
    g_hidden = trajectory(_run(0.9)[1], "guilt")  # stays hidden -> sustained
    g_exposed = trajectory(
        _run(0.9, expose_at=4)[1], "guilt"
    )  # exposed at t4 -> drip stops
    assert g_exposed[-1] < g_hidden[-1]  # once it's out, the weight stops pressing


def test_guilt_weight_drip_is_opt_in():
    """A legacy persona (no overlay -> no ledger_params) gets no guilt drip even with a seeded secret."""
    secret = [
        {
            "id": "s",
            "owner_id": "self",
            "topic": "x",
            "category": "crime",
            "hidden_from": ["g"],
            "moral_weight": 0.9,
        }
    ]
    events = [
        RawEvent(type="secret_cued", t=t, topic="x", intensity=1.0) for t in range(10)
    ]
    cfg = load_persona(HALGRIM, DEFAULTS)
    sc = Scenario(
        id="gw",
        persona="halgrim",
        initial_overrides={"global_state": dict(CALM), "secrets": secret},
        events=tuple(events),
    )
    rt, _ = run_scenario(cfg, sc, n_ticks=10)
    assert "secret_weight_to_guilt" not in cfg.ledger_params
    assert rt.moral_ledger.secrets["s"].salience == 0.0  # inert without the overlay
