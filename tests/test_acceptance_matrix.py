"""MVP acceptance matrix -> executable assertions.

Source of truth: ``Acceptance/mvp_acceptance_matrix_TEMPLATE.md`` (filled 2026-06-04). One test per
matrix row; the docstring names the row. Runs against ``calibration/defaults.yaml`` -- the config the
golden traces and litmus tests use (where "emergence at default weights" was demonstrated); the frozen
Layer-2 gains apply only via the calibration harness, not here.

RULE 1 (assert CONTRASTS / ORDERINGS / DIRECTIONS, never absolute numbers) is honoured: comparisons
only, thresholds are READ from config (not hardcoded), and the few literals are tolerances, not state
expectations.

Both litmus halves that were PENDING (B visible-refuse, C visible-prisoner) are now CLOSED by the
per-persona thresholds calibrated 2026-06-04 (Halgrim react.refuse=0.357; Cichy react.cold_response=0.240,
a tagged-temporary stopgap -- see calibration/calibrated_thresholds.yaml). The potential-level contrasts
are still asserted separately from the visible ones, so a visible regression can't hide behind a passing
potential check.
"""

from pathlib import Path

from engine.runtime import init_runtime
from engine.simulation import run_scenario, tick
from engine.yaml_io import load_persona, load_scenario

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "calibration" / "defaults.yaml"

# Relations decay on a memory half-life (>=1e5 s); over the longest run here (25 ticks @ dt=3) that is
# <1e-3. A real leak is a channel deposit (gain ~0.15-0.25 -> ~0.05+). This tol cleanly separates them.
_UNCHANGED = 2e-3


def _persona(persona_id, overrides=None):
    return load_persona(
        ROOT / "data" / "personas" / f"{persona_id}.yaml",
        DEFAULTS,
        param_overrides=overrides,
    )


def _run(scenario_id, persona_id, n_ticks=None, overrides=None):
    cfg = _persona(persona_id, overrides)
    sc = load_scenario(ROOT / "data" / "scenarios" / f"{scenario_id}.yaml")
    _, trace = run_scenario(cfg, sc, n_ticks=n_ticks)
    return trace


def _actions(trace):
    return [tk.selection.action for tk in trace.ticks]


def _cold(trace):
    return [tk.potentials["cold_response"] for tk in trace.ticks]


def _overture_idx(trace):
    """First tick carrying an event -- the provocation; before it the persona has no reason to react."""
    return next((i for i, tk in enumerate(trace.ticks) if tk.event is not None), 0)


def _rel_initial(trace, src, dim):
    return trace.ticks[0].snapshot.relations[src][dim]


def _rel_final(trace, src, dim):
    return trace.ticks[-1].state_after_post.relations[src][dim]


def _react_threshold(persona_id, name):
    """Read the visibility threshold from config rather than hardcoding it (Rule 1)."""
    return _persona(persona_id).thresholds[f"react.{name}"]


# ============================ Family A -- burst vs suppress (LITMUS A) ============================
# Shared fixture: same_soup_bad_day (identical preload + 4x cabbage_soup); only the persona differs.


def test_A1_wojslaw_bursts():
    """A1: Wojslaw (low control, high pride) -> outburst fires."""
    assert "outburst" in _actions(_run("same_soup_bad_day", "wojslaw"))


def test_A2_halgrim_suppresses():
    """A2: Halgrim (high stoicism/control), SAME fixture -> cold_response, never outburst."""
    acts = _actions(_run("same_soup_bad_day", "halgrim"))
    assert "outburst" not in acts
    assert "cold_response" in acts


def test_A3_contrast():
    """A3 (litmus A): same soup + same initial anger -> different ACTION, purely from traits
    (anger*(1-self_control) vs anger*stoicism)."""
    woj = _actions(_run("same_soup_bad_day", "wojslaw"))
    hal = _actions(_run("same_soup_bad_day", "halgrim"))
    assert "outburst" in woj and "outburst" not in hal
    assert "cold_response" in hal


def test_A2_mustnotmove_relations_halgrim():
    """A2 must-not-move: cold_response books NO post-effect and food is non-relational ->
    Halgrim's relation to marta is unchanged on every dim (leak guard)."""
    tr = _run("same_soup_bad_day", "halgrim")
    for dim in ("trust", "respect", "resentment"):
        assert (
            abs(_rel_final(tr, "marta", dim) - _rel_initial(tr, "marta", dim))
            < _UNCHANGED
        )


def test_A1_outburst_books_resentment_on_target_only_wojslaw():
    """A1 moves vs must-not-move: the outburst post-effect books +resentment on the TARGET (marta)
    -> resentment[marta] rises, while trust/respect[marta] stay put (the cost is resentment-only)."""
    tr = _run("same_soup_bad_day", "wojslaw")
    assert _rel_final(tr, "marta", "resentment") > _rel_initial(
        tr, "marta", "resentment"
    )
    for dim in ("trust", "respect"):
        assert (
            abs(_rel_final(tr, "marta", dim) - _rel_initial(tr, "marta", dim))
            < _UNCHANGED
        )


# ====================== Family B -- obedience on command (LITMUS B, command half) ======================
# Shared fixture: same Halgrim, same command (intensity 1.0, has_authority); only the SOURCE differs.


def test_B1_cooperate_with_respected_source():
    """B1: command from Edda (respected) -> cooperate fires; cooperate > refuse."""
    tk0 = _run("command_from_edda", "halgrim", 4).ticks[0]
    assert tk0.selection.action == "cooperate"
    assert tk0.potentials["cooperate"] > tk0.potentials["refuse"]


def test_B2_refuse_with_resented_source():
    """B2: SAME command from Wojslaw (resented) -> refuse > cooperate in the potentials, and refuse clears
    Halgrim's per-persona theta_refuse (0.357) -> visible refuse."""
    tk0 = _run("command_from_wojslaw", "halgrim", 4).ticks[0]
    assert tk0.potentials["refuse"] > tk0.potentials["cooperate"]
    assert tk0.selection.action == "refuse"


def test_B3_potential_contrast():
    """B3 (potential level): purely from respect[source]/resentment[source]."""
    edda = _run("command_from_edda", "halgrim", 1).ticks[0].potentials
    woj = _run("command_from_wojslaw", "halgrim", 1).ticks[0].potentials
    assert woj["refuse"] > edda["refuse"]
    assert edda["cooperate"] > woj["cooperate"]


def test_B3_visible_contrast():
    """B3 (visible, litmus B): respected source -> cooperate; resented source -> refuse, purely from
    respect[source]/resentment[source]."""
    assert (
        _run("command_from_edda", "halgrim", 4).ticks[0].selection.action == "cooperate"
    )
    assert (
        _run("command_from_wojslaw", "halgrim", 4).ticks[0].selection.action == "refuse"
    )


def test_B2_command_amplified_by_low_respect():
    """B2 moves: the command's frustration deposit is amplified for a low-respect source (negative
    polarity) -> frustration@Wojslaw > frustration@Edda at the command tick."""
    edda = (
        _run("command_from_edda", "halgrim", 1).ticks[0].state_after_post.global_state
    )
    woj = (
        _run("command_from_wojslaw", "halgrim", 1)
        .ticks[0]
        .state_after_post.global_state
    )
    assert woj["frustration"] > edda["frustration"]


def test_B_mustnotmove_relations():
    """B must-not-move: the command channel books only a global frustration delta; cooperate/refuse
    have no post-effects -> the relation to the commander is unchanged (leak guard, both sources)."""
    for scenario, src in (
        ("command_from_edda", "edda"),
        ("command_from_wojslaw", "wojslaw"),
    ):
        tr = _run(scenario, "halgrim", 4)
        for dim in ("trust", "respect", "resentment"):
            assert (
                abs(_rel_final(tr, src, dim) - _rel_initial(tr, src, dim)) < _UNCHANGED
            )


def test_B_INV_no_command_no_obedience():
    """B-INV: with command_pressure == 0 (any non-command tick), the obedience potentials are dormant."""
    for tk in _run("command_from_edda", "halgrim", 4).ticks[1:]:
        assert tk.potentials["cooperate"] == 0.0
        assert tk.potentials["refuse"] == 0.0


# ============================ Family C -- prisoner cold-response ============================
# Carrier = a PRIVATE react.cold_response for Cichy (NOT yet promoted -> Cichy rows PENDING on the
# global 0.50). The beta*resentment[src] term was reverted; cold_response = anger*stoicism + frustration.


def test_C_carrier_no_relation_source_term():
    """Family C carrier guard: no relation_source term DRIVES cold_response (the beta term, commit 8ae4342,
    was reverted in b0df4e7) -- so cold stays a THRESHOLD carrier. The Theme-A kindness INHIBITOR
    (kindness_x_nonresent_src, a NEGATIVE-weight signed edge) does contain a relation_source factor, but it
    only SUPPRESSES cold on a kindness tick -- it never drives it -- so it is exempt (weight < 0)."""
    cfg = _persona("cichy")
    terms = cfg.potential_terms
    for term, w in cfg.potential_weights["cold_response"].items():
        if w < 0:  # inhibitory (kindness) edge -- not a driver, exempt
            continue
        assert not any(f["kind"] == "relation_source" for f in terms[term])


def test_C3_potential_contrast_holds_today():
    """C3 (potential level, HOLDS TODAY): resentment[guard] amplifies the SAME insult (negative
    affective_bias -> higher anger -> higher anger*stoicism), so resentful cold strictly dominates
    neutral cold from the overture on. min(resentful) > max(neutral) is the strong, robust form."""
    res = _run("prisoner_bias_resentful", "cichy", 8)
    neu = _run("prisoner_bias_neutral", "cichy", 8)
    res_from_overture = _cold(res)[_overture_idx(res) :]
    assert min(res_from_overture) > max(_cold(neu))


def test_C1_outburst_is_the_larger_potential_not_cold():
    """C1 anti-trap: the raw ordering is outburst > cold_response. The contrast lives in the
    THRESHOLD-GATED action (outburst gated out by its 0.55), NOT in the potential ordering -- so a
    naive `cold > outburst` assertion would be FALSE. Pin reality so nobody writes that."""
    tk0 = _run("prisoner_bias_resentful", "cichy", 8).ticks[0]
    assert tk0.potentials["outburst"] > tk0.potentials["cold_response"]


def test_C2_neutral_stable():
    """C2 (must-not-cross side): the non-resented baseline NEVER goes cold -- its cold (<=0.205) stays below
    Cichy's private theta (0.240), so promoting theta did NOT make the neutral guard go cold. (Theme A: the
    non-resented guard's HELP now draws a warm `positive_response` instead of bare neutral -- a deliberate
    change that SHARPENS the contrast to cold-vs-warm; the must-not-cross invariant is still 'no cold'.)"""
    acts = set(_actions(_run("prisoner_bias_neutral", "cichy", 8)))
    assert acts <= {"neutral", "positive_response"}
    assert "cold_response" not in acts


def test_C3_visible_contrast():
    """C3 (visible, prisoner): resented guard -> cold_response; non-resented guard -> NOT cold (Theme A: a
    warm `positive_response` to the guard's help). Same persona, the only difference is resentment[guard];
    Cichy fires cold via his per-persona theta (0.240, TEMP). The resented side is bit-unchanged
    (kindness_pressure=0 from a resented source -> no warmth, no inhibition); the contrast sharpens to
    cold-vs-warm."""
    res = _run("prisoner_bias_resentful", "cichy", 8)
    neu = _run("prisoner_bias_neutral", "cichy", 8)
    assert "cold_response" in _actions(res)
    assert "cold_response" not in _actions(neu)
    assert "positive_response" in _actions(neu)


def test_C_mustnotmove_per_source_resentful():
    """C1 must-not-move: insult/help from the guard touch only relations[guard] (per-source). The
    relation to 'player' is untouched on every dim, and respect[guard] doesn't move (insult deposits
    resentment, help deposits trust+(-resentment); neither touches respect)."""
    tr = _run("prisoner_bias_resentful", "cichy", 8)
    for dim in ("trust", "respect", "resentment"):
        assert (
            abs(_rel_final(tr, "player", dim) - _rel_initial(tr, "player", dim))
            < _UNCHANGED
        )
    assert (
        abs(_rel_final(tr, "guard", "respect") - _rel_initial(tr, "guard", "respect"))
        < _UNCHANGED
    )
    # And the channels that DO move:
    assert _rel_final(tr, "guard", "trust") > _rel_initial(
        tr, "guard", "trust"
    )  # help builds trust


def test_C4_lutek_stays_neutral_at_global_threshold():
    """C4 (no-leak guard, PASS today): the same public insult leaves Lutek neutral -- his cold stays
    under the GLOBAL threshold. Note his ordering is cold > outburst (opposite of Cichy)."""
    tr = _run("insult_public", "lutek", 5)
    assert set(_actions(tr)) == {"neutral"}
    assert max(_cold(tr)) < _react_threshold("lutek", "cold_response")
    tk0 = tr.ticks[0]
    assert tk0.potentials["cold_response"] > tk0.potentials["outburst"]


def test_C4_no_leak_proves_theta_must_be_private():
    """C4 (the binding constraint, number-free): Lutek's cold peak EXCEEDS resentful-Cichy's cold from
    the overture. So any GLOBAL theta low enough to fire resentful Cichy would ALSO fire Lutek -> the
    prisoner threshold MUST be private to Cichy. This is the `lutek_stays` margin in prisoner_margins."""
    lut_peak = max(_cold(_run("insult_public", "lutek", 5)))
    res = _run("prisoner_bias_resentful", "cichy", 8)
    cichy_cold_min = min(_cold(res)[_overture_idx(res) :])
    assert lut_peak > cichy_cold_min


# ============================ Cross-cutting invariants ============================


def test_INV1_resentment_is_per_source():
    """INV1: insult from 'player' raises resentment[player] ONLY; resentment[marta] is untouched, and
    the insult deposits resentment alone (trust/respect[player] unchanged)."""
    tr = _run("insult_public", "wojslaw", 4)
    assert _rel_final(tr, "player", "resentment") > _rel_initial(
        tr, "player", "resentment"
    )
    assert (
        abs(
            _rel_final(tr, "marta", "resentment")
            - _rel_initial(tr, "marta", "resentment")
        )
        < _UNCHANGED
    )
    for dim in ("trust", "respect"):
        assert (
            abs(_rel_final(tr, "player", dim) - _rel_initial(tr, "player", dim))
            < _UNCHANGED
        )


def test_INV2_only_events_move_relations():
    """INV2: a non-relational event (food_given) books no relational delta. Witnessed on Halgrim
    same-soup (action cold_response, empty post-effects), isolating the EVENT's effect on relations.
    (Wojslaw's run DOES move resentment[marta] -- via the OUTBURST post-effect, an action cost, not
    the food event; that is why we witness INV2 on the action-with-no-post-effect run.)"""
    tr = _run("same_soup_bad_day", "halgrim")
    for dim in ("trust", "respect", "resentment"):
        assert (
            abs(_rel_final(tr, "marta", dim) - _rel_initial(tr, "marta", dim))
            < _UNCHANGED
        )


def test_INV3_standing_resentment_does_not_move_emotions():
    """INV3 (controlled, exact): two identical Cichy runtimes differing ONLY in standing
    resentment[player] (1.0 vs 0.0), with NO events, evolve bit-identical GLOBAL states. update reads
    relation dims only into relation deltas, never into a global-state delta, and with no event there is
    no relational channel for affective_bias to scale -> standing resentment alone moves nothing."""
    cfg = _persona("cichy")
    hi = init_runtime(cfg, {"relations": {"player": {"resentment": 1.0}}})
    lo = init_runtime(cfg, {"relations": {"player": {"resentment": 0.0}}})
    for t in range(6):
        th = tick(hi, t, None)
        tl = tick(lo, t, None)
        assert th.state_after_post.global_state == tl.state_after_post.global_state
    # Sanity: the standing resentment really did differ (the invariant isn't vacuous).
    assert hi.relations["player"]["resentment"] > lo.relations["player"]["resentment"]
