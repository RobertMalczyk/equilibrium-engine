"""eval/hourly_judge.py -- rolling 10%/hour BLIND-judge batch builder + aggregator.

Each "slice" S in 0..9 selects scenario indices S*10+1 .. S*10+10 (10/persona = 10% of the
corpus). For that slice it renders FOUR sub-corpora into blind-judge batch prompts:

    day      x burst OFF
    day      x burst ON
    multiday x burst OFF
    multiday x burst ON

= 28 batches/slice (7 personas x 4 sub-corpora x 1 chunk of 10) = 280 records/slice. Over 10
slices the whole 700-day + 700-multi corpus is blind-judged once, with and without the outburst
overlay.

Blind discipline (unchanged from eval/regression_judge.py): one FRESH judge agent per batch,
neutral rubric, no answer key, each record judged on its own. THIS SCRIPT ONLY renders the batch
prompts and aggregates the verdict files an agent writes back -- it never judges.

    python eval/hourly_judge.py --slice S --build       # render slice S -> batches/*.md
    python eval/hourly_judge.py --slice S --aggregate    # parse results/*.txt -> report

Layout:  eval/hourly_runs/slice_<S>/{batches,results}/ , report appended to eval/hourly_runs/report.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from engine.yaml_io import load_scenario
from eval.calibrated import load_eval_persona_timescale
from eval.judge_multiday import narrate
from eval.regression_judge import HEADER
from eval.render_narration import DISPLAY

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "eval" / "hourly_runs"
PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
CHUNK = 10
SUBCORPORA = [("day", False), ("day", True), ("multi", False), ("multi", True)]


def _slice_idxs(s: int) -> list[int]:
    start = s * CHUNK + 1
    return list(range(start, start + CHUNK))


def _tag(corpus: str, burst: bool) -> str:
    return f"{corpus}_{'burstON' if burst else 'burstOFF'}"


def _render(persona: str, corpus: str, burst: bool, i: int) -> str | None:
    cfg = load_eval_persona_timescale(persona, burst=burst)
    if corpus == "day":
        path = (
            ROOT
            / "eval"
            / "scenarios"
            / "day"
            / persona
            / f"{persona}_day_{i:03d}.yaml"
        )
        if not path.exists():
            return None
        return narrate(persona, cfg, load_scenario(path), 1)
    path = (
        ROOT
        / "eval"
        / "scenarios"
        / "multiday"
        / persona
        / f"{persona}_multi_{i:03d}.yaml"
    )
    if not path.exists():
        return None
    n_days = yaml.safe_load(path.read_text(encoding="utf-8"))["n_days"]
    return narrate(persona, cfg, load_scenario(path), n_days)


def build(s: int) -> None:
    sdir = BASE / f"slice_{s}"
    batches, results = sdir / "batches", sdir / "results"
    batches.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    idxs = _slice_idxs(s)
    man = []
    for corpus, burst in SUBCORPORA:
        for p in PERSONAS:
            profile = (ROOT / "eval" / "profiles" / f"{p}.md").read_text(
                encoding="utf-8"
            )
            blocks, sids = [], []
            for i in idxs:
                narration = _render(p, corpus, burst, i)
                if narration is None:
                    continue
                # the record id encodes the sub-corpus so burst ON/OFF verdicts never collide
                sid = f"{p}_{_tag(corpus, burst)}_{i:03d}"
                sids.append(sid)
                blocks.append(f"===== RECORD: {sid} =====\n{narration}")
            if not sids:
                continue
            prompt = HEADER.format(
                n=len(sids),
                name=DISPLAY[p],
                profile=profile,
                records="\n\n".join(blocks),
            )
            fn = f"{_tag(corpus, burst)}_{p}"
            (batches / f"{fn}.md").write_text(prompt, encoding="utf-8")
            man.append(
                {
                    "batch": fn,
                    "corpus": corpus,
                    "burst": burst,
                    "persona": p,
                    "scenarios": sids,
                }
            )
    (sdir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {"slice": s, "chunk": CHUNK, "n_batches": len(man), "batches": man},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(
        f"slice {s}: built {len(man)} batches ({sum(len(b['scenarios']) for b in man)} records) -> {batches}"
    )


_LINE = re.compile(r"^\s*([a-z_]+_\d{3})\s*:\s*(PASS|FLAG)\s*(?:--?\s*(.*))?$", re.I)


def aggregate(s: int) -> None:
    sdir = BASE / f"slice_{s}"
    man = yaml.safe_load((sdir / "manifest.yaml").read_text(encoding="utf-8"))
    per: dict[str, list[int]] = {}
    flags: list[str] = []
    missing, judged = [], 0
    seen: set[str] = set()
    expected = {sid for b in man["batches"] for sid in b["scenarios"]}
    for b in man["batches"]:
        rf = sdir / "results" / f"{b['batch']}.txt"
        if not rf.exists():
            missing.append(b["batch"])
            continue
        key = _tag(b["corpus"], b["burst"])
        for line in rf.read_text(encoding="utf-8").splitlines():
            m = _LINE.match(line.strip())
            if not m:
                continue
            sid, verdict = m.group(1).lower(), m.group(2).upper()
            if sid not in expected or sid in seen:
                continue
            seen.add(sid)
            judged += 1
            per.setdefault(key, [0, 0])
            per[key][1] += 1
            if verdict == "PASS":
                per[key][0] += 1
            else:
                flags.append(f"{sid}: {(m.group(3) or '').strip()}")
    lines = [
        f"\n## Slice {s} -- indices {_slice_idxs(s)[0]}..{_slice_idxs(s)[-1]}/persona\n"
    ]
    gp = gt = 0
    for key in (_tag(c, b) for c, b in SUBCORPORA):
        pa, to = per.get(key, [0, 0])
        gp += pa
        gt += to
        pct = (100 * pa // to) if to else 0
        lines.append(f"- {key:16}: {pa}/{to} PASS ({pct}%)\n")
    pct = (100 * gp // gt) if gt else 0
    lines.append(
        f"- **TOTAL: {gp}/{gt} PASS ({pct}%)**, {len(flags)} FLAG, {judged} judged, {len(missing)} batch(es) missing\n"
    )
    for f in flags[:40]:
        lines.append(f"    - {f}\n")
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "report.md").open("a", encoding="utf-8").write("".join(lines))
    print("".join(lines))
    if missing:
        print(f"WARNING missing results: {missing}")


def main() -> None:
    s = 0
    for a in sys.argv[1:]:
        if a.startswith("--slice"):
            s = (
                int(a.split("=")[1])
                if "=" in a
                else int(sys.argv[sys.argv.index(a) + 1])
            )
    if "--aggregate" in sys.argv:
        aggregate(s)
    else:
        build(s)


if __name__ == "__main__":
    main()
