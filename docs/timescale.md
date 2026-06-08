# The believable timescale — one knob + a few honest anchors

> How the eval/story world is paced, and exactly how turning the knob changes it. The engine's placeholder
> constants run a *complete* dynamical system but at a **compressed** clock (anger half-life ≈ 30 s). The
> believable layer (`calibration/calibrated_timescale.yaml`, applied by `eval/calibrated.py:timescale_overrides`)
> stretches that to a real day. **Eval/story path only — `defaults.yaml` and the frozen golden/litmus suite
> stay at `time_scale = 1`.** Verified by `eval/timescale_keeper.py` against `timescale_ground_truth.yaml`.

## The one knob: `time_scale`
Multiplies **every half-life** (fast emotions, relations, boredom, sleep-pressure, duty) by one factor.
Because `dt = min(half_life)/10` scales with them, every per-tick **decay ratio is invariant** — so the
whole emotional + relational world keeps its *shape*; only the wall-clock stretches. This part of the trace
is **bit-identical in ticks** (see `engine/yaml_io.py`). Turning the knob moves the whole world together:

| `time_scale` | anger half-life | dt | a 24 h day |
|---|---|---|---|
| 20 | ~10 min | ~60 s | brisk |
| **40** | **~20 min** | **~120 s** | **the believable default (~717 ticks)** |
| 80 | ~40 min | ~240 s | languid |

A grudge always fades over weeks (relations scale with the knob too). The persona **contrasts**
(burst/cold/shrug, cooperate/refuse, who-bores-first) are **timescale-invariant** — they are trait-driven
selections at the event tick, so they survive any knob setting (verified: identical at `time_scale` 1 and 40).

## What the knob can't do, and why (the duration anchors)
A single uniform knob hits **6 of the 10** believability targets on its own. It *can't* fix four, because the
placeholder **ratios** between the fast emotions and the slow physiological accumulators were never
calibrated (e.g. uniform-scaling makes hunger reach "half-hungry" in ~97 h instead of ~5 h). Those four are
tied to the **24 h day**, not to how fast feelings move, so they get explicit real-world anchors — and the
per-tick **rates are *derived* from them** (closed form), never hand-tuned:

| anchor (`durations:` / `ceilings:`) | derives | how |
|---|---|---|
| `boredom_to_seek` ≈ 2 h | boredom drift | reach the urge-crossing level in that time |
| `hunger_to_half` ≈ 5 h + `ceilings.hunger` 0.62 | hunger half-life **and** drift | rise to 0.5 in the time, asymptote at the ceiling |
| `fatigue_to_high` ≈ 14 h + `ceilings.fatigue` 0.85 | fatigue half-life **and** drift | same |
| `night_length` ≈ 7 h | sleep-pressure discharge | 1.0 → 0.10 over the night |
| `seeking_giveup` ≈ 30 min | the seek timeout (ticks) | `round(giveup/dt)` |
| `wake_hunger` ≈ 0.4 | the overnight hunger drip | level / night-ticks |

`hunger`/`fatigue` get a **ceiling** (not a uniform-scaled half-life) so they cap believably — a meal can
still cut hunger back below half on a lean day, instead of running to 1.0.

## The only genuinely-independent numbers (2 gains)
`couplings.stress.{hunger,fatigue}` — *how hard* hunger/fatigue drive stress. A coupling **strength**, not a
duration, so not derivable from the knob. Halved from the placeholders (which were tuned when hunger never
left ~0; at believable levels they over-drove the loop → enraged-by-noon). **Not** the anger↔stress Jury
loop, so loop stability is untouched.

## Parameter inventory (the magic-number audit)
The believable world is **`time_scale` (1) + 6 durations + 2 ceilings + 2 gains ≈ 11 meaningful inputs**;
the ~16 per-tick rates and the relations/fast-cluster half-lives are **derived**. Everything is documented
in `calibrated_timescale.yaml`; nothing is a hand-tuned magic number.

## What it does NOT change
The engine, the topology, the trait coefficients, the action-selection math, and the frozen `defaults.yaml`
path are all untouched. This is a clock + a handful of physiological anchors layered on the eval path only.
