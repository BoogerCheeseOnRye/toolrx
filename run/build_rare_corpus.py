#!/usr/bin/env python3
"""build_rare_corpus.py — augment the full corpus with NEW, distinct examples
for the gate's rare classes (calculate, question, git_status, search_files).
The full corpus has only 17 calculate / 12 question / 15 git examples yet the
gate scores them at 8-10 samples each, so the model can't learn them. These are
genuinely new (not re-tiled — tiling collapsed v45): each generated from the
provider's exact record schema {query,tools,answers,reasoning,system} with
distinct queries/arguments. Merge into train_rare_enriched.jsonl.
"""
import json, os, random
from collections import Counter, OrderedDict


def t(name, desc, props, req):
    return {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}


def gen():
    rng = random.Random(777)
    out = []
    calc = lambda: t("calculate", "Evaluate arithmetic.",
                     {"expression": {"type": "string", "description": "e.g. 17*23"}},
                     ["expression"])
    qtool = lambda: t("question", "Ask clarifying questions.",
                      {"questions": {"type": "array", "items": {"type": "object",
                          "properties": {"header": {"type": "string"},
                                         "question": {"type": "string"}},
                          "required": ["header", "question"]}}}, ["questions"])
    git = lambda: t("git_status", "Show git working-tree status.", {}, [])
    search = lambda: t("search_files", "Search files for a pattern.",
                       {"path": {"type": "string"}, "pattern": {"type": "string"}},
                       ["path", "pattern"])
    ops = [lambda a, b: f"{a}+{b}", lambda a, b: f"{a}-{b}", lambda a, b: f"{a}*{b}",
           lambda a, b: f"{a}**{b}", lambda a, b: f"{a}//{b}", lambda a, b: f"{a}%{b}"]
    for _ in range(60):
        a, b = rng.randint(2, 300), rng.randint(2, 50)
        e = rng.choice(ops)(a, b)
        out.append({"query": "What is %s?" % e, "tools": [calc()],
                    "answers": [{"name": "calculate", "arguments": {"expression": e}}],
                    "reasoning": "", "system": ""})
    for q in ["What commit message do you want to use?", "Which host should I check?",
              "I see several files mentioned - which one should I read?",
              "In which directory should I run the command?",
              "Which branch should I commit to?"]:
        for _ in range(3):
            out.append({"query": "Read me the right file. " + q, "tools": [qtool()],
                        "answers": [{"name": "question", "arguments": {"questions": [
                            {"header": q[:18].strip(), "question": q}]}}],
                        "reasoning": "", "system": ""})
    for msg in ["add rate limiting", "fix the parser", "refactor the router", "update the docs",
                "add tests", "tune the gate", "bump the version"]:
        out.append({"query": "Check the git status, then commit everything with message '%s'." % msg,
                    "tools": [git()], "answers": [{"name": "git_status", "arguments": {}}],
                    "reasoning": "", "system": ""})
    for path in ["/src/main.py", "/src/agent.py", "/config/settings.json", "/run/gate_harness.py",
                 "/app/router.py", "/lib/tokenizer.py", "/docs/README.md", "/test/smoke.py"]:
        for pat in ["def agent", "import json", "TODO", "FIXME", "def main", "class Router",
                    "@app.route", "except"][:4]:
            out.append({"query": "Search for '%s' in %s." % (pat, path), "tools": [search()],
                        "answers": [{"name": "search_files", "arguments": {"path": path, "pattern": pat}}],
                        "reasoning": "", "system": ""})
    return out


def main(src, dst):
    full = [json.loads(l) for l in open(src) if l.strip()]
    rare = gen()
    seen = {json.dumps([r.get("query"), r.get("answers")], sort_keys=True) for r in full}
    new = [r for r in rare
           if json.dumps([r.get("query"), r.get("answers")], sort_keys=True) not in seen]
    enc = full + new
    with open(dst, "w") as fh:
        for r in enc:
            fh.write(json.dumps(r) + "\n")
    print("full:", len(full), "| new rare:", len(new), "| enriched:", len(enc))
    print("first-class counts:", dict(Counter(
        (r.get("answers") or [{}])[0].get("name", "?") for r in enc)))


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_full_v2.jsonl"),
         sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_rare_enriched.jsonl"))
