"""pipeline.process(): the one code path from raw query to result.

Order enforced here:
  1. Sanitize (SecurityPolicy)  -> deny on ANY failure (default-deny).
  2. Route (micro model)        -> pick tool + extract raw args.
  3. Execute (fail-closed)      -> executor re-validates args & tool.

Returns a dict with keys: blocked, reason, decision, result.
"""

import os

import router
import executor
import security

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


def process(query):
    pol = policy()
    ok, clean, reason = pol.sanitize(query)
    if not ok:
        return {"blocked": True, "reason": reason,
                "decision": {}, "result": {"ok": False, "reason": reason}}

    m = model()
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