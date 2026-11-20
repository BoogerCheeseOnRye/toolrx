"""The one source of numeric envelopes for the deterministic path.

`toolrx/limits.json` is checked in once. Python reads it here; the browser loads
`toolrx/web/limits.js`, which `toolrx/gen_limits.py` generates from the same
JSON. No runtime may carry its own copy of these numbers.

Ranges (the human-facing contract):
  singleChars      1–100,000   one routed request
  planChars        2,000–100,000  one plan
  planSteps        2–200
  planBuildBytes   4,096–1,048,576  estimated bytes one build writes
  planEditBytes    256–65,536  estimated bytes one edit writes
  planVariantBytes 1,024–32,768  stored compacted-plan variant
  thinkChars       256–32,000  thinking input characters
  thinkGoals       2–32  goals listed per thinking run
  thinkRules       4–32  rules evaluated per critique
  explainChars     512–32,000  one project or plan explanation
  explainFiles     2–128  files listed per explanation
  explainEdits     1–32  recent edits listed per explanation
  computeChars     16–100,000  one pure-compute script
  computeStatements 1–200  statements in one script
  computeOps       8–10,000  evaluated nodes in one script
  computeVars      1–64  local variables in one script
  computeMs        1–5,000  wall budget for one script
  computeResultChars 16–100,000  rendered result of one script
  repairPasses     1–5  accepted repair passes per failed plan
  traceBytes       256–16,384  stored reasoning trace
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
  contextKeep      1–16  session rows kept raw by compaction
  contextAutoAt    50–100  automatic compaction trigger percent
  contextSummary   1–20  summary lines per compacted entry
  undoDepth        1–64
  outputChars      1,000–100,000
  bundleBytes      65,536–8,388,608
  extractChars     1,000–32,000  extractor input
  extractItems     10–500  extractor output lines
  diffLines        50–2,000  diff lines per side
  conversationTurns 2–64  stored conversation turns
  conversationBytes 512–65,536  serialized conversation state
  journalEntries   4–128  decisions kept per project
  journalBytes     512–65,536  serialized project journal
  journalText      80–2,000  one journal entry
  styleChars       80–8,000  response wrapper added to one exact result
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "limits.json")

_RANGES = {
    "singleChars": (1, 100_000),
    "planChars": (2_000, 100_000),
    "planSteps": (2, 200),
    "planBuildBytes": (4_096, 1_048_576),
    "planEditBytes": (256, 65_536),
    "planVariantBytes": (1_024, 32_768),
    "thinkChars": (256, 32_000),
    "thinkGoals": (2, 32),
    "thinkRules": (4, 32),
    "explainChars": (512, 32_000),
    "explainFiles": (2, 128),
    "explainEdits": (1, 32),
    "computeChars": (16, 100_000),
    "computeStatements": (1, 200),
    "computeOps": (8, 10_000),
    "computeVars": (1, 64),
    "computeMs": (1, 5_000),
    "computeResultChars": (16, 100_000),
    "repairPasses": (1, 5),
    "traceBytes": (256, 16_384),
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
    "contextKeep": (1, 16),
    "contextAutoAt": (50, 100),
    "contextSummary": (1, 20),
    "undoDepth": (1, 64),
    "outputChars": (1_000, 100_000),
    "bundleBytes": (65_536, 8_388_608),
    "extractChars": (1_000, 32_000),
    "extractItems": (10, 500),
    "diffLines": (50, 2_000),
    "conversationTurns": (2, 64),
    "conversationBytes": (512, 65_536),
    "journalEntries": (4, 128),
    "journalBytes": (512, 65_536),
    "journalText": (80, 2_000),
    "styleChars": (80, 8_000),
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
