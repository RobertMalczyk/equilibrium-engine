"""M-J.3 deferred completion: the `suspicion_raised` cue (PRESSURE WITHOUT TRUTH).

Closes the one accused-side M-J.3 deferral that does NOT need the multi-agent driver (M-MEM). A watcher
signals suspicion of an INNOCENT persona each tick. Per spec section 3 the cue raises PRESSURE --
`suspicion[watcher]` (a per-source relation memory) and `exposure_anxiety` (feeling watched) -- WITHOUT
revealing or creating any truth: guilt stays 0 ("looks suspicious from avoidance without being guilty").
The exposure pressure couples into `avoidance_drive`, so a CONFLICT-AVOIDANT persona starts to AVOID the
watcher. Magnitudes are calibration placeholders; only the ORDERING/invariants are asserted.

Still DEFERRED (needs M-MEM, review R7): `false_accusation`'s accuser-after-discovery guilt and the
multi-agent witness fan-out. `blame_shift` is a `lie_type` for the M-J.4 ledger, not an accusation event.
"""

from __future__ import annotations

from pathlib import Path

from engine.simulation import run_scenario
from engine.stability import jury_margin
from engine.yaml_io import load_persona, load_scenario
from eval.moral import moral_overrides
from eval.observe import action_counts, relation_trajectory, trajectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
HALGRIM = ROOT / "data" / "personas" / "halgrim.yaml"
SUSPICION = ROOT / "data" / "scenarios" / "moral_suspicion.yaml"
ACCUSATION = ROOT / "data" / "scenarios" / "moral_accusation.yaml"

# Honest (so being exposed never tempts a lie) + conflict-avoidant: avoidance is the axis under test.
AVOIDANT = {
    "conflict_avoidance": 0.9,
    "injustice_sensitivity": 0.1,
    "guilt_proneness": 0.5,
    "honesty_humility": 0.9,
}


def _run(scenario, traits, n=14):
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(traits))
    return run_scenario(cfg, load_scenario(scenario), n_ticks=n)[1]


def test_suspicion_cue_raises_suspicion_and_exposure_without_guilt():
    """The core invariant: a suspicion cue is PRESSURE, not knowledge and not guilt."""
    tr = _run(SUSPICION, AVOIDANT)
    susp = relation_trajectory(tr, "watcher", "suspicion")
    exa = trajectory(tr, "exposure_anxiety")
    guilt = trajectory(tr, "guilt")
    assert (
        susp[-1] > 0.0 and susp[-1] >= susp[0]
    )  # suspicion toward the watcher builds (cue active from t0)
    assert exa[-1] > 0.0  # the persona feels watched / more exposed
    assert all(
        v == 0.0 for v in guilt
    )  # ...but did nothing wrong -> NO guilt is ever created
    assert all(0.0 <= v <= 1.0 for v in susp)  # bounded per-source memory


def test_suspicion_pressure_drives_avoidance():
    """suspicion -> avoidance_drive (conflict_avoidance-gated): sustained suspicion makes a conflict-avoidant
    persona dodge the watcher, even with no accusation and nothing to hide."""
    tr = _run(SUSPICION, AVOIDANT)
    av = trajectory(tr, "avoidance_drive")
    assert (
        av[-1] > 0.0 and av[-1] >= av[0]
    )  # avoidance accumulates under sustained suspicion
    assert all(0.0 <= v <= 1.0 for v in av)
    assert "avoid" in action_counts(tr)


def test_false_accusation_is_the_accusation_channel_accused_side():
    """`false_accusation` decomposes to the same accused-side `accusation` channel: an innocent persona
    (no guilt seed) reacts to it exactly as it would a plain accusation -- the grievance route. The DISTINCT
    accuser-discovery half is deferred (M-MEM)."""
    from engine.mapper import map_event
    from engine.schema import HistoryFeatures, RawEvent

    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(AVOIDANT))
    feats = HistoryFeatures()
    acc = map_event(
        RawEvent(type="accusation", t=0, source="x", intensity=1.0), cfg, feats
    )
    false = map_event(
        RawEvent(type="false_accusation", t=0, source="x", intensity=1.0), cfg, feats
    )
    assert "accusation" in acc and "accusation" in false
    assert false["accusation"].value == acc["accusation"].value


def test_suspicion_slice_keeps_anger_stress_stable():
    cfg = load_persona(HALGRIM, DEFAULTS, param_overrides=moral_overrides(AVOIDANT))
    assert jury_margin(cfg.decay, cfg.couplings) > 0.0
