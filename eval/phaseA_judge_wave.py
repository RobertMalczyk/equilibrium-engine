"""eval/phaseA_judge_wave.py -- paced wave generator for the Phase-A (M1/M2) re-judge (run helper).

Same blind discipline + per-batch on-disk persistence as eval/hour_judge.py, but parameterised:
  --rundir <abs>   run directory (default eval/phaseA_run)
  --wave N         how many un-judged batches to queue this wave (default 35 = 280/8h)
  --status         just print done/missing
  --aggregate      parse results -> phaseA_run/REPORT.md, compared to the committed Sonnet baseline

Each wave writes <rundir>/wave_workflow.js (a Workflow script: one fresh Sonnet agent per batch, each
agent Reads its batch file and Writes its own verdict file). Run that workflow, then re-invoke for the
next wave -- it resumes from whatever results already exist on disk.

    PYTHONPATH=. python eval/phaseA_judge_wave.py --wave 35
    PYTHONPATH=. python eval/phaseA_judge_wave.py --aggregate
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNDIR = (
    ROOT / "eval" / "phaseA_run"
)  # holds ONLY results + REPORT (committed footprint)
BATCHDIR = (
    ROOT / "eval" / "hourly_runs"
)  # rebuilt M1/M2 batches live here (gitignored, regenerable)
BASELINE = (
    ROOT / "eval" / "hourly_runs"
)  # the committed all-Sonnet baseline verdicts (2618/2800)
_LINE = re.compile(r"^\s*([a-z_]+_\d{3})\s*:\s*(PASS|FLAG)\s*(?:--?\s*(.*))?$", re.I)


def _arg(name: str, default: str) -> str:
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def scan(rd: Path):
    """Batches are read from the (gitignored, rebuilt) BATCHDIR; results are written under the run dir
    `rd`. So the committed footprint is only the verdict files -- never the 18MB of regenerable batches."""
    only = _arg(
        "--filter", ""
    )  # optional substring filter on the batch stem (e.g. "burstON")
    allb, done = {}, set()
    for p in glob.glob(str(BATCHDIR / "slice_*" / "batches" / "*.md")):
        pp = Path(p)
        if only and only not in pp.stem:
            continue
        s = int(pp.parts[-3].split("_")[1])
        allb[(s, pp.stem)] = pp
    for p in glob.glob(str(rd / "slice_*" / "results" / "*.txt")):
        pp = Path(p)
        if pp.stat().st_size > 0:
            done.add((int(pp.parts[-3].split("_")[1]), pp.stem))
    missing = sorted(k for k in allb if k not in done)
    return allb, done, missing


def make(rd: Path, wave: int) -> None:
    allb, done, missing = scan(rd)
    if not allb:
        print(
            f"NO BATCHES under {BATCHDIR}. Build them first:\n"
            "  for s in 0 1 2 3 4 5 6 7 8 9; do PYTHONPATH=. python eval/hourly_judge.py --slice $s --build; done"
        )
        return
    queue = missing[:wave]
    items = []
    for s, batch in queue:
        bpath = allb[(s, batch)].resolve().as_posix()
        out = (rd / f"slice_{s}" / "results" / f"{batch}.txt").resolve().as_posix()
        (rd / f"slice_{s}" / "results").mkdir(parents=True, exist_ok=True)
        items.append({"batch": f"s{s}_{batch}", "path": bpath, "out": out})
    js = (
        """export const meta = {
  name: 'phaseA-judge-wave',
  description: 'Blind-judge a wave of batches with Sonnet; each agent writes its own result file',
  phases: [{ title: 'Judge', detail: 'fresh Sonnet agent per batch, read batch -> write verdict file' }],
}
const ITEMS = """
        + json.dumps(items)
        + """;
phase('Judge')
log(`judging ${ITEMS.length} batches (Sonnet); each writes its own result file`)
const out = await parallel(ITEMS.map((it) => async () => {
  const prompt = `You are a BLIND believability judge. Use the Read tool to read this file:\\n\\n    ${it.path}\\n\\nIt is a COMPLETE self-contained judging prompt (rubric + profile + ~10 INDEPENDENT records). Judge EACH record ON ITS OWN - no comparing, no answer key. Then use the Write tool to save your verdicts to EXACTLY:\\n\\n    ${it.out}\\n\\nThe file must contain ONLY the verdict lines, one per record in order:\\n<record_id>: PASS|FLAG -- <max 12 words>`
  const o = await agent(prompt, { label: it.batch, phase: 'Judge', model: 'sonnet' })
  return { batch: it.batch, ok: !!o }
}))
return out
"""
    )
    (rd / "wave_workflow.js").write_text(js, encoding="utf-8")
    print(
        f"queued {len(queue)} batches | done {len(done)}/{len(allb)} | remaining {len(missing) - len(queue)} after this wave"
    )
    print(f"-> {(rd / 'wave_workflow.js')}")


def status(rd: Path) -> None:
    allb, done, missing = scan(rd)
    sc_done, sc_total = len(done) * 10, len(allb) * 10
    pct = sc_done * 100 // sc_total if sc_total else 0
    print(
        f"scenarios ~{sc_done}/{sc_total} judged | {len(missing)} batches remaining ({len(done)}/{len(allb)}, {pct}%)"
    )


def _verdicts(results_dir: Path) -> dict[str, str]:
    """scenario_id -> PASS|FLAG from every result file in a results/ dir."""
    out: dict[str, str] = {}
    for p in glob.glob(str(results_dir / "*.txt")):
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            m = _LINE.match(line.strip())
            if m:
                out.setdefault(m.group(1).lower(), m.group(2).upper())
    return out


def aggregate(rd: Path) -> None:
    """Phase-A pass rate + the scenarios that FLIPPED vs the committed all-Sonnet baseline."""
    new = _verdicts_all(rd)
    base = _verdicts_all(BASELINE)
    n = len(new)
    npass = sum(1 for v in new.values() if v == "PASS")
    fixed = sorted(s for s, v in new.items() if v == "PASS" and base.get(s) == "FLAG")
    regressed = sorted(
        s for s, v in new.items() if v == "FLAG" and base.get(s) == "PASS"
    )
    bpass = sum(1 for v in base.values() if v == "PASS")
    lines = [
        "# Phase-A (M1/M2) re-judge -- all-Sonnet, judge model held constant",
        "",
        f"- Baseline (committed):  {bpass}/{len(base)} PASS",
        f"- Phase A (this run):    {npass}/{n} PASS"
        + ("" if n else "  (no results yet)"),
        f"- Net: {npass - bpass:+d} PASS  |  fixed (FLAG->PASS): {len(fixed)}  |  regressed (PASS->FLAG): {len(regressed)}",
        "",
        f"## Fixed ({len(fixed)})",
        *([f"- {s}" for s in fixed] or ["- none"]),
        "",
        f"## Regressed ({len(regressed)}) -- investigate any of these",
        *([f"- {s}" for s in regressed] or ["- none"]),
    ]
    (rd / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6]))
    print(f"-> {rd / 'REPORT.md'}")


def _verdicts_all(run: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for s in range(10):
        out.update(_verdicts(run / f"slice_{s}" / "results"))
    return out


def main() -> None:
    rd = Path(_arg("--rundir", str(DEFAULT_RUNDIR)))
    if "--status" in sys.argv:
        status(rd)
        return
    if "--aggregate" in sys.argv:
        aggregate(rd)
        return
    make(rd, int(_arg("--wave", "35")))
    status(rd)


if __name__ == "__main__":
    main()
