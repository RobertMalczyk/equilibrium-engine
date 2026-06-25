# State-response diagnostic -- halgrim

Each state is a bounded first-order leaky integrator `x[n+1] = decay*x[n] + gain*event[n] + drift`, `decay = 2**(-dt/half_life)`. An event is a **finite single-tick deposit**, not a Dirac delta; the impulse response is the bounded exponential tail. `x_inf = drift/(1-decay)` is the unconstrained drift steady state (before couplings/clamp); a flagged state relies on clamp saturation.

`dt = 3` (derived from `min(half_life)/nyquist`).

| state | half_life | decay | drift | x_inf (drift) | clamp-reliant | impulse response (unit event) |
|---|---|---|---|---|---|---|
| hunger | 3000 | 0.9993 | 0.001 | 1.443 | **YES** | 1.000, 0.999, 0.999, 0.998, 0.997, 0.997 |
| fatigue | 2000 | 0.9990 | 0.0015 | 1.443 | **YES** | 1.000, 0.999, 0.998, 0.997, 0.996, 0.995 |
| boredom | 150 | 0.9862 | 0.004 | 0.2905 | no | 1.000, 0.986, 0.973, 0.959, 0.946, 0.933 |
| stress | 70 | 0.9707 | 0 | 0 | no | 1.000, 0.971, 0.942, 0.915, 0.888, 0.862 |
| frustration | 45 | 0.9548 | 0 | 0 | no | 1.000, 0.955, 0.912, 0.871, 0.831, 0.794 |
| anger | 30 | 0.9330 | 0 | 0 | no | 1.000, 0.933, 0.871, 0.812, 0.758, 0.707 |
| satisfaction | 35 | 0.9423 | 0 | 0 | no | 1.000, 0.942, 0.888, 0.837, 0.788, 0.743 |
| self_control | 50 | 0.9593 | 0 | 0 | no | 1.000, 0.959, 0.920, 0.883, 0.847, 0.812 |
| duty | 600 | 0.9965 | 0 | 0 | no | 1.000, 0.997, 0.993, 0.990, 0.986, 0.983 |
| sleep_pressure | 2000 | 0.9990 | 0 | 0 | no | 1.000, 0.999, 0.998, 0.997, 0.996, 0.995 |

> **Clamp-reliance warning:** hunger, fatigue have a drift steady state outside [0,1] -- they pin at the clamp. (Expected for the *accumulator* role -- hunger/fatigue/sleep_pressure are designed to ride toward the ceiling and are reset by eat/sleep; a clamp-reliant *emotion* state, by contrast, would be a calibration smell.)

## anger <-> stress loop stability

- Jury margin: `0.000760085` (bound `0.00196008`, ratio `0.388`)
- dominant eigenvalue/pole: `0.9913+0.0000i` -> |pole| = `0.9913`
- effective tail half-time: `79.5 ticks (~238s)`
- stable: `True`
- WARNING: near-unit dominant pole rho=0.9913: stable but expect a LONG emotional tail
