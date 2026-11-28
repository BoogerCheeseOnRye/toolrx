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
Steps 46–59 shipped as everyday language became a measured surface, the
envelope became a visible bar with explicit compaction, and thinking became its
own deterministic program. Steps 60–69 are the locked next batch: deeper
everyday and domain language, deterministic explain and verification helpers,
richer starters, one bounded pure-compute tool, a workspace journal, dashboard
events with replay and export, plan macros, accessibility polish, and a public
evaluation and comparison kit. Steps 70–79 then grow the worlds into editable,
chunked, shareable documents with simple deterministic agents. The LLM stays
optional and off by default.

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
4. **Assets are procedural and seeded.** Sprites, tiles, palettes, and names
   derive from the build seed. There is no vendored asset pack and no runtime
   network; a project is reproducible from its seed and files alone.
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

### 44. Deterministic summarizers and extractors for long intermediates — done

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

Landed as `text.list`, `text.facts`, `text.code`, and `text.diff` in
`toolrx/web/skills.js`, with 65 command patterns in `toolrx/build_commands.py`
(catalog 11,334). `extract the list` returns bullet, numbered, and checkbox
items in source order; `extract the key facts` takes the first sentence of each
prose paragraph and skips headings, lists, tables, and fenced code; `outline the
code` lists `function`, `class`, arrow, and `def` declarations as they appear;
`diff a and b` walks a line-level LCS (common prefix and suffix trimmed first)
and prints added/removed/unchanged counts plus the changed lines. Every
extractor reads a literal, a file path, or the previous step through
`resolveText`, so a facts result can feed the list extractor with no model.
Three caps joined `limits.json`: `extractChars` = 8,000 (input),
`extractItems` = 200 (output lines), and `diffLines` = 400 (per side).
Truncation is printed with the exact numbers, an over-long diff throws
`the diff is capped at 400 lines per side (left has 401)`, and empty or
marker-free input returns a sentence instead of an empty string.
`tests/fixtures/extractors.json` pins every output byte;
`tests/test_extractors_js.py` checks determinism, both caps, the diff refusals,
the empty/short replies, and the two-step chain; `tests/test_commands.py` pins
routing, arguments, and that `outline notes.md` still means headings.

### 45. End-to-end long harness demo and pitch refresh — done

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

Landed as `toolrx/demo_request.txt` (3,367 characters, 32 steps),
`toolrx/demo_harness.js` (the real browser modules in Node with a fake catalog
fetch, no server/browser/model), `toolrx/demo.py` (`--write`, `--check`, and a
measured transcript), and the checked-in `toolrx/demo_report.json`. The request
builds a 22-file shooter, grows the four modules and eleven systems, applies a
five-patch bundle in one step, reads the generated files through the step-44
extractors, expands the stored plan with one pending step, continues it from
context, and undoes it byte-exactly. The report normalizes `at`/`ms` (including
the build line's elapsed milliseconds) and re-pins each step's byte count and
sha; two runs produce identical JSON. `tests/test_demo.py` checks the plan
envelope, every step's deterministic `via`, the project shape, the bundle, the
continuation, the exact undo, the shared limits envelope, and the README/pitch
numbers. Two robustness fixes came out of the demo: title, theme, toggle,
footer-note, and project-file writes now push one undo snapshot like patches
already did, and `context.expand`/`context.continue` no longer store their own
plan listing as `result/last`, which used to evict the plan they had just
edited.

## Harness roadmap 3 — everyday language, visible budgets, deterministic thinking (steps 46–59)

Steps 46–59 extend the same deterministic surface in three phases. First the
system learns how people actually talk: paraphrase tables, conversational
repair, and a measured everyday-language family. Then the envelope becomes
visible: a live budget bar, explicit compaction, and a budget-aware plan
rewrite. Finally thinking becomes a first-class program: a deterministic
`think` skill, bounded self-critique, and reasoning traces that live in
context. The optional LLM adapter stays off and none of these steps may
require it.

### Design rules for this phase

1. **Language is data.** Synonyms and paraphrase families live in checked-in
   tables that feed both the exact matcher and the hashed router. They are
   rebuilt, diffed, and tested like the command catalog.
2. **Compaction is visible.** Nothing is dropped or summarized silently: every
   compacted entry is named with its bytes and reason, and the stored plan
   survives.
3. **Thinking is a program.** `think` and the critique loop have fixed inputs,
   bounded passes, structured output, and no hidden state or network call.
4. **Budgets are shown before and during work.** Characters, steps, context,
   project bytes, and time each have a numeric read-out and a filling bar.
5. **No new limit ships in two places.** Every cap joins `limits.json` and is
   read by Python and the browser.
6. **Everyday does not mean fuzzy.** A natural phrasing either maps to an exact
   command or gets an honest refusal naming the closest supported action.

### 46. Everyday paraphrase layer — done

Teach the catalog the intents people use most — builds, edits, file operations,
math, context, growth, and extractors — in the way people actually type them:
casual variants, synonyms, incomplete sentences, and reordered clauses. Keep
the positive allowlist, metacharacter rejection, and bounded arguments. The new
phrasings are generated from data and reviewed as one catalog diff, not added
as one-off regexes.

**Done when** at least 500 new high-signal phrasings cover ten everyday
families, `tests/fixtures/everyday.json` pins every phrasing, at least 90% of
the fixture set resolves to an exact command with no chat or router fallback,
the catalog rebuild is reproducible with zero duplicate ids and zero duplicate
regexes, and the README/pitch catalog count is regenerated from the build.

Landed with 541 phrasings across ten families (`build`, `edit`, `growth`,
`context`, `projects`, `math`, `extract`, `text`, `memory`, `system`). One
checked-in table, `toolrx/everyday.py`, feeds both the catalog and
`tests/fixtures/everyday.json`; `build_commands.py` appends it last so every
original exact form still wins. The catalog is 11,875 patterns. The fixture
runs through the shipped first-match order: 541/541 resolve to their own
`everyday.*` command with exact arguments, with zero chat/router fallbacks,
zero shadowing, and zero duplicate ids or regexes. Two ordering rules keep it
honest: specific text transforms precede the generic `reverse {text}`, and
`work out …` stays with the existing `math.expr` route instead of duplicating
it. `tests/test_everyday.py` fails on fixture drift, a family below 30 cases,
a table/catalog mismatch, a shadowed case, or a README/pitch count that no
longer matches the build; its Node harness runs the same 541 through the real
browser `planPreview` and gets 541 exact hits.

### 47. Conversational glue and soft intents — done

Handle greetings, acknowledgements, corrections, confirmations, and short
multi-turn repair deterministically. `no, I meant …` and `actually make it …`
must revise the previous action or ask one bounded clarifying question; a
confirmation applies only the pending action and never re-runs a build.
Conversation memory stays small, capped, inspectable, and local.

**Done when** corrections, confirmations, and repairs have exact routes with
fixtures; an ambiguous confirmation changes nothing and says what it needs; the
conversation-memory cap is explicit; and the same transcript produces the same
replies on every run.

Landed with 55 exact routes across seven kinds (`confirm`, `reject`, `correct`,
`repair`, `ack`, `show`, `clear`) in `toolrx/conversation.py`, feeding both the
catalog and `tests/fixtures/conversation.json`. The previous turn lives beside
facts and notes in the same local memory and is capped by two new envelope
keys: `conversationTurns` (12) and `conversationBytes` (4,096). `show
conversation` prints both caps, the stored bytes, the dropped-turn count, the
last action, the pending action, and every retained turn; `clear conversation`
resets only that state. `no, I meant …` and `actually …` either revise the last
action immediately (`no, I meant 13 plus 30` → 43) or, for a build, stage one
action and ask a single yes/no. A confirmation runs the staged action at most
once and never repeats the previous build; a second `yes`, or a `yes` with
nothing staged, changes nothing and says so. An unmappable correction asks one
bounded question and leaves the project untouched. `tests/test_conversation.py`
pins the fixture, the exact routes, the once-only confirmation, the ambiguous
cases, the caps, and a byte-identical replay of the same transcript. The catalog
is 11,987 patterns.

### 48. Synonym and paraphrase tables — done

Move everyday variation into explicit data: a checked-in synonym/paraphrase
table keyed by intent, consumed by the exact matcher and by centroid
generation. Rebuild the model from the expanded knowledge, and measure margin
on a fixed natural-language prompt set before and after.

**Done when** the table is the only source of paraphrase expansion, the router
rebuild consumes it, the fixed prompt set shows no lower median margin and a
higher exact-hit rate, and the table round-trips through a deterministic
export.

Landed with one checked-in table, `toolrx/paraphrase.json`: 25 intents, 57
expanded exact routes, and 52 knowledge lines. `toolrx/paraphrase.py` validates
the table, expands synonyms in table order, feeds `build_commands.py`, and
exports `tests/fixtures/paraphrase.json`; `builder.py` appends each tool's
`knowledge` lines before the centroid is built, so the exact matcher and the
hashed router consume the same data. The catalog is 11,987 patterns and the
model is 494,381 bytes, under the 541,042-byte cap. A fixed 32-prompt set
(`tests/fixtures/paraphrase_eval.json`) measures both lanes: exact hits go
0/22 → 22/22, router hits 9/10 → 10/10, and the router-lane median margin rises
from 0.1511 to 0.2247. The validator refuses an unknown placeholder, a repeated
capture, an unknown tool, an out-of-range capture, an unused capture, a phrase
duplicated across intents, and an over-long knowledge list. `--check` fails on
fixture drift, and `--measure` rebuilds the baseline and expanded models in
separate temporary directories so one build cannot overwrite the other.

### 49. Everyday-language coverage dashboard — done

Add an `everyday` family to `coverage.py` and the coverage report. Track exact
hits, router hits, chat fallbacks, refusals, and the confidence/margin
distribution per family. Surface the same numbers in the command center or a
small dashboard panel.

**Done when** `coverage.json` carries the new family with lane counts and
margin buckets, `coverage.py --check` fails when the fixture set or thresholds
drift, the dashboard shows the same numbers, and no everyday case is counted
twice.

Landed with an `everyday` family built from the 541 everyday phrasings and the
32-prompt paraphrase evaluation set, deduplicated by normalized query so a
repeated case fails the build instead of inflating the score. The family reports
573 cases: 563 exact (541 everyday plus 22 paraphrase-exact), 10 router-lane
paraphrase prompts, 0 fallbacks, and 0 refusals; the router-lane margin is min
0.025 / median 0.225 / max 0.403, and every case resolves to its expected lane
with the expected op and arguments. `coverage.json` carries the per-subfamily
lanes, the confidence and margin distributions, the declared floors (exact ≥
98%, router hits ≥ 90%, zero fallback, minimum margin ≥ 0.019), and a summary
that says whether the measurement meets them. `coverage.py --check` fails on
fixture or threshold drift. The Command Center's Language coverage panel reads
the same `web/coverage.json` shipped by `docs/build.py` and renders the report's
own lanes, subfamilies, margins, and summary, so the dashboard cannot recompute
a friendlier version; the local server serves the same file at
`/web/coverage.json`. `tests/test_coverage.py` pins the deduplication, the
subfamily arithmetic, the summary, and the threshold-drift refusal.

### 50. Visual budget bar — done

Extend the existing context bar into a live envelope bar for the plan preview
and the running plan: characters, steps, context bytes, project bytes, and
time headroom. Each segment shows used/max, a fill bar, and warning/limit
colors. The numeric read-out stays visible; the bar is an addition, not a
replacement.

**Done when** the preview and the last-run detail show all five budgets with
accessible labels, the bar updates while steps run, a limit crossing is
announced in text as well as color, and the DOM harness asserts the numbers
match the report.

Landed with one pure model, `toolrx/web/budget.js`: `toolrxBudget.bars()` turns
a `{used, max}` pair for characters, steps, context bytes, project bytes, and
time into labelled descriptors with a formatted read-out, remaining room, a
ratio, and `ok`/`warn`/`over` levels (warn at 80%). Every maximum comes from
`toolrxLimits`, which is generated from `toolrx/limits.json`; the module owns
no cap of its own. `skills.planPreview` now attaches all five bars, using the
active project bytes and stored context bytes supplied by
`sandbox.planPreview`, and `recordRun` attaches the same five bars to the
last-run report. The composer renders them as five progress bars with visible
numeric read-outs and `role="progressbar"` plus `aria-valuemin`,
`aria-valuemax`, `aria-valuenow`, and `aria-valuetext`; the expanded last-run
detail repeats them beside the exact room numbers. A visually hidden
`role="status"` region announces "budget limit crossed · …" once per crossing,
so color is never the only signal. Multi-step plans emit a `plan` progress
event before the first step and after each one, so steps and elapsed time move
while the plan runs; single-step builds keep their existing progress sequence.
`tests/test_budget_bar.py` drives the real modules in Node and compares every
bar number with the preview and last-run reports, then compares the caps with
the Python envelope.

### 51. Deterministic compaction engine — done

Add explicit context compaction. Keep the active plan, build spec, last N
results, and critical file hashes; summarize older results with the step-44
extractors; drop low-value session notes first. Every action records what was
compacted, its bytes, and why. Add `compact context` and an automatic trigger
before the byte cap.

**Done when** compaction is byte-identical across runs, the plan and spec
survive, every dropped or summarized entry appears in the notes, automatic
compaction never evicts the active plan, and the cap stays enforced.

Landed with one fixed policy order in `toolrx/web/context.js`: summarize older
session rows while keeping the newest `contextKeep` (4), summarize
`result/last` through the step-44 `keyFactsOf` extractor, drop `session`,
`result`, and `edit`, drop non-critical files, then critical files
(`index.html`, `app.js`), then trim the largest remaining entry. The active
plan and build spec are never dropped. Automatic compaction runs at
`contextAutoAt` (85%) of the context cap before the following `fit`, so a full
store compacts instead of evicting the plan. `contextSummary` (6) bounds each
summary line, and every action is recorded in a dedicated
`toolrx.context.v1.<slug>.compact` report with kind, key, before/after bytes,
and why (`summarized`, `dropped`, `trimmed`, `evicted`); `notes()` merges that
report into the visible context listing so the three-note eviction ring cannot
hide what compaction did. A second run reports
`nothing to compact · already at its compacted form` and leaves the stored
bytes and report untouched. The catalog is 12,004 patterns and the everyday
fixture is 547 cases; `tests/test_compaction.py` drives the engine directly in
Node for idempotence, plan/spec survival, cap enforcement, tiny caps, and
byte-identical replay, while `tests/test_skills_js.py` runs the same path
through chat.

### 52. Budget-aware plan rewriting — done

When a long request would exceed the character, step, time, context, or
project budget, produce a deterministic compacted plan variant: keep the
highest-value steps, summarize or drop the rest, and show the before/after
bars. The user can accept, edit, or refuse; nothing is truncated silently.

**Done when** an over-budget plan yields a named variant with exact before and
after numbers, accepting it runs only the listed steps, refusing leaves the
project untouched, and a test covers each budget kind.

Landed with one pure module, `toolrx/web/planrewrite.js`. It scores each step
(writes 3, exact commands 2, router 1), keeps the highest-value steps that fit,
restores original order, and reports every dropped step with the budget that
forced it out. Characters, steps, and time are measured directly; context is an
upper bound from the stored plan entry and the 12-row session slice; project
uses the explicit `planBuildBytes` (65,536) and `planEditBytes` (4,096)
estimates in `limits.json`. The preview returns one named variant
(`compact-steps-time`, `compact-project`, …) with before/after bars. The variant
is stored beside conversation memory under `planVariantBytes` (9,216), not
inside the 4 KB short-turn cap; `yes` runs exactly the listed steps and
re-checks them, `no` clears it without touching the project, and any other
request is the edit path. A budget already over its cap is refused by name.
`tests/test_plan_rewrite.py` covers each budget kind, the stuck refusal, exact
acceptance, refusal, and the real chat path; `tests/test_skills_js.py` and
`tests/test_budget_bar.py` keep the existing preview and bar contracts.

### 53. `think` and `reason` as deterministic skills — done

Add first-class `think about …`, `reason step by step`, `analyze the
trade-offs`, and `critique this plan` routes. They run a small inspectable
program: structured decomposition, a checklist against the active limits and
known systems, a deterministic pro/con table, and one recommended next action
or revised plan. They accept a literal, a file, the previous step, or context,
and their output can feed the next step.

**Done when** at least four thinking intents have exact routes, the same input
produces byte-identical output, every claim in the output is traceable to the
input or a checked-in rule, empty input returns a clear message, and no
thinking route touches the network.

Landed with one checked-in table, `toolrx/thinking.json`, expanded by the
step-48 template machinery into 34 exact routes across four intents
(`think.decompose`, `think.reason`, `think.tradeoff`, `think.critique`). The
same table exports `tests/fixtures/thinking.json`, so routes and fixture cannot
drift. The pure program is `toolrx/web/thinking.js`: an ordered rule table with
stable ids (`r.split`, `r.steps-cap`, `r.repair-project`, …), and every output
line names the rule that produced it or quotes its input. The handler resolves
a topic in this order — existing file (bounded by `readFileBytes`), previous
result, active plan, context, literal — and an empty topic returns one message
naming those sources. Decomposition reuses the planner's `splitPromptInfo`, so
each goal carries its real exact route or `router`; a non-literal listing with
no exact route is reported as "a listing, not a request". Three limits are
explicit in `limits.json`: `thinkChars` (4,000), `thinkGoals` (8), `thinkRules`
(12). Truncated input, unlisted goals, and skipped critique rules are all named.
Trade-off verdicts are emitted only for matched keyword rules; an unmatched pair
returns `none` with the reason instead of inventing a preference. Critique runs
a fixed rule list and returns the smallest repair in priority order (failed
step, duplicate, steps, chars, time, project, context, files, none). A
single-step run becomes the `last run` plan when no multi-step entry exists, and
an empty thinking route is not recorded as a run. `tests/test_thinking.py`
covers the table, byte-identical repeats, every cap, each repair, source
resolution, and a fetch spy that must record zero calls.

Plan:

* One checked-in table, `toolrx/thinking.json`, expanded by the step-48
  template machinery into exact routes. Four intents — `decompose`, `reason`,
  `tradeoff`, `critique` — map to `think.decompose`, `think.reason`,
  `think.tradeoff`, and `think.critique`. The same table exports
  `tests/fixtures/thinking.json`, so routes and fixture cannot drift.
* One pure module, `toolrx/web/thinking.js`. Its rules are an ordered,
  checked-in table with stable ids (`r.steps-cap`, `r.duplicate`, …). Every
  output line names the rule id that produced it, or quotes the input it came
  from. No DOM, no fetch, no caps of its own.
* The handler resolves the topic in this order: an existing file (bounded by
  `readFileBytes`), the previous result, the active plan, the context, then a
  literal. An empty topic returns one clear message naming those four sources.
* Decomposition uses the planner's own `splitPromptInfo`, so the goals are the
  steps a plan would actually run. Each goal carries its real exact route when
  one exists, otherwise `router`.
* Three explicit limits: `thinkChars` (4,000), `thinkGoals` (8), `thinkRules`
  (12). An over-long input is analyzed up to the cap and the output says so;
  goals beyond the cap are counted but not listed; critique evaluates at most
  `thinkRules` rules and names any it skipped.
* A trade-off verdict is emitted only when a keyword rule matches an option.
  Unmatched criteria are listed as unmatched, and when no rule matches at all
  the recommendation is "none" with the reason — no invented preference.
* Critique checks the active plan against a fixed rule list (plan exists, step
  cap, character cap, time cap, duplicates, exact routes, failed step, pending
  step, project cap, context cap, file cap) and returns the smallest repair in
  a fixed priority order, or `none`.
* No network: `thinking.js` contains no fetch/XHR, and the test runs all four
  routes with a fetch spy that must record zero calls.

### 54. Self-critique and plan repair loop — done

After a plan preview or a failed step, offer a bounded critique pass: identify
the failing constraint, propose the smallest repair, and either emit a revised
plan or say why it cannot proceed. The loop is capped at two passes and never
marks a failed or skipped step as done.

**Done when** a failed middle step produces a repair or a refusal with the
exact reason, the revised plan runs only the changed suffix, the two-pass cap
is enforced, and the original plan remains available for undo.

Landed with one checked-in table, `toolrx/repair.json`, expanded by the step-48
template machinery into nine `repair.plan` routes and exported to
`tests/fixtures/repair.json`. `runPrompt` now attaches the full plan and the
failed index to its results, and `recordRun` stores them as `lastRun.plan`
(`steps`, `failedAt`, `pending`, stripped `errorText`) so a later repair sees
the plan that actually ran rather than only the executed prefix. The pure
module `toolrx/web/repair.js` returns exactly `retry`, `revise`, `refuse`, or
`none`, with stable rule ids (`r.repair-cap`, `r.repair-kind`,
`r.repair-missing`, `r.repair-route`, `r.repair-retry`, `r.repair-suffix`,
`r.repair-dependency`, `r.repair-empty`, …). Classification is fixed: a
kind-gated patch is refused with the compatible starters, a missing input or a
division by zero is revised by dropping the failed step, a transient or unknown
error retries the failed step plus suffix, a step with no exact route is
refused, a pending step that depends on the failed result is refused, and
dropping the last step is refused. A revised plan contains only the failed step
(retry) or the pending steps (revise); completed steps are never rerun and a
failed or skipped step is never relabelled done. `repairPasses` (2) is explicit
in `limits.json`; the record lives under `planRepair`, bounded by
`planVariantBytes`, `yes` increments the pass count, and a third request
refuses with `r.repair-cap`. `repairState()` always reads `lastRun.plan`, never
the active context plan, because only the run knows which step failed.
Inspection and proposal turns (`conversation.*`, `think.*`, `repair.*`) do not
replace `lastRun`, so a later repair or critique still sees the real failure. A
failed mid-plan result gains one offer line naming the route. The record keeps
the original full plan and project undo is untouched. `tests/test_repair.py`
covers each rule, the suffix-only run, the two-pass cap, the oversized-record
refusal, the original-plan record, undo, and a fetch spy that records zero
calls.

### 55. Reasoning traces in context and observability — done

Store thinking and critique outputs as their own context kind with an explicit
priority and byte cap. Show the trace in the last-run detail and the context
snapshot, and compact traces before the active plan or spec.

**Done when** a trace survives a reload, the last-run view names the trace that
chose or rejected a path, traces have a named cap and eviction note, and
compaction never leaves a trace without its plan.

Landed with one new limit, `traceBytes` (2,048), in `limits.json`,
`envelope.py`, the generated `limits.js`, and `skills.limitsText()`. The pure
module `toolrx/web/trace.js` turns a thinking or repair result into a
`trace/last` record with the route, decision, rule, source, plan steps, and a
plan hash; `record()` trims the text to the cap, marks `trimmed`, and returns
`null` only when even the minimum cannot fit. `decisionOf()` and
`decisionRuleOf()` read the same output the user saw — the `repair:` line for a
critique, the `recommendation:` line for a trade-off — so the trace names the
rule that chose or rejected a path instead of inventing one. `thinkRun` and
`repairPlan` attach a trace; `runPrompt` exposes the last one; the sandbox
stores it under context kind `trace` and stamps `planSha` from the plan entry
that is actually stored; `recordRun` keeps a bounded summary on `lastRun.trace`
and, because inspection turns do not replace the last run, updates that run's
trace in place. Compaction order is now `trace`, `session`, `result`, `edit`,
then non-critical files, and `enforceTracePlan()` runs both inside compaction
and after the ordinary `fit`: a trace whose `planSha` no longer matches the
stored plan is dropped with a named note, so a trace can never outlive its
plan. The context snapshot and `context` listing name the trace, and the
dashboard last-run detail gains one trace line plus a chip-title entry.
`tests/test_trace.py` covers the pure record and cap, the decision and rule
readers, storage and reload from raw `localStorage`, the last-run summary, the
snapshot line, trace-first compaction, the orphan-trace invariant, and a fetch
spy that records zero calls.

### 56. Project journal and multi-turn memory — done

Add a per-project deterministic journal for decisions, rejected alternatives,
and user preferences. It is queryable in everyday language (`what did we
decide about the art style?`), bounded, exportable with the project bundle,
and separate from the short conversation memory.

**Done when** the journal records decisions and rejections with a source step,
an everyday question returns the matching entry, the bundle round-trips it,
the cap and eviction notes are visible, and switching projects never leaks one
journal into another.

Landed with one pure module, `toolrx/web/journal.js`, backed by one localStorage
key per project (`toolrx.journal.v1.<slug>`), so two projects can never share a
journal. Each entry is `{seq, kind, topic, text, source, n}` where `kind` is
exactly `decision`, `rejection`, or `preference`, and `source` names the route
that made it (`build`, `edit.apply`, `project.themeToggle`, `repair.plan`,
`plan.variant`, `memory.remember`, …). Three explicit limits bound the log:
`journalEntries` (24), `journalBytes` (4,096), and `journalText` (240). `add()`
trims one entry's text to `journalText`, evicts the oldest entries beyond either
cap, and records a bounded note ring naming the evicted entry and the reason
(`entry cap`, `byte cap`, `trimmed`); a repeated identical decision is not
appended twice. One checked-in table, `toolrx/journal.json`, expands into 19
`journal.show`, `journal.query`, and `journal.clear` routes and exports
`tests/fixtures/journal.json`. `journal.query` tokenizes the topic, drops
stopwords, and scores each entry against its topic, text, and source, with exact
phrase matches winning; it returns the match with its seq, kind, text, and
source, or says `nothing about "<topic>" yet` and lists the known topics. The
sandbox records a decision after a successful build (topic `art style`, text
from the real spec line, genre, seed, and file count), after an edit, theme,
title, or note change, after `undo`, after a staged plan variant (a rejection
naming the dropped steps), and after a repair (decision for retry/revise,
rejection for refuse). `memory.remember` records a preference with the fact key
as its topic. `projectPayload()` carries `journal`, so both the project and
workspace bundles round-trip it; `stageProject()` validates and bounds it,
`installProject()` and the workspace import restore it, and delete/reset clear
it. `tests/test_journal.py` covers the pure add/query/text/evict/dedupe/export
path, the phrase fixture, the real build → art-style question, the plan-variant
and repair rejections, the preference, the bundle round-trip, project
isolation, the visible cap notes, and a fetch spy that records zero calls.

### 57. Error recovery and partial-result continuation — done

Make a mid-plan failure recoverable without a rebuild: isolate the failing
step, name the smallest fix or compatible starter, and offer one command to
resume the pending suffix. The failed step stays failed; completed files stay
written.

**Done when** a failed step yields an isolated reason and a resume command,
resuming runs only the pending steps, the project before the failure is still
openable, and the recovery path is covered for build, patch, and context
failures.

Plan:

* Extend the step-54 pure module `toolrx/web/repair.js` with `resume(input)`
  and `resumeText(out)`. `resume` reads the last run's plan (steps, failedAt,
  errorText, and the matched op of each step) and returns exactly `resume` or
  `refuse`. It skips the failed step and returns only the pending suffix;
  completed steps are never rerun and the failed step is never relabelled done.
  Guards, in order: no plan (`r.resume-none`), no failed step
  (`r.resume-nofail`), the failed step is last (`r.resume-last`), the shared
  pass cap (`r.resume-cap`), a failed build (`r.resume-build`: the previous
  project stays open, but the pending steps were meant for the new build), a
  pending step that needs a project and none is open (`r.resume-noproject`), a
  pending step that depends on the failed result (`r.resume-dependency`), and
  the step/character caps (`r.resume-steps`, `r.resume-chars`). A kind-gated
  patch is skipped and named, because continuing past it is the whole point of
  resume.
* One checked-in table, `toolrx/resume.json`, expanded by `toolrx/resume.py`
  into `repair.resume` routes and exported to `tests/fixtures/resume.json`.
  Phrases are `resume`, `resume the plan`, `continue the plan`, `run the
  pending steps`, `run the remaining steps`, `skip the failed step`, `carry
  on`, and `keep going`. Routes are appended after the repair layer, so a real
  command wins.
* `runPrompt` intercepts a standalone `resume` before the plan path, calls the
  pure module, and on `resume` re-enters the normal plan runner with
  `forcedSteps` equal to the pending suffix. The inner run is not recorded as
  its own conversation turn; the outer `resume` turn is. A successful resume
  clears the staged repair record; a failed one keeps the pass count so the cap
  is honest. An in-plan `resume` step returns a clear refusal instead of
  guessing.
* The failure offer line names both recovery commands in one line:
  `repair: say "repair this plan" for the smallest fix · or "resume" to run
  the N pending step(s)`.
* Resume shares `repairPasses` (2) with repair; no new limit is added, and the
  code and docs say so. The resume record lives under the same `planRepair`
  key with `kind: "resume"`, bounded by `planVariantBytes`, and its trace uses
  via `repair.resume` with a `r.resume-*` rule so the step-55 invariant holds.
* `tests/test_resume.py` covers every pure guard, the phrase fixture, a build
  then kind-gated patch then resume (the project keeps the completed build and
  the pending patch runs), a missing-file context failure resumed, a build
  failure with the previous project still openable and an honest refusal, the
  dependency and pass-cap refusals, the in-plan refusal, the failure offer
  line, and a fetch spy that records zero calls.

Landed by extending the step-54 module rather than adding a second one:
`toolrx/web/repair.js` now exports `resume(input)` and `resumeText(out)`, and
`record()` accepts `kind: "resume"` with the skipped step named. Resume reads the
last run's plan, skips `failedAt`, and returns only the suffix after it; the
matched op of each step decides whether a pending step needs a project, and a
pending step that names the failed result (`it`, `that`, `the result`, …) is
refused instead of guessed. The guard order is exactly the plan: no plan
(`r.resume-none`), no failure (`r.resume-nofail`), failed step last
(`r.resume-last`), shared `repairPasses` cap (`r.resume-cap`), failed build
(`r.resume-build`), pending step needs a project and none is open
(`r.resume-noproject`), dependency (`r.resume-dependency`), then `planSteps` and
`planChars` (`r.resume-steps`, `r.resume-chars`). No new limit is added. One
checked-in table, `toolrx/resume.json`, expands into nine `repair.resume` routes
and `tests/fixtures/resume.json`. `runPrompt` intercepts a standalone resume
before the plan path, calls the pure module, and on `resume` re-enters the plan
runner with `forcedSteps` equal to the suffix; the inner run is not a separate
conversation turn. A successful resume clears the staged record, a failed one
keeps the pass count, and the resume record stays under `planRepair` with
`kind: "resume"` bounded by `planVariantBytes`. The trace uses via
`repair.resume` with the `r.resume-*` rule. The first inner result carries the
resume header, while `errorText` keeps the real first-step error so `recordRun`
never quotes the header as the failure. The failure offer line names both
commands. `tests/test_resume.py` covers every pure guard, the fixture, the
build → kind-gated patch → resume path, a missing-file context failure, the
build-cancel refusal with the previous project still openable, the dependency
and cap refusals, the in-plan refusal, the real-error preservation, and zero
fetches.

### 58. Adaptive response style — done

Add a persisted `concise`, `explanatory`, or `tutorial` style that changes only
the wrapper text around exact results. Tool choice, arguments, files, limits,
and refusals never change with style.

**Done when** the same request under each style produces identical tool
choices, arguments, and file bytes; the style persists across reloads; the
wrapper stays within a named character cap; and tests compare the three
outputs.

Landed as one pure module, `toolrx/web/style.js`, exporting `normalize`,
`wrappable`, `apply`, `showText`, and `setText`. `concise` adds nothing;
`explanatory` adds a `style · <name> · <route>` prefix plus one honest `why:`
line; `tutorial` adds the same prefix plus one deterministic `try next:`
suggestion chosen from the route family. `sandbox.prompt` wraps results only
**after** the whole plan has run, so chained steps, `prev`, context, the
journal, the trace, and the stored plan all keep the raw result. Only exact,
non-error command results are wrapped: `chat`, `conversation.*`, `think.*`,
`repair.*`, `plan.*`, `budget.*`, and `style.*` are skipped, so refusals stay
byte-identical. `runOne` now marks an exact match with `exact: true`; router
fallbacks stay `exact: false`. The preference persists under
`toolrx.reply.style`, defaults to `concise`, survives a reload, and is exposed
as `toolrxWeb.style()` / `toolrxWeb.setStyle(value)`. `styleChars` (600) in
`toolrx/limits.json` caps the wrapper; an oversized wrapper is trimmed with a
visible `r.style-trim` note while the inner text is never truncated. One
checked-in table, `toolrx/style.json`, expands into fourteen `style.set` /
`style.show` routes and `tests/fixtures/style.json`; `show style` prints the
cap. `toolrx/web/style.js` is wired into `dashboard.html`, `web/sw.js`
(`toolrx-shell-v18-r7`), and `docs/build.py`. `tests/test_style.py` covers the
pure normalize/apply/trim/skip path, the fixture, the default concise output,
the explanatory and tutorial wrappers, persistence through a simulated reload,
identical `via` and project file bytes across all three styles, unchanged
refusals, and a fetch spy that records zero calls.

### 59. LLM-parity scorecard and gap analysis — done

Add a living, checked-in scorecard mapping common harness capabilities
(planning, tool use, long context, compaction, self-correction, natural
language, offline operation, inspectability, cost, reproducibility) to
toolrx's current coverage, evidence, and next step. It drives prioritization
after this batch and keeps claims tied to tests.

**Done when** every capability has a status, evidence link, and honest gap;
`coverage.py --check` or a dedicated test fails when the scorecard drifts from
the suite; and the pitch and README quote the scorecard rather than ad-hoc
claims.

Landed as one checked-in table, `toolrx/scorecard.json`, with the ten
capabilities above. Each row has a `shipped`, `partial`, or `deferred` status,
a short claim, at least one evidence entry (`{path, test?}`), a non-empty
honest gap, and a next move. `toolrx/scorecard.py` derives every quoted number
from the repository: catalog and fixture counts from `toolrx/coverage.json`,
named caps from `toolrx/limits.json`, and the test count from `def test_`
across `tests/test_*.py`. It renders one Markdown table and one HTML row list
from the same data; `--write` replaces the marker-bound blocks in `README.md`
and `docs/pitch.html`, and `--check` fails on a stale block, a duplicate id,
an unknown status, an empty gap, a missing evidence path or test, a `shipped`
row without a test, or any drifted metric. The pitch's catalog and test counts
are now marker-bound, so the old ad-hoc `429 automated tests` claim is gone.
`tests/test_scorecard.py` covers the schema, the derived metrics, every cited
path and test, both generated blocks, the inline markers, the stale-block
failure, and the no-network promise. No route, command, or numeric limit was
added.

## Harness roadmap 4 — everyday depth, operator tools, and public evidence (steps 60–69)

Steps 60–69 deepen the surface that already works instead of adding a second
system. Language grows where coverage shows gaps; projects gain an explainer,
more deterministic starters, a bounded compute tool, and verification helpers;
the operator gets a workspace journal, an event stream with replay, and named
plan macros; the batch closes with accessibility polish and a checked-in
evaluation kit that keeps public claims honest. No step may require a model, a
network call, an external test runner, or a real shell.

### Design rules for this phase

1. **Depth before breadth.** A new phrase family, starter, or helper lands only
   where the coverage or scorecard names a concrete gap. Counts alone are not
   progress.
2. **Explain and verify are pure programs.** They read the active project,
   last run, spec, journal, and limits; they never mutate files, call a model,
   or invent state.
3. **Compute stays bounded and pure.** The only new evaluator extends the
   existing `math.expr` parser with named caps, no filesystem, no network, and
   no `eval`/`Function`.
4. **Memory stays local and scoped.** A workspace journal indexes projects; it
   never merges their contexts or silently crosses a project boundary.
5. **Macros are data.** Named plan fragments are checked-in step lists with a
   bounded expansion, previewed before they run and editable after expansion.
6. **Evidence is generated.** The evaluation report and comparison document are
   derived from checked-in fixtures and tests, and a drift check fails when a
   quoted number changes.

### 60. Broader everyday and domain language packs — done

Grow the existing paraphrase, synonym, and everyday tables only where the
coverage report or scorecard shows a gap. Add focused packs for the domains
already present: math and units, file operations, project growth, extractors,
journal and memory, and build/edit. Add multi-turn repair phrasings and
corrections such as "no, the other one", "I meant the project one", and "use
the same seed" to the conversation layer.

- Keep one checked-in table per layer (`everyday.py`, `paraphrase.json`,
  `conversation.py`) and regenerate the catalog from it.
- Extend the existing correction path instead of adding a second memory store.
- Gate on the exact-lane floor, duplicate ids, duplicate regexes, and shadowing.

**Done when** at least 250 new high-signal phrasings land across the named
domains, every affected family keeps at least 30 cases, every fixture case
resolves to its own exact command with exact arguments and zero chat/router
fallback, the exact-hit rate stays at or above the current 90% floor, the
correction fixtures cover at least three "I meant…" forms, and the catalog
rebuild is byte-identical with zero duplicate ids or regexes.

Landed as one `DEPTH` table in `toolrx/everyday.py`: 351 new phrasings across
nine domains (math and units, files, project growth, extractors, builds,
edits, projects, context, and memory), each a full display phrase
with placeholders, fixed args, and expected captured args. One capture
vocabulary (`_rx`, `_sample`, `_expect`, `_generated`) expands them, so a pack
cannot introduce a second regex dialect. The base catalog is the authority on
coverage: every row was matched against it before it landed, and a phrase an
earlier command already owns was dropped rather than shipped as a route that can
never win. `entries(exclude=...)` re-applies that rule at build time for exact
pattern duplicates, and `tests/test_everyday.py` fails if any row becomes
shadowed later. The everyday fixture grew from 547 to 898 cases; all eleven
families carry at least 30 cases, every case resolves to its own exact command
with exact arguments, and there are zero chat or router fallbacks. The
conversation table gained seven specific correction routes (`no, the other
one`, `i meant the project one`, `i meant the first one`, `i meant the second
one`, `try the other one`, `use the same seed`) ahead of the generic capture,
and `toolrx/journal.json` grew to 33 query templates, 12 show phrases, and six
clear phrases, exported as a 53-case fixture. The catalog rebuilds at 12,481
patterns with 199 duplicate patterns skipped and no duplicate ids or regexes.

### 61. Deterministic explain this project / this plan — done

Add a first-class pure program that walks the active project or the last plan
and emits a structured, readable explanation: files and their roles, systems
present, recent edits, build seed, budgets used, journal decisions, and open
risks. It reads only state the workspace already stores.

- New browser module `toolrx/web/explain.js` with a Python fixture renderer in
  `toolrx/explain.py` for byte-pinned tests.
- Routes such as `explain this project`, `explain the last plan`, and
  `why did this build pick that theme`.
- Output can be stored in context or the journal on request, but is read-only by
  default and never rewrites a file.

**Done when** the same project and plan state produce byte-identical output on
two runs, every named file and system exists in the project, the explanation
names the seed and each budget it reports, a missing project or plan returns an
honest refusal naming what is absent, output is bounded by a named cap, and the
suite proves zero network calls.

Landed as one checked-in table, `toolrx/explain.json`, expanded into 52
`explain.*` routes for the active project, the last plan, the build theme, and
two explicit store forms. `toolrx/web/explain.js` is the pure program and
`toolrx/explain.py` is its byte-identical Python twin; `tests/fixtures/explain.json`
pins 13 rendered states across all three targets. A project explanation lists
only the project's real files with a name-derived role, its `systems/` files,
its applied edits, the build-spec seed, the page and named theme with the rule
that chose them, the journal counts, and the project, file, context, and
`explainChars` budgets. A plan explanation lists each recorded step with its
exact route or router fallback and its done/error/pending status, then names the
failed step and every open risk. Missing state refuses by name. Two explicit
routes store the explanation in context or as a bounded journal entry; every
other route is read-only and prints `writes: no file`. The new caps are
`explainChars` (8,000), `explainFiles` (24), and `explainEdits` (8); an
over-cap explanation is trimmed at a line boundary with a visible `r.trim`
note. Explaining is an inspection turn, so it does not replace the last run,
write the context result, or change the stored plan.

### 62. Richer project templates and starter library — done

Grow the deterministic starter library beyond games with a small set of
high-quality, fully offline templates: a web app with an auth stub, a data
dashboard, a note-taking app with local search, a multi-page static site, and an
API mock. Each ships real files, an `ARCHITECTURE.md`, and seed-reproducible
content.

- Keep the build-spec parser in charge: a new starter is a kind plus a fixed
  file plan, not a second prose parser.
- Reuse the existing module, patch, undo, and budget paths.
- Seed names, sample rows, and copy from `hash(prompt + seed)`.

**Done when** at least five new starters build offline, the same prompt and seed
produce byte-identical files, each starter has a previewable entry point and an
`ARCHITECTURE.md`, every file stays inside the existing size and count caps,
and the catalog, README, and pitch counts are regenerated from the build.

Landed as five kinds with fixed file plans in `toolrx/web/templates.js`:
`authapp`, `datadash`, `notebook`, `multipage`, and `apimock`. The build-spec
parser is still the only prose parser; a starter is a canonical kind plus a
file list, and `starterExtras()` supplies the extra files that kind always
ships. Names, sample rows, and copy are derived from `hash(prompt + seed)` by
one seeded generator, so the same prompt and seed rebuild byte-identical files
and a different explicit seed changes real content. Every starter ships a
previewable `index.html`, `styles.css`, `app.js`, `README.md`, and
`ARCHITECTURE.md`; the auth starter adds `auth.js`, the dashboard `data.js`, the
notebook `seed-notes.js`, the static site `about.html`, `docs.html`,
`contact.html`, and `site.js`, and the API mock `api.js` plus `openapi.json`.
Extra scripts are referenced before `app.js`, so the existing preview bundler
inlines them in order and the module, patch, undo, and budget paths are
unchanged. Every generated file stays inside the existing `projectFiles` (32),
`projectFileBytes` (131,072), and `projectBytes` (524,288) caps, and no
generated file calls `fetch`, `XMLHttpRequest`, `WebSocket`, or `sendBeacon`.
`tests/test_starters.py` pins the five kinds, byte-identical rebuilds, required
files, script order, shared multi-page assets, seed variation, the caps, the
no-network rule, and the exact catalog routes; the catalog is regenerated to
13,373 commands.

### 63. Bounded pure-compute tool — done

Extend the existing safe `math.expr` parser into one bounded compute surface for
short pure expressions and tiny scripts: local assignments, string transforms,
and simple shaping over literal values. It is not a shell and adds no new
allow-listed tool.

- Hard caps in `limits.json` for source characters, operations, local variables,
  and wall time; refusal names the cap that was hit.
- Default-deny any identifier or call that could touch the filesystem, network,
  timers, storage, or the DOM.
- No `eval`, `Function`, `import`, or dynamic property access. Python and
  JavaScript share the same grammar, caps, and refusal text.

**Done when** pure expressions and the documented statement forms evaluate
identically twice, an over-cap script refuses with the named cap, every
filesystem/network/DOM attempt refuses before evaluation, the Python and
JavaScript fixtures agree on results and errors, and the tests prove no network
or file access.

Landed as one program behind the existing `math.expr` route, with no new
allow-listed tool and no new web asset. `toolrx/web/skills.js` replaces the old
expression parser with a two-phase tokenize, parse, then evaluate pass;
`toolrx/compute.py` is the byte-identical Python twin. Statements are separated
by `|`, `;`, or a newline, and `|` is the form that survives chat plan
splitting. The grammar covers `let`/reassignment locals, numbers (including
exponents), single- and double-quoted strings, booleans, null, arrays,
indexing, slicing, comparisons, `and`/`or`/`not`, and a fixed table of pure
builtins for math, strings, and arrays. Parsing completes before evaluation, so
a cap or a denied name refuses before any value is computed. The six caps live
in `limits.json` and are read by both runtimes: `computeChars` (2,000),
`computeStatements` (20), `computeOps` (200), `computeVars` (8), `computeMs`
(50), and `computeResultChars` (4,000); each refusal names its cap, and
`tests/test_compute.py` drives the wall clock with a deterministic fake. The
deny list refuses `eval`, `Function`, `import`, `require`, `fetch`, storage,
timers, the DOM, `Math`, `Date`, `Reflect`, `Proxy`, and dynamic property
access before evaluation, and names resolve only against builtins and locals
declared earlier in the same script. Numbers render through one fixed
10-decimal form plus integer and exponential branches so both runtimes print
identical bytes; `%` uses `fmod` on both sides. The fixture is 80 cases over
results, errors, cap refusals, and operation counts, and it is replayed through
Node and Python on every suite run.

### 64. Cross-project memory and workspace journal — done

Extend the per-project journal into an optional workspace-level journal and a
light cross-project index. It stays fully local, capped, and inspectable, and it
never merges one project's context into another's.

- Index project slug, theme, seed, last build, and decision topics; keep the
  full entries in their per-project journals.
- Queries such as `what themes have I used across projects` and
  `show decisions about art style in the last three builds`.
- Workspace bundles may carry the index on request, never silently.

**Done when** cross-project queries are deterministic and bounded by named
caps, a project switch cannot leak another project's context, the index is
exported and re-imported byte-identically, a deleted project is removed from
the index, and tests cover the capped and empty cases.

Landed as a derived index, not a second copy of the journals.
`toolrx/workspace.json` is the only source of the 35 `workspace.*` routes;
`toolrx/workspace.py` expands it into catalog entries and a 35-case,
15-state fixture, and `toolrx/web/workspace.js` is the byte-identical twin.
The index reads the project list plus each project's own journal and keeps only
the newest `build` line and the sorted topic names, so full entries stay in
their per-project journals and project context is never read. The five caps are
`workspaceProjects` (24), `workspaceTopics` (8), `workspaceRows` (12),
`workspaceIndexBytes` (8,192), and `workspaceChars` (4,000); drops are reported
in the index and in the rendered answer. The routes are inserted before the
journal block, so "what did we decide about art style across projects" wins over
the generic journal template while "what did we decide about art style" still
reaches `journal.query`. A workspace bundle carries the index only when
`export the workspace with the index` asks for it; import validates the optional
index against the staged projects and refuses a stale one, and `stageProject`
preserves the bundle timestamps so the rebuilt index matches byte for byte.
`tests/test_workspace.py` pins the table, the Python/JS parity, the caps, the
empty and capped states, cross-project themes and decisions, deletion, context
isolation, the bundle round-trip, and the no-network rule.

### 65. Operator dashboard upgrades — done

Make the existing last-run, trace, journal, compaction, and rewrite data
visible as one event stream, and add the operator actions that data already
supports.

- A live event stream for compaction, rewrite, repair, resume, and refusal,
  rendered from stored records rather than ad-hoc strings.
- One-click replay of the last successful plan, guarded so it runs once.
- Clearer headroom warnings and a "why this was compacted or rewritten" detail
  that quotes the recorded reasons.
- An export action for the last run plus the journal snapshot, validated on
  import.

**Done when** every event in the stream comes from a stored record with a
timestamp and route, replay runs exactly the recorded steps once and refuses
when none exist, the headroom detail names the cap and the reason, the export
round-trips through the existing bundle validator, and the panel is keyboard
reachable with text alternatives for every status.

Landed as one bounded store fed only by records the sandbox already kept.
`toolrx/events.json` is the only source of the 26 `events.*` routes, and
`toolrx/web/events.js` is the pure store behind them. Three caps bound the
stream: `eventEntries` (32), `eventBytes` (8,192), and `eventText` (240); the
oldest events are dropped at a cap and the dropped count stays in the record.
Compaction events quote the context report's actions and `why` values, rewrite
events quote the stored variant's over-budget list and dropped steps, repair and
resume events quote the stored repair record and trace rule, and refusal events
quote the first failed step. Every event carries the route and the run's own
timestamp; the store never reads the clock. `replay the last plan` hands the
recorded steps to the planner as `forcedSteps`, writes a `replayedAt` guard
before the first step runs, and refuses a second replay. `export the last run`
writes a `toolrx.events` bundle with the last run, journal snapshot, and event
stream; `parseBundle` validates the format, the version, the event list, and the
run timestamp before `import events from <bundle>` restores it. The last-run
panel adds a headroom warning that names the cap, a "why compacted / rewritten"
line, keyboard-reachable replay and export buttons, and a live status with text
alternatives. `tests/test_events.py` pins the table, both caps, all five event
kinds, one-shot replay, the bundle round-trip, the validation refusals, and the
no-network rule.

### 66. Deterministic verification helpers — done

Add a small family of exact commands that answer "did this build produce what it
said it would?" without an external test runner or an unconstrained shell.

- List expected versus actual files after a build, naming missing and extra
  files.
- Run a project-local smoke check such as "does `index.html` contain the
  expected title" or "does `app.js` define the expected entry point".
- Produce a short verification report that can be stored in context or the
  journal.

**Done when** the expected file list derives from the build spec and the actual
list from the project, a missing or extra file is named exactly, each smoke
check is a pure predicate over project files, the report is deterministic and
bounded, and tests cover pass, fail, and empty-project cases.

Landed as one pure program with no test runner, no shell, and no new
allow-listed tool. `toolrx/verify.json` is the only source of the 48 `verify.*`
routes; `toolrx/verify.py` expands it into catalog entries and a 19-state
fixture, and `toolrx/web/verify.js` is the byte-identical twin. Expected files
derive from the stored build spec: the five base files, the RPG runtime, the
2D or 3D engine chosen by the route, `content.js` for a long spec, the starter
extras, and every grown module or `systems/<id>.js`. Actual files are the
project's real names, so `verify the project files` names every missing and
extra file exactly. Eight smoke checks are pure predicates over project text:
index content, title, stylesheet content, entry point, script order before
`app.js`, local links, docs, and budgets; none of them executes project code.
`verify this project` combines the diff and the checks into one report whose
verdict survives trimming, and the two store routes put that report in context
or the project journal. The three caps are `verifyFiles` (32), `verifyChecks`
(8), and `verifyReportChars` (4,000). `tests/test_verify.py` pins the table,
Python/JavaScript parity, expected files against 52 real `templates.project()`
builds plus growth and the 3D route, the pass/fail/empty cases, the caps, both
stores, and the no-network rule.

### 67. Plan composition and named macros — done

Allow named, reusable plan fragments that expand deterministically into step
lists. A user can invoke, preview, and edit the expanded plan, while the macro
itself stays immutable.

- One checked-in table, `toolrx/macros.json`, generated by `toolrx/macros.py`
  and expanded by a small pure function.
- Examples: `standard shooter growth`, `add inventory + save + ui`.
- Expansion is literal, non-recursive, and capped by the existing step limit.

**Done when** each macro expands byte-identically twice, preview shows the exact
steps before running, the user can edit the expanded list without changing the
macro, recursion or an over-cap expansion refuses with a named reason, and no
new allow-listed tool is added.

Landed as a table of literal step lists, with no recursion and no new cap.
`toolrx/macros.json` is the only source of the 60 `macro.*` routes and the
expansion data; `toolrx/macros.py` expands it into catalog entries and a
60-case, 13-state fixture, and `toolrx/web/macros.js` is the byte-identical
twin. The table ships inside `commands.json` as a top-level `macros` payload so
the browser needs no extra fetch. Five macros cover the growth paths already
built (`standard shooter growth`, `add inventory + save + ui`, `polish pass`,
and two others), each with four run phrases and four preview phrases; eight
generic routes turn an unknown name into `r.macro-missing` instead of a router
fallback. Preview stages the exact expanded list in memory under `macroPlan`,
bounded by the existing `planVariantBytes`, and reports the steps without
writing; `yes` runs the staged list through `forcedSteps`, and direct
`run macro …` does the same without staging. `edit the macro plan to …`
rewrites only the staged list, separated by `|`, `;`, newline, or `then`, and
reports `r.macro-immutable`; the macro table is never modified. Expansion is
capped by the existing `planSteps` (40) and `planChars` (8,000) plus
`singleChars` (2,000) per step, and refuses with `r.macro-recursive`,
`r.macro-steps`, `r.macro-chars`, or `r.macro-step-chars` rather than
truncating. `tests/test_macros.py` pins the table, the fixture, Python and
JavaScript byte parity, preview-without-writing, exact execution, list and edit
behaviour, the named refusals, and the no-network rule.

### 68. Accessibility and mobile polish — done

Tighten the installed-app and small-screen experience around the paths that
already exist.

- Better composer behaviour on small screens, including keyboard and safe-area
  handling.
- Clearer budget bars and headroom text, with status announced in words as well
  as colour.
- Focus management for drawers, dialogs, and the last-run detail.
- Reduced-motion respect across the shell, mascot, and animations.
- Make the offline install path and the "airplane mode still works" story
  obvious in the empty state.

**Done when** every interactive control is keyboard reachable with a visible
focus ring, the shell has no horizontal scroll at 360 px, reduced-motion
disables non-essential animation, every status has a text alternative, the
offline state is explained in the UI, and the HTML and smoke checks cover these
paths.

Landed as shell-only work: no route, cap, or allow-listed tool changed. The
composer keeps `enterkeyhint`, `autocapitalize`, `autocomplete`, and
`spellcheck`, adds safe-area padding on all three sides, a 16 px field on
phones, and a 380 px layout that keeps the budget bar to two columns. The shell
sets `max-width:100vw` and `overflow-x:hidden`, every pane and the hint row get
`min-width:0`, and long tokens in results, events, and the file editor wrap with
`overflow-wrap:anywhere`. The device drawer and the quality-curve drawer now
move focus inside when opened, return it on close, expose `aria-expanded` on
their toggles, and carry `aria-hidden` plus `inert` while closed; the quality
drawer is a real labelled dialog with a keyboard-reachable close button and
keyboard-reachable PNG actions. The device detail moves focus to its close
button and restores it. Budget bars carry a `status` word from
`toolrx/web/budget.js` — `within cap`, `near cap`, `over cap` — printed for
warn/over and always included in `aria-valuetext`, and `budgetSay` still
announces a crossed limit. The build status is a `role="status"` live region.
Reduced-motion stops the mascot, equaliser, flow, pulse, and drawer transitions
while progress values still update instantly. The empty state explains the
offline path and airplane mode, an opt-in `install app` button appears only on
`beforeinstallprompt` and disappears on `appinstalled`, and an `offline-ready`
chip becomes `offline · still works` or `installed · offline-ready` from the
real `online`/`offline` events. `tests/test_a11y.py` drives the real HTML and
budget module in Node: it pins the mobile composer, the focus contracts, the
status words, reduced motion, the offline/install story, and a structural
parser check that catches a malformed drawer tag. The live smoke checks
`scrollWidth <= innerWidth` at 360 px and 320 px.

### 69. Public evaluation suite and comparison kit — done

Ship a checked-in, offline-evaluable suite and a short, honest comparison
document so public claims stay tied to measurements.

- The suite measures everyday exact-hit rate, long-form plan success and undo
  fidelity, compaction and rewrite correctness, and think/repair determinism.
- `toolrx/evaluation.json` is the one source of numbers; a text and HTML render
  feed the pitch and the comparison document through marker-bound blocks.
- The comparison document covers toolrx versus pure rule chatbots and LLM
  coding agents, naming real files, budgets, offline operation, and
  inspectability as strengths and conversational breadth and general terminal
  work as gaps.

**Done when** one offline command regenerates the evaluation report from the
fixtures, every quoted number in the report and comparison document matches the
checked-in source, the drift check fails on a stale block or a missing fixture,
the comparison document names at least three honest gaps, and the suite proves
zero network calls.

Landed as a checked-in report, a harness, and a comparison document; no route,
cap, or allow-listed tool changed. `toolrx/evaluation_harness.js` loads the real
browser modules in Node behind a fake fetch that only reads local files, runs
five thinking modes, five repair rules, seven plan rewrites, and two context
compactions twice each, and reports 18 of 18 byte-identical programs. It also
counts fetches after module init, which must be zero. `toolrx/evaluation.py`
reads `coverage.json` and `demo_report.json`, runs the harness, validates the
report, writes `toolrx/evaluation.json`, and keeps one Markdown block in
`README.md` and `COMPARISON.md` and one HTML block in `docs/pitch.html`
byte-identical to it; `--check` fails on a stale report, a missing or duplicate
block, a determinism mismatch, a failed build step, a budget overrun, or a
non-zero network count. `COMPARISON.md` names six honest gaps — conversational
breadth, general terminal work, generation quality, no learning, single-user and
local, and that the numbers are not a benchmark. `tests/test_evaluation.py`
pins every measured section to its source, the zero-network rule, the shared
blocks, the stale-report path, and the three-gap minimum.

## Harness roadmap 5 — world building, remix, and shareable packages (steps 70–79)

Steps 70–79 grow the existing deterministic 2D and 3D worlds from single-build
projects into editable, chunked, shareable worlds with simple agents. Every step
stays offline, seeded, capped, inspectable, and free of any external engine,
asset, or service. The world is always a plain document the user can read; a
renderer and a player are views over that document, never the source of truth.

### 70. World spec v1 — planned

Define one checked-in world document that describes a world without describing
its renderer. It becomes the only source every later world step reads.

- One table, `toolrx/world.json`, generated by `toolrx/world.py` and expanded by
  a pure function; `toolrx/web/world.js` is the byte-identical twin.
- The document names seed, size, tiles, terrain bands, spawn points, objects,
  and named regions; no pixel, mesh, or DOM detail is stored.
- A build route derives the existing 2D and 3D projects from the document, so a
  renderer change cannot silently change the world data.

**Done when** the same document renders byte-identically twice through the 2D
and 3D routes, the document validates against a named schema with named refusal
reasons, every field is bounded by an existing or newly named cap, Python and
JavaScript agree byte for byte, and no new allow-listed tool is added.

### 71. Chunked worlds — planned

Let a world larger than one screen be stored and rebuilt in deterministic
chunks, so memory and render time stay bounded.

- Fixed chunk size and a stable chunk key derived from the seed and coordinates.
- Only the chunks near the camera are materialized; the rest stay as keys.
- A chunk is regenerated from its key alone, never from render order.

**Done when** the same chunk key produces byte-identical content twice, a world
larger than the render budget loads with a named cap and a reported chunk count,
a missing or corrupt chunk refuses with a named reason instead of rendering a
hole, and tests cover the seam between adjacent chunks.

### 72. Live remix and world mutations — planned

Add deterministic in-place mutations so a user can reshape a world without
rebuilding it from scratch.

- Named mutations such as "raise the terrain", "add a river", "scatter trees",
  and "make it night", each a pure edit over the world document.
- A mutation is recorded as an ordered, replayable list; undo removes the last
  one and nothing else.
- A mutation that would break a cap refuses with a named reason before applying.

**Done when** every mutation is byte-identical on replay, undo restores the
prior document byte for byte, an over-cap mutation leaves the document
untouched, the recorded list survives a project switch, and tests cover the
empty, capped, and rejected cases.

### 73. Starter worlds — planned

Ship a small curated set of starter worlds that a user can open, inspect, and
grow, all derived from seeds rather than bundled art.

- A checked-in starter table with a name, a seed, and a one-line description.
- Opening a starter builds the same deterministic project the build route
  produces, with no extra assets.
- A starter may be copied into a new project, but the starter itself is
  immutable.

**Done when** every starter rebuilds byte-identically twice, opening one writes
a real project under `projects/<slug>/`, the starter table is the only source of
the routes and the fixture, and tests cover the list, open, copy, and missing
cases.

### 74. Tiny deterministic scene bank — planned

Provide a small bank of reusable scene fragments so builds share structure
without sharing art or code.

- Each scene names its footprint, required terrain, and the objects it places,
  all as data.
- Scenes compose by deterministic placement rules, not by random overlap.
- A scene that does not fit refuses with a named reason and leaves the world
  unchanged.

**Done when** every scene places byte-identically twice, composed scenes never
overlap two objects in one cell, an unfit scene refuses by name, the bank is
the only source of its routes and fixture, and tests cover placement, refusal,
and composition order.

### 75. Shareable world packages — planned

Let a user export and import a world as one validated bundle, using the same
bundle discipline as the existing workspace and event exports.

- The package carries the world document, its mutation list, and its seed, and
  nothing host-specific.
- Import validates the format, version, caps, and schema before staging.
- A stale or malformed package refuses with a named reason and changes nothing.

**Done when** a package round-trips byte for byte, import rejects a wrong
format, version, cap, or schema by name, importing over an existing project
requires an explicit confirmation, and tests cover the round-trip and every
refusal.

### 76. Deterministic agents — planned

Add simple non-player characters whose behaviour is a pure function of the
world, the seed, and the tick number.

- Agents have a position, a small state machine, and a fixed movement rule; no
  clock, no randomness at run time, and no model.
- The same tick sequence replays identically, and a replay can start from any
  saved tick.
- Agent count and per-tick work are bounded by named caps.

**Done when** a fixed tick sequence produces byte-identical positions twice,
replay from a saved tick matches a full run, an over-cap agent count refuses by
name, agents never leave the world bounds, and tests cover idle, moving, and
blocked states.

### 77. Speech-friendly phrases — planned

Make the most common world commands short enough to say out loud, and make the
replies short enough to hear.

- Short spoken forms such as "make it night", "add a river", "bigger world",
  and "save this world" map to the same deterministic routes.
- Spoken replies stay within a small named character cap and lead with the
  outcome.
- Ambiguous spoken forms ask one bounded question instead of guessing.

**Done when** every spoken form resolves to the same route as its long form,
spoken replies stay inside the named cap, an ambiguous form asks exactly one
question, Python and JavaScript agree byte for byte, and tests cover every
spoken form and the refusals.

### 78. Play and build modes — planned

Separate looking at a world from playing in it, over the same world document.

- Build mode edits the document; play mode only reads it and moves the player.
- Switching modes never rewrites the world and never loses an unsaved edit
  without saying so.
- Play mode has a named input and tick budget, and pausing is exact.

**Done when** a mode switch leaves the document byte-identical, play mode
cannot mutate the world, an unsaved edit is reported before a switch, pause and
resume reproduce the same tick, and tests cover both modes and the switch.

### 79. World-building evaluation suite — planned

Measure the world batch the same way earlier batches are measured, so public
claims stay tied to checked-in numbers.

- The suite measures spec determinism, chunk reproducibility, mutation and undo
  fidelity, package round-trips, agent replay, and spoken-route parity.
- `toolrx/world_eval.json` is the one source of numbers; text and HTML renders
  feed the pitch and the comparison document through marker-bound blocks.
- The suite names at least three honest limits, such as world size, agent
  count, and scene variety.

**Done when** one offline command regenerates the report from the fixtures,
every quoted number matches the checked-in source, the drift check fails on a
stale block or missing fixture, the report names at least three honest limits,
and the suite proves zero network calls.

## Order

1. 12 (spec) → 13 (2D engine) → 15 (3D engine) — done
2. 16 (RPG world) → 17 (themes/titles) → 18 (library) → 19 (patches) — done
3. 21 (archive catalog) → 22 (language recognition) → 23 (archive search) →
   24 (localized intents) → 25 (Library panel) — done
4. 20 (LLM adapter) — done
5. 26 (ceiling) → 27 (hierarchical routing) → 28 (catalog) → 29 (build specs) →
   30 (project growth) → 31 (context) → 32 (output budgets) → 33 (argument
   capture) → 34 (vocab/centroids) → 35 (gate) — done
6. 36 (budgets) → 37 (suite) → 38 (limit source) → 39 (continuation) →
   40 (systems) → 41 (coverage) → 42 (observability) → 43 (workspaces) →
   44 (extractors) → 45 (demo) — done
7. 46 (paraphrase) → 47 (glue) → 48 (tables) → 49 (language coverage) →
   50 (budget bar) → 51 (compaction) → 52 (plan rewrite) — done;
   53 (think) → 54 (critique) → 55 (traces) → 56 (journal) →
   57 (recovery) → 58 (style) → 59 (scorecard) — done
8. 60 (domain language) → 61 (explain) → 62 (starters) → 63 (pure compute) — done
9. 64 (workspace journal) → 65 (dashboard events) → 66 (verify helpers) →
   67 (plan macros) → 68 (accessibility) → 69 (evaluation kit) — done
10. 70 (world spec) → 71 (chunked worlds) → 72 (live remix) →
    73 (starter worlds) → 74 (scene bank) → 75 (world packages) →
    76 (deterministic agents) → 77 (speech-friendly phrases) →
    78 (play/build modes) → 79 (world evaluation) — planned

Steps 36–37 come first because they define the budget and the gate every later
step measures against. Step 38 lands immediately after so no new limit is added
to two places. Steps 39–44 may be reordered within the batch if a measurement
justifies it; step 45 is last.

Steps 46–49 come first because everyday language must be measured before the
budget UI claims to help it. Steps 50–52 landed as one envelope batch. Steps
53–55 are the thinking program. Steps 56–59 close the remaining parity gaps;
they may be reordered within the batch when a measurement justifies it.

Steps 60–63 come first because language, explanation, starters, and compute are
the most visible daily improvements. Steps 64–67 add memory, events, and
verification, and may be reordered within the batch when a measurement
justifies it. Steps 68–69 are last: accessibility needs the final UI, and the
evaluation kit needs every earlier measurement.

Steps 70–79 are a separate batch; 68–69 are done, so it can start. Step 70
defines the world document that every later step reads, so it cannot move.
Steps 71–74 and 76 may be reordered within the batch when a measurement
justifies it; step 75 depends on the package validator already used by the
workspace bundles, and steps 77–79 are last because they measure and re-express
everything before them.

## Open questions

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
- Steps 11–13 and 15–59 are complete. Steps 60–69 are planned and stay
  `planned` until buildout starts.
- Which defaults should v2 change, if any: keep 2,000 / 8,000 / 40 / 32 files /
  512 KB, or raise one dimension at a time from measurements? Raise only after
  the step-37 suite proves the margin.
- Should workspace bundles include the whole settings object or only project,
  context, plan, and limits? Include only what affects reproduction.
- Should the coverage report ship as a generated file in `docs/` or stay a test
  artifact? Ship it once step 41 proves the format is stable.
- Everyday coverage starts at a 90% exact-hit floor with no median-margin
  regression; change the floor only from the first measurement, never from
  optimism.
- Compaction ships command-only first. Automatic compaction at 90% of the cap
  follows only after the notes and the plan-survival test are green, and the
  user can always turn it off.
- Thinking traces: store the last trace per project by default and store every
  trace only on request, so the context cap stays honest.
- Response style may change sentence shape and examples, never tool choice,
  arguments, files, or refusal text. The wrapper gets its own named cap.
- The parity scorecard is one JSON source plus a generated markdown table, so
  the docs and the drift test read the same numbers.
- This batch covers English paraphrases only. Localized intents stay in the
  existing language packs.
- Domain language packs stay in the existing per-layer tables until a family
  needs its own review cadence; a second table would split the exact matcher.
- The project and plan explainer emits one structured record with a text
  renderer, so chat, context, and the journal read the same explanation.
- Bounded compute starts at 400 source characters, 200 operations, 16 locals,
  and 50 ms, and rises only from a measured need. The grammar stays pure: no
  filesystem, network, timer, storage, DOM, `eval`, or `Function`.
- The workspace journal keeps an index across projects and never merges their
  entries. Cross-project queries read the index; full entries stay scoped.
- Plan macros expand literally with no recursion and a 40-step cap, matching the
  existing plan limit. The macro table is data, not a new tool.
- The evaluation report and comparison document are generated from checked-in
  fixtures; `evaluation.json` is the one source of quoted numbers.
- Dashboard events are rendered from stored last-run, trace, and journal
  records, so an event stream can never claim something the run did not record.
