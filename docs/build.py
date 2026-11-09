#!/usr/bin/env python3
"""Generate the GitHub Pages copy of the dashboard.

Pages serves static files only, so `docs/index.html` is a byte-for-byte copy
of `toolrx/dashboard.html`. The dashboard detects a missing backend and falls
back to a "static demo" host card instead of rendering an empty shell.

Run after editing the dashboard:  python3 docs/build.py
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "toolrx" / "dashboard.html"
OUT = ROOT / "docs" / "index.html"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    (OUT.parent / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
