"""planner.plan(): the "chain of thought" / reasoning trace.

Purely a verification aid. Given raw input text it produces an ordered,
deterministic list of steps (the fake reasoning) and ONE proposed action.

CRITICAL: this NEVER executes anything. The proposed action is returned
as a description only; a human must run it via a separate gated call.
There is no autonomous loop, no self-execution, no recurrence.
"""

import json
import os

import router
import security

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "micro_model.json")
CATALOG = os.path.join(HERE, "catalog.json")

# Tool name prefixes that change state. Currently only the diff tool exists
# and it is read-only, but the flagging stays for forward safety.
_MUTATING_PREFIXES = ("config.apply", "write.", "exec.")


def _knowledge_snippet(rels, limit=170):
    out = []
    for rel in rels:
        p = os.path.join(HERE, rel)
        if os.path.exists(p):
            out.append(open(p, encoding="utf-8").read().strip())
    return (" ".join(out))[:limit]


def _knowledge_for(tool_name):
    try:
        with open(CATALOG, encoding="utf-8") as f:
            cat = json.load(f)
        for t in cat["tools"]:
            if t["name"] == tool_name:
                return t.get("knowledge", [])
    except (OSError, KeyError, ValueError):
        pass
    return []


def plan(query):
    pol = security.SecurityPolicy.load()
    trace = []

    # step 1: input + security allowlist
    ok, clean, reason = pol.sanitize(query)
    trace.append({
        "step": 1, "kind": "input",
        "note": (f"normalized and allowlist-checked against {len(pol.vocab)} "
                 f"whitelisted words")
        if ok else f"DENIED: {reason}",
        "ok": ok,
    })
    if not ok:
        return {"blocked": True, "reason": reason, "query": clean,
                "trace": trace, "proposed_action": None}

    # step 2: routing (the micro model)
    m = router.load(MODEL)
    dec = router.route(clean, m, host_allowlist=pol.allowed_hosts)
    top_scores = ", ".join(
        f"{k}={round(v, 3)}" for k, v in list(dec["scores"].items())[:3])
    trace.append({
        "step": 2, "kind": "route",
        "note": (f"closest tool={dec['tool']} (conf={dec['confidence']}, "
                 f"margin={dec['margin']}); scores: {top_scores}"),
        "ok": True,
    })

    if dec["confidence"] <= 0.12 and dec["margin"] < 0.01:
        reason = "no confident tool (low confidence / no margin)"
        trace.append({"step": 3, "kind": "gate", "note": reason, "ok": False})
        return {"blocked": True, "reason": reason, "query": clean,
                "trace": trace, "proposed_action": None}

    # step 3: rationale from the tool's knowledge doc
    tool = next((t for t in m["tools"] if t["name"] == dec["tool"]), None)
    kw = _knowledge_snippet(_knowledge_for(dec["tool"]))
    trace.append({"step": 3, "kind": "rationale",
                  "note": ("why: " + kw) if kw else f"why: {dec['tool']}",
                  "ok": True})

    # step 4: mutating vs read-only policy flag
    mutates = dec["tool"].startswith(_MUTATING_PREFIXES)
    trace.append({
        "step": 4, "kind": "policy",
        "note": (f"tool {dec['tool']} is READ-ONLY; safe to run manually"
                 if not mutates else
                 f"tool {dec['tool']} MUTATES STATE; requires explicit manual apply"),
        "ok": True,
    })

    return {
        "blocked": False, "reason": None, "query": clean,
        "trace": trace,
        "decision": dec,
        "proposed_action": {
            "tool": dec["tool"], "args": dec["args"],
            "dry_run": True, "mutates": mutates,
            "gated": True,  # requires a human to run it
        },
    }