"""pipeline.process(): the one code path from raw query to result.

Order enforced here:
  1. Sanitize (SecurityPolicy)  -> deny on ANY failure (default-deny).
  2. Route (micro model)        -> pick tool + extract raw args.
  3. Execute (fail-closed)      -> executor re-validates args & tool.

Returns a dict with keys: blocked, reason, decision, result.
"""

import json
import os

import router
import executor
import longform
import security
import blocks

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "micro_model.json")

_policy = None
_model = None


def policy():
    global _policy
    if _policy is None:
        _policy = security.SecurityPolicy.load()
    return _policy


def model():
    global _model
    if _model is None:
        _model = router.load(MODEL)
    return _model


def _run_step(clean, pol, m):
    """Route and execute one already-sanitized step."""
    decision = router.route(clean, m, host_allowlist=pol.allowed_hosts)
    # confidence gate: refuse when the router is unsure (avoids misfires)
    if decision["confidence"] <= 0.12 and decision["margin"] < 0.01:
        reason = "no confident tool (low confidence / no margin)"
        return {"blocked": True, "reason": reason,
                "decision": decision, "result": {"ok": False, "reason": reason}}

    res = executor.execute(decision, m["tools"], pol)
    if res.get("blocked"):  # execution-time security refusal (e.g. bad path)
        return {"blocked": True, "reason": res.get("reason"),
                "decision": decision, "result": res}
    return {"blocked": False, "reason": None, "decision": decision, "result": res}


def _result_text(out):
    res = out.get("result") or {}
    value = res.get("result") if res.get("ok") else res.get("reason")
    if value is None:
        value = "failed"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def process_plan(clean, pol, info):
    """Execute an ordered plan. Stop at the first blocked or failed step."""
    m = model()
    steps = info["steps"]
    outputs = []
    lines = []
    for i, step in enumerate(steps):
        ok, step_clean, reason = pol.sanitize(step)
        if not ok:
            out = {"blocked": True, "reason": reason, "decision": {},
                   "result": {"ok": False, "reason": reason}}
        else:
            out = _run_step(step_clean, pol, m)
        outputs.append({
            "query": step,
            "blocked": out.get("blocked"),
            "reason": out.get("reason"),
            "decision": out.get("decision") or {},
            "result": out.get("result") or {},
        })
        lines.append(f"{i + 1}. {_result_text(out)}")
        if out.get("blocked") or not (out.get("result") or {}).get("ok"):
            reason = out.get("reason") or _result_text(out)
            return {
                "blocked": True,
                "reason": f"step {i + 1}: {reason}",
                "decision": {"tool": "plan", "confidence": 1.0, "margin": 1.0,
                             "steps": [o["query"] for o in outputs]},
                "result": {"ok": False, "tool": "plan", "result": "\n".join(lines),
                           "steps": outputs},
            }
    return {
        "blocked": False,
        "reason": None,
        "decision": {"tool": "plan", "confidence": 1.0, "margin": 1.0,
                     "steps": [o["query"] for o in outputs]},
        "result": {"ok": True, "tool": "plan", "result": "\n".join(lines),
                   "steps": outputs},
    }


def process(query):
    pol = policy()
    # A "write the following into <file>:" request carries user-authored
    # content that must not be lowercased, split into a plan, or passed
    # through the word allowlist. Capture it verbatim first, validate the
    # path and safety properties, then hand the pending edit to the same
    # confirm-gated executor used by every other write.
    if blocks.detect(query):
        block = blocks.capture(query, pol, pol.max_plan_len)
        if not block["ok"]:
            return {"blocked": True, "reason": block["reason"],
                    "decision": {}, "result": {"ok": False,
                                                "reason": block["reason"]}}
        decision = {"tool": "file.edit", "confidence": 1.0, "margin": 1.0,
                    "args": {"path": block["path"], "content": block["content"],
                             "mode": "replace"}}
        res = executor.execute(decision, model()["tools"], pol)
        if res.get("blocked"):
            return {"blocked": True, "reason": res.get("reason"),
                    "decision": decision, "result": res}
        return {"blocked": False, "reason": None,
                "decision": decision, "result": res}

    # `;` and `->` are plan separators but shell metacharacters. Rewrite them
    # to newlines before sanitizing, then check every resulting step again.
    ok, clean, reason = pol.sanitize_plan(longform.normalize_connectors(query))
    if not ok:
        return {"blocked": True, "reason": reason,
                "decision": {}, "result": {"ok": False, "reason": reason}}

    if not longform.is_plan(clean, pol.max_len):
        return _run_step(clean, pol, model())

    info = longform.split_info(clean, max_steps=pol.max_plan_steps,
                               max_step=pol.max_len)
    if info["overLimit"]:
        reason = f"plan too long ({info['total']} > {pol.max_plan_steps} steps)"
        return {"blocked": True, "reason": reason,
                "decision": {}, "result": {"ok": False, "reason": reason}}

    # More than one step (or an over-long single route) executes as a plan.
    if len(info["steps"]) > 1 or len(clean) > pol.max_len:
        return process_plan(clean, pol, info)

    return _run_step(clean, pol, model())


def reload():
    """Force reload of policy/model (e.g. after editing knowledge/policy)."""
    global _policy, _model
    _policy, _model = None, None


def process_for_tool(tool, args):
    """Directly run a specific tool with given args (structured endpoints that
    bypass routing/sanitize because the payload is already safe by
    construction, e.g. the safe-DSL net config form). Still runs through the
    executor's default-deny allowlist and arg checks."""
    m = model()
    decision = {"tool": tool, "args": args, "confidence": 1.0, "margin": 1.0}
    res = executor.execute(decision, m["tools"], policy())
    if res.get("blocked"):
        return {"blocked": True, "reason": res.get("reason"),
                "decision": decision, "result": res}
    return {"blocked": False, "reason": None, "decision": decision, "result": res}