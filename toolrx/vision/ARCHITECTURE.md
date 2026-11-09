# Phase-1 Architecture — tiny vision SAN ("vision-agent on the edge")

Status: DRAFT (Phase 1 design)
Authors: opencode + user
Supersedes: none. Companion to the Needle 2 reference run on the lab host.

---

## 1. Goal

A single **small vision model** that shares the design philosophy and runtime of
Needle 2 (attention-only / SAN, 2-bit QAT, single binary) and covers, in priority order:

1. **image → structured output** (the primary goal): a photo / scan / receipt
   becomes a JSON document (e.g. `{"kind":"receipt","total":12.4,"items":[...]}`).
2. **classification**: N-way labels (ImageNet-1000-compatible, or domain sets).
3. **detection**: bounding boxes + class + confidence for `M` objects.
4. **embeddings**: L2-normalized vector for retrieval / similarity.
5. **generation** (EXPERIMENTAL / stretch): free-form caption or prose about the image.

## 2. Design principles (derived from measured references)

- **Attention-only core, no dense FFN.** The SAN paper (arXiv:2607.18363) shows
  attention-only transformers match standard ones at matched parameter count, with
  better context-grounded answers, and a much smaller / simpler binary. The vision
  backbone reuses this core so the **whole family shares one runtime + quantizer**.
- **Fixed Walsh-Hadamard transform + Sinkhorn routing** for the attention primitive
  (as in Needle) — cheap, deterministic, QAT-friendly.
- **Tiny token counts on purpose.** 96–128 px input, 8×8 patches → 144–256 tokens,
  sitting inside Needle's own 256-token KV window.
- **Heads are thin; the backbone is shared.** One encoder, several small task heads.
- **QAT 2-bit from the start** (CQ2), single binary export — the deployment contract.
- **Distill, don't pretrain-from-scratch** (compute is the hard constraint — see §9).

## 3. System overview

```
                 ┌───────────────────────────────────────────────┐
   image ──► ┌───┴───┐   patch-embed conv   ┌──────────────────┐   │
 (96/128²)   │ stem  │ ──► tokens (144-256) │  vision SAN core  │   │
             └───────┘                      │  (attn-only ×L)   │   │
                                            └────────┬─────────┘   │
                                                     │ shared features
                       ┌──────────────┬──────────────┼──────────────┬─────────────┐
                       ▼              ▼              ▼              ▼             │
                 [class head]   [embed head]   [detect head]   [JSON head]       │
                 logits(1000)   L2 (d-dim)     boxes+cls       bytes→JSON ───────┘  generation
                 ──────────        ──────        ─────────     (cross-attn to decoder, stretch)
   onnxruntime (conv/linear)   ←──────── hybrid: SAN core via Needle engine ──────►
```

- **onnxruntime** runs the conv stem + linear heads (already proven on the lab host).
- The **SAN core + JSON decoder** reuse the Needle ctypes engine (already running).
- Outputs are typed; a schema validator converts the byte stream to JSON (§6).

## 4. Backbone — vision SAN encoder

### 4.1 Stem (patch embedding)
- Conv `3→C` with `kernel=8, stride=8` (non-overlapping patches), + LayerNorm, + optional
  hard-swish activation (mobile-friendly, matches MobileNetV3 recipe).
- `96²` → `12×12 = 144` tokens; `128²` → `16×16 = 256` tokens.
- Add a small learned 2D positional embedding (learned, or fixed Walsh–Hadamard rows).

### 4.2 Core blocks (×L, attention-only)
Each block:
1. **Walsh–Hadamard attention** — fixed Hadamard transform of Q/K, Sinkhorn-renormalized
   routing, head-mixing via a small projection (no softmax QK^T, no FFN).
2. Optional 2-bit **KV-sink pinning** so the encoder also sits in the 256-token window.
3. Residual + layer-norm on every block (standard).

Config knobs: `d_model`, `num_heads`, `L`, input resolution.

### 4.3 Token pooling
- CLS-style learned token at the front for classification / embedding.
- Detection + JSON heads consume the full token sequence (all 144–256).

## 5. Heads

| Head | Input | Output | Notes |
|------|-------|--------|-------|
| **Class** | CLS token | `logits[N]` | softmax; soft targets from teacher |
| **Embedding** | CLS token → linear | L2-normalized `d`-dim | mirrors the 576-dim MobileNet reference, reduced to `d=128` |
| **Detect** | token seq → 2-lay. decoder (10 learned queries) | `[M, (cx,cy,w,h,cls,conf)]` | DETR-style, `M` fixed budget |
| **JSON / structured** | token seq (cross-attn) | byte sequence → JSON | the PRIMARY head; see §6 |
| **Generation** (stretch) | causal decoder over image tokens | free text | shares SAN core; bigger config |

## 6. image → structured output (primary head)

- A small **autoregressive SAN decoder** emits bytes, grammar-constrained to a
  declared JSON schema (same idea as Needle's byte-level grammar + schema-constrained
  generation, which yields clean tool-calls / refusals).
- `encode: image → image tokens`; decoder cross-attends to image tokens, emits
  `{...}` via schema-guided sampling. Empty / low-confidence → structured refusal
  `{"error":"unsupported"}`.
- Runtime pairing already proven: Needle emits `{"name":...,"arguments":...,"confidence":0.97}`.

## 7. Scaling ladder

| Config | input | d_model | heads | L | backbone | decoder | ≈params | ≈size(2-bit) | tokens |
|--------|-------|---------|-------|---|----------|---------|---------|--------------|--------|
| **S** | 96² | 128 | 4 | 4 | ~0.9M | — | ~0.9M | <0.4 MB | 144 |
| **M** | 128² | 192 | 6 | 6 | ~3M | JSON head ~0.6M | ~3.6M | ~1.8 MB | 256 |
| **L** | 128² | 256 | 8 | 8 | ~7M | + decoder ~8M | ~15M | ~7.5 MB | 256 |

Baselines for reference (measured on the lab host Atom):
- MobileNetV3-Small (2.5M, fp32 10.2 MB): 576-dim embed / 1000-class at ~40 ms.
- Needle 2 (45M, 14 MB, 28 MB RAM): SAN agent, 9 tok/s decode.

**Sizing conclusion:** config-**M** (~3.6M) is the sweet spot — comparable to
MobileNetV3-Small in cost but with detection + JSON heads, comfortably within
Needle's RAM envelope.

## 8. Runtime & quantization

- **Quantization:** QAT 2-bit from pretrain (CQ2), matching Needle's
  `needle2.cact` contract. Post-quant 2-bit → final single-binary export.
- **Hybrid runner:**
  - conv stem + linear heads → onnxruntime (installed, working).
  - SAN core + JSON decoder → Needle ctypes engine (installed, working).
  - A thin C ABI glues them; both already run on the lab host.
- **Device-agnostic:** same binary targetable to ARM (phone) later, as Needle is.

## 9. Training plan (Phase 2 — risks here)

1. **Distill the backbone** — teacher = MobileNetV3-Small embeddings (live) + soft
   ImageNet labels; match cosine / L2 on a real-photo pool (picsum + a small labeled
   set). Lighter than pretraining, works on the lab host.
2. **Detection + JSON post-train** — supervised image→box and image→JSON fine-tune
   (receipts/scans/UI, ~1–5k synthetic examples generated programmatically).
3. **QAT 2-bit** from the fine-tuned float model.
4. **LoRA** for task-adaptation without full retrain.
5. **Generation** (stretch) — separate, larger config; deferred.

**Compute risk (explicit):** no GPU (3060 gone), the lab host is a weak Atom. Distillation
is feasible; any real pretrain/scale-up needs a cloud GPU or waiting for the 3060.
This is the single biggest open risk — flagged, not yet resolved.

## 10. Open questions

- Token strategy: overlap (`stride<kernel`) for detection vs pure non-overlap?
- SAN routing vs softmax self-attention for vision — measure both on config-S.
- Schema scope for JSON head: fixed receipt schema first, or open-schema (harder)?
- Teacher for image→text: MobileNet + Needle can't do vision-language directly;
  a real VLM teacher needs bigger hardware (§9 risk).

## 11. Roadmap

- [x] Phase 0 need: Needle runtime on the lab host (9 tok/s, tool-call demo, 0.97 conf).
- [x] Phase 0 vision: MobileNetV3-Small ONNX — 1000-class + 576-dim embeddings, 40 ms.
- [ ] Phase 1a: stem + SAN core (config-S) in a trainable form (cloud/GPU).
- [ ] Phase 1b: heads (class/embed first; detect, then JSON).
- [ ] Phase 2: distill → post-train → QAT 2-bit → LoRA → single binary.
- [ ] Phase 3: generation (stretch, config-L).

---

*All benchmark numbers here are vendor/own-measured, not third-party reproductions.*
