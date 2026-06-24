"""eval/hour_judge.py -- paced hourly blind-judge driver (10 batches/hour) with on-disk persistence.

Old-mechanism judging (one fresh agent per 10-record batch, neutral rubric, no answer key, plain
`id: PASS|FLAG` lines), paced to avoid rate/session limits. Each hour:

  python eval/hour_judge.py --make           # pick the next 10 un-judged batches -> hour_workflow.js

Then the caller runs that workflow. EACH agent reads its batch file and WRITES its own verdict file to
slice_<s>/results/<batch>.txt — so progress is persisted batch-by-batch and a crash/shutdown loses at
most the batches still in flight; on restart `--make` simply resumes from whatever results exist.

`--status` prints done/missing counts. RUNDIR defaults to eval/hourly_runs but can be overridden with
an absolute path as the last arg (so the run can live in another worktree).
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

PER_HOUR = 16


def rundir() -> Path:
    for a in sys.argv[1:]:
        if a.startswith("/") or (len(a) > 2 and a[1] == ":"):
            return Path(a)
    return Path(__file__).resolve().parents[1] / "eval" / "hourly_runs"


def scan(rd: Path):
    done, allb = set(), {}
    for p in glob.glob(str(rd / "slice_*" / "batches" / "*.md")):
        pp = Path(p)
        s = int(pp.parts[-3].split("_")[1])
        allb[(s, pp.stem)] = pp
    for p in glob.glob(str(rd / "slice_*" / "results" / "*.txt")):
        pp = Path(p)
        if pp.stat().st_size > 0:
            done.add((int(pp.parts[-3].split("_")[1]), pp.stem))
    missing = sorted(k for k in allb if k not in done)
    return allb, done, missing


def make(rd: Path) -> None:
    allb, done, missing = scan(rd)
    queue = missing[:PER_HOUR]
    items = []
    for s, batch in queue:
        bpath = allb[(s, batch)].resolve().as_posix()
        out = (rd / f"slice_{s}" / "results" / f"{batch}.txt").resolve().as_posix()
        items.append({"batch": batch, "path": bpath, "out": out})
    js = (
        """export const meta = {
  name: 'hour-judge',
  description: 'Blind-judge the next 10 batches; each agent writes its own result file',
  phases: [{ title: 'Judge', detail: '10 fresh agents, read batch -> write verdict file' }],
}
const ITEMS = """
        + json.dumps(items)
        + """;
phase('Judge')
log(`judging ${ITEMS.length} batches; each writes its own result file`)
const out = await parallel(ITEMS.map((it) => async () => {
  const prompt = `You are a BLIND believability judge. Use the Read tool to read this file:\\n\\n    ${it.path}\\n\\nIt is a COMPLETE self-contained judging prompt (rubric + profile + ~10 INDEPENDENT records). Judge EACH record ON ITS OWN - no comparing, no answer key. Then use the Write tool to save your verdicts to EXACTLY:\\n\\n    ${it.out}\\n\\nThe file must contain ONLY the verdict lines, one per record in order:\\n<record_id>: PASS|FLAG -- <max 12 words>`
  const o = await agent(prompt, { label: it.batch, phase: 'Judge', model: 'sonnet' })
  return { batch: it.batch, ok: !!o }
}))
return out
"""
    )
    (rd / "hour_workflow.js").write_text(js, encoding="utf-8")
    print(
        f"queued {len(queue)} batches | done {len(done)}/{len(allb)} | remaining {len(missing)}"
    )
    print(f"-> {(rd / 'hour_workflow.js')}")


def status(rd: Path) -> None:
    allb, done, missing = scan(rd)
    sc_done, sc_total, sc_wait = len(done) * 10, len(allb) * 10, len(missing) * 10
    msg = (
        f"scenarios {sc_done}/{sc_total} done | {sc_wait} waiting "
        f"({len(done)}/{len(allb)} batches, {sc_done * 100 // sc_total}%)"
    )
    print(msg)
    (rd / "progress.md").write_text(msg + "\n", encoding="utf-8")


def main() -> None:
    rd = rundir()
    if "--status" in sys.argv:
        status(rd)
    else:
        make(rd)
        status(rd)


if __name__ == "__main__":
    main()
