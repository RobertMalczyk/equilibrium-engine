"""eval/blind5.py -- OLD-mechanism blind-judge, 5% sample (token-cost probe).

Restores the pre-M20.1 efficient style: the batch .md file IS the whole prompt (rubric + profile +
~10 records baked in), fed INLINE to one fresh agent per batch -- no Read round-trip, no schema,
plain `id: PASS|FLAG` verdict lines. Engine NEUTRAL (burst-off), exactly like commit 7697571.

This builds a 5% sample = 7 batches of 10 records (70 scenarios = 5% of the 1400-scenario corpus),
mixed across both corpora and all 7 personas so a day-batch and a multi-batch token cost can both be
measured. It ONLY writes batch prompts + a size report; it does NOT judge (judging is a separate,
gated step).

    python eval/blind5.py --build     # write eval/blind5/batches/*.md + sizes.md
"""

from __future__ import annotations

import sys
from pathlib import Path

from eval.regression_judge import render_day, render_multi

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "blind5"
CHUNK = 10
# 5% of 1400 = 70 records = 7 batches; first chunk (indices 1..10) per (corpus, persona)
SAMPLE = [
    ("day", "halgrim"),
    ("day", "cichy"),
    ("day", "wojslaw"),
    ("day", "branic"),
    ("multi", "lutek"),
    ("multi", "welf"),
    ("multi", "edda"),
]


def _batch_prompt(corpus: str, persona: str) -> tuple[str, list[str]]:
    """The full inline prompt for one batch + the record ids in it (old mechanism: content baked in)."""
    from eval.regression_judge import HEADER
    from eval.render_narration import DISPLAY

    profile = (ROOT / "eval" / "profiles" / f"{persona}.md").read_text(encoding="utf-8")
    blocks, sids = [], []
    for i in range(1, CHUNK + 1):
        if corpus == "day":
            narration = render_day(persona, i)
            sid = f"{persona}_day_{i:03d}"
        else:
            narration, _ = render_multi(persona, i)
            sid = f"{persona}_multi_{i:03d}"
        sids.append(sid)
        blocks.append(f"===== RECORD: {sid} =====\n{narration}")
    prompt = HEADER.format(
        n=len(sids), name=DISPLAY[persona], profile=profile, records="\n\n".join(blocks)
    )
    return prompt, sids


def build() -> None:
    batches = OUT / "batches"
    batches.mkdir(parents=True, exist_ok=True)
    (OUT / "results").mkdir(parents=True, exist_ok=True)
    sizes = [
        "# 5% sample batch sizes (token estimate ~= chars/4)\n",
        "| batch | records | chars | ~tokens |",
        "|---|---|---|---|",
    ]
    tot_c = 0
    for corpus, persona in SAMPLE:
        prompt, sids = _batch_prompt(corpus, persona)
        fn = f"{corpus}_{persona}_b00"
        (batches / f"{fn}.md").write_text(prompt, encoding="utf-8")
        c = len(prompt)
        tot_c += c
        sizes.append(f"| {fn} | {len(sids)} | {c} | {c // 4} |")
    sizes.append(f"| **TOTAL (7 batches)** | 70 | {tot_c} | {tot_c // 4} |")
    sizes.append("")
    sizes.append(
        "Note: input-token estimate per agent = its batch ~tokens + the agent's own system"
    )
    sizes.append(
        "prompt overhead. Output per agent ~= 10 short verdict lines. Full 1400-scenario run"
    )
    sizes.append("= 140 batches (burst-off); the 2800 burst-on+off run = 280 batches.")
    (OUT / "sizes.md").write_text("\n".join(sizes), encoding="utf-8")
    print("\n".join(sizes))
    print(f"\n-> {batches} (7 batch prompts)\n-> {OUT / 'sizes.md'}")


def main() -> None:
    if "--build" in sys.argv:
        build()
    else:
        print("use --build (judging is a separate, gated step)")


if __name__ == "__main__":
    main()
