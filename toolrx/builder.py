"""Builder: derives the micro model's weights from knowledge documents.

The "training data" is ordinary .md/.txt files. The output is a small
JSON model file containing one normalized centroid vector per tool plus
global idf weights. This is the entire neural-net replacement: no PyTorch,
no GGUF, no pretrained weights — just hashed text stats.
"""

import json
import math
import os
import sys

from tokhash import features, l2, _DIM

MODEL_PATH = "micro_model.json"


def count_docs(catalog, base):
    """Return {tool_name: [ {index: count}, ... ]} plus aggregate df."""
    per_tool = {}
    df = {}  # document frequency per feature index
    n_docs = 0
    for tool in catalog["tools"]:
        vecs = []
        for rel in tool["knowledge"]:
            path = os.path.join(base, rel)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            v = features(text, catalog.get("dim", _DIM))
            seen = set()
            for k in v:
                seen.add(k)
                # both document-frequency (for idf) and term-frequency kept
            for k in seen:
                df[k] = df.get(k, 0) + 1
            vecs.append(v)
            n_docs += 1
        per_tool[tool["name"]] = vecs
    return per_tool, df, n_docs


def build(catalog_path="catalog.json"):
    base = os.path.dirname(os.path.abspath(catalog_path))
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)
    if not isinstance(catalog, dict) or "tools" not in catalog:
        # tolerate a top-level list via wrapper
        catalog = {"dim": _DIM, "tools": catalog}

    dim = catalog.get("dim", _DIM)
    per_tool, df, n_docs = count_docs(catalog, base)

    # idf: log(N / df) smoothed
    idf = {k: math.log(n_docs / (1 + v)) + 1.0 for k, v in df.items()}

    centroids = {}
    for name, vecs in per_tool.items():
        agg = {}
        for v in vecs:
            for k, c in v.items():
                agg[k] = agg.get(k, 0) + c * idf.get(k, 1.0)
        l2(agg)
        centroids[name] = agg

    # serialize compactly (drop near-zero entries)
    model = {
        "dim": dim,
        "idf": {str(k): round(v, 5) for k, v in idf.items()},
        "centroids": {
            name: {str(k): round(v, 4) for k, v in c.items()}
            for name, c in centroids.items()
        },
        "tools": [
            {"name": t["name"], "params": t["params"], "impl": t["impl"]}
            for t in catalog["tools"]
        ],
    }
    out = os.path.join(base, MODEL_PATH)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(model, f, separators=(",", ":"))
    sizes = {name: len(c) for name, c in centroids.items()}
    print(f"built {out} ({os.path.getsize(out)//1024} KB)")
    print(f"features per tool centroid: {sizes}")
    return out


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "catalog.json")