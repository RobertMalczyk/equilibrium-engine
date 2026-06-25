# Moral-tension (M-J) test report

**Subsystem:** M-J moral overlay (guilt · secrecy/secrets · lies · accusation · suspicion · betrayal),
an **opt-in** layer on the deterministic engine. Merged to `main`; calibration **closed**.

> **There is no PASS/FAIL rate for the moral layer.** Unlike the base believability corpus (binary
> per-record judging), moral behaviour is judged on a **fuzzy 1–5 quality scale** (believability +
> curve_plausibility). The headline numbers below are *mean judge scores*, not pass counts.

---

## 1. How the moral layer is tested

Three judging surfaces feed the §10 objective (believability + curve_plausibility), each preceded by a
**deterministic pre-filter** so LLM tokens are only spent on candidates that already pass the hard gates:

| layer | what it checks | tool |
|---|---|---|
| **Deterministic pre-filter** | Jury + litmus gates over an 81-point magnitude grid; no LLM | `calibration/calibrate_moral.py` |
| **Litmus blind judge** | 12 single-situation observable vignettes (guilt/lie/confide/probe) | `eval/render_moral.py` |
| **Gate-C corpus blind judge** | the full moral corpus across all personas × situations | `eval/moral_corpus.py` |
| **Multi-day blind judge** | half-life persistence over 4 believable days | `eval/moral_multiday.py` |

All blind judging is **paced** — single agents spread over time, never one large parallel burst.

---

## 2. Gate-C moral corpus

**126 observable vignettes** (regenerable: `python -m eval.moral_corpus --build`) =
**7 personas** (branic, cichy, edda, halgrim, lutek, welf, wojslaw) × moral situations:

| situation | vignettes | trait contrast exercised |
|---|---|---|
| probe (wrong, then questioned) | 28 | guilt_prone / hardened / habitual_liar / empathic |
| confide (friend present after a wrong) | 21 | discreet / gossip_prone / empathic |
| accusation (falsely accused) | 14 | injustice-sensitive / conflict-avoidant |
| suspicion (watched, innocent) | 14 | avoidant / sensitive |
| betrayal (a trusted man lied) | 7 | one representative per persona |
| multi-day guilt | 42 | guilt_prone / hardened / empathic × minor/serious half-life |

Each vignette renders to **plain-language, observable** demeanor + actions only — no engine vocabulary —
so the judge scores behaviour, not internals.

### Blind-judge results (Sonnet, 1–5)

| | mean |
|---|---|
| full-corpus initial sweep | **3.93** |
| weak situation — betrayal | 3.05 → **4.0** (residual close: 4.1, curve 4.3) |
| weak situation — suspicion | 3.29 → **4.0** |
| confide (gossip vs discreet split) | → **3.39** |

The full sweep (154 records incl. extra variants since consolidated to 126) scored **3.93/5**. A **paced
collect-fix-rejudge loop** lifted the two weak situations from 3.05/3.29 to **4.0/4.0**. Fixed clusters,
all confirmed by the blind judge:

- **innocent-under-suspicion lying** — an innocent never fires a lie under exposure (sensitive variant
  given `honesty_humility`); judge confirms "no innocent lies".
- **betrayal anger snap-recovery** — the renderer collapses oscillation into a sustained chill; a
  betrayal lands in withdrawn distrust, never on a flash of temper.
- **variant indistinguishability** — kind↔variant pairing; the confide situation makes gossip vs
  discreet observably distinct ("unburdens vs holds back").

Two diminishing-returns residuals were then closed (betrayal arcs always land the chill;
suspicion-avoidant arcs *develop* to fully closed-off rather than repeating a wary beat) — verified by a
single paced re-judge (`lands_chill: true`, `verbatim_repeat_feel: false`). Verdicts:
`calibration/moral_corpus_verdict.json`, `calibration/moral_corpus_residual_verdict.json`.

---

## 3. Litmus blind judge

12 single-situation observable vignettes (confess/lie/confide/probe). Believability across the
collect-fix-rejudge passes:

| pass | mean believability |
|---|---|
| initial | 3.17 |
| after fixes | 4.42 |
| **final** | **4.83** (10×5, 2×4) |

Verdict: `calibration/moral_judge_verdict.json`.

---

## 4. Half-life calibration (multi-day blind judge)

The short litmus scenarios cannot discriminate the moral **half-lives** (decay timescales); only
multi-day arcs at the believable timescale can. Two were judge-validated:

**Guilt** — which guilt persistence over 4 days reads believable for a *serious* unconfessed wrong?

| arc | judge score | reading |
|---|---|---|
| 72h | **5/5** | sustained visible weight across four days, present but not resolving |
| 18h | 3/5 | plausible fade, but a clean conscience by day 4 feels too tidy for a serious wrong |
| 6h | 1/5 | near-total dissipation in one evening — denial or sociopathy, not a conscience |

→ confirms the **minor(18h) / serious(72h) split**, implemented without a second state: an active
`Secret` re-injects guilt ∝ `moral_weight` × salience (`ledger_params.secret_weight_to_guilt`), so a
serious unconfessed wrong keeps weighing (~72h feel) while a minor one fades (18h). Confession/exposure
inactivates the secret and the drip stops → relief.

**Suspicion** — half-life lowered **48h → 24h**, judge-ranked **24h > 48h > 14d**: 24h "fast enough to
feel healthy, slow enough to feel real"; 48h "slightly rigid"; 14d "pathological" without evidence.

`perceived_injustice` was **not** half-life-judged — it is **confounded** (the persona vents it via
`blame_other`, so it discharges rather than purely decaying); its within-scenario behaviour is covered by
the corpus (accusation). Verdicts: `calibration/moral_multiday_verdict.json`,
`calibration/moral_halflife_verdict.json`.

---

## 5. Deterministic guarantees

| guarantee | status |
|---|---|
| pre-filter survivors (81-point grid, hard gates) | **18/81** (unchanged after every magnitude edit) |
| full test suite | **399 passed, 4 skipped** |
| legacy goldens (no overlay) | **byte-identical** |
| base 1400 believability corpus across the whole M-MEM + M-J merge | **byte-identical** (deterministic build+diff vs pre-feature baseline `65249a1`) |

The last row is the key opt-in proof: enabling the moral subsystem changes **zero** records of the base
corpus, so the [base blind-judge believability numbers](hourly_runs/FINAL_report.md) stand unchanged. A
re-judge would re-score identical text — it was deliberately not run (token discipline).

**Calibration lesson (recorded):** re-run the deterministic pre-filter after *any* magnitude change — a
naive confess-relief bump once broke the confide litmus.

---

## 6. Deferred (named, not built)

- corpus scaling (more personas/variants, new situation types);
- evidence-grade suspicion (a longer 14d half-life once there *is* evidence);
- Inn integration + designer-readable half-life units (e.g. "18h").

Plans: `docs/moral_tension_PLAN.md`, `docs/moral_tension_impl_spec.md`, `docs/moral_calibration_plan.md`.
