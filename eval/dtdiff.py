"""Deterministic engine-output diff: render every corpus narration and hash it.

Used to prove the dt-invariant merge did NOT change engine output: run with the CURRENT engine and
with the pre-dt engine (swap engine/yaml_io.py between runs), then compare the two hash files.

    PYTHONPATH=. python eval/dtdiff.py <outfile>
"""

import hashlib
import sys

from eval.hourly_judge import PERSONAS, SUBCORPORA, _render, _tag


def sha(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def main() -> None:
    out = sys.argv[1]
    rows = []
    n = 0
    for corpus, burst in SUBCORPORA:
        for p in PERSONAS:
            for i in range(1, 101):
                narration = _render(p, corpus, burst, i)
                if narration is None:
                    continue
                sid = f"{p}_{_tag(corpus, burst)}_{i:03d}".lower()
                rows.append(f"{sid} {sha(narration.strip())}")
                n += 1
    rows.sort()
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows) + "\n")
    print(f"rendered+hashed {n} narrations -> {out}")


if __name__ == "__main__":
    main()
