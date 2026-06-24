"""eval/regression_judge.py — FULL-CORPUS (1400) blind regression: 700 one-day + 700 multi-day.

Purpose: after the burst-saturation engine changes (all shipped NEUTRAL, plus the stranger-grudge
relational-deposit fix), re-judge the WHOLE corpus blind so regressions in the believable-day
behaviour cannot hide. Method = the established batched-blind discipline (one FRESH judge agent per
batch of ~10 same-persona records; neutral rubric; no answer key; judge each record on its own).

Stages (all deterministic except the judging itself):
  python eval/regression_judge.py --build        # run all 1400 sims, render records, write batches
  python eval/regression_judge.py --list         # list batches + their result status
  python eval/regression_judge.py --aggregate    # parse results/, write the regression report

Judging: a driver spawns one fresh LLM agent per batch prompt (eval/regression_judge/batches/*.md);
each agent writes its verdict lines to eval/regression_judge/results/<batch>.txt:
    <scenario_id>: PASS|FLAG -- <max 12 words>

Baselines for comparison (the aggregate report states them): multi-day full-700 blind judge of
2026-06-08 = ~697/700 (batched 627/630). The day corpus has NOT been full-700 blind judged before
(D11 judged samples), so its number here is BASELINE-SETTING, not a delta.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from engine.yaml_io import load_scenario
from eval.calibrated import load_eval_persona_timescale
from eval.judge_multiday import narrate
from eval.render_narration import DISPLAY

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "eval" / "regression_judge"
BATCHES = BASE / "batches"
RESULTS = BASE / "results"
PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
CHUNK = 10
N_PER_PERSONA = 100

HEADER = """\
You are a BLIND believability judge. Below are {n} INDEPENDENT records of the SAME character
({name}) — each record is one or more simulated days. Judge EACH record ON ITS OWN — do NOT compare
records to one another and do NOT try to prove anything about the character's traits. You are only
checking the GENERAL working of the model: does each record look like a sane stretch of life?

For EACH record, check two things:
(a) DOES IT MAKE SENSE as a day / days in a life? Sane pacing — not starving within minutes, not
    enraged for no reason, sleeps at night and wakes recovered, hunger/temper rise and fall over
    believable spans, nothing absurd.
(b) IS IT NOT WRONG for this person? Nothing contradicts the profile below (a calm man isn't raging
    all day; a hot one isn't a saint). You are NOT asked to prove he differs from anyone — only that
    nothing jars.

# Who this is (applies to EVERY record below)
{profile}

# The records
{records}

# Output — EXACTLY one line per record, in record order, nothing else:
<scenario_id>: PASS|FLAG -- <max 12 words; for FLAG, the one thing that most needs a look>
"""


def render_day(persona: str, index: int) -> str:
    cfg = load_eval_persona_timescale(persona)
    path = (
        ROOT
        / "eval"
        / "scenarios"
        / "day"
        / persona
        / f"{persona}_day_{index:03d}.yaml"
    )
    return narrate(persona, cfg, load_scenario(path), 1)


def render_multi(persona: str, index: int) -> tuple[str, int]:
    cfg = load_eval_persona_timescale(persona)
    path = (
        ROOT
        / "eval"
        / "scenarios"
        / "multiday"
        / persona
        / f"{persona}_multi_{index:03d}.yaml"
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return narrate(persona, cfg, load_scenario(path), raw["n_days"]), raw["n_days"]


def build() -> None:
    BATCHES.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    man = []
    for corpus in ("day", "multi"):
        for p in PERSONAS:
            profile = (ROOT / "eval" / "profiles" / f"{p}.md").read_text(
                encoding="utf-8"
            )
            idxs = list(range(1, N_PER_PERSONA + 1))
            for bn, start in enumerate(range(0, len(idxs), CHUNK)):
                chunk = idxs[start : start + CHUNK]
                blocks, sids = [], []
                for i in chunk:
                    if corpus == "day":
                        narration = render_day(p, i)
                        sid = f"{p}_day_{i:03d}"
                    else:
                        narration, _ = render_multi(p, i)
                        sid = f"{p}_multi_{i:03d}"
                    sids.append(sid)
                    blocks.append(f"===== RECORD: {sid} =====\n{narration}")
                prompt = HEADER.format(
                    n=len(chunk),
                    name=DISPLAY[p],
                    profile=profile,
                    records="\n\n".join(blocks),
                )
                fn = f"{corpus}_{p}_b{bn:02d}"
                (BATCHES / f"{fn}.md").write_text(prompt, encoding="utf-8")
                man.append(
                    {"batch": fn, "corpus": corpus, "persona": p, "scenarios": sids}
                )
                print(f"  built {fn} ({len(chunk)})")
    (BASE / "manifest.yaml").write_text(
        yaml.safe_dump(
            {"chunk": CHUNK, "n_batches": len(man), "batches": man}, sort_keys=False
        ),
        encoding="utf-8",
    )
    print(f"\n{len(man)} batches -> {BATCHES}")


_LINE = re.compile(r"^\s*([a-z_]+_\d{3})\s*:\s*(PASS|FLAG)\s*(?:--?\s*(.*))?$", re.I)


def aggregate() -> None:
    man = yaml.safe_load((BASE / "manifest.yaml").read_text(encoding="utf-8"))
    per: dict[tuple[str, str], list[int]] = {}
    flags: list[str] = []
    missing_batches, judged = [], 0
    expected = {s: b["batch"] for b in man["batches"] for s in b["scenarios"]}
    seen: set[str] = set()
    for b in man["batches"]:
        rf = RESULTS / f"{b['batch']}.txt"
        if not rf.exists():
            missing_batches.append(b["batch"])
            continue
        for line in rf.read_text(encoding="utf-8").splitlines():
            m = _LINE.match(line.strip())
            if not m:
                continue
            sid, verdict, why = m.group(1).lower(), m.group(2).upper(), m.group(3) or ""
            if sid not in expected or sid in seen:
                continue
            seen.add(sid)
            judged += 1
            key = (b["corpus"], b["persona"])
            per.setdefault(key, [0, 0])
            per[key][1] += 1
            if verdict == "PASS":
                per[key][0] += 1
            else:
                flags.append(f"{sid}: {why.strip()}")
    lines = [
        "# Full-corpus blind regression — 1400 scenarios (700 day + 700 multi-day)",
        "",
        "Engine: branch `burst-saturation` (burst machinery present but NEUTRAL/disabled in all",
        "shipped config; includes the stranger-grudge relational-deposit fix). Judges: one fresh",
        "LLM agent per batch of 10 same-persona records, neutral rubric, no answer key.",
        "",
        "| corpus | persona | pass | judged |",
        "|---|---|---|---|",
    ]
    tot = {"day": [0, 0], "multi": [0, 0]}
    for corpus, p in sorted(per):
        ok, n = per[(corpus, p)]
        tot[corpus][0] += ok
        tot[corpus][1] += n
        lines.append(f"| {corpus} | {p} | {ok} | {n} |")
    for corpus, (ok, n) in tot.items():
        pct = f"{ok / n:.1%}" if n else "—"
        lines.append(f"| **{corpus} TOTAL** | | **{ok}** | **{n}** ({pct}) |")
    lines += [
        "",
        "Baseline: multi-day full-700 (2026-06-08) ≈ 697/700 (batched 627/630 = 99.5%). The day",
        "corpus had no prior full-700 blind run — its number here is baseline-setting.",
        "",
        f"## Flags ({len(flags)})",
        "",
    ]
    lines += [f"- {f}" for f in sorted(flags)] or ["- none"]
    if missing_batches:
        lines += ["", f"## Missing batch results ({len(missing_batches)})", ""]
        lines += [f"- {b}" for b in missing_batches]
    (BASE / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"judged {judged}; flags {len(flags)}; missing batches {len(missing_batches)}"
    )
    print(f"-> {BASE / 'REPORT.md'}")


def list_status() -> None:
    man = yaml.safe_load((BASE / "manifest.yaml").read_text(encoding="utf-8"))
    done = sum(1 for b in man["batches"] if (RESULTS / f"{b['batch']}.txt").exists())
    print(f"{done}/{man['n_batches']} batches have results")


if __name__ == "__main__":
    if "--build" in sys.argv:
        build()
    elif "--aggregate" in sys.argv:
        aggregate()
    else:
        list_status()
