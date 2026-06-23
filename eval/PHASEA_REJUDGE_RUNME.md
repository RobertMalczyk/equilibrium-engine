# Phase-A (M1/M2) re-judge — RUN-ME (fresh session)

Re-judge the full **2800-scenario** corpus (700 day + 700 multi × burst {on,off}) **with Sonnet**, judge
model held constant, to confirm the Phase-A expression fixes (M1 mood weighs anger, M2 acknowledge a
kindness) shrink the L4 flag cluster vs the committed baseline **2618/2800 PASS (93.5%)**.

Paced as **~8 waves of 35 batches ≈ 8 hours total** (gentle on rate/session limits). Per-batch results
persist to disk, so any interruption resumes cleanly — just re-run the wave command.

Everything is on branch `blind-judge-sonnet-baseline`. The fixes are EXPRESSION-only (`eval/render_narration.py`
M1+M2, `eval/judge_multiday.py` M2) — golden DebugTrace byte-identical.

## One-time setup (this session) — rebuild the M1/M2 batches (~15 min, deterministic)

The batch prompts are gitignored (18MB, regenerable). Rebuild them with the M1/M2 renderer:

```bash
cd /c/Robak/equilibrium-engine
git checkout blind-judge-sonnet-baseline
for s in 0 1 2 3 4 5 6 7 8 9; do PYTHONPATH=. python eval/hourly_judge.py --slice $s --build; done
```

This writes `eval/hourly_runs/slice_*/batches/*.md` (the rebuilt M1/M2 prompts). It does NOT touch the
committed baseline verdicts in `eval/hourly_runs/slice_*/results/` — those stay as the comparison baseline.

## The run loop — repeat ~8 times, ~1 hour apart

Each iteration:

1. **Queue the next wave** (writes `eval/phaseA_run/wave_workflow.js` with the next 35 un-judged batches):
   ```bash
   PYTHONPATH=. python eval/phaseA_judge_wave.py --wave 35
   ```
2. **Run that workflow** — invoke the Workflow tool with:
   `{ scriptPath: "eval/phaseA_run/wave_workflow.js" }`
   (35 fresh Sonnet agents; each Reads its batch and Writes its own verdict file into
   `eval/phaseA_run/slice_*/results/`.)
3. **Pace** — wait ~1 hour (ScheduleWakeup `delaySeconds ≈ 3400`), then go back to step 1.

Stop when `--status` shows 0 batches remaining (280/280). The wave command auto-skips already-judged
batches, so re-running after a crash just continues.

```bash
PYTHONPATH=. python eval/phaseA_judge_wave.py --status     # progress any time
```

## When done — aggregate vs the baseline

```bash
PYTHONPATH=. python eval/phaseA_judge_wave.py --aggregate
```

Writes `eval/phaseA_run/REPORT.md`: Phase-A pass rate vs the 2618/2800 baseline, plus the scenarios that
**flipped** — `FLAG→PASS` (fixed by M1/M2) and `PASS→FLAG` (regressions to investigate). Expect the L4
"settled↔fury" and "kindness rendered as a snub" clusters to clear; **no other cluster should regress**.
Hold the judge model = Sonnet for the comparison to be valid (never compare across judge models).

Then commit `eval/phaseA_run/slice_*/results/*.txt` + `REPORT.md`.

## Notes
- Wave size / cadence: `--wave N` sets batches/wave; 280/8h ⇒ 35. Smaller waves = gentler pacing.
- Branch is push-protected; this is a local run. Don't self-merge — open a PR only when explicitly asked.
