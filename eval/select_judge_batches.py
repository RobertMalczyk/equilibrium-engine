"""eval/select_judge_batches.py -- BATCHED-blind judging of the REMAINING multi-day corpus.

Companion to eval/select_judge_sample.py (which did the first stratified 70, one fresh agent each).
This packs the *remaining* scenarios (everything NOT in batch/manifest.yaml) into batch prompts so a
SINGLE fresh-context (blind) agent judges ~CHUNK same-persona records independently in one context --
~63 agent spawns instead of 630. Same blind inputs (profile + observable record + rubric); the agent is
told to judge each record ON ITS OWN and never compare them.

Run:  PYTHONPATH=. python eval/select_judge_batches.py             # write the batch prompts + manifest
      PYTHONPATH=. python eval/select_judge_batches.py --list       # just list batches
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from eval.judge_multiday import render
from eval.select_judge_sample import load_plans, personas

ROOT = Path(__file__).resolve().parents[1]
DONE_MANIFEST = ROOT / "eval" / "judge_multiday" / "batch" / "manifest.yaml"
OUT = ROOT / "eval" / "judge_multiday" / "full"
CHUNK = 10


def already_done() -> dict[str, set[int]]:
    man = yaml.safe_load(DONE_MANIFEST.read_text(encoding="utf-8"))
    out: dict[str, set[int]] = {}
    for s in man["scenarios"]:
        out.setdefault(s["persona"], set()).add(int(s["index"]))
    return out


def remaining(persona: str, done: set[int]) -> list[int]:
    return sorted(i for i in load_plans(persona) if i not in done)


HEADER = """\
You are a BLIND believability judge. Below are {n} INDEPENDENT records, each a few simulated days of the
SAME character ({name}). Judge EACH record ON ITS OWN -- do NOT compare the records to one another, and do
NOT prove anything about the character's traits. For each record you are only checking the GENERAL working
of the model: does this look like a sane stretch of days in a life?

For EACH record, check two things:
(a) DOES IT MAKE SENSE as days in a life? Sane pacing -- not starving within minutes, not enraged for no
    reason, sleeps at night and wakes recovered, hunger/temper rise and fall over believable spans, nothing
    absurd.
(b) IS IT NOT WRONG for this person? Nothing contradicts the profile below (a calm man isn't raging all day;
    a hot one isn't a saint). You are NOT asked to prove he differs from anyone -- only that nothing jars.

# Who this is (applies to EVERY record below)
{profile}

# The records
{records}

# Output -- EXACTLY one line per record, nothing else:
<scenario_id>: PASS|FLAG -- <max 12 words; for FLAG, the one thing that most needs a look>
"""


def build_batch_prompt(persona: str, idxs: list[int]) -> str:
    from eval.judge_multiday import (
        RUBRIC,  # noqa: F401  (kept for parity; not used directly)
    )

    profile = (ROOT / "eval" / "profiles" / f"{persona}.md").read_text(encoding="utf-8")
    blocks = []
    from eval.render_narration import DISPLAY

    name = DISPLAY[persona]
    for idx in idxs:
        narration, _ = render(persona, idx)
        sid = f"{persona}_multi_{idx:03d}"
        blocks.append(f"===== RECORD: {sid} =====\n{narration}")
    return HEADER.format(
        n=len(idxs), name=name, profile=profile, records="\n\n".join(blocks)
    )


def batches() -> list[tuple[str, int, list[int]]]:
    done = already_done()
    out = []
    for p in personas():
        rem = remaining(p, done.get(p, set()))
        for bn, start in enumerate(range(0, len(rem), CHUNK)):
            out.append((p, bn, rem[start : start + CHUNK]))
    return out


def main():
    bs = batches()
    if "--list" in sys.argv:
        for p, bn, idxs in bs:
            print(f"  {p}_batch{bn:02d}: {len(idxs)} scenarios {idxs}")
        print(
            f"total batches: {len(bs)}; total scenarios: {sum(len(i) for _, _, i in bs)}"
        )
        return
    OUT.mkdir(parents=True, exist_ok=True)
    man = []
    for p, bn, idxs in bs:
        prompt = build_batch_prompt(p, idxs)
        fn = f"{p}_batch{bn:02d}.prompt.md"
        (OUT / fn).write_text(prompt, encoding="utf-8")
        man.append(
            {
                "persona": p,
                "batch": bn,
                "prompt": fn,
                "scenarios": [f"{p}_multi_{i:03d}" for i in idxs],
            }
        )
    (OUT / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "chunk": CHUNK,
                "n_batches": len(man),
                "n_scenarios": sum(len(b["scenarios"]) for b in man),
                "batches": man,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(
        f"wrote {len(man)} batch prompts ({sum(len(b['scenarios']) for b in man)} scenarios) "
        f"to {OUT.relative_to(ROOT)} (+ manifest.yaml)."
    )


if __name__ == "__main__":
    main()
