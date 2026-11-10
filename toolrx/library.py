#!/usr/bin/env python3
"""Personal library catalog: validate, index, and optionally ingest a PDF.

The catalog is metadata-only. Personal copies stay out of git, and extracted
text is written under `library/.local/` (gitignored) only when explicitly
requested. There is no network access except for the optional `scan` command,
which reads the public folder listing.

    python3 toolrx/library.py check
    python3 toolrx/library.py stats
    python3 toolrx/library.py index
    python3 toolrx/library.py scan
    python3 toolrx/library.py ingest path/to/book.pdf --id cpp-complete-guide
    python3 toolrx/library.py tag cpp-complete-guide --programming cpp --topic stl
"""

import argparse
import hashlib
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "library"
CATALOG = LIBRARY / "catalog.json"
INDEX = LIBRARY / "index.json"
LOCAL = LIBRARY / ".local"
I18N = ROOT / "toolrx" / "web" / "i18n.json"

LEVELS = {"beginner", "intermediate", "advanced", "reference", "all"}
KINDS = {"book", "book-set", "course", "article", "notes"}
RIGHTS = {"personal-copy", "public-domain", "open-licence", "purchased",
          "borrowed", "link-only"}
NATURAL = {"en", "es", "fr", "de", "hi", "ja", "zh", "ko", "pt", "it", "ru",
           "ar", "nl", "tr", "id", "vi", "sw", "pl", "uk", "fa", "ur", "mr",
           "ne", "bn", "th", "el", "he", "cs", "da", "no", "sv", "fi"}
PROGRAMMING = {"cpp", "c", "csharp", "rust", "python", "javascript", "typescript",
               "lua", "glsl", "hlsl", "wgsl", "gdscript", "java", "kotlin",
               "swift", "go", "php", "ruby", "sql", "bash", "html", "css",
               "json", "yaml", "toml", "xml", "asm"}
REQUIRED = ("id", "title", "authors", "year", "kind", "format", "parts",
            "source", "rights", "classification", "reading", "search")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.-]{1,40}")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def load(path=CATALOG):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(data, path=CATALOG):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def known_programming():
    ids = set(PROGRAMMING)
    if I18N.exists():
        try:
            data = json.loads(I18N.read_text(encoding="utf-8"))
            ids.update((data.get("programming") or {}).keys())
        except (OSError, ValueError):
            pass
    return ids


def validate(data):
    errors = []
    if data.get("version") != 1:
        errors.append("catalog version must be 1")
    records = data.get("records")
    if not isinstance(records, list) or not records:
        return ["catalog has no records"]

    ids = set()
    prog = known_programming()
    for i, rec in enumerate(records):
        where = rec.get("id") or f"record[{i}]"
        for key in REQUIRED:
            if key not in rec:
                errors.append(f"{where}: missing {key}")
        rid = rec.get("id")
        if not isinstance(rid, str) or not ID_RE.match(rid or ""):
            errors.append(f"{where}: id must be a lowercase slug")
        elif rid in ids:
            errors.append(f"{where}: duplicate id")
        else:
            ids.add(rid)
        if not isinstance(rec.get("title"), str) or not rec.get("title").strip():
            errors.append(f"{where}: title must be a non-empty string")
        if rec.get("kind") not in KINDS:
            errors.append(f"{where}: unknown kind {rec.get('kind')!r}")

        parts = rec.get("parts")
        if not isinstance(parts, list):
            errors.append(f"{where}: parts must be a list")
            parts = []
        seen_parts = set()
        for part in parts:
            if not isinstance(part, dict) or not part.get("file"):
                errors.append(f"{where}: every part needs a file")
                continue
            if part["file"] in seen_parts:
                errors.append(f"{where}: duplicate part {part['file']}")
            seen_parts.add(part["file"])
        if rec.get("format") == "pdf-set" and not parts:
            errors.append(f"{where}: pdf-set needs parts")

        source = rec.get("source") or {}
        if source.get("provider") != "google-drive":
            errors.append(f"{where}: unknown source provider {source.get('provider')!r}")
        sha = source.get("sha256")
        if sha is not None and not SHA_RE.match(str(sha)):
            errors.append(f"{where}: sha256 must be 64 lowercase hex characters")
        for num in ("bytes", "pages"):
            val = source.get(num)
            if val is not None and (not isinstance(val, int) or val < 0):
                errors.append(f"{where}: source.{num} must be a non-negative int or null")

        rights = rec.get("rights") or {}
        if rights.get("status") not in RIGHTS:
            errors.append(f"{where}: unknown rights status {rights.get('status')!r}")
        if not isinstance(rights.get("redistributable"), bool):
            errors.append(f"{where}: rights.redistributable must be true or false")
        if rights.get("redistributable") is False:
            for key in ("text", "content", "body", "extracted_text"):
                if key in rec:
                    errors.append(f"{where}: non-redistributable record has {key}")

        cls = rec.get("classification") or {}
        if cls.get("level") not in LEVELS:
            errors.append(f"{where}: unknown level {cls.get('level')!r}")
        for lang in cls.get("programming_languages") or []:
            if lang not in prog:
                errors.append(f"{where}: unknown programming language {lang!r}")
        for lang in cls.get("natural_languages") or []:
            if lang not in NATURAL:
                errors.append(f"{where}: unknown natural language {lang!r}")
        if not isinstance(cls.get("topics"), list) or not cls.get("topics"):
            errors.append(f"{where}: classification.topics must be a non-empty list")

        reading = rec.get("reading") or {}
        if not isinstance(reading.get("next", []), list):
            errors.append(f"{where}: reading.next must be a list")
        search = rec.get("search") or {}
        if not str(search.get("summary") or "").strip():
            errors.append(f"{where}: search.summary is required")

    for rec in records:
        for target in (rec.get("reading") or {}).get("next") or []:
            if target not in ids:
                errors.append(f"{rec.get('id')}: reading.next points at unknown {target!r}")
    return errors


def summary(data):
    recs = data["records"]
    parts = sum(len(r.get("parts") or []) for r in recs)
    langs = {}
    for r in recs:
        for lang in (r.get("classification") or {}).get("programming_languages") or []:
            langs[lang] = langs.get(lang, 0) + 1
    topics = {}
    for r in recs:
        for topic in (r.get("classification") or {}).get("topics") or []:
            topics[topic] = topics.get(topic, 0) + 1
    return {
        "records": len(recs),
        "parts": parts,
        "files": len(recs) + parts - sum(1 for r in recs if r.get("parts")),
        "programming": dict(sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))),
        "topics": dict(sorted(topics.items(), key=lambda kv: (-kv[1], kv[0]))),
        "levels": {
            level: sum(1 for r in recs
                       if (r.get("classification") or {}).get("level") == level)
            for level in sorted(LEVELS)
        },
    }


def tokens_of(rec):
    cls = rec.get("classification") or {}
    search = rec.get("search") or {}
    bits = [rec.get("id", ""), rec.get("title", "")]
    bits += rec.get("authors") or []
    bits += [str(rec.get("year")) if rec.get("year") else ""]
    bits += cls.get("topics") or []
    bits += cls.get("programming_languages") or []
    bits += cls.get("natural_languages") or []
    bits += search.get("aliases") or []
    bits += search.get("keywords") or []
    bits += [search.get("summary") or ""]
    seen, out = set(), []
    for bit in bits:
        for token in TOKEN_RE.findall(str(bit).lower()):
            if token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out


def build_index(data):
    documents = {}
    postings = {}
    for rec in data["records"]:
        rid = rec["id"]
        toks = tokens_of(rec)
        documents[rid] = {
            "title": rec["title"],
            "summary": (rec.get("search") or {}).get("summary") or "",
            "tokens": toks,
        }
        for token in toks:
            postings.setdefault(token, []).append(rid)
    return {
        "version": 1,
        "updated": data.get("updated"),
        "documents": documents,
        "postings": dict(sorted(postings.items())),
        "stats": summary(data),
    }


def cmd_check(args):
    data = load(args.catalog)
    errors = validate(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        print(f"{len(errors)} problem(s)", file=sys.stderr)
        return 1
    stats = summary(data)
    print(f"ok · {stats['records']} records · {stats['parts']} parts · "
          f"{stats['files']} source files")
    print("programming: " + (", ".join(f"{k} {v}" for k, v in stats["programming"].items()) or "none"))
    print("levels: " + ", ".join(f"{k} {v}" for k, v in stats["levels"].items() if v))
    return 0


def cmd_stats(args):
    print(json.dumps(summary(load(args.catalog)), indent=2))
    return 0


def cmd_index(args):
    data = load(args.catalog)
    errors = validate(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1
    out = pathlib.Path(args.out) if args.out else INDEX
    out.parent.mkdir(parents=True, exist_ok=True)
    index = build_index(data)
    out.write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(index['postings'])} tokens)")
    return 0


def cmd_tag(args):
    data = load(args.catalog)
    rec = next((r for r in data["records"] if r["id"] == args.id), None)
    if not rec:
        print(f"error: no record {args.id!r}", file=sys.stderr)
        return 1
    cls = rec.setdefault("classification", {})
    if args.topic:
        cls["topics"] = sorted(set(cls.get("topics") or []) | set(args.topic))
    if args.programming:
        cls["programming_languages"] = sorted(
            set(cls.get("programming_languages") or []) | set(args.programming))
    if args.natural:
        cls["natural_languages"] = sorted(
            set(cls.get("natural_languages") or []) | set(args.natural))
    if args.level:
        cls["level"] = args.level
    if args.status:
        rec.setdefault("reading", {})["status"] = args.status
    errors = validate(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1
    save(data, args.catalog)
    print(f"updated {args.id}")
    return 0


def cmd_ingest(args):
    data = load(args.catalog)
    rec = next((r for r in data["records"] if r["id"] == args.id), None)
    if not rec:
        print(f"error: no record {args.id!r}", file=sys.stderr)
        return 1
    path = pathlib.Path(args.pdf).expanduser()
    if not path.is_file():
        print(f"error: no file {path}", file=sys.stderr)
        return 1
    if path.suffix.lower() != ".pdf":
        print("error: expected a PDF", file=sys.stderr)
        return 1
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    source = rec.setdefault("source", {})
    source["sha256"] = digest
    source["bytes"] = path.stat().st_size
    if shutil.which("pdfinfo"):
        try:
            info = subprocess.run(["pdfinfo", str(path)], capture_output=True,
                                  text=True, timeout=30).stdout
            m = re.search(r"^Pages:\s+(\d+)", info, re.M)
            if m:
                source["pages"] = int(m.group(1))
        except (OSError, subprocess.SubprocessError):
            pass
    if args.extract:
        if not shutil.which("pdftotext"):
            print("error: --extract needs pdftotext", file=sys.stderr)
            return 1
        LOCAL.mkdir(parents=True, exist_ok=True)
        out = LOCAL / f"{args.id}.txt"
        subprocess.run(["pdftotext", "-layout", str(path), str(out)], check=True)
        print(f"extracted text → {out} (gitignored)")
    errors = validate(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1
    save(data, args.catalog)
    print(f"ingested {args.id} · {source['bytes']} bytes · "
          f"sha256 {digest[:12]}… · pages {source.get('pages')}")
    return 0


def cmd_scan(args):
    folder = args.folder or "16Sikf0ytQ9cLwPj7cORBeGEInsESuAmd"
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", folder)
    if m:
        folder = m.group(1)
    url = f"https://drive.google.com/embeddedfolderview?id={folder}#list"
    req = urllib.request.Request(url, headers={"User-Agent": "toolrx-library/1"})
    try:
        page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except OSError as exc:
        print(f"error: could not read the folder listing: {exc}", file=sys.stderr)
        return 1
    entries = []
    for match in re.finditer(
            r'id="entry-([A-Za-z0-9_-]+)".*?flip-entry-title">([^<]+)</div>', page, re.S):
        entries.append({"file_id": match.group(1), "name": html.unescape(match.group(2))})
    print(json.dumps({"folder": folder, "entries": entries}, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog", default=str(CATALOG))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="validate the catalog")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("stats", help="print coverage counts")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("index", help="build library/index.json")
    p.add_argument("--out")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("scan", help="list the public Drive folder (read-only)")
    p.add_argument("--folder")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("ingest", help="record a local PDF's hash and page count")
    p.add_argument("pdf")
    p.add_argument("--id", required=True)
    p.add_argument("--extract", action="store_true")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("tag", help="add topics/languages or set reading status")
    p.add_argument("id")
    p.add_argument("--topic", action="append")
    p.add_argument("--programming", action="append")
    p.add_argument("--natural", action="append")
    p.add_argument("--level", choices=sorted(LEVELS))
    p.add_argument("--status", choices=["unread", "reading", "done", "paused"])
    p.set_defaults(func=cmd_tag)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
