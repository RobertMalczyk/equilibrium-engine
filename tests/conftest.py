"""Test split: the fast core (golden trace, determinism, stability, metrics, loss reactions,
diagnostics smoke) runs by default in a few seconds. The SLOW optimizer runs (Morris screening +
CMA-ES + run_layer1 -- each hundreds of loss() evaluations) are gated behind --runslow, since Layer 2
will iterate on them a lot. Golden + determinism stay in the fast core ON PURPOSE.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="run slow optimizer/calibration tests (Morris + CMA-ES + run_layer1)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: optimizer/calibration run; excluded unless --runslow"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="optimizer run; pass --runslow to include")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
