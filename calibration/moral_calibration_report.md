# M-J.4.4 calibration -- deterministic pre-filter

Grid: 81 points over gains.guilt.wrongdoing, gains.exposure_anxiety.probe, couplings.stress.guilt, half_lives.guilt.
Survivors (passed ALL hard gates): **18 / 81**.

Hard gates: Jury margin > 0; moral states bounded + no ceiling pin; the five litmus orderings hold.
Deterministic sub-score (~0.75 of the spec section 10 objective; curve_plausibility is the judge's job):
`0.45*persona_diff + 0.20*jury + 0.20*rel_sensitivity + 0.15*anti_pin`.

## Top survivors

| rank | det_score | persona_diff | jury | rel_sens | peak | point |
|---|---|---|---|---|---|---|
| 1 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.02, guilt=43200 |
| 2 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.02, guilt=64800 |
| 3 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.02, guilt=86400 |
| 4 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.03, guilt=43200 |
| 5 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.03, guilt=64800 |
| 6 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.03, guilt=86400 |
| 7 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.05, guilt=43200 |
| 8 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.05, guilt=64800 |
| 9 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.03, guilt=0.05, guilt=86400 |
| 10 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.05, guilt=0.02, guilt=43200 |
| 11 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.05, guilt=0.02, guilt=64800 |
| 12 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.05, guilt=0.02, guilt=86400 |
| 13 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.05, guilt=0.03, guilt=43200 |
| 14 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.05, guilt=0.03, guilt=64800 |
| 15 | 0.6923 | 6.0 | 0.00076 | 1.0 | 0.72 | wrongdoing=0.3, probe=0.05, guilt=0.03, guilt=86400 |

## Next step (AWAIT APPROVAL -- budgeted)
Take the top survivors to the LLM blind-judge sample (docs/moral_calibration_plan.md, step 2),
then the full judged 700+700 corpus (step 3). The judge scores curve_plausibility + confirms the
deterministic orderings.