import json
from pathlib import Path

base = Path("eval/hourly_runs")
items = []
for p in sorted(base.glob("slice_*/batches/*.md")):
    s = int(p.parts[-3].split("_")[1])
    items.append({"slice": s, "batch": p.stem, "path": p.as_posix()})
(base / "worklist.json").write_text(json.dumps(items))
print(f"{len(items)} batches")

have = {(it["slice"], it["batch"]) for it in items}
subs = ["day_burstOFF", "day_burstON", "multi_burstOFF", "multi_burstON"]
pers = ["halgrim", "wojslaw", "cichy", "branic", "lutek", "welf", "edda"]
miss = [
    (s, f"{sub}_{p}")
    for s in range(10)
    for sub in subs
    for p in pers
    if (s, f"{sub}_{p}") not in have
]
print("missing:", miss)
