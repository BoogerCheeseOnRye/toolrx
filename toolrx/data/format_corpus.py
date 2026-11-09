#!/usr/bin/env python3
"""Convert opencode corpus into TRAINABLE turn-level examples.

Each session's message stream is cut into many short examples:
  context = up to K prior messages (user + assistant)
  target  = the next non-empty assistant message (text or tool call)
Content lengths are capped so examples fit a small model's context window.

Emission: JSONL of {"messages":[{"role":..,"content":..},...]}. Local-only.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "corpus.jsonl")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "training.jsonl")

MAX_TOOL_OUT = 3000      # chars per tool output
MAX_CTX_MSGS = 12        # context messages kept before target
MAX_CTX_CHARS = 16000    # context budget (chars)
MAX_TARGET_CHARS = 4000  # target budget (chars)


def part_text(p):
    if p.get("type") == "text":
        return p.get("text") or ""
    if p.get("type") == "tool":
        out = p.get("output") or ""
        if not isinstance(out, str):
            out = json.dumps(out)
        if len(out) > MAX_TOOL_OUT:
            out = out[:MAX_TOOL_OUT] + f"...<truncated {len(out)}>"
        inp = p.get("input") or ""
        if not isinstance(inp, str):
            inp = json.dumps(inp)
        return f"[tool:{p.get('tool')} input:{inp} -> output:{out}]"
    return ""


def msg_content(parts):
    return "\n".join(s for s in (part_text(p) for p in parts) if s)


def main():
    n_ex = n_tool = 0
    with open(IN) as fi, open(OUT, "w") as fo:
        for line in fi:
            rec = json.loads(line)
            stream = [(m.get("role"), msg_content(m.get("parts", [])))
                      for m in rec["stream"]]
            stream = [(r, c) for r, c in stream if c]  # drop empties

            # Emit an example before every assistant message (the target),
            # conditioned on a sliding window of prior user+assistant messages.
            for i, (role, content) in enumerate(stream):
                if role != "assistant":
                    continue
                target = content[:MAX_TARGET_CHARS]
                # build context window going backward
                ctx = []
                total = 0
                j = i - 1
                while j >= 0 and len(ctx) < MAX_CTX_MSGS:
                    r, c = stream[j]
                    if total + len(c) > MAX_CTX_CHARS:
                        break
                    ctx.append((r, c))
                    total += len(c)
                    j -= 1
                ctx = ctx[::-1]
                messages = [{"role": r, "content": c} for r, c in ctx]
                messages.append({"role": "assistant", "content": target})
                fo.write(json.dumps({"messages": messages,
                                     "session": rec["session"]}) + "\n")
                n_ex += 1
                n_tool += target.count("[tool:")

    print(json.dumps({"examples": n_ex, "tool_targets": n_tool, "out": OUT}, indent=2))


if __name__ == "__main__":
    main()