# FULL 2800 re-judge — Phase A + M3 + renderer fix + coherent corpus (GATE CHECK)

All-Sonnet, judge model held constant. Re-baselined on the coherence-fixed corpus. Paced 28/wave × 10, ~58 min apart.

## Result — the gate is CLEARED
| run | PASS / 2800 | rate |
|---|---|---|
| pre-Phase-A baseline | 2618 | 93.5% |
| **Phase-A-only (run2) — THE GATE** | 2662 | **95.1%** |
| **Phase A + M3 + renderer + coherent corpus (run5)** | **2686** | **95.9%** |

- **run5 vs Phase-A-only: net +24** (79 fixed, 55 regressed). ✅ beats the gate.
- run5 vs baseline: net +68.

## Sub-corpus (run5 vs Phase-A-only)
| sub-corpus | baseline | Phase-A-only | run5 |
|---|---|---|---|
| day · burstOFF | 650 | 663 | 670 |
| day · burstON | 655 | 636 | **647** |
| multi · burstOFF | 661 | 695 | 693 |
| multi · burstON | 652 | 668 | **676** |

## Per persona (the corpus fix targets)
- **wojsław 351 → 375 (+24)** — corpus coherence (Marta no longer mocks-then-feeds) + M3.
- branic 376 → 381 (+5). cichy 387 → 382 (−5: intentional resented-guard behavior, judge-debatable; untouched).

## Conclusion
The combined stack — M1 (recency-gated mood) + M2 (acknowledge kindness) + M3 (burst source-valence gate)
+ the renderer-attribution fix + the corpus-coherence fix — reaches **95.9%**, clearing the Phase-A-only
gate (95.1%) by +24 with no sub-corpus regressing materially. The work is now eligible to propose for
merge (user merges).
