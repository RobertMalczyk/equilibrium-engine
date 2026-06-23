"""Read-only fail-triage: classify every FLAG by pipeline layer + root cause (fail_triage_playbook.md).

Pure analysis -- NO engine change. Note-signature classification per the playbook's §4 catalogue,
refined with event/direction/burst context. The key forks the playbook names (STATE-vs-NARRATION,
TOPOLOGY-vs-CALIBRATION) still need per-record trace confirmation for the L2/L3 buckets; this gives
the layer histogram + clusters + a per-flag table to drive that. Writes eval/hourly_runs/TRIAGE.md.

    PYTHONPATH=. python eval/triage.py
"""

from __future__ import annotations

import glob
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path("eval/hourly_runs")
VL = re.compile(r"^\s*([a-z0-9_]+)\s*:\s*(PASS|FLAG)\s*(?:--?\s*(.*))?$", re.I)

LAYER_ACTION = {
    "L1": "scenario generator (min-spacing / dedup) — not the engine",
    "L2/L3": "diagnose topology-vs-gain on the trace, then fix the edge (spec-first) or re-fit the constant",
    "L3": "re-fit the specific constant via the calibration harness (confirm it isn't a label issue)",
    "L4": "fix render_narration phrasing — no dynamics change",
    "L5": "confirm-read (same model); accept or sharpen the rubric",
    "L?": "manual read (capture the diagnostic card)",
}


def classify(sid: str, note: str):
    n = note.lower()
    on = "burston" in sid
    pos = re.search(r"kindness|soup|food|marta|help|hand|warmth|gift", n)
    hostile = re.search(
        r"erupt|snap|fury|furious|burst|cold|contempt|curt|bristle|brush|mutter|complain|angr|shout",
        n,
    )

    # L1 — degenerate input cadence
    if re.search(
        r"two soups?|three soups?|double soup|double serving|back-to-back|artifact|glitch|implausibl|minutes apart|two minutes|ten minutes|sixteen minutes|34 minutes|dense",
        n,
    ):
        return "L1", "corpus: degenerate event cadence"
    # L4 — positive event mislabeled with a neutral/mock phrase (state likely fine, narration wrong)
    mislabel = re.search(
        r"lets it pass|no notable reaction|no ?reaction|flat|neutral|indifferen|dismiss|wrong (label|for)|as if.*barb|like a mock|not warmth|zero warmth|wording|logged as|mock-indifference|muted",
        n,
    )
    if pos and mislabel and not hostile:
        return (
            "L4",
            "expression: positive event mislabeled (lets-it-pass / no-reaction)",
        )
    # L3 — post-eruption recovery too fast (fury -> settled in minutes)
    if re.search(
        r"too fast|recovery too fast|seconds after|settled.*(after|min).*(fury|erupt|outburst)|(fury|erupt|outburst).*(seconds|min).*(settled|calm)|then (sits calmly|settled).*(fast|\d+ ?min)|resolved to settled",
        n,
    ):
        return "L3", "calibration: post-eruption recovery / anger decay too fast"
    # L2/L3 — hostility/eruption displaced onto a KIND source
    if pos and hostile:
        return (
            "L2/L3",
            f"dynamics: hostility displaced onto a kind source ({'burst ON' if on else 'burst OFF'})",
        )
    # L2/L3 — high-authority persona vs stranger command
    if re.search(
        r"stranger.*(order|command)|orders? (her|castellan)|complies.*stranger|obeys a stranger|subordination",
        n,
    ):
        if re.search(r"compl|obey", n):
            return (
                "L2/L3",
                "dynamics: high-authority persona COMPLIES with a stranger order (target-policy)",
            )
        return "L5", "judge-marginal: authority refuses stranger order (defensible)"
    # L2/L3 — hostility / non-compliance toward a RESPECTED source
    if re.search(
        r"respect|contempt|ignores?.*(order|edda)|edda.*(cold|ignore|refus|contempt|complain|curt|mutter)|mutter.*edda|buttons anger|authority",
        n,
    ):
        return (
            "L2/L3",
            "dynamics: hostility/non-compliance toward a RESPECTED source (relational gating)",
        )
    # L2/L3 — burst over-eager / escalation too compressed / refusal too sticky
    if re.search(
        r"escalation too compressed|two full eruptions|erupts at routine|no clear buildup|no buildup|near-total refusal|refusal of every order",
        n,
    ):
        return "L2/L3", "dynamics: burst over-eager / escalation or refusal too sticky"
    # L3 — persona contrast too weak (too mild/warm for a hot/ungrateful profile)
    if re.search(
        r"too mild|near-saintly|saintly|inconsistent with.*(ungrateful|profile)|sustained warmth.*inconsistent|not hot-tempered",
        n,
    ):
        return "L3", "calibration: persona-contrast too weak (too mild for profile)"
    # L3 — thick-skinned over-reply
    if re.search(
        r"thick-skinned|contradicts.*profile|curt cold reply|mockery rolls off", n
    ):
        return "L3", "calibration: thick-skinned persona over-replies to mockery"
    # L3 — sleep / pacing
    if re.search(
        r"sleep|past midnight|working (past|until)|late for|00:[0-5]\d|23:[0-5]\d|late night",
        n,
    ):
        return "L3", "calibration: sleep-onset / late pacing"
    # L4 — expected reaction missing (hot persona lets a mock pass) — likely label or threshold
    if re.search(
        r"no reaction.*uncharacteristic|passes with no reaction|mock.*no reaction|letting barb pass|ignores? .*mock",
        n,
    ):
        return "L4", "expression/threshold: expected reaction missing (verify state)"
    # L5 — marginal
    if re.search(
        r"plausible|warrants|minor|slightly|looks like|unusual|odd|check|jars", n
    ):
        return "L5", "judge-marginal"
    return "L?", "unclassified"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    flags = []
    for f in glob.glob(str(BASE / "slice_*" / "results" / "*.txt")):
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            m = VL.match(line.strip())
            if m and m.group(2).upper() == "FLAG":
                flags.append((m.group(1).lower(), (m.group(3) or "").strip()))

    hist, clus, rows = Counter(), Counter(), []
    for sid, note in flags:
        lyr, tag = classify(sid, note)
        hist[lyr] += 1
        clus[(lyr, tag)] += 1
        rows.append((sid, lyr, tag, note))

    L = ["# Fail triage — all-Sonnet baseline (per fail_triage_playbook.md)", ""]
    L.append(
        f"**{len(flags)} flags** classified by pipeline layer (note-signature + event/burst context)."
    )
    L.append(
        "L2/L3 splits (topology vs calibration) and state-vs-narration still need per-record trace"
    )
    L.append(
        "confirmation — see the deep-verified examples in the believability plan.\n"
    )
    L.append("## Layer histogram")
    L.append("| layer | flags | what to do |\n|---|---|---|")
    for lyr in ["L1", "L2/L3", "L3", "L4", "L5", "L?"]:
        if hist[lyr]:
            L.append(f"| {lyr} | {hist[lyr]} | {LAYER_ACTION[lyr]} |")
    L.append("\n## Clusters (layer · root cause)")
    L.append("| n | layer | root cause |\n|---|---|---|")
    for (lyr, tag), c in clus.most_common():
        L.append(f"| {c} | {lyr} | {tag} |")
    L.append("\n## Per-flag")
    L.append("| scenario | layer | cause | judge note |\n|---|---|---|---|")
    for sid, lyr, tag, note in sorted(rows, key=lambda r: (r[1], r[2], r[0])):
        L.append(f"| {sid} | {lyr} | {tag} | {note} |")
    (BASE / "TRIAGE.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"{len(flags)} flags")
    print(
        "layer histogram:",
        {k: hist[k] for k in ["L1", "L2/L3", "L3", "L4", "L5", "L?"] if hist[k]},
    )
    print("clusters:")
    for (lyr, tag), c in clus.most_common():
        print(f"  {c:3}  {lyr:6} {tag}")
    print(f"-> {BASE / 'TRIAGE.md'}")


if __name__ == "__main__":
    main()
