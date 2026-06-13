# M20.1 C1 — measured loop operating points per coincidence depth

Corpus sample: 3/persona, waking ticks. n(<=2-way)=43297, n(>=3-way)=391. Burst OFF (linear-loop operating points; the local-gain argument linearizes around these).

| set | anger p99 | stress p99 | anger max | stress max |
|---|---|---|---|---|
| <=2-way (must stay stable) | 0.443 | 0.442 | 0.700 | 0.526 |

| set | anger p50 | stress p50 | anger max | stress max |
|---|---|---|---|---|
| >=3-way (burst-allowed) | 0.257 | 0.153 | 0.700 | 0.517 |

The <=2-way p99 (anger*, stress*) is the BINDING stable operating point: k_esc is chosen so
the escalated 2-cycle Jury margin stays >= 0 there (with a safety fraction). The >=3-way
points are where the burst is allowed to cross. Consumed by calibration/calibrate_burst.py.
