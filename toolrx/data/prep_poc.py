#!/usr/bin/env python3
"""Pre-tokenize the training set for the CPU-jax PoC.

Byte-level vocab + special role tokens. Persists token-id arrays as .npy so the
jax trainer on lab host reads a compact binary instead of JSONL.
"""
import json
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "training_all.jsonl")
OUT = os.path.join(HERE, "poc_ids.npy")
OUTLEN = os.path.join(HERE, "poc_len.npy")

BOS, EOS, U, A = 256, 257, 258, 259   # special ids beyond byte vocab 0..255
MAX_LEN = 256
VOCAB = 260


def role_id(role):
    return U if role == "user" else A


def tokenize(msg):
    return list(msg.encode("utf-8"))


def main():
    seqs = []
    with open(SRC) as f:
        for line in f:
            m = json.loads(line)["messages"]
            ids = [BOS]
            for msg in m:
                ids.append(role_id(msg["role"]))
                ids += tokenize(msg["content"])
            ids.append(EOS)
            if len(ids) > MAX_LEN:
                ids = ids[:MAX_LEN - 1] + [EOS]
            seqs.append(ids)

    N = len(seqs)
    X = np.full((N, MAX_LEN), EOS, dtype=np.int32)
    L = np.zeros(N, dtype=np.int32)
    for i, s in enumerate(seqs):
        X[i, :len(s)] = s
        L[i] = len(s)
    np.save(OUT, X)
    np.save(OUTLEN, L)
    print(json.dumps({"examples": N, "max_len": MAX_LEN, "vocab": VOCAB,
                      "tokens_total": int(L.sum()), "mean_len": round(float(L.mean()), 1)},
                     indent=2))


if __name__ == "__main__":
    main()