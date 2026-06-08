"""Diagnostics (diagnostics.py) -- a light smoke test. These are derived artifacts (not goldens,
not bit-stable), so we only check that they generate FROM a trace and write files; the curves'
correctness is the metrics/loss tests' job (a plot can show nothing the tests don't)."""

import pytest

pytest.importorskip("matplotlib")


def test_generate_writes_plot_and_table(tmp_path):
    from engine.diagnostics import dump_debug_table, plot_impulse_contributions

    png = plot_impulse_contributions(out_dir=tmp_path)
    csv = dump_debug_table(
        "food_impulse", "halgrim", "food_impulse", 90.0, out_dir=tmp_path
    )
    assert png.exists() and png.stat().st_size > 0
    assert csv.exists() and csv.read_text(encoding="utf-8").startswith("t,sec,action")
