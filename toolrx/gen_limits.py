#!/usr/bin/env python3
"""Generate `toolrx/web/limits.js` from `toolrx/limits.json`.

The browser needs the envelope synchronously, before any script calls into the
workspace. Rather than copy the numbers by hand, this generator emits a frozen
object from the one checked-in JSON. `tests/test_limits.py` fails if the two
drift apart.

Run after editing `limits.json`:

    python3 toolrx/gen_limits.py
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "limits.json"
OUT = ROOT / "web" / "limits.js"

BANNER = ("/* GENERATED from toolrx/limits.json by toolrx/gen_limits.py. "
          "Do not edit by hand. */\n")


def render(data):
    """Return the exact browser module text for an envelope object."""
    body = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
    return (BANNER
            + "(function (root) {\n"
            + '  "use strict";\n'
            + "  root.toolrxLimits = Object.freeze(" + body + ");\n"
            + '})(typeof self !== "undefined" ? self : this);\n')


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    text = render(data)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(text)} bytes) from {SRC.name}")


if __name__ == "__main__":
    main()
