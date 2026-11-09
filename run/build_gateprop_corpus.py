#!/usr/bin/env python3
"""build_gateprop_corpus.py — build a corpus whose class counts mirror the
rebalanced gate MIX, so training effort matches what the gate actually scores.

The full corpus is 65% bash (one of 1584 unique commands a tiny model can't
memorize) but the gate rewards bash only 14/120. Meanwhile calculate (17 ex),
question (12), git (15) are nearly absent yet scored at 8-10 samples each.
This corpus scales every gate class ~20x so rare classes get real presence.
"""
import json, os, random, collections

GATE_MIX = {"bash":14,"read_file":22,"write_file":22,"list_dir":20,
            "search_files":14,"calculate":10,"git_status":10,"question":8}
SCALE = 20  # per-class examples per gate-sample
TARGET = {k: v*SCALE for k,v in GATE_MIX.items()}


def load(path):
    byc = collections.defaultdict(list)
    for line in open(path):
        try: r = json.loads(line)
        except Exception: continue
        a = r.get("answers") or []
        if a and a[0]["name"] in TARGET:
            byc[a[0]["name"]].append(r)
    return byc


def main(src, dst):
    byc = load(src)
    rng = random.Random(2026)
    out = []
    for cls, want in TARGET.items():
        recs = byc.get(cls, [])
        rng.shuffle(recs)
        picks = []
        while len(picks) < want and recs:
            picks += recs[:min(want-len(picks), len(recs))]
        picks = picks[:want]
        out += picks
        print(f"{cls:14} want={want:4} got={len(picks):4}")
    rng.shuffle(out)
    with open(dst, "w") as fh:
        for r in out:
            fh.write(json.dumps(r) + "\n")
    print("TOTAL", len(out))


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_focused.jsonl")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_gateprop.jsonl")
    main(src, dst)
