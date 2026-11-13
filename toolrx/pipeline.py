"""pipeline.process(): the one code path from raw query to result.

Order enforced here:
  1. Sanitize (SecurityPolicy)  -> deny on ANY failure (default-deny).
  2. Route (micro model)        -> pick tool + extract raw args.
  3. Execute (fail-closed)      -> executor re-validates args & tool.

Returns a dict with keys: blocked, reason, decision, result.
"""

import json
import os
import time

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


def _ms_since(started):
    return max(0, round((time.monotonic() - started) * 1000))


def _plan_report(clean, pol, outputs, started):
    elapsed = _ms_since(started)
    step_cap = getattr(pol, "max_step_ms", 4000)
    plan_cap = getattr(pol, "max_plan_ms", 160000)
    errors = sum(1 for o in outputs
                 if o.get("blocked") or not (o.get("result") or {}).get("ok"))
    return {
        "chars": len(clean),
        "steps": len(outputs),
        "errors": errors,
        "ms": elapsed,
        "ok": errors == 0 and elapsed <= plan_cap,
        "budget": {
            "stepMs": step_cap,
            "planMs": plan_cap,
            "remainingMs": max(0, plan_cap - elapsed),
        },
    }


def _plan_return(blocked, reason, outputs, lines, report):
    return {
        "blocked": blocked,
        "reason": reason,
        "decision": {"tool": "plan", "confidence": 1.0, "margin": 1.0,
                     "steps": [o["query"] for o in outputs]},
        "result": {"ok": not blocked, "tool": "plan",
                   "result": "\n".join(lines), "steps": outputs},
        "report": report,
    }


def process_plan(clean, pol, info):
    """Execute an ordered plan. Stop at the first blocked or failed step."""
    m = model()
    steps = info["steps"]
    outputs = []
    lines = []
    started = time.monotonic()
    step_cap = getattr(pol, "max_step_ms", 4000)
    plan_cap = getattr(pol, "max_plan_ms", 160000)
    for i, step in enumerate(steps):
        if _ms_since(started) >= plan_cap:
            reason = (f"plan wall budget {plan_cap} ms exhausted before step "
                      f"{i + 1}")
            outputs.append({
                "query": step, "blocked": True, "reason": reason,
                "decision": {}, "result": {"ok": False, "reason": reason},
                "ms": _ms_since(started),
            })
            lines.append(f"{i + 1}. {reason}")
            return _plan_return(True, f"step {i + 1}: {reason}", outputs, lines,
                                _plan_report(clean, pol, outputs, started))
        step_started = time.monotonic()
        ok, step_clean, reason = pol.sanitize(step)
        if not ok:
            out = {"blocked": True, "reason": reason, "decision": {},
                   "result": {"ok": False, "reason": reason}}
        else:
            out = _run_step(step_clean, pol, m)
        step_ms = _ms_since(step_started)
        outputs.append({
            "query": step,
            "blocked": out.get("blocked"),
            "reason": out.get("reason"),
            "decision": out.get("decision") or {},
            "result": out.get("result") or {},
            "ms": step_ms,
        })
        lines.append(f"{i + 1}. {_result_text(out)}")
        if step_ms > step_cap:
            reason = f"step timed out after {step_ms} ms (step budget {step_cap} ms)"
            outputs[-1]["blocked"] = True
            outputs[-1]["reason"] = reason
            outputs[-1]["result"] = {"ok": False, "reason": reason}
            lines[-1] = f"{i + 1}. {reason}"
            return _plan_return(True, f"step {i + 1}: {reason}", outputs, lines,
                                _plan_report(clean, pol, outputs, started))
        if out.get("blocked") or not (out.get("result") or {}).get("ok"):
            reason = out.get("reason") or _result_text(out)
            return _plan_return(True, f"step {i + 1}: {reason}", outputs, lines,
                                _plan_report(clean, pol, outputs, started))
    return _plan_return(False, None, outputs, lines,
                        _plan_report(clean, pol, outputs, started))


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