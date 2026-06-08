"""Unit tests for the shared per-entity filter resolver (engine/filters.py, spec section 5/14).

Covers the two pure functions and, above all, the IDENTITY-by-default property that makes every
migration onto this kernel bit-identical: an unpopulated table or a zero gain leaves a signal unchanged.
"""

from engine import filters

# --- lookup: the entity -> scalar seam ------------------------------------------------------------


def test_lookup_present_returns_value():
    assert filters.lookup("rose", {"rose": 0.7, "thorn": -0.2}) == 0.7


def test_lookup_absent_returns_neutral():
    assert filters.lookup("daisy", {"rose": 0.7}) == 0.0


def test_lookup_none_entity_returns_neutral():
    assert filters.lookup(None, {"rose": 0.7}) == 0.0


def test_lookup_empty_table_is_neutral():
    assert filters.lookup("anything", {}) == 0.0


def test_lookup_custom_neutral():
    assert filters.lookup("x", {}, neutral=1.0) == 1.0


# --- factor: the 1 + gain*sign*value modulation ---------------------------------------------------


def test_factor_zero_gain_is_identity():
    assert filters.factor(0.9, 0.0) == 1.0


def test_factor_zero_value_is_identity():
    assert filters.factor(0.0, 0.5) == 1.0


def test_factor_positive():
    # liked entity, positive gain -> amplifies above 1
    assert filters.factor(0.5, 0.5) == 1.25


def test_factor_sign_flips_direction():
    # a negative polarity channel inverts the bend (relation_filter's polarity_sign)
    assert filters.factor(0.5, 0.5, sign=-1.0) == 0.75


def test_factor_compose_is_identity_when_either_neutral():
    # the bit-identical guarantee: neutral table value OR zero gain -> factor 1.0 -> value unchanged
    value = filters.lookup("stranger", {})  # -> 0.0
    assert filters.factor(value, 0.5) == 1.0
    populated = filters.lookup("friend", {"friend": 0.8})
    assert filters.factor(populated, 0.0) == 1.0
