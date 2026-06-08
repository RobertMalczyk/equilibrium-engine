# Block diagram — night & sleep (M7.5 Part B: fast-state reset, slow-cause persistence)

> Maintained in two forms (spec §12): **control** (the relaxation drive + the SLEEP-mode reset, signed) and
> **functional** (the night cycle in domain language). Synchronized with the engine + `calibration/defaults.yaml`.
> The multi-day reset: *"sleep angry, wake calm, but the grudge stays."* One new mode + one decoupled state;
> **no trait/param specialization** — every persona sleeps by the same generic mechanism, and sleep mutates
> only the FAST state vector for a night (no trait, relation, or config parameter changes → personas STATIC).

## Functional form (the night cycle)

```
   WORLD (day/night runner)                ENGINE (pure per-tick)
   ------------------------                ----------------------
   nightfall event ──► night channel ──► sleep_pressure ↑           (a decoupled accumulator; setpoint 0,
                                              │                       no drift -> 0 unless the world sends night)
                                              ▼  read in 2nd role
        sleep_urge = w·sleep_pressure + w·fatigue − arousal
                                              │   arousal = w·stress + w·anger + w·frustration  (BLOCKER:
                                              ▼   wound-up => delayed onset, not prevention)
                              [ sleep_urge ≥ theta_start ]  ──► START `sleep`  ──►  SLEEP mode
                                                                                      │
   in SLEEP (per-tick, placeholders):                                                 │
     FAST  anger↓↓ stress↓↓ frustration↓↓ satisfaction→0     (reset)                  │
     PHYS  fatigue↓↓  self_control↑  hunger↑(slow)  sleep_pressure↓↓ (discharge)      │
     SLOW  trust / respect / resentment  — UNTOUCHED (grudge persists by construction)│
                                                                                      ▼
            WAKE:  rested (end_when_below {fatigue, sleep_pressure}) ─► COOLDOWN ─► IDLE
                   OR a strong provocation (≥ theta_interrupt) ─► wake + react   (wake-on-threat)
                   a mild stimulus never clears theta_interrupt ─► slept through (ignored)
```

## Control form (relaxation drive + signed reset)

```
   night ──(+g)──►┌── sleep_pressure ──┐ (∫ decay; setpoint 0; NO drift)        NEW state, decoupled
   sleep per-tick │     (state)        │
   discharge ◄────┘                    └─►(+w_sp)─►(Σ)─► sleep_urge ─►[≥θ_start]─► START sleep ─► SLEEP
   fatigue ──────────────────(+w_fat)─────►(Σ)        ▲
   stress,anger,frustration ─(+w·)─► arousal ─(−)─────┘   (derived BLOCKER: −arousal delays onset)

   SLEEP mode (signed per-tick, config placeholders):
     anger,stress,frustration ─(−−)─► toward 0      satisfaction ─(→0)
     fatigue ─(−−)            self_control ─(+)      hunger ─(+ slow)      sleep_pressure ─(−−) discharge
     trust,respect,resentment : NO edge  ── slow causes persist
     ┌─ MODE FF ─────────────────────────────────────────────────────────────────────┐
     │  IDLE --START sleep (sleep_urge≥θ_start)--> SLEEP                                │
     │  SLEEP --end_when_below{fatigue,sleep_pressure}--> COOLDOWN (rested -> wake)     │
     │  SLEEP --max_react ≥ theta_interrupt--------> COOLDOWN + reactive (wake-on-threat)│
     │  SLEEP --else--------------------------------> SLEEP (sleep on; mild stimulus ignored)│
     └──────────────────────────────────────────────────────────────────────────────┘
```

## Invariants made visible
- **Sparse / neutral default:** no `nightfall` ⇒ `sleep_pressure ≡ 0` ⇒ `sleep_urge ≤ 0` ⇒ the drive never
  fires. Single-day litmus/goldens are bit-identical (only an additive `sleep_pressure:0.0` trace field).
- **Decoupled:** `sleep_pressure` is in no state→state coupling ⇒ no new pole; long half-life ⇒ `dt =
  min(half_life)/10` unchanged. The SLEEP-mode reset is a per-tick effect (like an activity), not a coupling.
- **Fast vs slow by construction:** the sleep per-tick lists only the FAST + physiological states; relations
  are absent ⇒ the grudge survives the night. No special-cased stimulus tiers — wake-on-threat is just the
  existing high `theta_interrupt`. The world owns the clock (`nightfall`); the engine stays pure.
