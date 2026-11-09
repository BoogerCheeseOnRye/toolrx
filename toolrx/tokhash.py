"""Hashing tokenizer for the micro model.

Deliberately NO pretrained weights, NO vocab file, NO neural net.
Features are produced by hashing character n-grams + whole words into a
fixed-dimension vector. The "weights" of the model are therefore derived
entirely from the knowledge documents fed into the builder.
"""

import hashlib
import math
import re

_DIM = 4096
_WORD = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _ngrams(text, n):
    return (text[i : i + n] for i in range(len(text) - n + 1))


def features(text, dim=_DIM):
    """Map arbitrary text -> a sparse-ish fixed-dim hashed vector.

    Returns a plain dict {index: weight} so it stays memory-cheap and
    serializable. Weighting is TF * sublinear idf-style boost done in the
    builder; here we just count ASCII-normalized keys.
    """
    text = (text or "").lower()
    keys = []
    keys.extend(_WORD.findall(text))
    for n in (3, 4):
        keys.extend(_ngrams(text, n))

    counts = {}
    for k in keys:
        h = int(hashlib.blake2b(k.encode("utf-8"), digest_size=8).hexdigest(), 16)
        counts[h % dim] = counts.get(h % dim, 0) + 1
    return counts


def l2(vect):
    """L2-normalize a {index: weight} vector in place, return its norm."""
    norm = math.sqrt(sum(w * w for w in vect.values())) or 1.0
    for k in list(vect.keys()):
        vect[k] /= norm
    return vect


def dot(a, b):
    sa, sb = (a, b) if len(a) <= len(b) else (b, a)
    return sum(v * sb.get(k, 0.0) for k, v in sa.items())


def embed(text, dim=_DIM, idf=None):
    """Convenience: features -> weighted -> L2-normalized vector."""
    v = features(text, dim)
    if idf:
        for k in v:
            v[k] *= idf.get(k, 1.0)
    l2(v)
    return v