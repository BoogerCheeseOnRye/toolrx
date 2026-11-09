#!/usr/bin/env python3
"""router_bench.py — honest, reproducible numbers for toolrx.

Three separate measurements (do not conflate them):

1. feature throughput : tokhash.features() over a fixed corpus, tokens/s
2. routing throughput : router.route() over a fixed query set, queries/s
3. end-to-end         : POST /call p50/p95 latency (needs a running server)

Usage:
    python3 bench/router_bench.py
    python3 bench/router_bench.py --http http://127.0.0.1:8080
    python3 bench/router_bench.py --reps 50 --json

"Token" here means the feature events emitted by tokhash: one word token plus
one token for every character 2/3-gram. It is NOT a transformer token — always
report the definition and the corpus hash next to the number.
"""

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(os.path.dirname(HERE), "toolrx")
sys.path.insert(0, CORE)

import router  # noqa: E402
import tokhash  # noqa: E402

DEFAULT_QUERIES = [
    "list contents of all files",
    "read my notes.txt",
    "how much memory is free",
    "add five and seven",
    "ping 8.8.8.8",
    "show the routing table",
    "write a file hello.py that prints hi",
    "check disk usage",
]

CORPUS_FILES = [
    "knowledge/fs.cat_all.md",
    "knowledge/fs.read_file.md",
    "knowledge/fs.list_dir.md",
    "knowledge/math.sum.md",
    "knowledge/net.ping.md",
]


def _cpu():
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "unknown"


def feature_bench(reps):
    text = ""
    for rel in CORPUS_FILES:
        path = os.path.join(CORE, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                text += fh.read()
        except OSError:
            continue
    if not text:
        return {"error": "no corpus files found"}
    # warm up
    for _ in range(3):
        tokhash.features(text)
    t0 = time.perf_counter()
    for _ in range(reps):
        tokhash.features(text)
    dt = time.perf_counter() - t0
    words = sum(1 for _ in tokhash._WORD.findall(text))
    grams = max(0, len(text) - 2) + max(0, len(text) - 3)
    tokens = words + grams
    return {
        "chars": len(text),
        "corpus_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "token_definition": "word tokens + one token per char 3-gram + 4-gram",
        "tokens_per_rep": tokens,
        "reps": reps,
        "seconds": round(dt, 4),
        "feature_tokens_per_sec": round(tokens * reps / dt),
    }


def route_bench(reps):
    model = router.load(os.path.join(CORE, "micro_model.json"))
    for q in DEFAULT_QUERIES:          # warm up
        router.route(q, model)
    samples = []
    t0 = time.perf_counter()
    n = reps * len(DEFAULT_QUERIES)
    for i in range(n):
        q0 = time.perf_counter()
        router.route(DEFAULT_QUERIES[i % len(DEFAULT_QUERIES)], model)
        samples.append((time.perf_counter() - q0) * 1000)
    dt = time.perf_counter() - t0
    samples.sort()
    return {
        "queries": n,
        "seconds": round(dt, 4),
        "queries_per_sec": round(n / dt),
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": round(samples[int(len(samples) * 0.95) - 1], 3),
    }


def http_bench(base, reps):
    timings = []
    for i in range(reps):
        body = json.dumps({"query": DEFAULT_QUERIES[i % len(DEFAULT_QUERIES)]}).encode()
        req = urllib.request.Request(base.rstrip("/") + "/call", data=body,
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        timings.append((time.perf_counter() - t0) * 1000)
    timings.sort()
    return {
        "requests": reps,
        "p50_ms": round(statistics.median(timings), 3),
        "p95_ms": round(timings[int(len(timings) * 0.95) - 1], 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--http", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    out = {
        "hardware": {"cpu": _cpu(), "machine": platform.machine(),
                     "python": platform.python_version()},
        "feature": feature_bench(args.reps),
        "route": route_bench(args.reps),
    }
    if args.http:
        out["http"] = http_bench(args.http, args.reps)
    if args.json:
        print(json.dumps(out, indent=2))
        return
    print("core        :", out["hardware"])
    f = out["feature"]
    print(f"features    : {f.get('feature_tokens_per_sec', '?'):,} tok/s  "
          f"({f.get('tokens_per_rep', 0):,} tok/rep, {f.get('reps')} reps)")
    print(f"corpus hash : {f.get('corpus_sha256', '?')[:16]}...")
    r = out["route"]
    print(f"routing     : {r['queries_per_sec']:,} q/s  "
          f"p50 {r['p50_ms']} ms  p95 {r['p95_ms']} ms")
    if "http" in out:
        h = out["http"]
        print(f"POST /call  : p50 {h['p50_ms']} ms  p95 {h['p95_ms']} ms "
              f"({h['requests']} req)")


if __name__ == "__main__":
    main()
