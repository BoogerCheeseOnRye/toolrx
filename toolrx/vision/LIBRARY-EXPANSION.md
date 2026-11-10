# Library expansion — the archive and the command library, wired together

Status: PLAN (next roadmap batch)
Companion to: `HARNESS-ROADMAP.md` steps 21–25
Scope owner: toolrx

---

## 1. What “the library” means

The library is two layers that must behave as one:

1. **The archive** — the personal C++ and game-development book collection in
   Google Drive, plus legal free references we add links to.
2. **The toolrx command library** — the generated pattern set in
   `toolrx/web/commands.json` and the router in `toolrx/web/skills.js`.

Wiring them together means: a prompt such as *“I’m stuck on shaders, what do I
have?”* should (a) recognize that it is a **library/search** intent, (b) recognize
the **topic** (shaders / graphics), (c) return matching archive entries with
where to read them, and (d) optionally propose the next book or a reading order.
The same language-recognition layer that tags the books also lets the router
understand prompts written in other human languages and prompts that contain
code in other programming languages.

The deterministic path stays first and complete. No LLM is required. No network
call is made at query time.

---

## 2. Archive inventory (as of this plan)

Source folder:
`https://drive.google.com/drive/folders/16Sikf0ytQ9cLwPj7cORBeGEInsESuAmd`

Root: **9 PDFs**

| # | File | Primary language | Topic | Assumed level |
|---|------|------------------|-------|---------------|
| 1 | `A_Complete_Guide_to_Programming_in_C++.pdf` | C++ | language + OOP fundamentals | beginner → intermediate |
| 2 | `A_Study_path_for_game-programmer(2017 links).pdf` | — | career/learning path, curated links | all |
| 3 | `Creating_Games_in_C-_A_Step-by-Step_Guide.pdf` | C++ | game loops, input, simple games | beginner |
| 4 | `DevelopingSimplegameswithOpenGL.pdf` | C++ / OpenGL | real-time graphics | intermediate |
| 5 | `Fundamentals_of_C++_programming(2017 Draft).pdf` | C++ | language fundamentals | beginner |
| 6 | `Intro_to_Game_Programming.pdf` | C++ (likely) | game programming survey | beginner |
| 7 | `Programming-2D-Games-1st-Edition.pdf` | C++ (likely) | 2D games, sprites, collision | beginner → intermediate |
| 8 | `The_C++_language_Tutorial.pdf` | C++ | language tutorial/reference | beginner → intermediate |
| 9 | `TutorialsPoint_Learn_C++.pdf` | C++ | language tutorial | beginner |

Subfolder **“Procedural content generation”** (folder id
`1-7D_S-pm2sU7wscXKvnUEQ7C2Irn9p-X`):

- `chapter01.pdf` … `chapter12.pdf`
- `interviews.pdf`

This looks like a 12-chapter PCG text plus interviews. The exact title, authors,
year, and licence must be read from `chapter01.pdf` front matter during
ingestion — do not guess them in the catalog. Treat the set as **one book with
13 parts**, not 13 separate books.

### Coverage summary

- **Strong:** introductory C++, 2D game programming, intro graphics, a career
  study path, and a structured PCG set.
- **Thin:** modern C++ (C++11/14/17/20), data structures and algorithms, math
  for graphics, engine architecture, debugging/profiling, tools and pipelines.
- **Absent:** C, C#, Rust, Python, JavaScript/TypeScript, Lua, shader languages,
  scripting/engine-specific languages, networking, audio, game AI, animation,
  and non-English editions.

---

## 3. Catalog record schema

One JSON file, one record per book (a multi-part book is one record with
`parts`). Committed metadata is small and human-readable; extracted text is
local-only unless the work is public domain or openly licensed.

```json
{
  "id": "cpp-complete-guide",
  "title": "A Complete Guide to Programming in C++",
  "authors": ["Unknown — verify from front matter"],
  "year": null,
  "edition": null,
  "kind": "book",
  "format": "pdf",
  "parts": [],
  "source": {
    "provider": "google-drive",
    "folder_id": "16Sikf0ytQ9cLwPj7cORBeGEInsESuAmd",
    "file_id": "…",
    "url": "https://drive.google.com/…",
    "sha256": "…",
    "bytes": 0,
    "pages": 0
  },
  "rights": {
    "status": "personal-copy",
    "redistributable": false,
    "notes": "Private archive; metadata only in git."
  },
  "classification": {
    "topics": ["cpp", "oop", "language-basics"],
    "programming_languages": ["cpp"],
    "natural_languages": ["en"],
    "level": "beginner",
    "audience": "self-study",
    "era": "pre-c++11"
  },
  "reading": {
    "status": "unread",
    "priority": 2,
    "prerequisites": [],
    "next": []
  },
  "search": {
    "aliases": ["complete guide c++", "cpp complete guide"],
    "keywords": ["classes", "templates", "stl", "inheritance"],
    "summary": "One-line description written by us, not copied from the book."
  }
}
```

Field rules:

- `id` is a stable slug, never reused.
- `rights.status` is one of `personal-copy`, `public-domain`, `open-licence`,
  `purchased`, `borrowed`, `link-only`.
- `redistributable: false` means the PDF and extracted text never enter git or
  the Pages build; only metadata and our own summary do.
- `programming_languages` uses the canonical IDs from §6.1.
- `natural_languages` uses BCP-47 primary subtags (`en`, `es`, `fr`, `de`, `hi`,
  `ja`, `zh`, `ko`, `pt`, `ru`, `ar`, …).
- `reading.next` is an ordered list of catalog IDs, so a reading path is data.
- Unknown values are `null` or `[]`, never invented.

The index is derived, never hand-edited:

```
library/catalog.json     # committed metadata
library/index.json       # generated: tokens, snippets, scores (gitignored if
                         # any source is non-redistributable)
library/aliases.json     # language/topic alias tables used by the router
```

---

## 4. Gap analysis and acquisition targets

Acquire **legally**: buy, borrow, or link. Do not add pirated copies, and do not
commit copyrighted PDFs. Free/open references are preferred where they are good.

### 4.1 Programming languages

| Language | Current archive | Gap | Target (first choice) |
|----------|-----------------|-----|------------------------|
| C++ | strong (6+ books) | modern C++ (11–20), idioms, performance | *A Tour of C++* (purchase); ISO C++ Core Guidelines + cppreference (link, open licence) |
| C | none | language + systems | *The C Programming Language* (purchase); cppreference C pages (link) |
| C# | none | language + Unity/game use | Microsoft Learn C# path (link); *C# Yellow Book* (free) |
| Rust | none | language + gamedev | *The Rust Book* + *Rust by Example* (MIT/Apache, link) |
| Python | none | language + tooling | official tutorial + *Automate the Boring Stuff* (free online) |
| JavaScript / TypeScript | incidental only | language + browser/game | MDN + *Eloquent JavaScript* (CC BY-NC) + TypeScript Handbook (link) |
| Lua | none | scripting, LÖVE | Lua 5.4 manual (link); *Programming in Lua* (free online edition) |
| GLSL / HLSL / WGSL | indirect (OpenGL book) | shader authoring | *LearnOpenGL* shading chapters (link); WebGPU/WGSL docs |
| GDScript | none | Godot | Godot docs (CC BY 4.0, link) |
| Assembly | none | optional, low priority | *Computer Systems: A Programmer’s Perspective* (purchase) |

### 4.2 Game-development topics

| Topic | Current | Gap | Target |
|-------|---------|-----|--------|
| 2D games | strong | polish, juice, content pipelines | *Game Programming Patterns* (free online) |
| 3D graphics | one OpenGL book | modern API, PBR, shadows | *LearnOpenGL* (link); *Vulkan Tutorial* (link); *Physically Based Rendering* (free online) |
| Math | none | vectors, matrices, quaternions, curves | *3D Math Primer* (purchase); *Mathematics for 3D Game Programming* (purchase) |
| Engine architecture | none | modules, memory, job systems | *Game Engine Architecture* (purchase) |
| PCG | 13-part set | practical algorithms + evaluation | *Procedural Content Generation in Games* (free online) + the existing set |
| Game AI | none | pathfinding, behavior, utility | *AI for Games* (purchase); Red Blob Games pathfinding articles (link) |
| Physics | none | rigid bodies, collision | *Game Physics Engine Development* (purchase) |
| Networking | none | prediction, rollback | *Multiplayer Game Programming* (purchase); Gaffer On Games (link) |
| Audio | none | mixing, synthesis | *The Audio Programming Book* (purchase); Web Audio docs |
| Animation | none | rigging, state machines | *Game Anim* (purchase); Godot animation docs |
| Tools/pipelines | none | editors, asset builds | *Game Programming Patterns* + engine docs |
| Testing/debugging | none | profilers, asserts, CI | *Debugging* (purchase); platform docs |
| Career/study | one path PDF | updated path | refresh the 2017 link list with checked, live links |

### 4.3 Natural languages

The archive is English-only. The goal here is **not** to translate whole books.
It is to (a) record the language of each work, (b) accept prompts in other
languages, and (c) recommend translated editions when one is known. Acquisition
targets are therefore metadata and links, not new PDFs.

Priority order for prompt support: **Spanish, French, German, Hindi, Japanese**,
then Portuguese, Italian, Russian, Korean, Simplified Chinese, Arabic.

---

## 5. Ingestion and search design

### 5.1 Ingestion (offline, explicit)

A small Python tool, not a background service:

```bash
python3 toolrx/library.py scan                 # list Drive folder, read-only
python3 toolrx/library.py ingest <pdf>         # sha256, pages, pdftotext -layout
python3 toolrx/library.py tag <id> --topic …   # manual correction wins
python3 toolrx/library.py index                # build library/index.json
python3 toolrx/library.py check                # schema, hashes, dead links
```

Rules:

- `scan` uses the public folder listing and stores file IDs, names, and sizes.
  It never downloads on its own.
- `ingest` requires an explicit local path; it never fetches a URL.
- Text extraction uses `pdftotext` when available and degrades to metadata-only.
- Every derived file records the source `sha256`; a mismatch is an error, not a
  silent re-index.
- The indexer strips page headers/footers, hyphenation, and licence pages before
  tokenizing.
- Personal-use sources set `redistributable: false`; their text stays local.

### 5.2 Search (deterministic, explainable)

Phase 1 is lexical, not embedding-based:

1. Normalize the query (case-fold, strip punctuation, expand aliases such as
   `c++` → `cpp`, `csharp` → `c#`, `gfx` → `graphics`).
2. Score fields with fixed weights: title 5, aliases 4, topics/tags 3,
   summary 2, body snippets 1.
3. Add an exact-phrase bonus and a level/priority tie-break.
4. Return the top N with **why** it matched: `title`, `topic: shaders`,
   `page 214 snippet`.
5. If fewer than N results, say so and offer the nearest topic, not filler.

Budgets: 10 000 records searched in < 10 ms in the browser; index ≤ 2 MB
gzipped for the archive’s current size.

### 5.3 Commands exposed to chat

```
library stats
find a book about shaders
what do i have on procedural generation
list books by language c++
which book covers quaternions
what should i read after programming 2d games
recommend a book for learning rust
what is the study path for game programming
mark complete guide to programming in c++ as reading
```

Every answer names the catalog ID and the section/topic that matched. Missing
coverage is reported as a gap and, when a legal free target exists, a link is
offered.

---

## 6. Language recognition layer

One module, two jobs: identify **programming languages** and identify **natural
languages**, then hand a canonical intent to the existing router. Detection must
be fast, offline, deterministic, and honest about uncertainty.

### 6.1 Programming-language IDs and aliases

Canonical IDs: `cpp`, `c`, `csharp`, `rust`, `python`, `javascript`,
`typescript`, `lua`, `glsl`, `hlsl`, `wgsl`, `gdscript`, `java`, `kotlin`,
`swift`, `go`, `php`, `ruby`, `sql`, `bash`, `html`, `css`, `json`, `yaml`,
`toml`, `xml`, `asm`.

Alias examples:

| Canonical | Accepted spellings |
|-----------|--------------------|
| `cpp` | `c++`, `cpp`, `cxx`, `c plus plus`, `stl` |
| `csharp` | `c#`, `csharp`, `c sharp`, `dotnet`, `.net` |
| `javascript` | `js`, `javascript`, `ecmascript`, `node` |
| `typescript` | `ts`, `typescript` |
| `python` | `py`, `python3`, `python` |
| `rust` | `rs`, `rust`, `rustlang` |
| `lua` | `lua`, `love2d` (framework hint) |
| `glsl` | `glsl`, `shader`, `fragment shader`, `vertex shader` |
| `wgsl` | `wgsl`, `webgpu shader` |
| `gdscript` | `gdscript`, `godot script` |

### 6.2 Programming-language detection signals

Ordered from strongest to weakest:

1. Explicit fence or extension: ```` ```cpp ````, `.cpp`, `.cs`, `.rs`, `.py`,
   `.ts`, `.lua`, `.glsl`, `.wgsl`, `.gd`.
2. Unique syntax: `#include <…>` (C/C++), `using System;` / `namespace … {`
   (C#), `fn main()` + `let mut` (Rust), `def …:` + indentation (Python),
   `func … ->` (Swift), `local function` (Lua), `#version` + `gl_Position`
   (GLSL), `@fragment` / `fn … -> vec4` (WGSL), `extends Node` (GDScript).
3. Keyword/vocabulary scoring with language-specific stopwords.
4. Authored hints in the prompt: “in C++”, “write Rust”, “a Python script”.

Ambiguity handling:

- `C` vs `C++`: if any of `class`, `template`, `namespace`, `std::`, `cout`,
  `#include <iostream>` appears, prefer `cpp`; plain `printf`, `struct`, and
  `malloc` alone stay `c` with lower confidence.
- `JavaScript` vs `TypeScript`: type annotations, `interface`, `enum`, `: string`
  → `typescript`.
- `GLSL` vs `C`: `#version`, `uniform`, `varying`, `gl_FragColor` → `glsl`.
- `HTML`/`XML`/`JSON`/`YAML`: structural markers beat keywords.
- A snippet can be **mixed** (HTML + JS + CSS). Return a primary plus
  `also: ["css", "javascript"]`, never force one answer.

### 6.3 Natural-language detection

Signals, strongest first:

1. Script/Unicode ranges: Devanagari → `hi`/`mr`/`ne`; Kana → `ja`; Hangul →
   `ko`; Han → `zh`/`ja`; Arabic → `ar`/`fa`/`ur`; Cyrillic → `ru`/`uk`/`bg`;
   Greek, Hebrew, Thai.
2. Function-word profiles per language (small, curated stopword sets):
   Spanish `el la de que y en`, French `le la des que et en`, German `der die
   und ist nicht`, Portuguese `o a de que e não`, Italian `il la di che e non`,
   Dutch `de het een en niet`, Turkish `ve bir bu için`, Indonesian `yang dan
   di ini`, Vietnamese `và của là không`, Swahili `na ya kwa ni`.
3. Diacritics and orthography (`ñ`, `ç`, `ß`, `ő`, `å`, `ı`, `ě`).
4. Explicit statement: “in Spanish”, “answer in Hindi”, “responde en francés”.

Rules:

- Return `{lang, confidence, alternatives}`.
- `confidence ≥ 0.75` → act.
- `0.40–0.74` → act but state the assumption, or ask when the action is costly.
- `< 0.40` or a Han-only string that could be Chinese or Japanese → report
  `ambiguous` and ask, unless the user named the language.
- Short strings (< 6 words) are always low confidence; do not guess from one
  word such as “no” or “si”.

### 6.4 Localized intent normalization (not machine translation)

A curated phrase table maps known imperative templates to canonical English
commands. This is **recognition**, not translation: if no template matches, the
text is not rewritten.

```
crea un juego de naves        → build a shooter game
construis un jeu de plates-formes → build a platformer
baue ein 3d-rpg               → build a 3d rpg
5 किमी को मील में बदलो         → convert 5 km to miles
三角形の面積を計算して          → calculate area of a triangle
qué hora es                   → what time is it
responde en español           → reply in spanish
```

Implementation notes:

- Normalize accents and width before matching; keep the original for display.
- Numbers: map language words to digits where the existing numeric grammar
  already accepts them.
- Only rewrite when the **whole** step matches a known template; a partial match
  falls through to normal English matching.
- Report the rewrite in the reply (`interpreted as: build a shooter game`) so the
  behavior is inspectable.
- Store the phrase table as data (`toolrx/web/i18n.json`), not code, so it can
  grow without touching the router.

### 6.5 Response language

A small UI phrase pack, not translated books. Keys cover:

- acknowledgements (`building…`, `done`, `no match`, `ambiguous language`)
- spec labels (`dimension`, `view`, `seed`)
- library answers (`found`, `not in the archive`, `next up`)
- error and empty states

Defaults: English. Preferences: `reply in Spanish`, `habla en inglés`, or a
saved `toolrx.lang` in `localStorage`. Generated project files and code comments
stay English in phase 1; only the chat shell is localized.

---

## 7. Work phases (roadmap steps 21–25)

### 21. Archive catalog slice — done

- `library/catalog.json` exists with all 9 books + the 13-part PCG set.
- Every record validates against the schema; unknown fields stay null.
- `python3 toolrx/library.py check` passes and prints coverage counts.
- `library stats` and `find a book about <topic>` work from the catalog.
- No PDF bytes, extracted text, or personal identifiers enter git.

### 22. Language recognition core — done

- `toolrx/web/lang.js` exports `detectProgramming(text)`,
  `detectNatural(text)`, and `normalize(text)`.
- The alias table and stopword profiles live in `toolrx/web/i18n.json`.
- 40+ fixtures pass for programming languages and 30+ for natural languages,
  including every ambiguity pair in §6.2/§6.3.
- Detection of a 1 KB snippet is < 5 ms and a 64 KB file is < 20 ms in the
  browser under test.
- The router exposes `what language is this`, `detect the language of …`,
  `what programming language is …`, and `what natural language is …`.
- Unknown and ambiguous inputs return `unknown` / the top two, never a silent
  single guess.

### 23. Archive search and recommendations — done

- `library/index.json` builds locally and `find`, `which book covers`,
  `list books by language`, and `recommend …` return ranked results with a
  one-line reason.
- Queries expand aliases (`c++`/`cpp`, `graphics`/`gfx`, `pcg`/`procedural`).
- `what should i read after <id>` follows `reading.next`, and a gap in coverage
  is reported as a gap.
- Search stays under 10 ms for 10 000 records.

### 24. Localized intents and replies — done when

- The §6.4 examples, plus 20 more per priority language, produce the canonical
  command and show `interpreted as: …`.
- A full localized prompt builds the same project as its English form.
- `reply in Spanish/French/German/Hindi/Japanese` switches the chat shell and
  persists the preference; `reply in English` restores it.
- With i18n disabled or missing, everything falls back to English without an
  error.

### 25. Library surface and offline packaging — done when

- The dashboard has a **Library** panel: search, topic/level/language filters,
  reading status, and “next up”.
- The panel works offline from the same catalog/index files and adds them to the
  PWA cache (bump `toolrx-shell-v*`).
- Keyboard navigation and `Escape` match the existing dialog behavior.
- The Pages build ships catalog metadata only; non-redistributable text never
  leaves the machine.

---

## 8. Acceptance tests (language layer)

| Input | Expected |
|-------|----------|
| `#include <iostream>\nint main(){std::cout<<"hi";}` | `cpp` ≥ 0.9 |
| `using System; namespace A { class B {} }` | `csharp` ≥ 0.9 |
| `fn main() { let mut x = 1; }` | `rust` ≥ 0.9 |
| `def f(x):\n    return x + 1` | `python` ≥ 0.9 |
| `const x: string = "a"` | `typescript` ≥ 0.8 |
| `--[[ comment ]] local function f() end` | `lua` ≥ 0.85 |
| `#version 330\nvoid main(){gl_Position=vec4(0.0);}` | `glsl` ≥ 0.9 |
| `<html><body><script>let x=1</script></body></html>` | `html` + `also: javascript` |
| `Hola, ¿puedes crear un juego de naves?` | `es` ≥ 0.8, intent → build shooter |
| `Peux-tu construire un jeu de plates-formes ?` | `fr` ≥ 0.8, intent → build platformer |
| `Baue ein 3D-RPG mit 5 Quests.` | `de` ≥ 0.8, intent → build 3d rpg |
| `क्या आप एक शूटर गेम बना सकते हैं?` | `hi` ≥ 0.8, intent → build shooter |
| `三角形の面積を計算して` | `ja` ≥ 0.8, intent → calculate area |
| `no` (one word) | `unknown` / low confidence, no action |
| `我想做一个游戏` | `zh` (simplified-character evidence) |
| `漢字文章` | `ambiguous: zh/ja`, ask or lower confidence |
| `¿Qué hora es?` vs `Que hora es` | both `es`; accent-insensitive |

The Node harness (`tests/test_skills_js.py`) gains a `lang` section. Python
tests validate the catalog schema and reject any record with
`redistributable: false` whose body text appears under `library/`.

---

## 9. Constraints and non-goals

- **Offline-first:** detection, search, and normalization are local and
  deterministic. No network at query time. No hidden fetch of book text.
- **Rights:** personal copies stay personal. Git and Pages carry metadata, our
  own summaries, and links only. No DRM circumvention, no pirated editions.
- **Determinism:** a prompt + seed still produces identical builds; language
  detection does not consume randomness.
- **Privacy:** no device identifiers, no account names, no real names from the
  archive environment in fixtures or docs.
- **Not machine translation:** we recognize known intents and reply with a small
  phrase pack. We do not translate arbitrary prose.
- **Not a recommender model:** recommendations come from catalog metadata,
  prerequisites, and explicit `reading.next` links. An embedding-based ranker is
  a later, optional step.
- **No silent guessing:** ambiguity is visible in the reply.

## 10. Risks

| Risk | Mitigation |
|------|------------|
| Language detection false positives on short text | hard confidence floor; ask instead of acting |
| Mixed-language prompts | report primary + alternatives; match the dominant template |
| Catalog drift from Drive | `scan` diffs file IDs and hashes; `check` fails on missing sources |
| Copyright leakage into git | `redistributable: false` enforced by a test; `.gitignore` for extracted text |
| Command explosion | one `lang` op + data-driven aliases, not 200 hand-written patterns |
| PWA cache bloat | metadata-only catalog; index is local unless fully open-licensed |

---

## 11. Immediate next actions

Steps 21, 22, and 23 are complete and covered by `tests/test_library.py`,
`tests/test_commands.py`, and the fixture/scale matrix in
`tests/test_skills_js.py`. Next:

1. Step 24: expand the localized intent table past the first templates and add
   the `reply in <language>` preference.
2. Step 25: add the dashboard Library panel and cache catalog metadata in the
   PWA (bump `toolrx-shell-v*`).
