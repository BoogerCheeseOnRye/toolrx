"""The one source of numeric envelopes for the deterministic path.

`toolrx/limits.json` is checked in once. Python reads it here; the browser loads
`toolrx/web/limits.js`, which `toolrx/gen_limits.py` generates from the same
JSON. No runtime may carry its own copy of these numbers.

Ranges (the human-facing contract):
  singleChars      1–100,000   one routed request
  planChars        2,000–100,000  one plan
  planSteps        2–200
  blockBytes       256–64,000
  stepMs           250–30,000
  planMs           250–600,000
  projectFileBytes 1,024–2,097,152
  projectBytes     16,384–8,388,608
  projectFiles     8–256
  buildMs          250–30,000
  readFileBytes    256–1,000,000
  readTotalBytes   1,000–2,000,000
  contextBytes     256–65,536
  undoDepth        1–64
  outputChars      1,000–100,000
  bundleBytes      65,536–8,388,608
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "limits.json")

_RANGES = {
    "singleChars": (1, 100_000),
    "planChars": (2_000, 100_000),
    "planSteps": (2, 200),
    "blockBytes": (256, 64_000),
    "stepMs": (250, 30_000),
    "planMs": (250, 600_000),
    "projectFileBytes": (1_024, 2_097_152),
    "projectBytes": (16_384, 8_388_608),
    "projectFiles": (8, 256),
    "buildMs": (250, 30_000),
    "readFileBytes": (256, 1_000_000),
    "readTotalBytes": (1_000, 2_000_000),
    "contextBytes": (256, 65_536),
    "undoDepth": (1, 64),
    "outputChars": (1_000, 100_000),
    "bundleBytes": (65_536, 8_388_608),
}


def load(path=PATH):
    """Read and validate the active envelope."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if int(data.get("version", 0)) != 1:
        raise ValueError("unsupported limits version: %r" % data.get("version"))
    for key, (low, high) in _RANGES.items():
        if key not in data:
            raise ValueError("limits.json is missing %s" % key)
        value = int(data[key])
        if value < low or value > high:
            raise ValueError("%s=%s is outside %s–%s" % (key, value, low, high))
    return data


def get(key):
    return load()[key]


def table():
    """A stable, human-readable table used by `help` and the tests."""
    data = load()
    rows = ["limits · source toolrx/limits.json (version %s)" % data["version"]]
    for key in _RANGES:
        low, high = _RANGES[key]
        rows.append("  %-16s %-9s range %s–%s" % (key, data[key], low, high))
    return "\n".join(rows)
