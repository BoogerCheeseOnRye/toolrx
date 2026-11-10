# Harness roadmap 2 — build spec, engines, worlds, and an optional LLM

This plan moves toolrx from "a template per command" toward the output shape of a
general LLM coding harness, while keeping the deterministic core. The rule is
simple: **the deterministic path stays first, complete, and offline**. An LLM may
later fill a validated spec or propose a patch, but it never becomes required.

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
(`tower defense` → shooter, `roguelike` → RPG, `racing`/`kart` → racer) and the
reply names the closest supported option when the request is approximate.
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

### 17. Themes and titles without a default

- Expand from 10 packs to at least 20 (add e.g. frost, volcanic, fungal,
  sky-islands, clockwork, dream, plague, archipelago).
- Add a title grammar: `<adjective> <place> RPG` plus curated pack titles.
- Default `build an rpg` picks by seed hash, so consecutive builds differ.
- Keep `seed N` for an exact replay.
- Renaming a project to a known setting still retargets palette, names, quests,
  and title in place.

**Done when** ten default builds give ten distinct titles and `seed 7` is stable.

### 18. Intro-to-medium game library

Two-dimensional: platformer, top-down shooter, twin-stick, roguelike, tower
defense, top-down racing, merge/match puzzle, farming sim, card battler, rhythm.

Three-dimensional: first-person maze, third-person platformer, kart racer,
low-poly exploration, wave shooter, block builder.

Each template ships the same project skeleton and an `ARCHITECTURE.md` describing
state, entities, systems, balance knobs, and extension points. `plan a <genre>`
prints the brief; `build a <genre>` writes the working starter.

**Done when** every listed genre builds real files, runs offline, and appears in
the command catalog.

### 19. Composable edits

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

### 20. Optional LLM adapter and budgets

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

### 24. Localized intents and replies

A curated phrase table maps known imperative templates (`crea un juego de
naves`, `baue ein 3d-rpg`, `5 किमी को मील में बदलो`) to canonical English
commands and shows `interpreted as: …`. A small phrase pack localizes the chat
shell for Spanish, French, German, Hindi, and Japanese; preferences persist in
`localStorage`.

**Done when** localized prompts build the same project as their English form,
`reply in <language>` switches and persists, and a missing pack falls back to
English cleanly.

### 25. Library surface and offline packaging

Add a Library panel to the dashboard (search, topic/level/language filters,
reading status, next up), cache catalog metadata in the PWA, and keep keyboard
and dialog behavior consistent with the rest of the tool.

**Done when** the panel works offline, the Pages build ships metadata only, and
non-redistributable text never leaves the machine.

## Order

1. 12 (spec) → 13 (2D engine) → 15 (3D engine) — done
2. 16 (RPG world) — done → 17 (themes/titles) → 18 (library) → 19 (patches)
3. 21 (archive catalog), 22 (language recognition), and 23 (archive search) —
   done. 24 (localized intents) and 25 (Library panel) follow.
4. 20 (LLM adapter), with 14 (sprites) as soon as the subset is vendored

## Open questions

- Step 14 source is known: `huggingface.co/datasets/Angais/pixel-art-atlas-1.4m`,
  CC0-1.0, native 16×16 RGBA. Vendoring a pinned subset with a manifest and
  checksums is deferred until after the 3D and RPG work; procedural sprites
  remain the fallback.
- 3D leads with low-poly WebGL and a Canvas/isometric fallback (decided).
- Steps 11–13, 15–16, and 21–23 are complete. 17 (more theme packs) and 18
  (the game library) remain open; 24 (localized intents) and 25 (Library panel)
  are next. 14 lands when the sprite subset is vendored.
