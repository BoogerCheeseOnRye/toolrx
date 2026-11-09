"""Router: pick which tool a query should call, and decide its arguments.

At runtime the query is embedded with the SAME hashing tokenizer used at
build time, then scored against each tool's centroid vector by cosine
similarity (dot product, since vectors are L2-normalized). The tool with
the highest score wins; a confidence of 0 means the query didn't resemble
any known tool.
"""

import json
import os
import re

from tokhash import embed, dot, _DIM

_WORDISH = re.compile(r"[A-Za-z0-9./_\-~]+")

_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}


def _ints_in(query):
    out = [int(x) for x in re.findall(r"-?\d+", query)]
    for tok in _WORDISH.findall(query.lower()):
        if tok in _NUM_WORDS:
            out.append(_NUM_WORDS[tok])
    return out


def load(model_path):
    with open(model_path, encoding="utf-8") as f:
        m = json.load(f)
    m["centroids"] = {
        name: {int(k): float(v) for k, v in c.items()}
        for name, c in m["centroids"].items()
    }
    m["idf"] = {int(k): float(v) for k, v in m["idf"].items()}
    m["_path"] = model_path
    return m


def _pick_path(query):
    matches = _WORDISH.findall(query)
    for m in matches:
        if m in (".", ".."):
            return m
    for m in matches:
        if ("/" in m or m.endswith((".txt", ".md", ".json", ".log", ".html", ".htm"))
                or "." in m):
            return m
    return None


def _path_candidates(query):
    """All path-ish tokens, in order, for assigning to string params."""
    return [m for m in _WORDISH.findall(query)
            if ("/" in m or "." in m or m in (".", ".."))]


def extract_args(query, param_specs, host_allowlist=None):
    args = {}
    host_param = next((p for p in param_specs if p.get("type") == "string"
                       and p.get("name") == "host"), None)
    if host_param:
        cand = _extract_host(query, host_allowlist)
        if cand:
            args["host"] = cand
    string_params = [p for p in param_specs
                     if p.get("type") == "string" and p.get("name") != "host"
                     and p.get("name") in ("path", "path_a", "path_b", "file", "dir", "target")]
    for p in param_specs:
        name, ptype = p["name"], p["type"]
        if name == "name" and ptype == "string":
            mname = _extract_module_name(query)
            if mname is not None:
                args[name] = mname
        if name == "tool" and ptype == "string":
            mtool = _extract_module_tool(query)
            if mtool is not None:
                args[name] = mtool
    cands = _path_candidates(query)[::-1]  # pop from end
    for p in reversed(string_params):     # assign the LAST path param first
        name = p["name"]
        if name in args:
            continue
        if cands:
            args[name] = cands.pop()
        elif "default" in p:
            args[name] = p["default"]
    # remaining non-path string params (content, mode, ...) -> defaults
    for p in param_specs:
        name, ptype = p["name"], p["type"]
        if ptype == "string" and name not in args and name not in ("host",) and "default" in p:
            args.setdefault(name, p["default"])
    for p in param_specs:
        name, ptype = p["name"], p["type"]
        if name == "interval" and ptype == "int":
            iv = _extract_interval(query)
            if iv is not None:
                args[name] = iv
            elif name not in args and "default" in p:
                args[name] = p["default"]
        elif name == "duration" and ptype == "int":
            du = _extract_duration(query)
            if du is not None:
                args[name] = du
        elif ptype == "int_list":
            nums = _ints_in(query)
            if nums:
                args[name] = nums
        if name not in args and "default" in p:
            args.setdefault(name, p["default"])
    _extract_content(query, param_specs, args)
    return args


def _extract_content(query, param_specs, args):
    """For a 'content' param, take everything after the first ':' or after the
    extracted path token (chat path; the UI form is the reliable one)."""
    if not any(p.get("name") == "content" for p in param_specs):
        return
    if "content" in args and args.get("content"):
        return
    q = query
    if ":" in q:
        args["content"] = q.split(":", 1)[1].strip()
        return
    path = args.get("path")
    if path:
        q = q.replace(path, "", 1)
    # strip leading edit verbs / filler
    q = re.sub(r"^(write|create|edit|save|append|update|set|make|add|change|put|insert|with|to|in|the|a|an|for|contents?|as)\b\s*",
               "", q, count=6)
    q = q.strip(" :")
    args["content"] = q


def _extract_interval(query):
    """Pull the number from 'every 5 seconds' / 'each 10s' / 'every 30'."""
    m = re.search(r"(?:every|each|per)\s+(\d+)", query)
    if not m:
        m = re.search(r"(\d+)\s*(?:seconds?|secs?|\bs\b)", query)
    if m:
        return int(m.group(1))
    return None


def _extract_duration(query):
    """Pull 'for N minutes/seconds/min/s' -> seconds (duration)."""
    m = re.search(r"(?:for|during|over)\s+(\d+)\s*(minutes?|mins?|seconds?|secs?)", query)
    if not m:
        m = re.search(r"(\d+)\s*(minutes?|mins?)", query)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        return n * 60 if unit.startswith("min") else n
    return None


def _extract_module_name(query):
    """Map a tracker intent to a known module name (memory/disk/uptime)."""
    low = query.lower()
    for cand in ("memory", "disk", "uptime"):
        if cand in low:
            return cand
    return None


def _extract_module_tool(query):
    """Map 'ping / disk / memory / processes / uptime ...' to a read-only tool."""
    low = query.lower()
    if "ping" in low:
        return "net.ping"
    if "disk" in low:
        return "sys.disk"
    if "memory" in low or "ram" in low:
        return "sys.mem_status"
    if "process" in low:
        return "sys.processes"
    if "uptime" in low or "up time" in low:
        return "sys.uptime"
    if "interface" in low or "netw" in low:
        return "sys.ifconfig"
    if "port" in low or "listen" in low:
        return "sys.netstat"
    return None


def _extract_host(query, host_allowlist=None):
    host_allowlist = host_allowlist or []
    toks = [m for m in _WORDISH.findall(query) if "." in m or m.isalpha()]
    for t in toks:
        if t in host_allowlist:
            return t
    # "local machine" phrasing -> the loopback host (only if allowlisted)
    if any(t in ("local", "localhost") for t in toks) and "localhost" in host_allowlist:
        return "localhost"
    # fallback: last alphabetic/path token (executor enforces the allowlist)
    return toks[-1] if toks else None


def route(query, model, top_k=1, host_allowlist=None):
    qv = embed(query, model.get("dim", _DIM), model["idf"])
    scores = {name: dot(qv, c) for name, c in model["centroids"].items()}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_name, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    tool = model["tools"][0]["name"]
    for t in model["tools"]:
        if t["name"] == best_name:
            tool = t
            break
    return {
        "query": query,
        "tool": best_name,
        "confidence": round(best_score, 4),
        "margin": round(best_score - runner_up, 4),
        "scores": {n: round(s, 4) for n, s in dict(ranked).items()},
        "args": extract_args(query, tool["params"], host_allowlist),
    }


def main():
    model = load("micro_model.json")
    for q in [
        "add five and seven",
        "read my notes.txt",
        "how much memory is free on this machine",
        "list the files in the project folder",
    ]:
        r = route(q, model)
        print(f"\nQ: {q!r}\n   -> {r['tool']}  conf={r['confidence']} args={r['args']}")


if __name__ == "__main__":
    main()