# Harness roadmap 2 — specs, engines, worlds, and long-form work

This plan moves toolrx from "a template per command" toward the output shape of a
general LLM coding harness, while keeping the deterministic core. The rule is
simple: **the deterministic path stays first, complete, and offline**. An LLM may
later fill a validated spec or propose a patch, but it never becomes required.

Steps 26–35 extend the same rules to longer input and longer output. They add no
model: longer prompts become verified multi-step plans, and larger builds become
seeded, composable projects. Steps 36–45 harden that envelope: one limit table,
a larger long-form suite, stricter budgets, safer continuation, richer modules,
coverage metrics, portable workspaces, and a demo that proves the whole path.

## Where this plan started

- Builds are chosen by fixed phrasings over a fixed list of kinds
  (`build a {kind}`, `build a {kind} with {desc}`).
- `templates.js` contains every game as a hand-written canvas page.
- 3D exists for Tetris only (a small software projection).
- 2D games draw shapes; there are no sprite assets.
- RPG is a 20×13 fixed map with one enemy, one boss, one NPC, and a string
  replacement for themes. With no theme it always says "Verdant Wood".
- The chat shows per-step `tok/s` (measured output throughput, not inference).

## Design rules for the next phase

1. **A build is a spec.** Parse the prompt into
   `{kind, dimension, genre, perspective, theme, art, scale, seed, mechanics}`.
   Codegen reads the spec; it never re-parses prose.
2. **Determinism is generation, not play.** World layout, names, asset picks, and
   file contents derive from `hash(normalized prompt + explicit seed)`. Runtime
   gameplay may still use `Math.random`.
3. **Real files, shared engines.** Generated projects carry `engine2d.js` /
   `engine3d.js` / `worldgen.js` as real files. The LLM can patch one file later.
4. **Assets are optional and pinned.** A vendored sprite pack is selected by tag
   and checksum; procedural sprites are the fallback. No runtime network.
5. **The LLM is an adapter, not the engine.** It fills a strict JSON spec or
   proposes an allow-listed patch. Invalid output is rejected.
6. **Speed is visible.** Every step reports its own wall time; cached builds skip
   codegen and say so. Token counts are estimates and labelled as such.

## Steps

### 11. Measured throughput in chat — done

- Each skill result carries `ms`; the dashboard estimates output tokens as
  `ceil(characters / 4)` and renders `tok/s · tok · ms`.
- Content stays deterministic; only the timing is measured. The tooltip states
  that this is not model inference.
- Later: show cache hits and p50/p95 plan time in the same slot.

### 12. Build spec parser v2 — done

`buildSpec(kind, desc)` now returns
`{dim, view, genre, art, theme, scale, seed, engine}` and `specLine()` renders
the one-line plan shown in chat. Dimensions, views, art directions, scale
(`64x64`, `3 levels`, `5 quests`), and explicit `seed N` are parsed; the default
seed is a hash of the normalized prompt. Genre aliases map to real starters
(`tower defense` → tower defense, `roguelike` → roguelike,
`racing`/`kart` → racer) and the reply names the closest supported option when
the request is approximate.
`build a 3d platformer`, `build an isometric rpg in a desert with 3 quests`,
`build a top-down shooter with pixel art, 3 levels`, `build a first-person maze,
low-poly`, and `build a 2d racing game at night, seed 42` all produce inspectable
specs and complete projects.

### 13. Shared 2D engine — done

`toolrx/web/engine2d.js` is a dependency-free runtime with a fixed-step loop,
pause/resume, DPR-aware resizing, keyboard/pointer/touch/on-screen buttons,
camera follow, tile and sprite drawing, AABB physics, a particle pool, and
WebAudio beeps with a mute switch. Platformer, snake, breakout, top-down
shooter, and kart racer build on it. Generated projects ship `engine2d.js` as a
real file; `bundleProject()` inlines the same source for the preview.
`toolrx/embed_engine.py` generates `engine2d.embed.js` from the source, and the
PWA cache (`toolrx-shell-v2`) carries both files.

The parser accepts:

- dimension: `2d`, `3d`, `isometric`, `top-down`, `side-scroller`,
  `first-person`, `third-person`
- genre: platformer, shooter, RPG, roguelike, racing, tower defense, puzzle,
  farming sim, card battler, maze, exploration, wave shooter, kart
- art: `pixel`, `low-poly`, `flat`, `vector`, `neon`, `monochrome`
- scale: `small`, `medium`, `large`, `64x64`, `3 levels`, `5 quests`
- theme: existing packs plus free text
- seed: `seed 1234`

Example prompts that must work:

```
build a 3d platformer with a neon city theme
build an isometric rpg in a desert with 3 quests
build a top-down shooter with pixel art, 3 levels
build a first-person maze, low-poly
build a 2d racing game at night, seed 42
```

The reply starts with a one-line plan (`3D · third-person · platformer ·
low-poly · neon · seed 7`) so the choice is inspectable. Unknown combinations
return the closest supported options instead of falling through to chat.

**Done when** 40+ phrasing tests pass, identical prompts yield identical specs,
and the chat output names the chosen spec.

### 14. Sprite pack pipeline

- Vendor a pinned, licence-compatible subset of the chosen public sprite repo:
  `assets/<pack>/LICENSE`, `manifest.json`, sheet images.
- Manifest fields: name, sheet, frame rect, size, anchor, tags, checksum.
- Select by tag (`hero`, `enemy`, `tile.grass`, `prop.chest`) with stable
  tie-breaks from the build seed.
- Copy only referenced sheets into `projects/<slug>/assets/`.
- Include the licence in the project; fall back to procedural sprites when the
  pack is absent or a tag is missing.

**Blocked on** the repository URL and its licence. Until then, the interface and
procedural fallback can land.

### 15. Shared 3D engine — done

`engine3d.js` with a tiny WebGL1 renderer:

- camera, perspective, directional light, flat-shaded boxes and quads
- instanced-ish batching for tiles and props
- billboard sprites for characters
- Canvas2D isometric fallback when WebGL is unavailable or disabled

Start with procedural low-poly meshes; no external models. First templates:
third-person platformer, first-person maze, kart racer. Touch controls use the
same input layer as the 2D engine.

**Done when** each 3D template runs in the iframe preview at 60 fps on desktop,
is playable on a phone, and degrades to a clear fallback without WebGL.

### 16. RPG world engine v2 — done

Replace the fixed map with `worldgen.js`:

- 64×64 to 96×96 chunked tile world: biomes, rivers, roads, towns, dungeons
- camera follow and minimap
- NPCs with JSON dialogue trees, shops, and quest givers
- quests: fetch, kill, escort, discover; journal and objectives
- enemies with small state machines, elites, and a boss
- inventory, equipment, XP/levels, potions, gold
- three save slots, pause menu, new game + seed display

Theme packs define palette, names, enemy sets, quest verbs, and music tempo.
World layout, NPC placement, and quest order derive from the seed.

**Done when** a world is at least 64×64, has 3+ NPCs and 3+ quests, saves and
loads, and two seeds produce visibly different worlds while one seed reproduces
exactly.

### 17. Themes and titles without a default — done

- Expand from 10 packs to at least 20 (add e.g. frost, volcanic, fungal,
  sky-islands, clockwork, dream, plague, archipelago).
- Add a title grammar: `<adjective> <place> RPG` plus curated pack titles.
- Default `build an rpg` picks by seed hash, so consecutive builds differ.
- Keep `seed N` for an exact replay.
- Renaming a project to a known setting still retargets palette, names, quests,
  and title in place.

**Done when** ten default builds give ten distinct titles and `seed 7` is stable.

Landed with twenty packs (the original ten plus frost, volcanic, fungal,
sky-islands, clockwork, dream, plague, archipelago, verdant, and astral). The
first ten keep curated titles; the second ten use generated
`<adjective> <place> RPG` names. A default RPG build mixes a session counter into
the seed hash, so consecutive prompts choose different packs, and the printed
seed reproduces the exact world with `seed N`. Renaming to any pack keyword
rebuilds the same project in place.

### 18. Intro-to-medium game library — done

Two-dimensional: platformer, top-down shooter, twin-stick, roguelike, tower
defense, top-down racing, merge/match puzzle, farming sim, card battler, rhythm.

Three-dimensional: first-person maze, third-person platformer, kart racer,
low-poly exploration, wave shooter, block builder.

Each template ships the same project skeleton and an `ARCHITECTURE.md` describing
state, entities, systems, balance knobs, and extension points. `plan a <genre>`
prints the brief; `build a <genre>` writes the working starter.

Landed with all sixteen starters wired into the command catalog. The 2D
templates share `engine2d.js` (the card battler is plain DOM); the 3D templates
route through `engine3d.js`. Each genre has a distinct title, seeded gameplay
where it matters, and an architecture entry rather than a closest-match
fallback. Explicit `2d` requests keep the 2D runtime; `2d`/`3d` routing is part
of the spec.

### 19. Composable edits — done

Treat common follow-ups as deterministic patches against the active project:

```
add double jump
add three enemy types
add a boss
add a quest
add day/night
add sound
make it harder
make the world 96x96
switch to isometric
make it 3d
```

Each patch changes the spec and a named function in a real file, re-bundles the
preview, and reports which files changed. `undo` restores the previous files.
This is the feature that makes the harness feel conversational without an LLM.

**Done when** every example edits real files and `undo` is lossless.

Landed in `web/patches.js`. `edit.apply` patches a named function or constant in
`app.js` (or markup and CSS in `index.html` / `styles.css`), updates the build
spec, appends an `## Applied edits` block to the project docs, and re-bundles the
preview. Each project keeps up to eight full-file snapshots, so `undo` restores
the exact strings that existed before the edit, including files added or removed
by `make it 3d`. Patches that do not fit the genre answer with a short reason
instead of changing something unrelated.

### 20. Optional LLM adapter and budgets — done

- `plan(prompt)`: deterministic parser first. Only if it cannot produce a spec,
  an optional LLM returns strict JSON, validated against the schema.
- `patch(file, instruction)`: the LLM may propose a unified diff for allow-listed
  project files; a deterministic validator and smoke run must pass before install.
- Response cache keyed by normalized prompt + spec hash. Cached builds return
  immediately and report `cache hit`.
- Budgets: deterministic plan ≤ 20 ms, typical build ≤ 400 ms, first preview
  ≤ 1 s, main-thread block ≤ 50 ms, asset payload capped per project.
- Offline and `LLM disabled` are the default. No hidden network calls.

**Done when** with the LLM off every command still works, and with it on the same
prompt produces the same spec and files as the deterministic path.

Landed in `web/llm.js`. Settings live under `toolrx.llm.config` and stay off
until the user saves an OpenAI-compatible endpoint and model in Command Center.
`llm plan` returns a deterministic answer without any request when the parser
already knows the genre (only `playground` falls through); otherwise the reply
must be one JSON object with an allow-listed genre, an optional `2D`/`3D` dim,
and a short `why`. `llm patch` accepts only `{file, diff}`, rejects any other
key, keeps the file inside the active project, and applies hunks exactly or not
at all. A pending patch is stored in `toolrx.llm.pending` and is not written
until `apply the llm patch`, which pushes the normal undo snapshot; `discard the
llm patch` writes nothing. Requests are HTTPS-only (plain HTTP for localhost),
capped at 8 calls per session by default with a timeout, response-size cap, and
a 50-entry cache keyed by normalized prompt plus file hash. The API key stays in
`localStorage`, never in the cache or status text.

### 21. Archive catalog — done

Turn the personal C++ / game-dev Drive collection into a real, queryable catalog:
one metadata record per book (a 13-part set is one book), with topics,
programming languages, natural language, level, rights, source hash, and reading
links. Metadata only in git; personal PDFs and extracted text stay local.

**Done when** `library/catalog.json` covers the 9 books plus the 13-part
procedural-generation set, `python3 toolrx/library.py check` passes, and
`library stats` / `find a book about <topic>` answer from it.

### 22. Language recognition core — done

One offline module that detects programming languages (C++, C#, C, Rust, Python,
JS/TS, Lua, shaders, …) and natural languages (Spanish, French, German, Hindi,
Japanese, …), returns confidence plus alternatives, and exposes
`what language is this` / `what programming language is …` /
`what natural language is …`. Alias tables and stopword profiles live in data,
not in hand-written patterns.

**Done when** the ambiguity fixtures in `LIBRARY-EXPANSION.md` pass, short or
mixed input never gets a silent single guess, and 1 KB detection stays under
5 ms.

### 23. Archive search and recommendations — done

Lexical, explainable search over the catalog: alias expansion, weighted fields,
level/language filters, result reasons, and reading paths from `reading.next`.
`which book covers quaternions`, `list books by language rust`,
`what should i read after <id>`, and gap reports all work without an LLM.

**Done when** results name why they matched, alias queries behave, and 10 000
records search in under 10 ms.

### 24. Localized intents and replies — done

A curated phrase table maps known imperative templates (`crea un juego de
naves`, `baue ein 3d-rpg`, `5 किमी को मील में बदलो`) to canonical English
commands and shows `interpreted as: …`. A small phrase pack localizes the chat
shell for Spanish, French, German, Hindi, and Japanese; preferences persist in
`localStorage`.

**Done when** localized prompts build the same project as their English form,
`reply in <language>` switches and persists, and a missing pack falls back to
English cleanly.

Landed as 76 phrase entries (15 intents for each priority language) plus the
bare Japanese “make a game” template. `reply in`, `respond in`, `answer in`,
`switch to`, and `speak` resolve through aliases; `reply language` reports the
current preference, and `back to english` / `stop replying` clears it. The
preference lives under `toolrx.reply.lang`; shell messages are localized while
command output and user data are left untouched.

### 25. Library surface and offline packaging — done

Add a Library panel to the dashboard (search, topic/level/language filters,
reading status, next up), cache catalog metadata in the PWA, and keep keyboard
and dialog behavior consistent with the rest of the tool.

**Done when** the panel works offline, the Pages build ships metadata only, and
non-redistributable text never leaves the machine.

Landed as a full-screen `Library` dialog opened from the composer bar. It reads
the catalog embedded in `web/commands.json`, adds level/language/status filters,
shows up to three “next up” books, and saves reading-status overrides under
`toolrx.library.status`. Catalog metadata is already in the PWA shell cache
(now `toolrx-shell-v15`), so the panel works offline with no second fetch.

## Next batch: longer input, longer output (steps 26–35)

Steps 11–25 expanded what toolrx can understand and build. Two limits remain:
the 300-character input ceiling, and the small, fixed shape of generated output.
This batch attacks both by growing the deterministic surface rather than adding
a generative model. The LLM adapter stays optional, off by default, and is never
on the critical path for a normal route, plan, build, edit, or undo.

### Target envelope (v1)

These are starting commitments, to be tuned with the step-35 measurements. Every
limit is a hard cap with an explicit refusal or truncation message. "Longer"
never means unbounded.

| Dimension | Today | v1 target |
| --- | --- | --- |
| Single-route input | 2,000 chars | 2,000 chars |
| Plan input | 8,000 chars / 40 steps | 8,000 chars / 40 steps |
| Project files | 32 files | 32 files |
| Project text | 512 KB total | 512 KB total |
| Undo snapshots | 16, configurable | 16 |
| Command patterns | 11,248 | 12,000 |
| Context store | remember/forget notes | 8 KB serialized, inspectable |

### Guardrails

1. Deterministic path first; no network and no LLM requirement.
2. Length increases are policy changes, tested like security changes.
3. Every new generator is seeded; same prompt plus seed produces the same tree.
4. Plans print before execution, with per-step confidence and margin.
5. Partial output is labelled partial; a failure never leaves a silent half-project.
6. Caps live in `policy.json` or one constants module, not scattered magic numbers.
7. Each step ships with Python and browser tests plus a docs update.

### 26. Adaptive input ceiling — done

Raise the default `max_len` from 300 to 2,000 for a single route, and accept up to
8,000 characters only through the plan path (step 27). Before embedding, split at
sentence, paragraph, and newline boundaries into units of at most 2,000
characters; more than one unit forces plan mode. Truncation is the last resort and
must say `query truncated at N chars`, showing what was dropped or offering a
deterministic split. Run the banned-word, metacharacter, charset, and positive
allowlist checks on the full input and on every unit, so a payload cannot straddle
a chunk boundary. Generate the policy constants; do not hand-edit copies.

**Done when** a 2,000-character single-intent fixture routes identically to its
short form, an 8,001-character request refuses with a clear message, a
chunk-boundary injection fixture is rejected, and 300-character behavior is
unchanged.

Landed with `max_len` 2,000, `max_plan_len` 8,000, and `max_plan_steps` 40 in
`policy.json`, mirrored in `toolrx/longform.py` and `toolrx/web/skills.js`, and
pinned by `tests/test_longform.py` and `tests/test_skills_js.py`. `sanitize()`
takes an explicit cap and `sanitize_plan()` preserves newlines under the 8,000
cap. The full prompt is checked for blocked words, injection phrases,
metacharacters, and the positive word allowlist before splitting, and every
unit is checked again after splitting, so a payload cannot straddle a boundary.
Punctuation separators (`;`, `->`, `→`) are rewritten to newlines before the
metacharacter layer; `|`, `&`, `$`, backticks, and the rest remain refused.
Short single-intent prompts keep the old one-tool shape. Over-cap prompts name
the cap and suggest splitting; truncation is never silent.

### 27. Hierarchical routing for long prompts

Detect plan mode from length, three or more sentences, numbered or bulleted
lines, a `plan:` / `steps:` prefix, or two or more explicit connectors. Extract
ordered sub-queries with the existing splitter, strengthened for numbered lines,
`then`, `and then`, `after that`, `;`, and `->`. Route each sub-query
independently and thread the previous result as `prev`. Print the full plan with
per-step confidence and margin before executing; add a preview form (`plan …`)
that runs no tools. Stop at the first refused step unless the plan marks it
optional, and name the step that failed.

**Done when** 500-, 1,500-, and 3,000-character plans execute in order, every step
shows a score, a low-confidence step halts with a named failure, and no step is
silently skipped.

Landed with a shared plan gate: length, explicit connectors, numbered or
multi-line input, or three sentences at 240+ characters. Steps are extracted
from numbered lines, sentence boundaries, `then`, `and then`, `after that`,
`followed by`, `;`, and `->`, then chunked to 2,000 characters. The browser
dashboard previews the ordered steps before running anything, prints them once,
and `runPrompt` stops at the first failed step. The Python pipeline executes
plans in order, records a per-step decision (tool, confidence, margin) and result,
stops at the first blocked or failed step, and names it (`step 2: ...`). Exact
command matches in the browser show their operation; router fallbacks show
confidence and margin on the result line. Plans over 40 steps or 8,000 characters
refuse before any step runs.

### 28. Expand the command surface systematically — done

Grow the catalog from 7,569 toward 12,000 patterns. Prioritize higher-coverage
families for long modifier tails, multi-clause requests, build compositions, and
hierarchical build phrasing (kind → sub-genre → modifiers → scale → theme). Keep
generation in `build_commands.py`; add duplicate and near-duplicate detection and
stable ordering. Counts in the dashboard and tests must derive from the catalog,
not from hard-coded numbers.

**Done when** a long-prompt fixture set reaches at least 90% exact or near-exact
routing, the catalog regenerates byte-identically, no duplicate patterns remain,
and existing routes keep their current answers.

Landed at 12,425 patterns (12,502 after step 31 added 35 context routes). New families cover theme + genre, genre + feature,
scale + genre, scale + theme + genre + feature, and one generic tail pattern per
genre that accepts any number of scale/theme modifiers plus a feature clause.
The generator now skips whitespace-insensitive duplicate regexes (seven existing
duplicates were removed, first entry wins) and honours `TOOLRX_COMMANDS_OUT` so
tests can compare two fresh runs byte-for-byte. `tests/test_commands.py` pins the
count, unique ids and patterns, regenerated bytes, category totals, and a
long-prompt fixture set that checks both the captured genre and modifier text.
Existing routes are unchanged; the dashboard count still comes from
`toolrxSkills.count()`.

### 29. Build spec v3 and compositional generators — done

Extend `buildSpec` to accept multiple mechanics, nested counts, multi-level
structure, long modifier tails, explicit feature lists, and theme plus sub-theme.
Make the generators consume the expanded spec and emit proportionally larger
artifacts: more files and systems, maps larger than 96×96 when requested, more
quests, NPCs, and enemies, and richer `README.md` / `ARCHITECTURE.md`. Everything
stays seeded and deterministic, and respects the step-26 input and step-32 output
budgets.

**Done when** three reference long specs produce the expected file counts,
feature markers, and structural checks; the same seed reproduces the tree
byte-for-byte; and the spec line names every parsed feature.

Landed as `buildSpec` v3: features, per-noun counts (`levels`, `quests`, `npcs`,
`enemies`, `bosses`, `items`, `rooms`, `waves`, `towns`), multi-level defaults,
explicit `N×N` world size, and an optional sub-theme. A request with any of those
gains a real `content.js` module (levels, quests, NPCs, enemies, items) seeded
from the same spec seed, linked before `app.js`, summarised before the footer,
and documented in both README files. `bundleProject` now inlines every
project-local script in document order, so previews need no base URL and new
modules need no bundler change. The RPG template forwards `spec.size` (48–128)
and counts into `toolrxWorldgen.generate`, which trims or grows towns, enemies,
NPCs, and quests deterministically while leaving default worlds unchanged.
`tests/test_skills_js.py` pins the parsed spec, content markers, byte-identical
same-seed trees, the five-file shape of plain builds, count honouring, and
preview inlining.

### 30. Multi-file growth and patch composition — done

Move from single-app skeletons plus named-function patches toward multi-module
layouts (`core/`, `systems/`, `data/`, `ui/`, `content/`, or the engine-specific
equivalent) whose imports work from `file://` and through the preview bundler.
Accept two to five composable patches in one request; each patch sees the previous
file state and the set installs atomically or not at all. Add deterministic
`grow project`, `expand module <name>`, and `add <system>` commands that append
real code and files instead of regenerating. Raise undo depth from 8 to 16,
configurable, while keeping full-file snapshots.

**Done when** a five-patch sequence accumulates, each undo restores the exact
prior state, a growth command adds code without touching unrelated files, and the
preview still runs after each step.

Landed with additive growth under `core/`, `ui/`, `data/`, `content/`, and
`systems/`. Modules are plain scripts (no `import`/`export`) so they load from
`file://`, and `bundleProject` now inlines any project-local script path, nested
or flat. `grow project` adds the four base modules; `expand module <name>` adds
one; `add <system> system` adds a seeded `systems/<name>.js` that registers with
`window.toolrxSystems`. Each growth appends one bootstrap block to `app.js`,
inserts script tags before `app.js`, records paths in `spec.modules`, and appends
rows to README/ARCHITECTURE — no regeneration. The multi-patch command
`add <edit> and <edit>` (two to five known patches, comma or `and`) applies to one
working copy and writes only if every patch fits; one undo reverts the whole
bundle. Undo depth defaults to 16 full-file snapshots and reads
`toolrx.undo.depth` (1–64) from `localStorage`. Tests drive five-step stacks,
atomic failure, growth/undo, nested preview inlining, and the configurable depth.

### 31. Deterministic context and working memory — done

Add an explicit, size-capped context store beyond remember/forget notes: last
result, last plan, active build spec, per-file summary and hash, and a rolling
session plan. Persist it in `localStorage`, serialize it stably, scope it per
project, and expose `what is in context` plus a clear command. Add exact routes
for `continue from previous`, `apply the same changes to the other files`, and
`expand the last plan with …`. Keep it inspectable and printable; context never
enters a network payload.

**Done when** context survives reload, `what is in context` matches the stored
bytes, the cap evicts the oldest entry with a visible note, clearing works, and
cross-project isolation is tested.

Landed as `toolrx/web/context.js`: one `localStorage` key per project plus a
sorted index, entries for `result`, `plan`, `spec`, `edit`, `file`, and
`session`, serialized with sorted keys and a monotonic sequence number rather
than timestamps. The default cap is 8,192 serialized bytes, configurable through
`toolrx.context.cap` (256–65,536); eviction and trimming notes are stored beside
the capped state so the context itself never exceeds the cap. `what is in
context` prints entry bytes and the real stored byte count plus a BLAKE2b hash,
and the Node harness compares that hash against the raw `localStorage` string.
`continue from previous` runs only steps still marked pending and stops at the
first failed step without marking later steps done; `expand the last plan with …`
appends pending steps without executing them; `apply the same changes to the
other files` replays the last recorded patch or bundle per project, all-or-none,
with a separate undo entry for each. Context is scoped per project, survives a
reload, is cleared by `clear context`, and is asserted absent from fetch
payloads.

### 32. Chunked output, progress, and budgets — done

Emit progress events at phase boundaries and at least every ~250 ms or 32 KB of
generation, with a partial file list. Raise per-tool caps deliberately and add a
per-project total byte budget. Support cancellation and timeout that leave the
last good project intact. Report characters, estimated tokens, milliseconds, and
peak size, and mark partial results as partial.

**Done when** a maximum-size build emits at least three progress events, respects
the byte cap, is byte-identical to the non-progress build, and cancellation leaves
the previous project valid.

Landed with `onProgress`, `progress`, `cancelBuild`, `limits`, `budget`, and
`projectBytes` on the sandbox API. Builds emit a `spec` event, per-file `files`
checkpoints (at least every file or ~32 KB), a `bundle` event, and a final
`done` event with `chars`, `tokens`, `ms`, `peak`, and `partial:false`; each
intermediate event carries the partial file list. Write caps are now 128 KB per
file, 512 KB per project, and 32 files (read/cat output stays at 8 KB/24 KB).
`toolrx.project.budget` (16 KB–2 MB) and `toolrx.build.timeout` (250–30,000 ms)
are configurable. A build is generated into memory first, so an over-budget,
cancelled, or timed-out build is refused before any file is written and the
previous project stays intact. The dashboard shows a small `building · n/m
files · KB · partial %` status in the preview pane. Tests build a maximum RPG
(9 files, ~169 KB) and assert six events, a partial list, byte-identical files
with and without an observer, refusal under a 16 KB budget, cancellation, and a
fake-clock timeout.

### 33. Argument extraction and long-form content — done

Improve `extractArgs` for multi-sentence content, fenced blocks, indented lists,
quoted blocks, and multiple paths. Support `write the following into <file>:` by
capturing until the end of input or an explicit terminator, sanitized and capped,
with an exact round-trip inside the cap. Add deterministic summarizers and
extractors (`summarize text`, `extract headings`, `first N lines`, `outline`,
`table from …`) that can feed a next step through `prev`. Keep traversal and
injection fixtures for block capture.

**Done when** a long block round-trips byte-exact under the cap, an over-cap block
is refused rather than silently cut, traversal and injection fixtures are
rejected, and summarizers are reproducible.

Landed with `toolrx/blocks.py` (Python) and `blockCapture` in `skills.js`
(browser). A block write bypasses plan splitting and the command matcher,
preserves case, punctuation, and indentation byte-for-byte, and is capped at
8,000 bytes; an over-cap block is refused, never truncated. The target path is
still relative, traversal-free, and extension-checked, and the body is checked
for NUL bytes and injection patterns. Python returns a pending `file.edit`
(dry-run until confirmed); the browser writes through `ctx.fs.write`. Fenced,
triple-quoted, and multi-sentence arguments are extracted verbatim, and the
multi-path assignment order is fixed so `path_a`/`path_b` match the query order.
`text.headings`, `text.outline`, `text.firstlines`, and `text.table` read a
file or the previous step and are deterministic. The command catalog is now
12,502 routes.

### 34. Vocabulary, knowledge, and centroid scaling — done

Expand `knowledge/*.md` and the derived vocabulary and centroids so longer, more
varied phrasings keep high-confidence routes and healthy margins. Add
multi-centroid or hierarchical tool families (coarse family → fine command) only
where measurements justify the extra complexity. Keep rebuilds pure Python and
fast, and keep the model within a defined size budget.

**Done when** a rebuild stays under 2 seconds on the reference machine, the model
stays within 1.5× its current size, long-prompt accuracy meets the step-35
threshold, and margins are reported and non-degenerate.

Landed by expanding all 27 `knowledge/*.md` documents with longer phrasings plus
focused disambiguation for the near neighbours (`fs.read_file`/`fs.inspect_dir`,
`net.cfg_gen`/`net.cfg_check`, `net.lab_topo`/`net.lab_topo_apply`,
`net.lab_link`/`net.lab_state`, `net.lab_down`). Routing stays one centroid per
tool: the measured 109-case suite is 109/109 with minimum margin 0.019, p10
0.048, and median 0.126, so multi-centroid routing is not yet justified. The
in-process rebuild takes about 1.3 s, and the model is 469 KB (1.30× the 352 KB
baseline, below the 1.5× cap). `tests/test_router.py` now pins rebuild time,
model size, long-prompt accuracy, and the non-degenerate margin floor.

### 35. Long-input / long-output test suite and observability — done

Create a dedicated fixture suite: at least 20 prompts of 500–2,000+ characters,
multi-step plans, complex build specs, and five-patch sequences, each with
expected structural output. Measure routing confidence and margin, plan
completion, refusal correctness, generation time, bytes and file counts, and undo
fidelity. Surface the last run in the dashboard next to the existing `tok/s`, and
gate every earlier step's **Done when** criteria in CI. Document the real envelope
in the README and in the dashboard's honest-limits copy.

**Done when** the suite runs in `python3 -m unittest discover -s tests` plus the
Node harness, fails on regressions, the dashboard shows the last-run metrics, and
the README lists the actual limits.

Landed with `tests/fixtures/longform.json` (27 routing prompts of 541–635
characters, five plans, four refusal cases), `tests/test_envelope.py` for
routing/plan/refusal assertions, and `tests/test_envelope_js.py` for a complex
build spec and a five-patch sequence undone five times byte-exactly. The sandbox
records `chars`, `steps`, `errors`, `via`, `confidence`, `margin`, `ms`, `bytes`,
`files`, `undo`, and `ok` for the latest prompt, persists it under
`toolrx.lastRun.v1`, clears it on reset, and exposes it as
`toolrxWeb.lastRun()`. The dashboard renders it in the `last run` chip above the
preview and refreshes it after every prompt and on load. The overall test count
is 270 (Python + Node harnesses), and the full suite runs offline.

Start the fixture harness with step 26 so every step lands with measurements, even
though step 35 closes the batch.

## Next batch: hardening the long-form envelope (steps 36–45)

Steps 26–35 proved that longer input and larger output work. This batch makes the
promise durable: every cap has one source, every long request has a measured
budget, continuation survives failure and switching projects, and the demo,
tests, docs, and pitch all report the same numbers. The deterministic path stays
first and the LLM adapter stays optional and off.

### Target envelope (v2)

The v1 table is the contract for input, plans, projects, undo, and context. The
v2 table adds the budgets and observability that steps 36–45 must pin. Values are
defaults; every one is configurable within a stated range and printed by `help`,
`limits`, and the plan preview.

| Dimension | v2 target |
| --- | --- |
| Single-route input | 2,000 chars |
| Plan input | 8,000 chars / 40 steps |
| Per-step wall time | 4,000 ms default, 250–30,000 ms |
| Plan wall time | 60,000 ms default, refuses before running when the plan cannot fit |
| Project files | 32 files |
| Project text | 512 KB total |
| Undo snapshots | 16 default, 1–64 |
| Context store | 8 KB serialized, cap visible, eviction notes |
| Block capture | 8,000 bytes, over-cap refused not cut |
| Long-form suite | 48–80 prompts of 500–8,000 chars |
| Workspace bundle | versioned JSON, round-trips byte-exactly, size-capped |

### 36. Hard output budgets and progressive delivery — done

Enforce a per-step wall-clock cap and a plan-level wall budget in addition to the
existing per-file, per-project, and per-build caps. Every step (route, build,
patch, growth, or continuation) starts under the same budget object and ends with
a named success, refusal, timeout, or cancellation. Large builds and worldgens
keep emitting progress at phase boundaries and at least every ~250 ms or 32 KB.
Plan preview reports the active limits and whether the plan fits before anything
runs; the final report reports bytes, files, steps, elapsed time, and headroom for
each cap. A failed step stops the plan and leaves the last good project intact.

**Done when** a plan that would exceed the plan wall budget is refused at preview
time with the limiting cap named, a step that exceeds its cap is reported as
`timeout` without writing files, a maximum-size build still emits at least three
progress events and is byte-identical to the unobserved build, the final report
shows headroom for files, bytes, and time, and the dashboard renders the same
numbers.

Landed with a 4,000 ms per-step cap (`toolrx.step.timeout`, 250–30,000 ms) and
a 160,000 ms plan cap (`toolrx.plan.timeout`, 250–600,000 ms). The default plan
cap equals 40 steps × 4,000 ms, so every valid plan fits its worst case; a lower
configured cap refuses at preview time with the cap named. `planPreview` and
`toolrxWeb.planPreview()` report chars, steps, per-step time, plan time,
worst-case time, project file/byte headroom, and `fits`. A step that overruns is
reported as `budget.timeout` and stops the plan; the Python runner reports the
same `report.budget` shape, including remaining milliseconds, and stops before a
step when the plan wall budget is exhausted. `recordRun` now writes
`budget.files/bytes/ms/steps/chars` with used, max, and remaining values plus a
`within` flag and `over` list. The dashboard `last run` chip shows remaining
room and its title shows used/max per cap. `tests/test_budgets.py` drives a slow
step, a too-small plan budget, a full 40-step preview, and a built project's
headroom.

### 37. Long-form test suite v1 — done

Expand the step-35 fixtures into the source of truth for long input and output:
48–80 prompts between 500 and 8,000 characters, grouped into single-route
descriptions, connector and numbered plans, long build specs, multi-module
growth with two-to-five patches, context continuation, and edge/refusal cases.
Each fixture declares its family, expected plan structure, step count,
confidence and margin floors, expected files or markers, undo depth, and context
assertions. The Python and Node harnesses read the same fixture file and assert
the same structural outcomes.

**Done when** at least 48 fixtures span every family, at least six exceed 4,000
characters, every fixture asserts plan structure and outcome, routing floors are
non-degenerate, refusal fixtures fail before execution, context fixtures prove
isolation and continuation, and the suite runs offline in
`python3 -m unittest discover -s tests`.

Landed with `version: 2` in `tests/fixtures/longform.json`: 58 cases — 33
routing (six over 4,000 characters), six plans (one 4,111-character numbered
eight-step plan and one 2,999-character single-route plan chunked into two
steps), eight builds, four growth scenarios, three context scenarios, and four
refusals. Each family declares `minChars`, and routing/plans carry confidence
and margin floors (0.50/0.02 and 0.35/0.02). The six long routing prompts route
correctly at 0.54–0.66 confidence; plan steps stay at or above 0.383 confidence
and 0.081 margin. Builds are single-sentence, 561–671 characters, and produce
byte-identical file maps twice. Growth covers `grow project` (four module
files), `expand module content`, two sequential `system.add` installs, and a
two-patch bundle; every case undoes byte-exactly. Context proves a failed middle
step stays `error` while `continue from previous` runs only the pending suffix,
`expand the last plan with …` appends a pending step, and a second project never
sees the first project's files or edits. `tests/test_envelope.py` checks the
contract, routing, plans, and refusals; `tests/test_envelope_js.py` executes
builds, growth, and context in the real in-tab sandbox and keeps the step-35
complex build and five-patch undo regressions.

### 38. Unified limit source of truth — done

Replace the duplicated constants in `security.py` / `policy.json`, `longform.py`,
`blocks.py`, `executor.py`, `skills.js`, and `sandbox.js` with one checked-in
configuration (`toolrx/limits.json`) plus loaders on each side. Security policy
keeps its allowlists and denied patterns; numeric envelopes move to the shared
file. Python imports the loader, the browser fetches the same JSON, and tests
assert that every runtime limit equals the configured value. `help`, `limits`,
`toolrxWeb.limits()`, and the plan preview print the active envelope and its
source. A drift test fails if any duplicated constant reappears.

**Done when** all numeric envelopes are defined once, both runtimes expose the
same values, no duplicated limit constant remains outside the loader and tests,
`limits` prints the active table, and changing one value in the JSON changes both
the Python and browser behaviour in tests.

Landed with `toolrx/limits.json` version 1 as the only numeric envelope: 15
keys covering single-route and plan characters, plan steps, block bytes, step
and plan milliseconds, project file/project/file-count caps, build time, read
caps, context bytes, undo depth, and chat output. `toolrx/envelope.py` validates
each value against a declared range, `toolrx/gen_limits.py` renders the frozen
`toolrx/web/limits.js`, and `tests/test_limits.py` fails if the generated file
is stale, if the two runtimes disagree, or if a private literal reappears.
`security.py` now reads the envelope and `policy.json` keeps only allowlists,
denied patterns, hosts, and vocabulary. `longform.py`, `blocks.py`,
`executor.py`, and `pipeline.py` read the same loader; `skills.js`, `sandbox.js`,
and `context.js` read `root.toolrxLimits` and refuse to load without it.
`limits` and `show limits` print the source-aware table (12,504 catalog
patterns). One honest behaviour change: Python `fs.cat_all` now uses the same
24,000-character total cap as the browser instead of its old private 120,000.

### 39. Context and plan continuation hardening — done

Make `continue from previous`, `expand the last plan with …`, and cross-file
replay safe under truncation, partial failure, plan editing, and project
switches. Add `context snapshot` and `diff against previous context` commands
that show a stable, sorted diff of entries, bytes, and pending steps. A
continuation must never mark a failed or skipped step as done, must not leak
context across projects, and must say when a stored plan was truncated or
evicted. Keep the visible byte cap and eviction notes.

**Done when** snapshot and diff outputs are deterministic and match the stored
bytes, continuation after a failed middle step runs only the pending suffix,
switching away and back restores the same pending plan without duplication,
truncated and evicted plans report it explicitly, and context payloads never
enter a network request.

Landed with `context snapshot` and `diff against previous context` (12,516
catalog patterns). A snapshot is stored per project beside the context under
`toolrx.context.v1.<slug>.snapshot` and records sorted entry shapes (kind, key,
seq, bytes, sha), stored bytes and sha, pending plan steps, and eviction notes;
it is not a context entry and never touches the network. The diff lists added,
removed, and changed entries in kind/key order, the entry and stored byte
deltas, and the pending step delta. A dedicated `.plan-note` marker keeps the
last trim or eviction of `plan/last` after the general three-note ring has moved
on, so continuation and expansion say `the stored plan was trimmed/evicted …
rebuild the plan, then continue` instead of claiming there is no plan. Expansion
now uses the active `planSteps` envelope instead of a literal 40. Tests cover a
stable snapshot, a no-change diff, a pending-step diff, a project switch with no
duplicated steps, an evicted plan, and a trimmed plan; the network guard still
shows no context payload in any request.

### 40. Richer multi-module skeletons and system libraries — done

Grow the additive module surface with reusable, seeded system templates:
inventory, dialogue, combat, save/load, quests, crafting, UI panels, and audio
cues at minimum. Each system is a real named file under `systems/` (or the
engine-specific equivalent), registers through `window.toolrxSystems`, and
appends its bootstrap, README, and ARCHITECTURE rows without regenerating the
project. One long prompt may request and compose several systems at once; the
whole set installs atomically under one undo entry and respects the project
budgets. Shared engines stay plain scripts that load from `file://`.

**Done when** at least eight systems exist with seeded, reproducible output, a
single prompt can add three or more at once, each adds real code and files, the
preview still runs, one undo removes the whole bundle, repeated adds are
idempotent, and the project stays inside the v2 file and byte caps.

Landed with eleven systems: `inventory`, `dialogue`, `combat`, `save`,
`quests`, `crafting`, `ui`, `audio`, `weather`, `particles`, and `ai`. Each is a
real plain script under `systems/`, seeded from the project spec plus the system
name, and registers one API with `window.toolrxSystems`; the same prompt and
seed produce byte-identical files. Behaviour is real rather than a stub:
inventory counts, dialogue turns, combat damage, a localStorage/memory
save/load round trip, quest progress, crafting costs, DOM panels (guarded when
there is no document), WebAudio cues (silent fallback), a weather cycle, a
particle pool, and a small AI state machine. `add inventory and dialogue and
save systems` installs any two or more named systems in one atomic grow: the
script tags are inserted before `app.js`, README and ARCHITECTURE rows are
appended, the spec records the system list, and one undo entry removes the
whole bundle. A repeated bundle reports `already grown` and rewrites nothing;
a partial overlap adds only the missing files. The preview inlines the systems,
so it still runs from `file://`, and the full set stays well inside the 32-file
and 512 KB caps. `tests/test_skills_js.py` covers the bundle, registry
behaviour, idempotence, partial overlap, deterministic bytes, preview inlining,
and undo; `tests/fixtures/longform.json` gains a three-system growth case, and
the catalog reached 12,522 patterns before step 41 removed the dead literals.

### 41. Command-library quality pass and coverage metrics — done

Audit the command catalog for redundancy, near-duplicate regexes, low-margin
collisions, and gaps on long compositional prompts. Generate a deterministic
coverage report that maps every long-form family to exact-match, router, and
fallback shares, and to the confidence and margin distribution. Remove or merge
only patterns that measure as low signal; add only patterns that close a measured
gap. Counts and coverage derive from the generated catalog, never hard-coded.

**Done when** the catalog regenerates byte-identically with no duplicate ids or
whitespace-insensitive duplicate regexes, the coverage report is reproducible and
lists every fixture family, no long-form family falls to chat fallback, the
minimum margin stays above the step-34 floor, and additions are justified by the
report rather than by volume.

Landed with `toolrx/coverage.py` and the checked-in `toolrx/coverage.json`.
`python3 toolrx/coverage.py` prints the table, `--write` refreshes the report,
and `--check` exits non-zero when the catalog or fixtures drift. The catalog is
11,248 commands with 6,567 pure literals, 0 duplicate ids, 0 duplicate
whitespace-insensitive regexes, and 0 dead literals. The 1,080 removed
`build.compose.feature.*` entries were pure literals already matched by the
general `build.variant.*` pattern, so removing them changes no input; the
remaining compose entries cover the three genre aliases that are not standalone
build kinds. Pronoun text commands are now declared before the generic
`reverse {text}` family, `what weekday is it` is a target-free date command,
`what is my current project` reads project memory, and `who are you` is chat
identity rather than a duplicate `misc` command. `tests/test_commands.py` now
normalises escaped spaces in its uniqueness check and asserts the target-free
text commands; `tests/test_coverage.py` checks reproducibility, lane arithmetic,
the zero-fallback and margin floors, the dead-literal audit, and that the prefix
index returns the same first match as a full scan. Coverage over the six
families: routing 33 router / 0 fallback, plans 38 router / 0 fallback, builds
8 exact, growth 12 exact, context 11 exact + 3 router / 0 fallback, refusals 4
refusal. Minimum routing margin 0.027, plan margin 0.082, context margin 0.025,
all above the 0.019 step-34 floor. The catalog floor in `test_commands.py` moves
from 12,000 to 11,000 so the test guards regressions without demanding that
unreachable patterns return.

### 42. Observability dashboard for long runs — done

Extend `lastRun()` into a long-run record: plan length, steps executed and
failed, per-step `via`, `ms`, confidence, margin, and bytes, the confidence and
margin distribution, peak context bytes, total bytes written, files touched, undo
depth, and headroom for files, bytes, and time. Persist it beside the current
record, clear it on reset, and render it in the preview pane so "what just
happened on that long prompt" is readable without opening the console. Keep the
one-line chip and add an expandable detail view.

**Done when** every field is populated for a multi-step, multi-module run,
per-step timings sum to the reported total within the measurement tolerance,
headroom matches the active limits, the detail view renders from the stored
record after reload, reset clears both record and view, and the Node harness
asserts the fields rather than the markup.

Landed with `recordRun` v2 in `toolrx/web/sandbox.js` and the expandable
`#lastRunDetail` panel in `toolrx/dashboard.html`. The record is schema v2 and
adds `planned`, `executed`, `failed`, `written`, `emitted`, `filesTouched`,
`contextBytes`, `peakContextBytes`, `stepsDetail`, `distribution`, and
`budget.context`; the scalar `confidence` and `margin` stay as the minimum of
their distribution so the one-line chip keeps working. The workspace snapshot
is taken before the prompt, so touched files are a real diff rather than a
guess, and written bytes come from the project-size delta. `skills.js` tags each
result with `planLength` so a truncated or budget-stopped plan still reports
what it intended to run. `tests/test_budgets.py` runs a routed two-step plan
through the real model and asserts per-step parity with the results, the
distribution ordering, and the context cap; `tests/test_skills_js.py` runs a
multi-file growth and a two-patch plan and asserts touched files, written and
emitted bytes, and per-step fields. Both harnesses read the record, not the
markup; the dashboard renders from the same stored record.

### 43. Project portability and workspace bundles — done

Finish project export/import and add a versioned workspace bundle containing
multiple projects, per-project context, the active plan, and the relevant
settings. A project package exports the plan, the resulting file map, the seed,
and the limits so the run is reproducible; an import validates version, schema,
paths, and budgets before writing. Round-trips are byte-exact for files and
stable for context. Unknown versions, traversal paths, oversized bundles, and
duplicate slugs are refused with a named reason. No account and no network.

**Done when** a workspace with at least three projects round-trips byte-exactly,
context and the active plan survive the round-trip, a single-project package
reproduces the same files from its seed, unknown or oversized bundles are
refused before writes, traversal paths are rejected, and import leaves the
existing workspace intact on any failure.

Landed with `toolrx.project` v2 and `toolrx.workspace` v1 documents in
`toolrx/web/sandbox.js`. A project bundle carries `slug`, `name`, `kind`,
`desc`, `created`, `updated`, `spec`, `seed`, `files`, `plan`, and `context`
plus the `limits` envelope and the four operator `settings`
(`projectBytes`, `undoDepth`, `stepMs`, `planMs`); a workspace bundle carries
the same payload for every project and the active slug. Legacy v1 documents
still import. Validation runs entirely before writes: unknown formats and
versions are named (`unsupported toolrx.project version 9 (this build reads
1–2)`), file names must be plain (`refused "../../evil.txt": project files must
be plain names, not a folder path`), files are capped at 128 KB, projects at
32 files / 512 KB, plans at 40 steps, and bundles at the new
`bundleBytes` = 2 MB in `limits.json`. Workspace imports refuse duplicate slugs
inside the bundle and against the existing workspace, then write through a
snapshot and restore on any failure, including a storage read-back check.
Exports are saved in the tab under `toolrx.bundles.v1` (kept across `reset`)
and downloadable from Projects; `importBundle` dispatches on `format`, so the
picker accepts either kind. A package carries its files byte-exactly rather
than regenerating them; the seed travels with them so the same build can be
repeated. Commands: `export this project`, `export the
workspace`, `import the project from <bundle>`, `import the workspace from
<bundle>`, `list bundles`. `tests/test_sandbox_js.py` proves a three-project
round-trip with byte-exact files, stable plan and context, restored active slug
and settings, the all-or-none rollback, every named refusal, and the
named-bundle lifecycle; `tests/test_skills_js.py` runs the chat path.

### 44. Deterministic summarizers and extractors for long intermediates

Extend the step-33 text family with exact, offline tools for long intermediate
results: extract lists, key facts, file outlines, and diff summaries, alongside
the existing `summarize`, `headings`, `outline`, `firstlines`, and `table`.
Each accepts a file or the previous step, caps its input and output explicitly,
handles empty and short input honestly, preserves source order where it matters,
and produces byte-identical output for the same input. A summarizer result can
feed the next step without a model.

**Done when** at least four new extractors exist, each is deterministic across
runs, input and output caps are named and enforced, empty and short inputs return
a clear message rather than a crash, two-step chains consume the previous result,
and fixtures pin every output byte.

### 45. End-to-end long harness demo and pitch refresh

Ship a reproducible long-prompt demo that runs fully offline: one 3,000–6,000
character request that becomes a verified plan, builds a multi-module project,
composes several systems, applies a multi-patch bundle, continues from context,
and finishes with an exact undo. The demo emits a transcript with the active
limits, per-step decisions, confidence and margin, bytes and files, timings,
headroom, and context snapshots. Update `README.md`, `docs/pitch.html`, and the
dashboard copy from measured values; no number ships without a test or a
regenerated report behind it.

**Done when** the demo runs offline in the suite and as a documented command,
the transcript is reproducible byte-for-byte apart from timings, every demo
assertion passes, the pitch and README numbers match the report, and a live
GitHub Pages smoke of the same path passes with no severe console errors.

## Order

1. 12 (spec) → 13 (2D engine) → 15 (3D engine) — done
2. 16 (RPG world) → 17 (themes/titles) → 18 (library) → 19 (patches) — done
3. 21 (archive catalog) → 22 (language recognition) → 23 (archive search) →
   24 (localized intents) → 25 (Library panel) — done
4. 20 (LLM adapter) — done; 14 (sprites) deferred until a licence-compatible
   subset is pinned
5. 26 (ceiling) → 27 (hierarchical routing) → 28 (catalog) → 29 (build specs) →
   30 (project growth) → 31 (context) → 32 (output budgets) → 33 (argument
   capture) → 34 (vocab/centroids) → 35 (gate) — done
6. 36 (budgets) → 37 (suite) → 38 (limit source) → 39 (continuation) →
   40 (systems) — done; 41 (coverage) → 42 (observability) → 43 (workspaces) →
   44 (extractors) → 45 (demo) — planned
7. Step 14 stays independent; it can land whenever the sprite subset is chosen.

Steps 36–37 come first because they define the budget and the gate every later
step measures against. Step 38 lands immediately after so no new limit is added
to two places. Steps 39–44 may be reordered within the batch if a measurement
justifies it; step 45 is last.

## Open questions

- Step 14 source is known: `huggingface.co/datasets/Angais/pixel-art-atlas-1.4m`,
  CC0-1.0, native 16×16 RGBA. Vendoring a pinned subset with a manifest and
  checksums is deferred; procedural sprites remain the fallback.
- The v1 envelope is settled by the step-35 measurements: 2,000 / 8,000 / 40
  steps, 32 files, 512 KB, 16 undo, 8 KB context. v2 changes only from step-37
  evidence, never from optimism.
- Caps stay in the shared config, not in the Command Center. The Command Center
  may display them; changing them stays a file edit with a restart.
- Plan quality is scored by completion rate, the confidence floor, refusal
  correctness, and margin, all reported by the suite. No weighted single score.
- Context is per project and survives a project switch; cross-project payloads
  are never merged.
- Multi-file patches install atomically only. The LLM path may stage a pending
  diff; the deterministic path does not.
- 3D leads with low-poly WebGL and a Canvas/isometric fallback (decided).
- Steps 11–13, 15–40 are complete. 14 remains deferred. Steps 41–45 are
  planned; none of that subset is started.
- Which defaults should v2 change, if any: keep 2,000 / 8,000 / 40 / 32 files /
  512 KB, or raise one dimension at a time from measurements? Raise only after
  the step-37 suite proves the margin.
- Should workspace bundles include the whole settings object or only project,
  context, plan, and limits? Include only what affects reproduction.
- Should the coverage report ship as a generated file in `docs/` or stay a test
  artifact? Ship it once step 41 proves the format is stable.
