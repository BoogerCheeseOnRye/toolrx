#!/usr/bin/env python3
"""Build the GitHub Pages copy of the dashboard.

Pages serves static files only, so the dashboard is shipped together with the
in-browser router: the same hashed n-gram model (`toolrx/micro_model.json`) and
the JS port of `tokhash.py` / `router.py`. On a static host the dashboard runs
the router in the tab and reports that honestly; the Python server is optional.

Run after editing the dashboard or the web router:

    python3 docs/build.py
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "toolrx" / "dashboard.html"
MODEL = ROOT / "toolrx" / "micro_model.json"
WEB_SRC = ROOT / "toolrx" / "web"
DOCS = ROOT / "docs"
WEB_OUT = DOCS / "web"


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    WEB_OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "toolrx" / "embed_engine.py")],
                   check=True)
    (DOCS / "index.html").write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    shutil.copyfile(MODEL, WEB_OUT / "model.json")
    names = ("blake2b.js", "router.js", "sandbox.js", "skills.js",
             "templates.js", "engine2d.js", "engine2d.embed.js", "commands.json")
    for name in names:
        shutil.copyfile(WEB_SRC / name, WEB_OUT / name)
    pwa = ("sw.js", "manifest.webmanifest", "icon.svg")
    for name in pwa:
        shutil.copyfile(WEB_SRC / name, DOCS / name)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {DOCS / 'index.html'} ({SRC.stat().st_size} bytes)")
    print(f"wrote {WEB_OUT}/model.json ({MODEL.stat().st_size} bytes) + {len(names)} web assets")
    print(f"wrote {len(pwa)} offline assets (sw.js, manifest.webmanifest, icon.svg)")


if __name__ == "__main__":
    main()
