"""eval/hourly_report.py -- consolidate the rolling blind-judge slices into one MD + HTML report.

Reads every eval/hourly_runs/slice_*/{manifest.yaml,results/*.txt} present on disk and rolls them
up into a single human-review report: overall PASS rate, the four sub-corpora (day/multi x burst
OFF/ON) side by side, a burst-OFF vs burst-ON delta, per-persona breakdown, and the full FLAG list
with verdict text. Emits eval/hourly_runs/FINAL_report.md and eval/hourly_runs/FINAL_report.html.

    python eval/hourly_report.py

Pure read + render; never runs the engine and never judges.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "eval" / "hourly_runs"
SUBCORPORA = ["day_burstOFF", "day_burstON", "multi_burstOFF", "multi_burstON"]
LABEL = {
    "day_burstOFF": "day · burst OFF",
    "day_burstON": "day · burst ON",
    "multi_burstOFF": "multiday · burst OFF",
    "multi_burstON": "multiday · burst ON",
}
_LINE = re.compile(r"^\s*([a-z_]+_\d{3})\s*:\s*(PASS|FLAG)\s*(?:--?\s*(.*))?$", re.I)


def _tag(corpus: str, burst: bool) -> str:
    return f"{corpus}_{'burstON' if burst else 'burstOFF'}"


def collect() -> dict:
    slices = sorted(
        int(p.name.split("_")[1]) for p in BASE.glob("slice_*") if p.is_dir()
    )
    by_sub = {s: [0, 0] for s in SUBCORPORA}
    by_persona = {}  # persona -> [pass,total]
    by_sub_persona = {}  # (sub,persona) -> [pass,total]
    flags = []  # (sub, sid, why)
    seen = set()
    for s in slices:
        sdir = BASE / f"slice_{s}"
        man_f = sdir / "manifest.yaml"
        if not man_f.exists():
            continue
        man = yaml.safe_load(man_f.read_text(encoding="utf-8"))
        for b in man["batches"]:
            sub = _tag(b["corpus"], b["burst"])
            persona = b["persona"]
            rf = sdir / "results" / f"{b['batch']}.txt"
            if not rf.exists():
                continue
            expected = {s.lower() for s in b["scenarios"]}
            for line in rf.read_text(encoding="utf-8").splitlines():
                m = _LINE.match(line.strip())
                if not m:
                    continue
                sid, verdict, why = (
                    m.group(1).lower(),
                    m.group(2).upper(),
                    (m.group(3) or "").strip(),
                )
                if sid not in expected or sid in seen:
                    continue
                seen.add(sid)
                ok = verdict == "PASS"
                for d, k in ((by_sub, sub), (by_persona, persona)):
                    d.setdefault(k, [0, 0])
                    d[k][1] += 1
                    d[k][0] += 1 if ok else 0
                by_sub_persona.setdefault((sub, persona), [0, 0])
                by_sub_persona[(sub, persona)][1] += 1
                by_sub_persona[(sub, persona)][0] += 1 if ok else 0
                if not ok:
                    flags.append((sub, sid, why))
    return {
        "slices": slices,
        "by_sub": by_sub,
        "by_persona": by_persona,
        "by_sub_persona": by_sub_persona,
        "flags": flags,
        "judged": len(seen),
    }


def _pct(pt):
    p, t = pt
    return f"{100 * p / t:.1f}%" if t else "—"


def render_md(d: dict) -> str:
    gp = sum(v[0] for v in d["by_sub"].values())
    gt = sum(v[1] for v in d["by_sub"].values())
    off = [
        sum(d["by_sub"][s][i] for s in SUBCORPORA if s.endswith("OFF")) for i in (0, 1)
    ]
    on = [
        sum(d["by_sub"][s][i] for s in SUBCORPORA if s.endswith("ON")) for i in (0, 1)
    ]
    L = [
        "# Hourly blind-judge sweep — consolidated report",
        "",
        f"Slices present: {d['slices']}  ·  records judged: {d['judged']}",
        "",
        f"**Overall: {gp}/{gt} PASS ({_pct([gp, gt])})**",
        "",
        "## Burst OFF vs ON",
        "",
        "| overlay | PASS | rate |",
        "|---|---|---|",
        f"| burst OFF | {off[0]}/{off[1]} | {_pct(off)} |",
        f"| burst ON  | {on[0]}/{on[1]} | {_pct(on)} |",
        "",
        "## Sub-corpora",
        "",
        "| sub-corpus | PASS | rate |",
        "|---|---|---|",
    ]
    for s in SUBCORPORA:
        L.append(
            f"| {LABEL[s]} | {d['by_sub'][s][0]}/{d['by_sub'][s][1]} | {_pct(d['by_sub'][s])} |"
        )
    L += ["", "## Per persona", "", "| persona | PASS | rate |", "|---|---|---|"]
    for p in sorted(d["by_persona"]):
        L.append(
            f"| {p} | {d['by_persona'][p][0]}/{d['by_persona'][p][1]} | {_pct(d['by_persona'][p])} |"
        )
    L += ["", f"## FLAGS ({len(d['flags'])})", ""]
    if not d["flags"]:
        L.append("_none_")
    for sub, sid, why in sorted(d["flags"]):
        L.append(f"- `{sid}` ({LABEL[sub]}): {why}")
    L.append("")
    return "\n".join(L)


def render_html(d: dict, md: str) -> str:
    gp = sum(v[0] for v in d["by_sub"].values())
    gt = sum(v[1] for v in d["by_sub"].values())
    off = [
        sum(d["by_sub"][s][i] for s in SUBCORPORA if s.endswith("OFF")) for i in (0, 1)
    ]
    on = [
        sum(d["by_sub"][s][i] for s in SUBCORPORA if s.endswith("ON")) for i in (0, 1)
    ]

    def bar(pt):
        p, t = pt
        r = (100 * p / t) if t else 0
        hue = 120 * (r / 100)
        return (
            f'<div class="bar"><span style="width:{r:.1f}%;background:hsl({hue:.0f} 65% 45%)"></span>'
            f"<em>{_pct(pt)} · {p}/{t}</em></div>"
        )

    rows_sub = "".join(
        f"<tr><td>{LABEL[s]}</td><td>{bar(d['by_sub'][s])}</td></tr>"
        for s in SUBCORPORA
    )
    rows_p = "".join(
        f"<tr><td>{p}</td><td>{bar(d['by_persona'][p])}</td></tr>"
        for p in sorted(d["by_persona"])
    )
    flag_rows = (
        "".join(
            f"<tr><td><code>{html.escape(sid)}</code></td><td>{html.escape(LABEL[sub])}</td>"
            f"<td>{html.escape(why)}</td></tr>"
            for sub, sid, why in sorted(d["flags"])
        )
        or '<tr><td colspan="3">none</td></tr>'
    )
    return f"""<!doctype html><meta charset=utf-8>
<title>Hourly blind-judge report</title>
<style>
 body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
 h1{{font-size:1.6rem}} h2{{margin-top:2rem;border-bottom:1px solid #ddd;padding-bottom:.3rem}}
 .big{{font-size:2.4rem;font-weight:700}} .sub{{color:#666}}
 table{{border-collapse:collapse;width:100%;margin:.5rem 0}} td,th{{padding:.35rem .6rem;text-align:left}}
 tr:nth-child(even){{background:#fafafa}}
 .bar{{position:relative;background:#eee;border-radius:4px;height:20px;min-width:180px}}
 .bar span{{position:absolute;left:0;top:0;bottom:0;border-radius:4px}}
 .bar em{{position:relative;font-style:normal;font-size:12px;padding-left:6px;line-height:20px;color:#111}}
 code{{background:#f3f3f3;padding:1px 4px;border-radius:3px}}
 .cmp{{display:flex;gap:2rem}} .cmp>div{{flex:1}}
</style>
<h1>Hourly blind-judge sweep — consolidated report</h1>
<p class=sub>Slices present: {d["slices"]} · records judged: {d["judged"]}</p>
<p class=big>{_pct([gp, gt])} <span class=sub style="font-size:1rem">({gp}/{gt} PASS overall)</span></p>
<h2>Burst OFF vs ON</h2>
<div class=cmp>
 <div><b>burst OFF</b>{bar(off)}</div>
 <div><b>burst ON</b>{bar(on)}</div>
</div>
<h2>Sub-corpora</h2><table>{rows_sub}</table>
<h2>Per persona</h2><table>{rows_p}</table>
<h2>FLAGS ({len(d["flags"])})</h2>
<table><tr><th>scenario</th><th>sub-corpus</th><th>note</th></tr>{flag_rows}</table>
"""


def main() -> None:
    d = collect()
    md = render_md(d)
    (BASE / "FINAL_report.md").write_text(md, encoding="utf-8")
    (BASE / "FINAL_report.html").write_text(render_html(d, md), encoding="utf-8")
    print(md)
    print(f"\n-> {BASE / 'FINAL_report.md'}\n-> {BASE / 'FINAL_report.html'}")


if __name__ == "__main__":
    main()
