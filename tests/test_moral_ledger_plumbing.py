"""M-J.4.0 -- MoralLedger plumbing (data model + Snapshot/freeze + trace serialization).

The ledger (Secret + LieRecord) is the one genuinely-new structure (spec section 3). This slice wires it in
WITHOUT any lifecycle: it is OPT-IN (empty for every legacy persona), deep-copied into Snapshot.freeze() so
update/potentials get a read-only view, and serialized into the trace ONLY when non-empty -> legacy goldens
stay byte-identical. The create/reinforce/detect/inactivate lifecycle lands in later M-J.4 slices.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.runtime import init_runtime
from engine.schema import LieRecord, MoralLedger, Secret
from engine.simulation import run_scenario
from engine.yaml_io import load_persona, load_scenario

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"
WOJSLAW = ROOT / "data" / "personas" / "wojslaw.yaml"
INSULT = ROOT / "data" / "scenarios" / "insult_public.yaml"


def test_ledger_dataclasses_default_empty():
    assert MoralLedger().is_empty()
    led = MoralLedger()
    led.secrets["s1"] = Secret(
        id="s1", owner_id="self", topic="theft", category="crime"
    )
    assert not led.is_empty()
    # a LieRecord defaults its dynamic mini-integrators to 0
    li = LieRecord(id="l1", liar_id="self", target_id="guard")
    assert li.consistency_debt == 0.0 and li.lie_type == "denial"


def test_legacy_runtime_carries_an_empty_ledger_and_no_trace_key():
    cfg = load_persona(WOJSLAW, DEFAULTS)
    rt, tr = run_scenario(cfg, load_scenario(INSULT), n_ticks=4)
    assert rt.moral_ledger.is_empty()
    # the frozen snapshot's ledger is empty too, and NO tick serializes a `moral_ledger` key (byte-identical)
    for tk in tr.ticks:
        assert tk.state_after_post.moral_ledger.is_empty()
        assert "moral_ledger" not in tk.to_dict()


def test_freeze_deep_copies_the_ledger():
    """Snapshot.freeze() must DEEP-copy the ledger so update/potentials cannot mutate the live ledger through
    the frozen reference (the synchronous-snapshot discipline)."""
    cfg = load_persona(WOJSLAW, DEFAULTS)
    rt = init_runtime(cfg, {})
    rt.moral_ledger.lies["l1"] = LieRecord(
        id="l1", liar_id="self", target_id="guard", consistency_debt=0.3
    )
    snap = rt.freeze()
    # mutate the LIVE ledger after freezing
    rt.moral_ledger.lies["l1"].consistency_debt = 0.9
    rt.moral_ledger.lies["l2"] = LieRecord(id="l2", liar_id="self", target_id="x")
    # the frozen snapshot is unaffected (deep copy)
    assert snap.moral_ledger.lies["l1"].consistency_debt == 0.3
    assert "l2" not in snap.moral_ledger.lies


def test_seeded_ledger_serializes_canonically_in_the_trace():
    """A non-empty ledger appears in the tick's to_dict under `moral_ledger`, with sorted ids and the full
    field roster (deterministic, JSON-round-trippable)."""
    cfg = load_persona(WOJSLAW, DEFAULTS)
    rt = init_runtime(cfg, {})
    rt.moral_ledger.secrets["sec_b"] = Secret(
        id="sec_b",
        owner_id="self",
        topic="affair",
        category="shameful_fact",
        salience=0.5,
    )
    rt.moral_ledger.secrets["sec_a"] = Secret(
        id="sec_a", owner_id="self", topic="theft", category="crime"
    )
    snap = rt.freeze()
    from engine.debug import _ledger_dict

    d = _ledger_dict(snap.moral_ledger)
    assert list(d["secrets"].keys()) == ["sec_a", "sec_b"]  # canonical sorted-id order
    assert d["secrets"]["sec_b"]["salience"] == 0.5
    json.dumps(d)  # must be JSON-serializable (no exotic types leak into the trace)
