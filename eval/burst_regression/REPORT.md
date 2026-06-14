# Outburst on/off — 10% blind regression

Sample: seed `1400`, coverage `10%` = 140 scenarios (day + multi-day), each judged blind under the M20.1 outburst overlay **disabled** (shipped default) and **enabled**. One fresh Sonnet judge per batch, neutral rubric, no answer key.

**94/140** sampled scenarios change their narration when the outburst machinery is armed (the rest are bit-identical -> burst inert there).

| corpus | persona | pass (off) | pass (on) | judged |
|---|---|---|---|---|
| day | halgrim | 10 | 10 | 10 |
| day | wojslaw | 10 | 10 | 10 |
| day | cichy | 9 | 10 | 10 |
| day | branic | 10 | 10 | 10 |
| day | lutek | 10 | 10 | 10 |
| day | welf | 10 | 10 | 10 |
| day | edda | 8 | 10 | 10 |
| multi | halgrim | 10 | 10 | 10 |
| multi | wojslaw | 10 | 10 | 10 |
| multi | cichy | 10 | 10 | 10 |
| multi | branic | 10 | 9 | 10 |
| multi | lutek | 10 | 10 | 10 |
| multi | welf | 10 | 9 | 10 |
| multi | edda | 10 | 10 | 10 |
| **day TOTAL** | | **67/70** | **70/70** | |
| **multi TOTAL** | | **70/70** | **68/70** | |

## Verdict deltas (off -> on): 5

> Reading the deltas: the blind judge is itself non-deterministic, so a delta on a scenario whose narration is **unchanged** (`narration changed = no`) is pure JUDGE VARIANCE — the same text scored differently by two different agents — NOT a burst effect. Only `narration changed = yes` deltas are attributable to arming the outburst overlay.

| scenario | off | on | narration changed |
|---|---|---|---|
| branic_multi_091 | PASS | FLAG | yes |
| cichy_day_042 | FLAG | PASS | yes |
| edda_day_079 | FLAG | PASS | no |
| edda_day_087 | FLAG | PASS | no |
| welf_multi_030 | PASS | FLAG | yes |

## Flags — outburst off (3)

- cichy_day_042: settled at ease 2 min after snapping; cooldown implausibly fast
- edda_day_079: castellan simply obeys stranger's order rather than ignoring it
- edda_day_087: castellan complies with stranger's order; authority profile tension

## Flags — outburst on (2)

- branic_multi_091: Day 1 full eruption at Halgrim's kindness with no prior buildup
- welf_multi_030: calm man snaps angrily at soup-bringer without clear provocation
