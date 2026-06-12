"""Unit + property tests for the affinity FIELD (engine/affinity_field.py, spec section 5).

Covers: build validation (normalization, zero vector, kernel params), the resolution order at the
seam (exact-entry override beats the blend; field only answers for unknowns; ``field=None`` is
bit-identical to the historical flat lookup), the neutral-prior behaviour (far from every anchor
reads ~0), the debuggability contract (``explain`` reconstructs ``resolve`` exactly), and the spec's
demo landscape: roses/flowers (category vs adored sub-region) and dogs-vs-animals (a liked island
inside a disliked region) BY COORDINATE PROXIMITY, not enumeration.

Test-fixture numbers are authored demo data (a test persona's landscape), not engine literals.
"""

import math

import pytest

from engine import affinity_field, filters
from engine.affinity_field import build

# --- a small authored demo landscape (2D for readability; the engine is dimension-agnostic) -------
# Directions (unit-normalized by build): flowers point east; roses a touch north of east (inside
# the flowers region); animals point north; dogs a touch east of north (inside the animals region);
# stones point southwest, far from everything that carries valence.

DEMO = {
    "tau": 0.10,
    "w0": 0.05,
    "coordinates": {
        "daisy": [0.98, 0.20],  # near the flowers anchor
        "wild_rose": [0.92, 0.40],  # near the roses anchor (the adored sub-region)
        "stray_dog": [0.45, 0.89],  # near the dogs anchor
        "weasel": [0.05, 1.00],  # animals region, far from dogs
        "pebble": [-0.70, -0.70],  # far from every anchor
    },
    "anchors": [
        {"name": "flowers", "coord": [1.00, 0.10], "value": 0.5},
        {"name": "roses", "coord": [0.90, 0.44], "value": 0.9},
        {"name": "animals", "coord": [0.00, 1.00], "value": -0.6},
        {"name": "dogs", "coord": [0.40, 0.92], "value": 0.7},
    ],
}


@pytest.fixture()
def demo_field():
    return build(DEMO, "test")


# --- build: validation + hygiene ------------------------------------------------------------------


def test_build_absent_or_empty_is_none():
    assert build(None) is None
    assert build({}) is None
    assert build({"tau": 0.1, "w0": 0.0}) is None  # params without content = no field


def test_build_coordinates_without_anchors_is_none():
    raw = {"tau": 0.1, "w0": 0.0, "coordinates": {"x": [1.0, 0.0]}}
    assert build(raw) is None  # nothing to blend = identity


def test_build_normalizes_coordinates_and_anchors(demo_field):
    for vec in demo_field.coordinates.values():
        assert math.isclose(sum(x * x for x in vec), 1.0, rel_tol=1e-12)
    for a in demo_field.anchors:
        assert math.isclose(sum(x * x for x in a.coord), 1.0, rel_tol=1e-12)


def test_build_zero_vector_is_config_error():
    raw = dict(DEMO, coordinates={"void": [0.0, 0.0]})
    with pytest.raises(ValueError, match="zero vector"):
        build(raw, "test")


def test_build_requires_positive_tau():
    raw = dict(DEMO, tau=0.0)
    with pytest.raises(ValueError, match="tau"):
        build(raw, "test")


def test_build_rejects_negative_w0():
    raw = dict(DEMO, w0=-0.1)
    with pytest.raises(ValueError, match="w0"):
        build(raw, "test")


def test_build_rejects_mixed_dimensions():
    raw = dict(DEMO, coordinates=dict(DEMO["coordinates"], odd=[1.0, 0.0, 0.0]))
    with pytest.raises(ValueError, match="dimensionalities"):
        build(raw, "test")


def test_build_anchor_may_reference_a_coordinates_entry():
    raw = {
        "tau": 0.1,
        "w0": 0.0,
        "coordinates": {"flowers": [1.0, 0.0]},
        "anchors": [{"name": "flowers", "value": 0.5}],
    }
    f = build(raw, "test")
    assert f.anchors[0].coord == (1.0, 0.0)


def test_build_anchor_without_any_coord_is_config_error():
    raw = {
        "tau": 0.1,
        "w0": 0.0,
        "coordinates": {"x": [1.0, 0.0]},
        "anchors": [{"name": "ghost", "value": 0.5}],
    }
    with pytest.raises(ValueError, match="ghost"):
        build(raw, "test")


# --- the seam: resolution order at filters.lookup --------------------------------------------------


def test_lookup_without_field_is_bit_identical_to_flat():
    table = {"rose": 0.7}
    assert filters.lookup("rose", table) == filters.lookup("rose", table, field=None)
    assert filters.lookup("daisy", table, field=None) == 0.0


def test_exact_entry_override_beats_the_blend(demo_field):
    # daisy sits in a positive region of the landscape, but an explicit authored entry wins outright
    table = {"daisy": -1.0}
    assert filters.lookup("daisy", table, field=demo_field) == -1.0
    # and the authored value is returned EXACTLY (never routed through the kernel + prior)
    assert filters.lookup("daisy", table, field=demo_field) is table["daisy"]


def test_unknown_entity_with_no_coordinate_is_neutral(demo_field):
    assert filters.lookup("never_heard_of_it", {}, field=demo_field) == 0.0


def test_none_entity_is_neutral_with_field(demo_field):
    assert filters.lookup(None, {}, field=demo_field) == 0.0


# --- the blend: generalization by proximity --------------------------------------------------------


def test_daisy_near_flowers_reads_positive(demo_field):
    v = filters.lookup("daisy", {}, field=demo_field)
    assert v > 0.0


def test_rose_subregion_reads_higher_than_daisy(demo_field):
    # likes flowers (+), SUPER-likes roses (++): proximity to the stronger anchor orders the blend
    daisy = filters.lookup("daisy", {}, field=demo_field)
    rose = filters.lookup("wild_rose", {}, field=demo_field)
    assert rose > daisy > 0.0


def test_dog_island_inside_disliked_animals(demo_field):
    # dislikes animals (-) but likes dogs (+): the liked sub-region wins near it...
    dog = filters.lookup("stray_dog", {}, field=demo_field)
    assert dog > 0.0
    # ...while the rest of the animals region stays disliked
    weasel = filters.lookup("weasel", {}, field=demo_field)
    assert weasel < 0.0


def test_far_from_every_anchor_reads_near_neutral(demo_field):
    # the neutral prior dominates when every kernel weight is tiny
    pebble = filters.lookup("pebble", {}, field=demo_field)
    assert abs(pebble) < 0.05


def test_blend_is_clamped_signed():
    raw = {
        "tau": 0.05,
        "w0": 0.0,
        "coordinates": {"x": [1.0, 0.0]},
        "anchors": [
            {"name": "a", "coord": [1.0, 0.0], "value": 1.0},
            {"name": "b", "coord": [0.99, 0.14], "value": 1.0},
        ],
    }
    f = build(raw, "test")
    assert -1.0 <= affinity_field.resolve("x", f) <= 1.0


# --- debuggability contract -------------------------------------------------------------------------


def test_explain_reconstructs_resolve_exactly(demo_field):
    for entity in DEMO["coordinates"]:
        contributions = affinity_field.explain(entity, demo_field)
        total_w = sum(w for _, w, _ in contributions)
        expected = sum(w * v for _, w, v in contributions) / (total_w + demo_field.w0)
        assert math.isclose(
            affinity_field.resolve(entity, demo_field), expected, rel_tol=1e-12
        )


def test_explain_names_every_anchor(demo_field):
    names = [n for n, _, _ in affinity_field.explain("daisy", demo_field)]
    assert names == [a.name for a in demo_field.anchors]


def test_explain_unknown_entity_is_empty(demo_field):
    assert affinity_field.explain("never_heard_of_it", demo_field) == []


# --- integration: loader -> mapper (the real call path) ---------------------------------------------


def test_field_through_loader_and_mapper():
    from engine import mapper
    from engine.schema import HistoryFeatures, RawEvent
    from engine.yaml_io import load_persona

    overrides = {
        "affinity_field": {
            "tau": 0.1,
            "w0": 0.05,
            "coordinates": {"mushroom_stew": [0.95, 0.3, 0.1]},
            "anchors": [{"name": "hot_meals", "coord": [1.0, 0.2, 0.0], "value": 0.6}],
        }
    }
    cfg = load_persona(
        "data/personas/lutek.yaml",
        "calibration/defaults.yaml",
        param_overrides=overrides,
    )
    # an UNKNOWN item blends through the field...
    out = mapper.map_event(
        RawEvent(t=0, type="food_given", intensity=0.5, item="mushroom_stew"),
        cfg,
        HistoryFeatures(),
    )
    assert out["preference_match"].value == affinity_field.resolve(
        "mushroom_stew", cfg.affinity_field
    )
    assert out["preference_match"].value > 0.0
    # ...while an AUTHORED affinities entry returns its exact value (override)
    soup = mapper.map_event(
        RawEvent(t=0, type="food_given", intensity=0.5, item="cabbage_soup"),
        cfg,
        HistoryFeatures(),
    )
    assert soup["preference_match"].value == cfg.affinities["cabbage_soup"]


def test_loader_without_block_yields_no_field():
    from engine.yaml_io import load_persona

    cfg = load_persona("data/personas/lutek.yaml", "calibration/defaults.yaml")
    assert cfg.affinity_field is None


# --- determinism ------------------------------------------------------------------------------------


def test_resolve_is_deterministic(demo_field):
    first = [affinity_field.resolve(e, demo_field) for e in sorted(DEMO["coordinates"])]
    second = [
        affinity_field.resolve(e, demo_field) for e in sorted(DEMO["coordinates"])
    ]
    rebuilt = build(DEMO, "test")
    third = [affinity_field.resolve(e, rebuilt) for e in sorted(DEMO["coordinates"])]
    assert first == second == third
