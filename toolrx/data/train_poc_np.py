#!/usr/bin/env python3
"""CPU PoC (no-AVX): tiny transformer trained on distilled opencode tool-call corpus.

Pure NumPy autograd engine (works on the Atom x5-Z8350, which has no AVX and cannot
run jaxlib). Validates the end-to-end distillation pipeline: byte tokens -> tiny
causal LM -> loss decreases -> samples a [tool:...] call.

Run: python3 train_poc_np.py poc_ids.npy poc_len.npy [steps] [batch] [cap]
"""
import sys
import time

import numpy as np

XP = np.load(sys.argv[1]).astype(np.int64)
LP = np.load(sys.argv[2]).astype(np.int64)
N, MAXL = XP.shape
STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 400
BATCH = int(sys.argv[4]) if len(sys.argv) > 4 else 16
CAP = int(sys.argv[5]) if len(sys.argv) > 5 else 128

VOCAB = 260
D = 64
HEADS = 4
LAYERS = 2
D_FF = 128
E = D // HEADS
LR = 3e-3
RNG = np.random.default_rng(0)


# ---------------- autograd engine ----------------
class V:
    __slots__ = ("v", "g", "_in", "_back")

    def __init__(self, v, _in=(), _back=None):
        self.v = np.asarray(v, dtype=np.float64)
        self.g = None
        self._in = _in
        self._back = _back

    def backward(self):
        self.g = np.ones_like(self.v)
        order, seen = [], set()

        def build(n):
            if id(n) in seen:
                return
            seen.add(id(n))
            for i in n._in:
                build(i)
            order.append(n)
        build(self)
        for n in reversed(order):
            if n._back:
                n._back()


def _accum(t, g):
    g = np.asarray(g)
    while g.ndim > t.v.ndim:
        g = g.sum(axis=0)
    g = np.broadcast_to(g, t.v.shape)
    t.g = g if t.g is None else t.g + g


def add(a, b):
    r = V(a.v + b.v, (a, b))
    r._back = lambda: (_accum(a, r.g), _accum(b, r.g))
    return r


def smul(a, c):
    r = V(a.v * c, (a,))
    r._back = lambda: _accum(a, r.g * c)
    return r


def mul(a, b):
    r = V(a.v * b.v, (a, b))
    r._back = lambda: (_accum(a, r.g * b.v), _accum(b, r.g * a.v))
    return r


def matmul(a, b):
    r = V(np.matmul(a.v, b.v), (a, b))
    r._back = lambda: (_accum(a, np.matmul(r.g, np.swapaxes(b.v, -1, -2))),
                       _accum(b, np.matmul(np.swapaxes(a.v, -1, -2), r.g)))
    return r


def transpose(x, axes):
    r = V(np.transpose(x.v, axes), (x,))
    inv = np.argsort(axes)
    r._back = lambda: _accum(x, np.transpose(r.g, inv))
    return r


def reshape(x, shape):
    r = V(x.v.reshape(shape), (x,))
    r._back = lambda: _accum(x, r.g.reshape(x.v.shape))
    return r


def gelu(x):
    c = np.sqrt(2 / np.pi)
    t = np.tanh(c * (x.v + 0.044715 * x.v ** 3))
    r = V(0.5 * x.v * (1 + t), (x,))
    d = 0.5 * (1 + t) + 0.5 * x.v * (1 - t ** 2) * c * (1 + 3 * 0.044715 * x.v ** 2)
    r._back = lambda: _accum(x, r.g * d)
    return r


def layernorm(x, scale):
    mu = x.v.mean(-1, keepdims=True)
    var = x.v.var(-1, keepdims=True)
    inv = 1 / np.sqrt(var + 1e-5)
    y_unit = (x.v - mu) * inv
    r = V(y_unit * (1.0 + scale.v), (x, scale))

    def back():
        gy = r.g * (1.0 + scale.v)
        gx = inv * (gy - gy.mean(-1, keepdims=True)
                    - y_unit * (gy * y_unit).mean(-1, keepdims=True))
        _accum(x, gx)
        _accum(scale, (r.g * y_unit).sum(axis=tuple(range(r.g.ndim - 1))))
    r._back = back
    return r


def masked_softmax(x, mask):
    mx = x.v.max(-1, keepdims=True)
    e = np.exp(x.v - mx) * np.where(mask, 1.0, 0.0)
    p = e / e.sum(-1, keepdims=True)
    r = V(p, (x,))

    def back():
        fx = r.g * p - p * (r.g * p).sum(-1, keepdims=True)
        _accum(x, np.where(mask, fx, 0.0))
    r._back = back
    return r


def embed(ind, W):
    r = V(W.v[ind], (W,))

    def back():
        g = np.zeros_like(W.v)
        np.add.at(g, ind.ravel(), r.g.reshape(-1, D))
        _accum(W, g)
    r._back = back
    return r


def ce_loss(logit, y, mask):
    L = logit.v
    mx = L.max(-1, keepdims=True)
    e = np.exp(L - mx)
    p = e / e.sum(-1, keepdims=True)
    nll = -np.log(np.take_along_axis(p, y[..., None], -1)[..., 0] + 1e-12)
    num = mask.sum()
    r = V((nll * mask).sum() / num, (logit,))

    def back():
        one = np.zeros_like(L)
        nb, nt = y.shape
        one[np.arange(nb)[:, None], np.arange(nt)[None, :], y] = 1.0
        _accum(logit, (p - one) * (mask[..., None] / num))
    r._back = back
    return r


# ---------------- model ----------------
def runtime_leaves(p, cap):
    ps = {"tok": V(p["tok"]), "pos": V(p["pos"][:cap]), "out": V(p["out"]), "ly": []}
    for li in range(LAYERS):
        ps["ly"].append({k: V(p["ly"][li][k]) for k in p["ly"][li]})
    ps["scale_fixed"] = V(np.zeros(D))
    return ps


def fwd(ps, x, L, B, cap):
    h = add(embed(x, ps["tok"]), ps["pos"])
    causal = np.tril(np.ones((cap, cap), bool))[None, None]
    for li in range(LAYERS):
        ly = ps["ly"][li]
        hln = layernorm(h, ly["n1"])
        q = transpose(reshape(matmul(hln, ly["q"]), (B, cap, HEADS, E)), (0, 2, 1, 3))
        k = transpose(reshape(matmul(hln, ly["k"]), (B, cap, HEADS, E)), (0, 2, 3, 1))
        v = transpose(reshape(matmul(hln, ly["v"]), (B, cap, HEADS, E)), (0, 2, 1, 3))
        valid = (np.arange(cap)[None, None, None, :] < L[:, None, None, None])
        a = masked_softmax(smul(matmul(q, k), 1.0 / np.sqrt(E)), causal & valid)
        ctx = reshape(transpose(matmul(a, v), (0, 2, 1, 3)), (B, cap, D))
        h = add(h, matmul(ctx, ly["o"]))
        hln2 = layernorm(h, ly["n2"])
        h = add(h, matmul(gelu(matmul(hln2, ly["g1"])), ly["g2"]))
    logit = matmul(layernorm(h, ps["scale_fixed"]), ps["out"])
    y = np.concatenate([x[:, 1:], np.full((B, 1), 257)], 1)
    mask = (np.arange(cap)[None, :] < L[:, None]) & (np.arange(cap)[None, :] < (L[:, None] - 1))
    return ce_loss(logit, y, mask.astype(np.float64))


def init():
    W = lambda s: RNG.normal(0, 1 / np.sqrt(s[-1]), s).astype(np.float64)  # noqa: E731
    p = {"tok": W((VOCAB, D)), "pos": W((MAXL, D)), "out": W((D, VOCAB)), "ly": []}
    for _ in range(LAYERS):
        p["ly"].append(dict(q=W((D, D)), k=W((D, D)), v=W((D, D)), o=W((D, D)),
                            g1=W((D, D_FF)), g2=W((D_FF, D)),
                            n1=np.zeros(D), n2=np.zeros(D)))
    return p


def main():
    p = init()
    m = {"tok": np.zeros_like(p["tok"]), "pos": np.zeros_like(p["pos"]), "out": np.zeros_like(p["out"]), "ly": []}
    v = {"tok": np.zeros_like(p["tok"]), "pos": np.zeros_like(p["pos"]), "out": np.zeros_like(p["out"]), "ly": []}
    for li in range(LAYERS):
        m["ly"].append({k: np.zeros_like(p["ly"][li][k]) for k in p["ly"][li]})
        v["ly"].append({k: np.zeros_like(p["ly"][li][k]) for k in p["ly"][li]})

    print(f"poc numpy: N={N} cap={CAP} D={D} layers={LAYERS} steps={STEPS} batch={BATCH}", flush=True)
    t0 = time.time()
    b1, b2, eps = 0.9, 0.99, 1e-8
    for it in range(1, STEPS + 1):
        idx = RNG.integers(0, N, BATCH)
        x = XP[idx, :CAP]
        L = np.minimum(LP[idx], CAP)
        ps = runtime_leaves(p, CAP)
        loss = fwd(ps, x, L, BATCH, CAP)
        loss.backward()

        # adam update from leaf grads
        for k in ("tok", "pos", "out"):
            if k == "pos":
                m[k][:CAP] = b1 * m[k][:CAP] + (1 - b1) * ps[k].g
                v[k][:CAP] = b2 * v[k][:CAP] + (1 - b2) * ps[k].g ** 2
                mh = m[k][:CAP] / (1 - b1 ** it); vh = v[k][:CAP] / (1 - b2 ** it)
                p[k][:CAP] -= LR * mh / (np.sqrt(vh) + eps)
                continue
            g = ps[k].g
            m[k] = b1 * m[k] + (1 - b1) * g
            v[k] = b2 * v[k] + (1 - b2) * g ** 2
            mh = m[k] / (1 - b1 ** it); vh = v[k] / (1 - b2 ** it)
            p[k] -= LR * mh / (np.sqrt(vh) + eps)
        for li in range(LAYERS):
            for k in ("q", "k", "v", "o", "g1", "g2", "n1", "n2"):
                g = ps["ly"][li][k].g
                m["ly"][li][k] = b1 * m["ly"][li][k] + (1 - b1) * g
                v["ly"][li][k] = b2 * v["ly"][li][k] + (1 - b2) * g ** 2
                mh = m["ly"][li][k] / (1 - b1 ** it); vh = v["ly"][li][k] / (1 - b2 ** it)
                p["ly"][li][k] -= LR * mh / (np.sqrt(vh) + eps)

        if it == 1 or it % 50 == 0:
            print(f"step={it} loss={float(loss.v):.4f} t={time.time()-t0:.1f}s", flush=True)
    np.savez("poc_model.npz",
             tok=p["tok"], pos=p["pos"], out=p["out"],
             **{f"l{li}_{k}": p["ly"][li][k] for li in range(LAYERS) for k in p["ly"][li]})
    print("saved poc_model.npz", flush=True)
    print("SAMPLE: " + generate(p), flush=True)


# ---------------- inference-only sampling (no autograd) ----------------
def _ln(x, s):
    mu = x.mean(-1, keepdims=True)
    inv = 1 / np.sqrt(x.var(-1, keepdims=True) + 1e-5)
    return (x - mu) * inv * (1.0 + s)


def _gelu(x):
    c = np.sqrt(2 / np.pi)
    t = np.tanh(c * (x + 0.044715 * x ** 3))
    return 0.5 * x * (1 + t)


def infer_next_logits(p, ids, cap):
    T = len(ids)
    h = p["tok"][ids][None, :, :] + p["pos"][:T][None, :, :]
    for ly in p["ly"]:
        hln = _ln(h, ly["n1"])
        q = (hln @ ly["q"]).reshape(1, T, HEADS, E).transpose(0, 2, 1, 3)
        k = (hln @ ly["k"]).reshape(1, T, HEADS, E).transpose(0, 2, 3, 1)
        v = (hln @ ly["v"]).reshape(1, T, HEADS, E).transpose(0, 2, 1, 3)
        sc = (q @ k) / np.sqrt(E)
        sc = np.where(np.tril(np.ones((T, T), bool))[None, None], sc, -1e9)
        mx = sc.max(-1, keepdims=True)
        e = np.exp(sc - mx)
        a = e / e.sum(-1, keepdims=True)
        ctx = (a @ v).transpose(0, 2, 1, 3).reshape(1, T, D)
        h = h + ctx @ ly["o"]
        hln2 = _ln(h, ly["n2"])
        h = h + _gelu(hln2 @ ly["g1"]) @ ly["g2"]
    return (_ln(h, np.zeros(D)) @ p["out"])[0, T - 1]


def generate(p, seed=100, temp=0.8, n=80, cap=CAP):
    rng = np.random.default_rng(seed)
    ids = [256, 258]
    for _ in range(n):
        lg = infer_next_logits(p, ids, cap) / temp
        lg -= lg.max()
        pr = np.exp(lg); pr /= pr.sum()
        nxt = int(rng.choice(VOCAB, p=pr))
        ids.append(nxt)
        if nxt == 257:
            break
    out = bytearray()
    for t in ids:
        if t == 256:
            continue
        if t == 257:
            break
        if t == 258:
            out += b"<user>"
        elif t == 259:
            out += b"<asst>"
        else:
            out += bytes([t])
    return out.decode("utf-8", "replace")


if __name__ == "__main__":
    main()