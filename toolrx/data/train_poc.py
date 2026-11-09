#!/usr/bin/env python3
"""CPU-jax PoC: train a tiny transformer on the distilled opencode tool-call corpus.

Purpose: validate the end-to-end distillation pipeline on lab host's weak Atom CPU.
A small causal LM learns the next token (including [tool:...] calls) from byte-level
roles + content. Loss + sampled continuation demonstrate learning.

Run: python3 train_poc.py poc_ids.npy poc_len.npy [steps] [batch]
"""
import json
import os
import sys
import time

import numpy as np
import jax
import jax.numpy as jnp
import jax.random as jr

X = np.load(sys.argv[1])
L = np.load(sys.argv[2])
STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
BATCH = int(sys.argv[4]) if len(sys.argv) > 4 else 32

N, MAX_LEN = X.shape
VOCAB = 260
D = 96
HEADS = 4
LAYERS = 3
D_FF = 192
DROP = 0.0
START_SIGN = jr.PRNGKey(0)

PARAMS = {}


def init_params(key):
    keys = jr.split(key, LAYERS + 3)
    w = lambda k, s: jr.normal(k, s) * (1.0 / jnp.sqrt(s[-1]))  # noqa: E731
    p = {
        "tok": w(keys[0], (VOCAB, D)),
        "pos": w(keys[1], (MAX_LEN, D)),
        "out": w(keys[2], (D, VOCAB)),
    }
    p["layers"] = []
    for i in range(LAYERS):
        k = jr.split(keys[3 + i], 6)
        p["layers"].append(dict(
            q=w(k[0], (D, D)), kk=w(k[1], (D, D)), v=w(k[2], (D, D)),
            o=w(k[3], (D, D)),
            g1=w(k[4], (D, D_FF)), g2=w(k[5], (D_FF, D)),
            n1=jr.normal(k[0], (D,)) * 0.0, n2=jr.normal(k[0], (D,)) * 0.0,
        ))
    return p


def layer_norm(x, g, eps=1e-5):
    mu = jnp.mean(x, -1, keepdims=True)
    s = jnp.var(x, -1, keepdims=True)
    return (x - mu) / jnp.sqrt(s + eps) * (1.0 + g)


def forward(p, x, L_, key):
    B, T = x.shape
    h = p["tok"][x] + p["pos"][None, :T, :]
    for ln in p["layers"]:
        hh = layer_norm(h, ln["n1"])
        q = jnp.einsum("btd,dn->btn", hh, ln["q"]).reshape(B, T, HEADS, D // HEADS)
        k = jnp.einsum("btd,dn->btn", hh, ln["kk"]).reshape(B, T, HEADS, D // HEADS)
        v = jnp.einsum("btd,dn->btn", hh, ln["v"]).reshape(B, T, HEADS, D // HEADS)
        logits = jnp.einsum("bthd,bT hd->bhtT", q, k) / jnp.sqrt(D // HEADS)
        # causal + padding mask
        causal = jnp.tril(jnp.ones((T, T), bool))[None, None]
        valid = (jnp.arange(T)[None, :, None, None] < L_[:, None, None, None])
        mask = causal & valid
        logits = jnp.where(mask, logits, -1e9)
        att = jax.nn.softmax(logits, -1)
        ctx = jnp.einsum("bhtT,bThd->bthd", att, v).reshape(B, T, D)
        h = h + jnp.einsum("btd,dn->btn", ctx, ln["o"])
        hh = layer_norm(h, ln["n2"])
        h = h + jax.nn.gelu(jnp.einsum("btd,dn->btn", hh, ln["g1"])) @ ln["g2"]
    logits = jnp.einsum("btd,dv->btv", h, p["out"])
    return logits


def loss_fn(p, key):
    idx = jr.randint(key, (BATCH,), 0, N)
    x = jnp.asarray(X[idx]); L_ = jnp.asarray(L[idx])
    kl = jr.fold_in(key, 1)
    logits = forward(p, x, L_, kl)
    y = jnp.concatenate([x[:, 1:], jnp.full((BATCH, 1), 257)], -1)
    target = jax.nn.log_softmax(logits, -1)
    nll = -jnp.take_along_axis(target, y[:, :, None], -1)[..., 0]
    mask = (jnp.arange(MAX_LEN)[None, :] < L_[:, None]) & (jnp.arange(MAX_LEN)[None, :] < (L_[:, None] - 1))
    return (nll * mask).sum() / mask.sum()


def train():
    p = init_params(jr.PRNGKey(0))
    opt = {k: jnp.zeros_like(v) for k, v in p.items() if not isinstance(v, list)}
    opt["layers"] = [dict((k, jnp.zeros_like(v)) for k, v in ly.items()) for ly in p["layers"]]
    mom = {k: jnp.zeros_like(v) for k, v in opt.items() if not isinstance(v, list)}
    mom["layers"] = [dict((k, jnp.zeros_like(v)) for k, v in ly.items()) for ly in opt["layers"]]

    full = list(p.items()) if not isinstance(p, list) else p

    step = jax.jit(lambda a, b, c: jax.value_and_grad(loss_fn)(a, b))

    lr = 3e-3
    b1, b2, eps = 0.9, 0.99, 1e-8
    t0 = time.time()
    for i in range(1, STEPS + 1):
        key = jr.PRNGKey(i)
        lv, g = step(p, key)
        # manual adam over flat ordered keys
        keys = list(p.keys())
        for k in keys:
            if isinstance(p[k], list):
                for li in range(len(p[k])):
                    for kk in p[k][li]:
                        mom["layers"][li][kk] = b1 * mom["layers"][li][kk] + (1 - b1) * g[k][li][kk]
                        opt["layers"][li][kk] = b2 * opt["layers"][li][kk] + (1 - b2) * g[k][li][kk] ** 2
                        p[k][li][kk] -= lr * mom["layers"][li][kk] / (jnp.sqrt(opt["layers"][li][kk]) + eps)
            else:
                mom[k] = b1 * mom[k] + (1 - b1) * g[k]
                opt[k] = b2 * opt[k] + (1 - b2) * g[k] ** 2
                p[k] -= lr * mom[k] / (jnp.sqrt(opt[k]) + eps)
        if i % 200 == 0 or i == 1:
            print(f"step={i} loss={float(lv):.4f} t={(time.time()-t0):.1f}s", flush=True)

    return p


def sample(p, seed=100, temp=0.7, n=60):
    ids = [256, 258]
    k = jr.PRNGKey(seed)
    for _ in range(n):
        x = jnp.asarray([ids[:MAX_LEN]]).astype(jnp.int32)
        L_ = jnp.asarray([len(ids)])
        logits = forward(p, x, L_, k)[0, len(ids) - 1]
        logits = logits / temp
        pr = jax.nn.softmax(logits - logits.max())
        k, sub = jr.split(k)
        nxt = int(jr.categorical(sub, jnp.log(pr + 1e-9)))
        ids.append(nxt)
        if nxt == 257:
            break
    return ids


def decode(ids):
    out = b""
    for t in ids:
        if t == 256: continue
        if t == 257: break
        if t == 258: out += b"<user> "
        elif t == 259: out += b"<asst> "
        else: out += bytes([t])
    return out.decode("utf-8", "replace")


if __name__ == "__main__":
    print(f"train poc: N={N} L={MAX_LEN} D={D} layers={LAYERS} steps={STEPS} batch={BATCH}", flush=True)
    p = train()
    ids = sample(p)
    print("SAMPLE:", decode(ids)[:400], flush=True)