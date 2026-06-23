"""eval/test_report.py -- FULL per-test report: every scenario's stimulus, observed behaviour, verdict.

Builds a comprehensive reference document covering ALL judged scenarios (PASS and FLAG alike):
methodology + assertion criteria up front, an aggregate table, then per-test entries grouped
corpus -> persona -> burst. Each entry = the STIMULUS timeline (input events, believable clock times),
the OBSERVED behaviour (the exact narration the blind judge saw, extracted from the batch prompts),
and the VERDICT (PASS|FLAG + the judge's note).

Pure read + render -- no engine runs, no LLM. Sources: eval/hourly_runs/slice_*/{manifest,batches,results}
+ the scenario YAMLs (for the input event list).

    python eval/test_report.py        # -> eval/hourly_runs/TEST_REPORT.{md,html}
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path

import yaml

from engine.yaml_io import load_scenario
from eval.calibrated import believable_day_layout
from eval.judge_multiday import (
    clock as jclock,  # same dawn-based clock the narration uses
)
from eval.render_narration import event_phrase

FORCING = {"insult", "command", "food_given", "help", "weather"}

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "eval" / "hourly_runs"
DAY_TICKS = believable_day_layout()["day_ticks"]
PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
SUBS = [("day", False), ("day", True), ("multi", False), ("multi", True)]
SUBLABEL = {
    ("day", False): "Day · burst OFF",
    ("day", True): "Day · burst ON",
    ("multi", False): "Multiday · burst OFF",
    ("multi", True): "Multiday · burst ON",
}
_REC = re.compile(
    r"=====\s*RECORD:\s*([a-z0-9_]+)\s*=====\s*\n(.*?)(?=\n=====\s*RECORD:|\Z)",
    re.S | re.I,
)
_VLINE = re.compile(r"^\s*([a-z0-9_]+)\s*:\s*(PASS|FLAG)\s*(?:--?\s*(.*))?$", re.I)

METHOD = """\
This document reports every scenario in the persona-dynamics believability corpus: **2,800 tests**
= 700 one-day + 700 multi-day scenarios, each run with the outburst overlay **OFF** and **ON**.

**How a scenario runs.** Each scenario is a seeded, deterministic timeline of *forcing events* done
to one NPC (vocabulary: `insult`, `command`, `food_given`, `help`, `weather`). The NPC is driven
through a closed seeking loop against a mock world at a believable timescale (a 24 h day; the NPC
sleeps at night and wakes recovered). Visible behaviour *emerges* from internal state dynamics — it
is not scripted.

**How a test is judged (blind).** Records are batched 10 at a time (same persona). One FRESH LLM
agent judges each batch with no answer key and no comparison between records — it sees only the
persona profile, the observable narration, and the rubric below. (Judge model: **Claude Sonnet, held
constant** across all batches. This report = the final run with M1+M2+M3+renderer fix+corpus coherence:
**2686/2800 = 95.9%**; see `eval/BELIEVABILITY_REPORT.md` for the full method + run-by-run history.)

**Assertion criteria (applied to EVERY test).**
1. **Sane as a day / days in a life** — believable pacing: not starving within minutes, not enraged
   for no reason, sleeps at night and wakes recovered, hunger/temper rise and fall over plausible
   spans, nothing absurd.
2. **Not wrong for this person** — nothing contradicts the persona's profile (a calm man isn't raging
   all day; a hot one isn't a saint).

A record **PASSES** if both hold; it is **FLAGGED** if anything jars. (A separate deterministic gate
also checks every tick: states clamped to range/no NaN, hunger sane, a sleep stretch each night, the
fast temper drains overnight, stress not pegged near 1.0, calm by most dawns, not frozen in one mode.)
"""


def _verdicts(results_dir: Path, batch: str) -> dict:
    out = {}
    f = results_dir / f"{batch}.txt"
    if not f.exists():
        return out
    for line in f.read_text(encoding="utf-8").splitlines():
        m = _VLINE.match(line.strip())
        if m:
            out[m.group(1).lower()] = (m.group(2).upper(), (m.group(3) or "").strip())
    return out


def _narrations(batch_md: Path) -> dict:
    if not batch_md.exists():
        return {}
    txt = batch_md.read_text(encoding="utf-8")
    return {m.group(1).lower(): m.group(2).strip() for m in _REC.finditer(txt)}


def _stimulus(persona: str, corpus: str, idx: int) -> list[str]:
    sub = "day" if corpus == "day" else "multiday"
    tag = "day" if corpus == "day" else "multi"
    path = (
        ROOT / "eval" / "scenarios" / sub / persona / f"{persona}_{tag}_{idx:03d}.yaml"
    )
    if not path.exists():
        return []
    sc = load_scenario(path)
    obj = "her" if persona == "edda" else "him"
    lines = []
    for ev in sc.events:
        if ev.type not in FORCING:
            continue  # skip internal markers (nightfall, activity, ...)
        if ev.type == "weather":
            lines.append(f"{jclock(ev.t)} — a cold rain sets in")
        else:
            lines.append(f"{jclock(ev.t)} — {event_phrase(ev, obj)}")
    return lines


def _collect(results_base: Path = BASE):
    """-> {(corpus,burst): {persona: [ (idx, sid, verdict, note, stimulus[], narration) ]}}, plus totals.

    Manifests + batches (narrations) come from BASE (eval/hourly_runs); VERDICTS come from
    ``results_base`` (e.g. a phaseA_run* dir), so the report can pair the current narrations with any
    judged run."""
    data = {s: {p: [] for p in PERSONAS} for s in SUBS}
    totals = {s: [0, 0] for s in SUBS}
    per_persona = {p: [0, 0] for p in PERSONAS}
    for s in range(10):
        sdir = BASE / f"slice_{s}"
        man_f = sdir / "manifest.yaml"
        if not man_f.exists():
            continue
        man = yaml.safe_load(man_f.read_text(encoding="utf-8"))
        for b in man["batches"]:
            corpus, burst, persona = b["corpus"], b["burst"], b["persona"]
            verds = _verdicts(results_base / f"slice_{s}" / "results", b["batch"])
            narrs = _narrations(sdir / "batches" / f"{b['batch']}.md")
            for sid in b["scenarios"]:
                key = sid.lower()
                idx = int(sid.rsplit("_", 1)[1])
                verdict, note = verds.get(key, ("?", "(no verdict)"))
                stim = _stimulus(persona, corpus, idx)
                narr = narrs.get(key, "(narration unavailable)")
                data[(corpus, burst)][persona].append(
                    (idx, sid, verdict, note, stim, narr)
                )
                if verdict in ("PASS", "FLAG"):
                    totals[(corpus, burst)][1] += 1
                    per_persona[persona][1] += 1
                    if verdict == "PASS":
                        totals[(corpus, burst)][0] += 1
                        per_persona[persona][0] += 1
            for p in PERSONAS:
                data[(corpus, burst)][p].sort(key=lambda r: r[0])
    return data, totals, per_persona


def _pct(pt):
    p, t = pt
    return f"{100 * p / t:.1f}%" if t else "—"


def render_md(data, totals, per_persona) -> str:
    L = [
        "# Persona-dynamics believability — full test report",
        "",
        METHOD,
        "",
        "## Aggregate",
        "",
    ]
    gp = sum(v[0] for v in totals.values())
    gt = sum(v[1] for v in totals.values())
    L += [
        f"**Overall: {gp}/{gt} PASS ({_pct([gp, gt])})**",
        "",
        "| sub-corpus | PASS | rate |",
        "|---|---|---|",
    ]
    for s in SUBS:
        L.append(
            f"| {SUBLABEL[s]} | {totals[s][0]}/{totals[s][1]} | {_pct(totals[s])} |"
        )
    L += ["", "| persona | PASS | rate |", "|---|---|---|"]
    for p in PERSONAS:
        L.append(
            f"| {p} | {per_persona[p][0]}/{per_persona[p][1]} | {_pct(per_persona[p])} |"
        )
    L += ["", "---", "", "# Tests", ""]
    for s in SUBS:
        L += [f"## {SUBLABEL[s]}", ""]
        for p in PERSONAS:
            rows = data[s][p]
            if not rows:
                continue
            L += [f"### {p}", ""]
            for idx, sid, verdict, note, stim, narr in rows:
                badge = (
                    "✅ PASS"
                    if verdict == "PASS"
                    else ("⚠️ FLAG" if verdict == "FLAG" else verdict)
                )
                L += [f"#### `{sid}` — {badge}", ""]
                if note:
                    L.append(f"_Judge:_ {note}\n")
                L.append("**Stimulus (input events):**\n")
                L += [f"- {x}" for x in stim] or ["- (no forcing events)"]
                L += ["", "**Observed behaviour:**", "", narr, "", "---", ""]
    return "\n".join(L)


def render_html(data, totals, per_persona) -> str:
    gp = sum(v[0] for v in totals.values())
    gt = sum(v[1] for v in totals.values())

    def esc(x):
        return _html.escape(str(x))

    out = [
        f"""<!doctype html><meta charset=utf-8><title>Persona-dynamics — full test report</title>
<style>
 body{{font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
 h1{{font-size:1.7rem}} h2{{margin-top:2rem;border-bottom:2px solid #ddd;padding-bottom:.3rem}}
 table{{border-collapse:collapse;margin:.5rem 0}} td,th{{padding:.3rem .7rem;text-align:left;border-bottom:1px solid #eee}}
 details{{margin:.3rem 0;border:1px solid #e5e5e5;border-radius:6px;padding:.3rem .6rem}}
 details>summary{{cursor:pointer;font-weight:600}}
 .pass{{color:#197a2b}} .flag{{color:#b8860b}}
 .stim{{background:#f7f8fa;border-left:3px solid #cbd5e1;padding:.4rem .8rem;margin:.4rem 0}}
 .narr{{white-space:pre-wrap;background:#fcfcfc;border:1px solid #eee;border-radius:4px;padding:.5rem .8rem;font-size:14px}}
 .meta{{color:#666;font-size:13px}} code{{background:#f3f3f3;padding:1px 4px;border-radius:3px}}
</style>
<h1>Persona-dynamics believability — full test report</h1>
<div>{_html.escape(METHOD).replace(chr(10) + chr(10), "</p><p>").replace("**", "")}</div>
<h2>Aggregate</h2>
<p style="font-size:1.5rem;font-weight:700">{_pct([gp, gt])} <span class=meta>({gp}/{gt} PASS overall)</span></p>
<table><tr><th>sub-corpus</th><th>PASS</th><th>rate</th></tr>"""
    ]
    for s in SUBS:
        out.append(
            f"<tr><td>{SUBLABEL[s]}</td><td>{totals[s][0]}/{totals[s][1]}</td><td>{_pct(totals[s])}</td></tr>"
        )
    out.append("</table><table><tr><th>persona</th><th>PASS</th><th>rate</th></tr>")
    for p in PERSONAS:
        out.append(
            f"<tr><td>{p}</td><td>{per_persona[p][0]}/{per_persona[p][1]}</td><td>{_pct(per_persona[p])}</td></tr>"
        )
    out.append("</table><h2>Tests</h2>")
    for s in SUBS:
        out.append(f"<h2>{SUBLABEL[s]}</h2>")
        for p in PERSONAS:
            rows = data[s][p]
            if not rows:
                continue
            npass = sum(1 for r in rows if r[2] == "PASS")
            out.append(
                f"<details><summary>{esc(p)} — {npass}/{len(rows)} PASS</summary>"
            )
            for idx, sid, verdict, note, stim, narr in rows:
                cls = "pass" if verdict == "PASS" else "flag"
                badge = "PASS" if verdict == "PASS" else verdict
                stim_html = (
                    "".join(f"<li>{esc(x)}</li>" for x in stim)
                    or "<li>(no forcing events)</li>"
                )
                out.append(
                    f"<details><summary><span class={cls}>{badge}</span> &nbsp; <code>{esc(sid)}</code> "
                    f"<span class=meta>— {esc(note)}</span></summary>"
                    f"<div class=stim><b>Stimulus (input events):</b><ul>{stim_html}</ul></div>"
                    f"<div class=narr>{esc(narr)}</div></details>"
                )
            out.append("</details>")
    return "\n".join(out)


def main() -> None:
    import sys

    def _arg(name, default):
        return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

    results_base = Path(_arg("--results", str(BASE)))
    out_prefix = Path(_arg("--out", str(BASE / "TEST_REPORT")))
    data, totals, per_persona = _collect(results_base)
    md = render_md(data, totals, per_persona)
    html = render_html(data, totals, per_persona)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    out_prefix.with_suffix(".md").write_text(md, encoding="utf-8")
    out_prefix.with_suffix(".html").write_text(html, encoding="utf-8")
    gp = sum(v[0] for v in totals.values())
    gt = sum(v[1] for v in totals.values())
    print(
        f"wrote TEST_REPORT.md ({len(md)} chars) + .html ({len(html)} chars); {gp}/{gt} PASS"
    )


if __name__ == "__main__":
    main()
