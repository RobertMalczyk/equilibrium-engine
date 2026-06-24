"""eval/burst_regression_sample.py — 10%-coverage blind regression, OUTBURST on vs off.

A lighter sibling of regression_judge.py: instead of the full 1400, it samples a fixed RANDOM 10%
(seeded -> reproducible) of the day + multi-day corpora, and renders each sampled record TWICE --
once with the M20.1 burst/outburst overlay DISABLED (the shipped neutral default) and once ENABLED.
A fresh blind LLM (Sonnet) judge then scores each record on its own; the aggregate compares the two
modes so any regression introduced by arming the outburst machinery on the general corpus is visible.

Stages:
  python eval/burst_regression_sample.py --build [--coverage 0.1] [--seed 1400]
      -> samples, renders both modes, writes batch prompts + manifest + a narration-diff map.
  python eval/burst_regression_sample.py --aggregate
      -> parses results/*.txt for both modes, writes REPORT.md + REPORT.html (the comparison).

Judging (between the two stages): one fresh Sonnet agent per batch reads
eval/burst_regression/<mode>/batches/<corpus>_<persona>.md and writes its verdict lines to
eval/burst_regression/<mode>/results/<corpus>_<persona>.txt:  `<scenario_id>: PASS|FLAG -- <why>`.
"""

from __future__ import annotations

import random
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
BASE = ROOT / "eval" / "burst_regression"
PERSONAS = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
CORPORA = ("day", "multi")
MODES = (
    "off",
    "on",
)  # off = burst overlay disabled (shipped default); on = outburst armed
N_PER_PERSONA = 100
CORPUS_DIR = {"day": "day", "multi": "multiday"}
SID = {"day": "day", "multi": "multi"}


def _render(persona: str, corpus: str, index: int, burst: bool) -> str:
    cfg = load_eval_persona_timescale(persona, burst=burst)
    path = (
        ROOT
        / "eval"
        / "scenarios"
        / CORPUS_DIR[corpus]
        / persona
        / f"{persona}_{SID[corpus]}_{index:03d}.yaml"
    )
    if corpus == "day":
        return narrate(persona, cfg, load_scenario(path), 1)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return narrate(persona, cfg, load_scenario(path), raw["n_days"])


def _sample(coverage: float, seed: int) -> dict:
    """Reproducible random sample of indices per (corpus, persona). Same draw every run for a seed."""
    rng = random.Random(seed)
    k = max(1, round(N_PER_PERSONA * coverage))
    sel: dict = {}
    for corpus in CORPORA:
        for p in PERSONAS:
            sel[(corpus, p)] = sorted(rng.sample(range(1, N_PER_PERSONA + 1), k))
    return sel


def build(coverage: float, seed: int) -> None:
    sel = _sample(coverage, seed)
    manifest = {"coverage": coverage, "seed": seed, "modes": list(MODES), "batches": []}
    changed: dict[str, bool] = {}
    for mode in MODES:
        burst = mode == "on"
        for corpus in CORPORA:
            for p in PERSONAS:
                idxs = sel[(corpus, p)]
                blocks, sids = [], []
                for i in idxs:
                    text = _render(p, corpus, i, burst)
                    sid = f"{p}_{SID[corpus]}_{i:03d}"
                    sids.append(sid)
                    blocks.append(f"===== RECORD: {sid} =====\n{text}")
                    if mode == "off":  # compute the burst on/off narration diff once
                        changed[sid] = text != _render(p, corpus, i, burst=True)
                profile = (ROOT / "eval" / "profiles" / f"{p}.md").read_text(
                    encoding="utf-8"
                )
                prompt = HEADER.format(
                    n=len(idxs),
                    name=DISPLAY[p],
                    profile=profile,
                    records="\n\n".join(blocks),
                )
                bdir = BASE / mode / "batches"
                bdir.mkdir(parents=True, exist_ok=True)
                (BASE / mode / "results").mkdir(parents=True, exist_ok=True)
                fn = f"{corpus}_{p}"
                (bdir / f"{fn}.md").write_text(prompt, encoding="utf-8")
                if mode == "off":
                    manifest["batches"].append(
                        {"batch": fn, "corpus": corpus, "persona": p, "scenarios": sids}
                    )
                print(f"  built {mode}/{fn} ({len(idxs)})")
    manifest["narration_changed"] = changed
    manifest["n_changed"] = sum(1 for v in changed.values() if v)
    manifest["n_scenarios"] = len(changed)
    (BASE / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    print(
        f"\n{len(manifest['batches'])} batch(es)/mode x {len(MODES)} modes; "
        f"{manifest['n_scenarios']} scenarios sampled, "
        f"{manifest['n_changed']} change narration when outburst is armed.\n-> {BASE}"
    )


_LINE = re.compile(r"^\s*([a-z_]+_\d{3})\s*:\s*(PASS|FLAG)\s*(?:--?\s*(.*))?$", re.I)


def _parse_mode(man: dict, mode: str) -> tuple[dict, dict]:
    """Return (per[(corpus,persona)] = [pass,judged], verdicts[sid] = (PASS|FLAG, why))."""
    per: dict = {}
    verdicts: dict = {}
    expected = {s: b for b in man["batches"] for s in b["scenarios"]}
    for b in man["batches"]:
        rf = BASE / mode / "results" / f"{b['batch']}.txt"
        per.setdefault((b["corpus"], b["persona"]), [0, 0])
        if not rf.exists():
            continue
        for line in rf.read_text(encoding="utf-8").splitlines():
            m = _LINE.match(line.strip())
            if not m:
                continue
            sid, verdict, why = (
                m.group(1).lower(),
                m.group(2).upper(),
                (m.group(3) or "").strip(),
            )
            if sid not in expected or sid in verdicts:
                continue
            verdicts[sid] = (verdict, why)
            key = (b["corpus"], b["persona"])
            per[key][1] += 1
            if verdict == "PASS":
                per[key][0] += 1
    return per, verdicts


def aggregate() -> None:
    man = yaml.safe_load((BASE / "manifest.yaml").read_text(encoding="utf-8"))
    data = {mode: _parse_mode(man, mode) for mode in MODES}
    changed = man.get("narration_changed", {})

    def totals(per):
        t = {"day": [0, 0], "multi": [0, 0]}
        for (corpus, _p), (ok, n) in per.items():
            t[corpus][0] += ok
            t[corpus][1] += n
        return t

    # ----- MD -----
    md = [
        "# Outburst on/off — 10% blind regression",
        "",
        f"Sample: seed `{man['seed']}`, coverage `{man['coverage']:.0%}` "
        f"= {man['n_scenarios']} scenarios (day + multi-day), each judged blind under the M20.1 "
        "outburst overlay **disabled** (shipped default) and **enabled**. One fresh Sonnet judge "
        "per batch, neutral rubric, no answer key.",
        "",
        f"**{man['n_changed']}/{man['n_scenarios']}** sampled scenarios change their narration when "
        "the outburst machinery is armed (the rest are bit-identical -> burst inert there).",
        "",
        "| corpus | persona | pass (off) | pass (on) | judged |",
        "|---|---|---|---|---|",
    ]
    for corpus in CORPORA:
        for p in PERSONAS:
            off_ok, off_n = data["off"][0].get((corpus, p), [0, 0])
            on_ok, on_n = data["on"][0].get((corpus, p), [0, 0])
            md.append(f"| {corpus} | {p} | {off_ok} | {on_ok} | {max(off_n, on_n)} |")
    toff, ton = totals(data["off"][0]), totals(data["on"][0])
    for corpus in CORPORA:
        md.append(
            f"| **{corpus} TOTAL** | | **{toff[corpus][0]}/{toff[corpus][1]}** | "
            f"**{ton[corpus][0]}/{ton[corpus][1]}** | |"
        )

    # per-scenario deltas: where the verdict differs between modes
    voff, von = data["off"][1], data["on"][1]
    deltas = []
    for sid in sorted(set(voff) | set(von)):
        a = voff.get(sid, ("—", ""))[0]
        b = von.get(sid, ("—", ""))[0]
        if a != b:
            deltas.append((sid, a, b, changed.get(sid, False)))
    md += [
        "",
        f"## Verdict deltas (off -> on): {len(deltas)}",
        "",
        "> Reading the deltas: the blind judge is itself non-deterministic, so a delta on a scenario "
        "whose narration is **unchanged** (`narration changed = no`) is pure JUDGE VARIANCE — the same "
        "text scored differently by two different agents — NOT a burst effect. Only `narration changed "
        "= yes` deltas are attributable to arming the outburst overlay.",
        "",
    ]
    if deltas:
        md += ["| scenario | off | on | narration changed |", "|---|---|---|---|"]
        md += [
            f"| {sid} | {a} | {b} | {'yes' if ch else 'no'} |"
            for sid, a, b, ch in deltas
        ]
    else:
        md += [
            "- none — arming the outburst overlay produced no verdict change in the sample."
        ]

    for mode in MODES:
        flags = sorted(
            f"{sid}: {why}" for sid, (v, why) in data[mode][1].items() if v == "FLAG"
        )
        md += ["", f"## Flags — outburst {mode} ({len(flags)})", ""]
        md += [f"- {f}" for f in flags] or ["- none"]
    (BASE / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # ----- HTML -----
    _write_html(man, data, changed, deltas, toff, ton)
    n_judged = {m: sum(per[1] for per in data[m][0].values()) for m in MODES}
    print(f"judged off={n_judged['off']} on={n_judged['on']}; deltas {len(deltas)}")
    print(f"-> {BASE / 'REPORT.md'}\n-> {BASE / 'REPORT.html'}")


def _write_html(man, data, changed, deltas, toff, ton) -> None:
    def rows():
        out = []
        for corpus in CORPORA:
            for p in PERSONAS:
                o = data["off"][0].get((corpus, p), [0, 0])
                n = data["on"][0].get((corpus, p), [0, 0])
                out.append(
                    f"<tr><td>{corpus}</td><td>{p}</td><td>{o[0]}/{o[1]}</td>"
                    f"<td>{n[0]}/{n[1]}</td></tr>"
                )
        for corpus in CORPORA:
            out.append(
                f"<tr class='tot'><td>{corpus} TOTAL</td><td></td>"
                f"<td>{toff[corpus][0]}/{toff[corpus][1]}</td>"
                f"<td>{ton[corpus][0]}/{ton[corpus][1]}</td></tr>"
            )
        return "\n".join(out)

    def delta_rows():
        if not deltas:
            return "<tr><td colspan=4><em>none — no verdict changed between modes</em></td></tr>"
        return "\n".join(
            f"<tr class='{'warn' if b == 'FLAG' else 'good'}'><td>{sid}</td><td>{a}</td>"
            f"<td>{b}</td><td>{'yes' if ch else 'no'}</td></tr>"
            for sid, a, b, ch in deltas
        )

    def flag_list(mode):
        flags = sorted(
            f"{sid}: {why}" for sid, (v, why) in data[mode][1].items() if v == "FLAG"
        )
        if not flags:
            return "<li><em>none</em></li>"
        return "\n".join(f"<li>{f}</li>" for f in flags)

    html = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Outburst on/off — 10% blind regression</title>
<style>
 body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a;background:#fafafa}}
 h1{{font-size:1.5rem}} h2{{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid #ddd;padding-bottom:.3rem}}
 table{{border-collapse:collapse;width:100%;margin:1rem 0;background:#fff}}
 th,td{{border:1px solid #ddd;padding:.45rem .6rem;text-align:left}}
 th{{background:#f0f0f0}} tr.tot td{{font-weight:600;background:#f7f7f7}}
 tr.warn td{{background:#fff3f0}} tr.good td{{background:#f0fbf3}}
 .meta{{color:#555}} code{{background:#eee;padding:.1rem .3rem;border-radius:3px}}
 .pill{{display:inline-block;padding:.15rem .5rem;border-radius:10px;background:#eef;margin-right:.4rem}}
</style>
<h1>Outburst on/off — 10% blind regression</h1>
<p class="meta">Sample: seed <code>{man["seed"]}</code>, coverage <code>{man["coverage"]:.0%}</code>
= {man["n_scenarios"]} scenarios (day + multi-day). Each judged blind under the M20.1 outburst overlay
<b>disabled</b> (shipped default) and <b>enabled</b>. One fresh Sonnet judge per batch, neutral rubric,
no answer key.</p>
<p><span class="pill">{man["n_changed"]}/{man["n_scenarios"]} scenarios change narration when armed</span>
<span class="pill">{len(deltas)} verdict deltas</span></p>
<h2>Pass counts by corpus / persona</h2>
<table><tr><th>corpus</th><th>persona</th><th>pass (off)</th><th>pass (on)</th></tr>
{rows()}
</table>
<h2>Verdict deltas (off → on)</h2>
<p class="meta">The blind judge is non-deterministic: a delta where <b>narration changed = no</b> is pure
judge variance (same text, different agent), <b>not</b> a burst effect. Only <b>narration changed =
yes</b> rows are attributable to arming the outburst overlay.</p>
<table><tr><th>scenario</th><th>off</th><th>on</th><th>narration changed</th></tr>
{delta_rows()}
</table>
<h2>Flags — outburst off</h2><ul>
{flag_list("off")}
</ul>
<h2>Flags — outburst on</h2><ul>
{flag_list("on")}
</ul>
</html>
"""
    (BASE / "REPORT.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    if "--build" in sys.argv:
        cov = 0.1
        seed = 1400
        if "--coverage" in sys.argv:
            cov = float(sys.argv[sys.argv.index("--coverage") + 1])
        if "--seed" in sys.argv:
            seed = int(sys.argv[sys.argv.index("--seed") + 1])
        build(cov, seed)
    elif "--aggregate" in sys.argv:
        aggregate()
    else:
        print(__doc__)
