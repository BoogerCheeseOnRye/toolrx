"""Long-form prompt splitting for the deterministic path.

The router is tuned for short, concrete intents. A long prompt is therefore
treated as a plan: split on sentence boundaries, numbered lines, and explicit
connectors, then cap each step at the single-route length. This module is pure
text handling so both the Python pipeline and the tests can use it without a
model or a network.

Limits are mirrored in `toolrx/web/skills.js` (`LIMITS`) and in policy.json.
Keep the three in sync; `tests/test_longform.py` checks the Python side and the
Node harness checks the browser side.
"""

import re

SINGLE_MAX = 2000
PLAN_MAX = 8000
PLAN_STEPS = 40

# Sentence boundary: punctuation followed by whitespace and a likely new
# sentence. Decimals (3.5) and filenames (notes.txt) have no whitespace after
# the dot, so they stay intact.
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[a-z0-9\"'(\[])", re.IGNORECASE)

# Explicit step connectors. Keep this list in sync with skills.js.
_CONNECTOR = re.compile(
    r"\s*(?:;|->|→|\bthen\b|\bafter that\b|\band then\b|\bfollowed by\b)\s*",
    re.IGNORECASE,
)

_NUMBERING = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s*")

# Punctuation connectors are rewritten to newlines before the security layer,
# because `;` and `>` are shell metacharacters. Only the separator itself is
# removed; every resulting unit still passes the full sanitizer, and banned
# words / injection phrases anywhere in the prompt are rejected first.
_PUNCT_CONNECTOR = re.compile(r"\s*(?:;|->|→)\s*")


def normalize_connectors(text):
    return _PUNCT_CONNECTOR.sub("\n", str(text or "")).strip()


def sentence_count(text):
    return len([s for s in _SENTENCE.split(str(text or "")) if s.strip()])


def has_connectors(text):
    return bool(_CONNECTOR.search(str(text or "")))


def has_numbered_lines(text):
    return sum(1 for line in str(text or "").splitlines()
               if _NUMBERING.match(line)) >= 2


def has_multiple_lines(text):
    return len([line for line in str(text or "").splitlines()
                if line.strip()]) > 1


def is_plan(text, max_step=SINGLE_MAX):
    """Conservative plan gate: explicit structure or a genuinely long prompt."""
    raw = str(text or "").strip()
    if not raw:
        return False
    return (len(raw) > max_step
            or has_connectors(raw)
            or has_multiple_lines(raw)
            or has_numbered_lines(raw)
            or (sentence_count(raw) >= 3 and len(raw) >= 240))


def chunk_text(text, limit=SINGLE_MAX):
    """Split one over-long step at word boundaries into <= limit pieces."""
    text = str(text).strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    out = []
    rest = text
    while len(rest) > limit:
        cut = rest.rfind(" ", 0, limit + 1)
        if cut < limit // 2:  # no useful boundary; hard-cut the token
            cut = limit
        piece = rest[:cut].strip()
        if piece:
            out.append(piece)
        rest = rest[cut:].strip()
    if rest:
        out.append(rest)
    return out


def split_info(text, max_steps=PLAN_STEPS, max_step=SINGLE_MAX):
    """Return the full plan plus whether the step cap was exceeded."""
    raw = str(text or "").replace("\r", "").strip()
    if not raw:
        return {"steps": [], "total": 0, "truncated": False, "overLimit": False}

    lines = [_NUMBERING.sub("", line).strip() for line in re.split(r"\n+", raw)]
    lines = [line for line in lines if line]

    parts = []
    if len(lines) > 1:
        parts = lines
    else:
        # Sentence splitting only applies inside a plan; a short three-sentence
        # chat message stays one route, matching the browser splitter.
        sentences = _SENTENCE.split(raw) if is_plan(raw, max_step) else [raw]
        for sentence in sentences:
            parts.extend(_CONNECTOR.split(sentence))

    steps = []
    for part in parts:
        for chunk in chunk_text(part, max_step):
            if chunk:
                steps.append(chunk)

    total = len(steps)
    return {
        "steps": steps[:max_steps],
        "total": total,
        "truncated": total > max_steps,
        "overLimit": total > max_steps,
    }


def split_steps(text, max_steps=PLAN_STEPS, max_step=SINGLE_MAX):
    return split_info(text, max_steps=max_steps, max_step=max_step)["steps"]
