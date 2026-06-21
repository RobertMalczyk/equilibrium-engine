# M3 (Phase C) burst source-valence gate — believability re-judge (burst-ON only)

All-Sonnet, judge model held constant. M3 only affects burst-ON, so only the 1400 burst-ON scenarios
were re-judged (burst-OFF is byte-identical to run2). Paced 10/wave, ~90 min apart.

## Aggregate (burst-ON, 1400)
| run | PASS | rate |
|---|---|---|
| baseline | 1307 | 93.4% |
| run2 (M3 off, refined-M1) | 1304 | 93.1% |
| **run3 (M3 on)** | **1302** | **93.0%** |

run3 vs baseline: net -5 (61 fixed, 66 regressed). run3 vs run2: net -2 (35 fixed, 37 regressed). The
aggregate is FLAT — inside the run-to-run judge-noise band (large bidirectional churn). The signal is in
the targeted cluster + the deterministic conversions, not the aggregate.

## The targeted cluster — kindness/displacement (58 burst-ON flags in run2)
- **Cleared in run3 (→PASS): 23 (39%).**
- Still flagged: 35, of which:
  - **31 = still hostile at a kindness** — M3 reopened the kindness path (deterministic check: 50
    burst-ON kindness lines flipped hostile→warm), but at very high anger the kindness inhibition is
    too weak, so the reply is a low-tier "bristles" instead of warmth. **This is M20.1 CALIBRATION**
    (strengthen the kindness edge / lower theta_displace so warmth WINS), exactly as the plan predicted:
    M3 is topology; the magnitudes calibrate in M20.1.
  - 3 = cichy — a "kindness" from his resented guards; M3 correctly does NOT spare it (kindness_pressure
    0, it galls). Arguably correct behaviour / judge-debatable.
  - 1 = flag reason shifted to an unrelated issue.

## Conclusion
M3 is a **correct, necessary topology fix** (cleared 39% of the cluster where warmth could win;
deterministically converts genuine kindnesses to warmth; golden byte-identical; ships off by default).
It is **not sufficient alone**: the believability WIN is gated behind an M20.1 calibration step that
makes warmth actually win over escalated fury (the 31 residual "bristles at a kindness"). Recommended
next: calibrate the kindness-inhibition magnitude / theta_displace under the M20.1 boundedness gate, then
re-judge.
