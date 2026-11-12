# Harness roadmap 2 — specs, engines, worlds, and long-form work

This plan moves toolrx from "a template per command" toward the output shape of a
general LLM coding harness, while keeping the deterministic core. The rule is
simple: **the deterministic path stays first, complete, and offline**. An LLM may
later fill a validated spec or propose a patch, but it never becomes required.

Steps 26–35 extend the same rules to longer input and longer output. They add no
model: longer prompts become verified multi-step plans, and larger builds become
seeded, composable projects.

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
(now `toolrx-shell-v14`), so the panel works offline with no second fetch.

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
| Project files | template-sized | 32 files |
| Project text | template-sized | 512 KB total |
| Undo snapshots | 8 | 16, configurable |
| Command patterns | 12,362 | 12,000 |
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

Landed at 12,362 patterns. New families cover theme + genre, genre + feature,
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

### 30. Multi-file growth and patch composition

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

### 31. Deterministic context and working memory

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

### 32. Chunked output, progress, and budgets

Emit progress events at phase boundaries and at least every ~250 ms or 32 KB of
generation, with a partial file list. Raise per-tool caps deliberately and add a
per-project total byte budget. Support cancellation and timeout that leave the
last good project intact. Report characters, estimated tokens, milliseconds, and
peak size, and mark partial results as partial.

**Done when** a maximum-size build emits at least three progress events, respects
the byte cap, is byte-identical to the non-progress build, and cancellation leaves
the previous project valid.

### 33. Argument extraction and long-form content

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

### 34. Vocabulary, knowledge, and centroid scaling

Expand `knowledge/*.md` and the derived vocabulary and centroids so longer, more
varied phrasings keep high-confidence routes and healthy margins. Add
multi-centroid or hierarchical tool families (coarse family → fine command) only
where measurements justify the extra complexity. Keep rebuilds pure Python and
fast, and keep the model within a defined size budget.

**Done when** a rebuild stays under 2 seconds on the reference machine, the model
stays within 1.5× its current size, long-prompt accuracy meets the step-35
threshold, and margins are reported and non-degenerate.

### 35. Long-input / long-output test suite and observability

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

Start the fixture harness with step 26 so every step lands with measurements, even
though step 35 closes the batch.

## Order

1. 12 (spec) → 13 (2D engine) → 15 (3D engine) — done
2. 16 (RPG world) → 17 (themes/titles) → 18 (library) → 19 (patches) — done
3. 21 (archive catalog) → 22 (language recognition) → 23 (archive search) →
   24 (localized intents) → 25 (Library panel) — done
4. 20 (LLM adapter) — done; 14 (sprites) deferred until a licence-compatible
   subset is pinned
5. 26 (ceiling) → 27 (hierarchical routing) → 28 (catalog) → 29 (build specs) →
   30 (project growth) → 31 (context) → 32 (output budgets) → 33 (argument
   capture) → 34 (vocab/centroids) → 35 (gate) — planned
6. Step 14 stays independent; it can land whenever the sprite subset is chosen.

## Open questions

- Step 14 source is known: `huggingface.co/datasets/Angais/pixel-art-atlas-1.4m`,
  CC0-1.0, native 16×16 RGBA. Vendoring a pinned subset with a manifest and
  checksums is deferred; procedural sprites remain the fallback.
- Are the v1 envelope numbers right? Decide from step-35 measurements, not from
  optimism; adjust the table and the tests together.
- Should caps be editable in Command Center, or stay in `policy.json` only?
- How is plan quality scored: completion rate, confidence floor, refusal
  correctness, or a weighted mix? Pick one formula before step 27 ships.
- Should context be per project (default) or global, and should it survive a
  project switch?
- Do multi-file patches install atomically only, or may they stage a pending
  multi-file diff like the LLM path? Atomic is the default.
- 3D leads with low-poly WebGL and a Canvas/isometric fallback (decided).
- Steps 11–13 and 15–25 are complete. 14 remains deferred. Steps 26–35 are
  planned; none is started.
