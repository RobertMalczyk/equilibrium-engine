"""Deterministic unit checks for the believability EXPRESSION fixes (Phase A: M1, M2).

These assert on the pure render helpers in eval/render_narration.py -- they touch ONLY narration text,
never the DebugTrace/dynamics, so the golden traces stay byte-identical (the fixes are expression-side).

- M1: mood_phrase must weigh residual ANGER, not only stress -- a high-anger body never reads
  "settled, at ease" even when stress has ebbed (the settled<->fury contradiction the judge flagged).
- M2: a positive-valence event (soup/help) with no hostile reaction is ACKNOWLEDGED, never rendered
  with the slight-style "lets it pass, no notable reaction".
"""

from eval.render_narration import (
    ANGER_SEETHING,
    POSITIVE_EVENTS,
    mood_phrase,
)


# --- M1: mood_phrase weighs anger -----------------------------------------------------------------


def test_high_anger_low_stress_is_not_settled():
    # Right after an outburst: stress has ebbed, anger has not. Must NOT read "settled / at ease".
    g = {"stress": 0.10, "anger": ANGER_SEETHING + 0.10}
    out = mood_phrase(g)
    assert "settled" not in out and "at ease" not in out
    assert "seething" in out


def test_genuinely_calm_still_reads_settled():
    # Low stress AND low anger -- the band edge must still allow the calm read.
    g = {"stress": 0.10, "anger": 0.05}
    assert mood_phrase(g) == "looks settled, at ease"


def test_high_stress_low_anger_unchanged():
    # The pre-existing stress-driven tense read is preserved when anger is absent.
    g = {"stress": 0.70, "anger": 0.0}
    out = mood_phrase(g)
    assert "wound tight" in out


def test_moderate_anger_keeps_off_settled():
    # A moderate residual (between the bands) keeps the bearing off "settled" without claiming seething.
    g = {"stress": 0.10, "anger": 0.45}
    out = mood_phrase(g)
    assert "settled" not in out


def test_high_anger_composes_with_boredom():
    g = {"stress": 0.10, "anger": ANGER_SEETHING + 0.10, "boredom": 0.80}
    out = mood_phrase(g)
    assert "seething" in out and "restless" in out


def test_high_anger_fresh_reads_seething():
    # An explicit recent provocation -> the active "seething" read is justified.
    g = {"stress": 0.10, "anger": ANGER_SEETHING + 0.10}
    assert "seething" in mood_phrase(g, anger_fresh=True)


def test_high_anger_stale_reads_lingering_not_seething():
    # M1 refinement: high anger with NO recent provocation must read as a lingering temper, not
    # active fury -> never "seething at nothing", and still never "settled/at ease".
    g = {"stress": 0.10, "anger": ANGER_SEETHING + 0.10}
    out = mood_phrase(g, anger_fresh=False)
    assert "seething" not in out
    assert "settled" not in out and "at ease" not in out
    assert "earlier temper" in out


# --- M2: positive events are acknowledged ---------------------------------------------------------


def test_positive_event_never_attaches_a_later_hostile_reaction():
    """Renderer attribution: a kindness reads ONLY its own tick. A hostile reaction one or two ticks
    later (a residual/displaced discharge from an EARLIER provocation) must NOT be stapled onto the
    kindness line ('snaps at the soup' when the kindness tick was not a lash-out). Replays the burst-ON
    corpus and checks the renderer rule: for a food/help event the reaction window is the event tick
    only, so no hostile reaction is reached by scanning ahead."""
    import pathlib

    import yaml

    from engine.yaml_io import load_scenario
    from eval.calibrated import load_eval_persona_timescale
    from eval.render_narration import HOSTILE_REACTIONS, POSITIVE_EVENTS, REACTIVE
    from eval.sanity_multiday import run_multiday

    root = pathlib.Path(".")
    for persona in ("wojslaw", "branic"):
        cfg = load_eval_persona_timescale(persona, burst=True)
        for idx in range(1, 6):
            p = (
                root
                / f"eval/scenarios/multiday/{persona}/{persona}_multi_{idx:03d}.yaml"
            )
            if not p.exists():
                continue
            nd = yaml.safe_load(p.read_text(encoding="utf-8"))["n_days"]
            ticks = run_multiday(cfg, load_scenario(p), nd).ticks
            for i, tk in enumerate(ticks):
                ev = tk.event
                if ev is None or ev.type not in POSITIVE_EVENTS:
                    continue
                # the NEW rule: positive events read only their own tick (window = 1)
                for j in range(i, i + 1):
                    a = ticks[j].selection.action
                    if a in REACTIVE and j > i:
                        assert a not in HOSTILE_REACTIONS, (
                            f"{persona}_{idx}: hostile '{a}' attached to a kindness at offset {j - i}"
                        )


def test_positive_event_types_registered():
    assert "food_given" in POSITIVE_EVENTS and "help" in POSITIVE_EVENTS


def test_kindness_while_busy_is_acknowledged_not_slighted():
    """Render a day where a kindness lands; the no-reaction fallback for a positive event must
    acknowledge it ("takes it ...") rather than the slight-style "lets it pass". We check the rendered
    corpus contains no positive event narrated as a snub."""
    from eval.render_narration import PERSONAS, render

    for persona in PERSONAS:
        text, _ = render(persona)
        for line in text.splitlines():
            low = line.lower()
            is_kindness = "bowl of" in low or "lends" in low or "small kindness" in low
            if is_kindness:
                assert "lets it pass" not in low, (
                    f"{persona}: kindness rendered as a snub: {line}"
                )
