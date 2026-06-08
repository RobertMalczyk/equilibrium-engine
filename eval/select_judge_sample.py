"""eval/select_judge_sample.py -- pick a DETERMINISTIC, stratified sample of the 700 multi-day
scenarios for the blind judge, and write one self-contained judge prompt per chosen scenario.

Goal of the sample: a defensible PASS-rate over the corpus at a tractable agent count. For each persona
we choose K scenarios that together (a) cover every day-type that persona's corpus uses, and (b) spread
across the day-length range (3..6 days). The pick is greedy-by-coverage with the scenario INDEX as the
deterministic tie-break, so the sample is reproducible bit-for-bit.

Each emitted prompt is the SAME artifact the demo used (plain profile + observable, numbers-free,
mechanism-free multi-day record + neutral rubric) -- meant for a SEPARATE fresh-context (blind) agent.

Run:  PYTHONPATH=. python eval/select_judge_sample.py            # default K=10/persona -> 70 prompts
      PYTHONPATH=. python eval/select_judge_sample.py --k 5       # smaller sample
      PYTHONPATH=. python eval/select_judge_sample.py --list      # just print the chosen manifest
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from eval.judge_multiday import build_prompt

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "eval" / "scenarios" / "multiday"
OUT = ROOT / "eval" / "judge_multiday" / "batch"


def personas() -> list[str]:
    return sorted(d.name for d in CORPUS.iterdir() if d.is_dir())


def load_plans(persona: str) -> dict[int, list[str]]:
    plans = {}
    for f in sorted((CORPUS / persona).glob(f"{persona}_multi_*.yaml")):
        raw = yaml.safe_load(f.read_text(encoding="utf-8"))
        plans[int(f.stem.split("_")[-1])] = list(raw["day_plan"])
    return plans


def select(persona: str, k: int) -> list[int]:
    """Greedy: each pick adds the index that covers the most still-uncovered (day_type) and
    (n_days) buckets; ties broken by lowest index. Fully deterministic."""
    plans = load_plans(persona)
    want_types = {dt for plan in plans.values() for dt in plan}
    want_lens = {len(plan) for plan in plans.values()}
    chosen: list[int] = []
    cov_types: set[str] = set()
    cov_lens: set[int] = set()
    remaining = dict(plans)
    while len(chosen) < k and remaining:
        best_idx, best_gain = None, None
        for idx in sorted(remaining):
            plan = remaining[idx]
            gain = len(set(plan) - cov_types) + (1 if len(plan) not in cov_lens else 0)
            # once everything's covered, gain is 0 for all -> fall through to round-robin by index
            if best_gain is None or gain > best_gain:
                best_idx, best_gain = idx, gain
        chosen.append(best_idx)
        cov_types |= set(remaining[best_idx])
        cov_lens.add(len(remaining[best_idx]))
        del remaining[best_idx]
        if cov_types >= want_types and cov_lens >= want_lens:
            # coverage met; fill the rest evenly by index stride for spread, still deterministic
            rest = sorted(remaining)
            stride = max(1, len(rest) // max(1, (k - len(chosen))))
            for j in range(0, len(rest), stride):
                if len(chosen) >= k:
                    break
                chosen.append(rest[j])
            break
    return sorted(chosen[:k])


def manifest(k: int) -> list[tuple[str, int, list[str]]]:
    rows = []
    for p in personas():
        plans = load_plans(p)
        for idx in select(p, k):
            rows.append((p, idx, plans[idx]))
    return rows


def main():
    k = 10
    if "--k" in sys.argv:
        k = int(sys.argv[sys.argv.index("--k") + 1])
    rows = manifest(k)
    if "--list" in sys.argv:
        for p, idx, plan in rows:
            print(f"  {p}_multi_{idx:03d}  ({len(plan)}d): {plan}")
        print(f"total: {len(rows)} scenarios")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    man = []
    for p, idx, plan in rows:
        prompt = build_prompt(p, idx)
        fn = f"{p}_multi_{idx:03d}.prompt.md"
        (OUT / fn).write_text(prompt, encoding="utf-8")
        man.append(
            {
                "persona": p,
                "index": idx,
                "n_days": len(plan),
                "day_plan": plan,
                "prompt": fn,
            }
        )
    (OUT / "manifest.yaml").write_text(
        yaml.safe_dump(
            {"k_per_persona": k, "total": len(man), "scenarios": man}, sort_keys=False
        ),
        encoding="utf-8",
    )
    print(
        f"wrote {len(man)} blind judge prompts to {OUT.relative_to(ROOT)} (+ manifest.yaml)."
    )
    print(
        "Each prompt is self-contained and meant for a SEPARATE fresh-context (blind) agent."
    )


if __name__ == "__main__":
    main()
