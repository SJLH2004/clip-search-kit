# Provenance

This project was **not written from scratch**. It is an engineering refactor and optimization of an existing body of work. Here is the honest history.

## 1. Origin: internal scripts from a real project

It all started with a documentary project that had roughly 2,000 video files. Files were only findable by filename, but editors remember *content* — "that shot where someone salutes". A set of scripts grew out of that need:

| Script | Purpose |
|---|---|
| `extract_multiframe.py` | Grab 3 frames per clip (20% / 50% / 80%) |
| `build_index_mf.py` | Build frame embeddings with Chinese-CLIP |
| `vlm_tag_frames.py` | Call a vision LLM to write a Chinese description per frame |
| `transcribe_audio.py` | Local speech-to-text with faster-whisper |
| `serve_search.py` (v1) | A working web search service |

Those scripts solved the problem for **one project**: hardcoded paths, run-once, no graceful degradation, no self-test. They were effective *in that project* — and that deserves to be stated first.

## 2. Who wrote what

| Phase | Model | Evidence |
|---|---|---|
| Original search service and scripts | **DeepSeek V4.1 Flash** | Confirmed by the project owner |
| Subsequent project work | **Hy4 preview** | Confirmed by the project owner |
| Engineering refactor and optimization in this repo | DSH (DeepSeek Harness) environment | Verifiable from this session run records |

> **On verifiability**: the models used for the original work were confirmed from the project owner recall; no local run records survive from that period. The optimization work in this repo *is* traceable. We label the two accordingly rather than blurring them together.

## 3. External models and why they were chosen

| Stage | Model | Source |
|---|---|---|
| Visual embeddings | Chinese-CLIP `OFA-Sys/chinese-clip-vit-base-patch16` | Open source (HuggingFace) |
| Frame descriptions | Zhipu **GLM-4V** (`glm-4v-flash`) | Documented in the project: 1,890 frames tagged |
| Speech-to-text | faster-whisper (`small`) | Open source, fully offline |

### Why `glm-4v-flash` specifically

This was a **deliberate trade-off**, not a default:

| Consideration | Detail |
|---|---|
| **Cost** | The project was done by a student on a limited budget. `glm-4v-flash` is on the free tier — at the time, the only option that could tag all 1,890 frames |
| **Availability** | Reachable directly from mainland China, no extra network setup |
| **Outcome** | All 1,890 frames tagged; description quality was sufficient to drive keyword ranking and category filtering |

**The cost of that choice, stated plainly**: the free tier is rate-limited, so full-corpus tagging took a long time, and descriptions of complex scenes may be less detailed than a paid tier would produce. Two things make this safe:

- `clipkit tag` supports **resumable runs** — an interruption never loses completed work
- Switching tiers is a one-liner:

      clipkit update --set vlm.provider=zhipu --set vlm.model=glm-4v-plus

In other words: prove the workflow on the free tier, upgrade when quality demands it. For an individually-funded project that is the sensible order of operations.

## 4. What this version changed

The goal was to turn a set of one-off scripts into a **reusable tool**:

| Area | Change |
|---|---|
| **De-projectized** | All paths come from `clipkit.json`; zero hardcoded paths in code |
| **Single entry point** | Six scattered scripts collapsed into one CLI: init / doctor / scan / frames / index / tag / transcribe / serve / query / demo |
| **Graceful degradation** | No numpy means keyword search; no Pillow means skip thumbnails; no tkinter means console menu. Missing heavy dependencies never crash |
| **Cross-platform** | ffmpeg discovery covers Windows / macOS / Linux; added `start.sh`; platform-aware fonts |
| **Installable** | `pyproject.toml`; `pip install --user --no-deps .` makes it available from any directory |
| **Zero-dependency self-test** | `selftest.py`: 36 checks, no footage or models needed, passes in three environments |
| **CI** | GitHub Actions: 3 operating systems x 2 Python versions |
| **Skill packaging** | `SKILL.md` / `INSTRUCTIONS.md` / `PORTABILITY.md` so it can be reused by other AI agents |

### Defects found and fixed during verification

All of these were **reproduced by testing**, not theorized:

1. **Subtitle search returned an empty list** — missing `import sys` in the web layer, plus an inconsistent return contract
2. **Cached frame searches silently returned 0 results** — cache write and read unpacked differently
3. **Queries crashed on any machine with torch installed** — the demo synthetic 64-dim vectors versus Chinese-CLIP actual 512-dim output made `matmul` raise. **Most users have torch**, so this was broken out of the box
4. **The self-test was guaranteed to fail in a zero-dependency environment** — it unconditionally asserted vector and thumbnail generation; now dependency-adaptive
5. **The two template copies could drift** — added byte-level verification that fails loudly on mismatch

## 5. In one paragraph

> This project **grew out of the existing scripts and search service of a real documentary project.**
> It keeps the original technical approach (Chinese-CLIP + VLM descriptions + local transcription),
> and adds de-projectization, a unified entry point, graceful degradation, cross-platform support,
> installability, a self-test, and AI-skill packaging.
> Several defects that would have made it fail out of the box were found and fixed during verification.

## 6. License and acknowledgements

- This project is released under the **MIT** license.
- Open-source dependencies: Chinese-CLIP (OFA-Sys), faster-whisper, ffmpeg, Pillow, NumPy — thanks to their authors and maintainers.
- Frame descriptions use the Zhipu GLM-4V API, subject to its terms of service.
