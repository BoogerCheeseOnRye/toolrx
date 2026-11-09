import json, sys

def tool_schema(name):
    return {
        "name": name,
        "description": name,
        "parameters": {"type": "object", "additionalProperties": True},
    }

def main(src, dst):
    out = []
    skipped = 0
    with open(src) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            session = json.loads(line)
            stream = session.get("stream") or []
            user_text = ""
            for msg in stream:
                role = msg.get("role")
                parts = msg.get("parts") or []
                if role == "user":
                    user_text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
                elif role == "assistant":
                    tools = [p for p in parts if p.get("type") == "tool" and p.get("tool")]
                    if not tools:
                        continue
                    if not user_text:
                        skipped += 1
                        continue
                    MAX_Q = 150
                    if len(user_text) > MAX_Q:
                        user_text = user_text[:MAX_Q]
                    answers = [{"name": p["tool"], "arguments": p.get("input") or {}} for p in tools]
                    names = sorted({p["tool"] for p in tools})
                    out.append({
                        "query": user_text,
                        "tools": [tool_schema(n) for n in names],
                        "answers": answers,
                    })
    with open(dst, "w") as f:
        for ex in out:
            f.write(json.dumps(ex) + "\n")
    print(f"wrote {len(out)} examples -> {dst} (skipped {skipped})")

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "corpus_all.jsonl"
    dst = sys.argv[2] if len(sys.argv) > 2 else "needle_data.jsonl"
    main(src, dst)
