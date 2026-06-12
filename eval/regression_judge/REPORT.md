# Full-corpus blind regression — 1400 scenarios (700 day + 700 multi-day)

Engine: branch `burst-saturation` (burst machinery present but NEUTRAL/disabled in all
shipped config; includes the stranger-grudge relational-deposit fix). Judges: one fresh
LLM agent per batch of 10 same-persona records, neutral rubric, no answer key.

| corpus | persona | pass | judged |
|---|---|---|---|
| day | branic | 100 | 100 |
| day | cichy | 100 | 100 |
| day | edda | 100 | 100 |
| day | halgrim | 99 | 100 |
| day | lutek | 100 | 100 |
| day | welf | 100 | 100 |
| day | wojslaw | 99 | 100 |
| multi | branic | 98 | 100 |
| multi | cichy | 99 | 100 |
| multi | edda | 30 | 30 |
| multi | halgrim | 99 | 100 |
| multi | lutek | 100 | 100 |
| multi | welf | 100 | 100 |
| multi | wojslaw | 100 | 100 |
| **day TOTAL** | | **698** | **700** (99.7%) |
| **multi TOTAL** | | **626** | **630** (99.4%) |

Baseline: multi-day full-700 (2026-06-08) ≈ 697/700 (batched 627/630 = 99.5%). The day
corpus had no prior full-700 blind run — its number here is baseline-setting.

## Flags (6)

- branic_multi_017: two snaps at 06:40/07:16 right after a recovered wake
- branic_multi_058: days-long flat defiant refusals to respected sergeant, little cooling between
- cichy_multi_060: Day 2 ~7 back-to-back furious eruptions, relentless rage cluster
- halgrim_day_027: mutters complaint at respected Edda on calm, unprovoked day
- halgrim_multi_030: cold cutting contempt aimed at respected Edda (22:48)
- wojslaw_day_097: erupts in fury at Marta merely bringing soup (19:57)

## Missing batch results (7)

- multi_edda_b03 … multi_edda_b09 (session limits ended the run; the 30 edda multi-day records
  that WERE judged all passed, and edda scored 99–100/100 in the 2026-06-08 full run — the gap is
  a coverage note, not a suspicion. User accepted concluding on 1330/1400.)

## CONCLUSION — NO REGRESSION

- **Multi-day: 626/630 judged = 99.4%**, statistically identical to the 2026-06-08 baseline
  (627/630 = 99.5%) — the burst-branch engine changes (k_esc/latch/displacement machinery, all
  neutral in shipped config, plus the stranger-grudge deposit fix) did not move the corpus.
- **Day corpus: 698/700 = 99.7% — the first-ever full blind run of this corpus; this number IS
  the baseline going forward.**
- **Every one of the 6 flags maps to a KNOWN residual family** (none is new):
  - `branic_multi_058` dense refusals — the standing branic_058 residual, verbatim.
  - `cichy_multi_060` eruption cluster — the saturation/runaway family, i.e. exactly the case the
    M20 burst calibration exists to address (currently neutral, so unchanged).
  - `halgrim_day_027` / `halgrim_multi_030` grumble/contempt at respected Edda — the halgrim_081
    family (bystander-respect texture).
  - `branic_multi_017` snaps right after waking — the cichy_015 fury-on-waking family.
  - `wojslaw_day_097` fury at Marta's soup — the soup/kindness family (cleared in the multiday
    corpus by Theme A; this single day-corpus occurrence is one in 700 and the displacement
    machinery that frames it properly ships with M20).
