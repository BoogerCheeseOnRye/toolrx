"""Verbatim block capture for "write the following into <file>:" requests.

The ordinary sanitizer lowercases text, collapses whitespace, and rejects
shell/injection metacharacters. That is the right default for a routed intent,
but it is the wrong shape for user-authored content: a code snippet or a
paragraph must survive byte-for-byte. This module therefore captures the block
before the normal sanitizer, validates the target path through the same
sandbox, and then applies the explicit safety checks that still make sense for
content: a size cap, no NUL bytes, and the policy's injection patterns.

The block is deliberately not interpreted as a plan. Everything after the
header is content, including lines that look like commands.
"""

import re

import envelope

MAX_BLOCK = int(envelope.get("blockBytes"))

_HEADER = re.compile(
    r"^[ \t]*(?:write|save|put|create|append)[ \t]+(?:the[ \t]+)?"
    r"(?:following|below|block|text)[ \t]+(?:into|to|in|as)[ \t]+"
    r"([A-Za-z0-9._/\-]+)[ \t]*:[ \t]*(?:\r?\n)?",
    re.IGNORECASE,
)

# A terminator is a line on its own. It is not part of the content.
_TERMINATOR = re.compile(
    r"^[ \t]*(?:end|eof|end[ \t]+of[ \t]+block|end[ \t]+block|\.)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

_INJECTION = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
        r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
        r"reveal\s+(?:the\s+)?(?:system\s+)?prompt",
        r"developer\s+mode",
        r"jailbreak",
        r"you\s+are\s+now\s+(?:dan|unrestricted|root)",
    )
]


def header(text):
    """Return the block header match, or None if this is not a block write."""
    return _HEADER.match(str(text or ""))


def _body(text, match):
    """Extract the content after a header, stopping at a terminator line.

    At most one formatting newline is removed: the one that separates the
    header/terminator from the content. Every other byte is preserved.
    """
    rest = str(text)[match.end():]
    term = _TERMINATOR.search(rest)
    terminated = bool(term)
    if terminated:
        rest = rest[:term.start()]
    if rest.endswith("\r\n"):
        rest = rest[:-2]
    elif rest.endswith("\n"):
        rest = rest[:-1]
    return rest, terminated


def capture(text, pol=None, limit=MAX_BLOCK):
    """Validate and capture a block write.

    Returns ``{"ok": True, "path", "content", "terminated", "bytes"}`` or
    ``{"ok": False, "reason"}``. The caller owns execution; this function only
    parses and validates, so it stays pure and testable.
    """
    raw = str(text or "")
    match = header(raw)
    if not match:
        return {"ok": False, "reason": "not a block write"}
    path = match.group(1)
    if "\x00" in raw:
        return {"ok": False, "reason": "null byte rejected"}
    if re.search(r"(^|/)\.\.(/|$)", path.replace("\\", "/")):
        return {"ok": False, "reason": "path traversal (..) rejected"}
    if pol is not None:
        try:
            pol.safe_path(path)  # absolute paths, extensions, sandbox escape
        except Exception as e:  # SecurityError, but keep this module import-light
            return {"ok": False, "reason": str(e)}
    body, terminated = _body(raw, match)
    if not body.strip():
        return {"ok": False, "reason": "empty block — nothing to write"}
    size = len(body.encode("utf-8"))
    if size > limit:
        return {
            "ok": False,
            "reason": f"block too large ({size} > {limit} bytes); "
                      "split it into smaller writes",
        }
    for pat in _INJECTION:
        m = pat.search(body)
        if m:
            return {"ok": False,
                    "reason": f"injection pattern: {m.group(0)!r}"}
    if pol is not None:
        for pat in pol.injection_patterns:
            m = pat.search(body)
            if m:
                return {"ok": False,
                        "reason": f"injection pattern: {m.group(0)!r}"}
    return {"ok": True, "path": path, "content": body,
            "terminated": terminated, "bytes": size}


def detect(text, pol=None, limit=MAX_BLOCK):
    """True when the text starts with a block-write header."""
    return header(text) is not None
