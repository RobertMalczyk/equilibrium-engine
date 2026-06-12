# G6 — measured input co-occurrence (burst spec section 8)

Sample: 21 multiday corpus runs (3/persona, the sanity-gate runner), waking ticks only, n = 43688 tick-observations. Drive bins documented in `eval/measure_cooccurrence.py` (measurement discretization, not engine config).

## How many loop drives coincide per tick

| simultaneous drives | ticks | share |
|---|---|---|
| 0 | 18706 | 42.8% |
| 1 | 18539 | 42.4% |
| 2 | 6052 | 13.9% |
| 3 | 387 | 0.9% |
| 4 | 4 | 0.0% |

## Most frequent combinations (the ones the stability verification must cover)

| combination | ticks | share |
|---|---|---|
| hungry | 10032 | 23.0% |
| tired | 7028 | 16.1% |
| hungry + tired | 4814 | 11.0% |
| provoked | 890 | 2.0% |
| weather | 442 | 1.0% |
| hungry + provoked | 393 | 0.9% |
| provoked + tired | 277 | 0.6% |
| hungry + seeking | 186 | 0.4% |
| hungry + provoked + tired | 177 | 0.4% |
| hungry + weather | 177 | 0.4% |
| hungry + tired + weather | 157 | 0.4% |
| seeking | 147 | 0.3% |
| tired + weather | 141 | 0.3% |
| seeking + tired | 30 | 0.1% |
| hungry + seeking + tired | 26 | 0.1% |

**>=3-way coincidences: 391 ticks (0.89%).** Per the spec these are the
accepted rare-risk region: when they push the escalated loop past linear stability, that IS
the burst, and saturation + the latch bound it by construction. The PAIRS above are the
operating points the k_esc calibration must verify linear stability at.
