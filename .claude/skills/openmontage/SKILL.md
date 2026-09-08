---
name: openmontage
description: Use when a short-form concept has to become an actual rendered 9:16 MP4 — narration, scenes, captions, music, compose, render. Wraps the vendored OpenMontage agentic video engine (12 pipelines, ~52 tools, Piper/Remotion/HyperFrames/FFmpeg free tier). Reach for it at stage 10 of the Growth Office pipeline, after a script exists and before quality control. Also use to check which generation providers are actually reachable with the keys currently set.
---

# OpenMontage — the render layer

`viral-short-form` and the platform skills write the script. **OpenMontage turns
a script into a file.** It is the only installed capability that produces an
actual `.mp4`; everything else in this workspace produces text.

Upstream: [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage),
**AGPL-3.0**. It is vendored at `vendor/OpenMontage/` (gitignored — it is 160 MB
and reproducible). It is *not* part of this repo's skills tree and is not covered
by `skills-lock.json`; `npx skills update` will never touch it.

> **License boundary.** AGPL-3.0 is copyleft with a network clause. Rendering
> videos locally and publishing the videos is fine — video output is not a
> derivative work of the renderer. Do **not** merge OpenMontage source into this
> repo, and do not expose it as a hosted network service without publishing the
> corresponding source.

## Install / repair

```bash
bash .claude/skills/openmontage/scripts/install.sh
```

Idempotent: clones or updates `vendor/OpenMontage`, installs Python deps, checks
for `ffmpeg`/`ffprobe`, and prints the capability catalogue. Run it whenever a
tool reports missing.

## Check what is actually reachable before promising a render

Provider availability is a function of which keys are set. Never plan a shot
list around a provider you have not confirmed:

```bash
cd vendor/OpenMontage && python3 -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"
```

The registry is the single source of truth. Do not maintain a hardcoded tool
list, and do not assume a tool exists because the README names it.

## The free tier is the default

`GEMINI_API_KEY` is set in this workspace and OpenMontage reads it as
`GOOGLE_API_KEY`'s alias — that unlocks Imagen images, Google TTS and Veo. Every
other provider key is unset. The zero-key path still produces finished video:

| Need | Free tool | Notes |
|---|---|---|
| Narration | Piper TTS | offline, no key, no per-call cost |
| Composition | Remotion (React) | default for data-driven explainers, stat cards, word-level captions |
| Composition | HyperFrames (HTML/GSAP) | default for motion-graphics-heavy briefs, kinetic typography |
| Footage | Archive.org · NASA · Wikimedia | real motion footage, public domain |
| Post | FFmpeg | encode, burn subtitles, mix audio, grade |
| Subtitles | built-in | word-level timing |

**Cost rule from `CLAUDE.md` applies here too.** Piper, Remotion, HyperFrames,
FFmpeg and the archive sources are free. Veo, Imagen, Kling, ElevenLabs, fal.ai
and Replicate bill per call. Say roughly what a plan will spend before running
it, and prefer the free path for experiments — a hook test does not need a $1.50
generative shot.

## Pipelines

Pick the narrowest one. Defined in `vendor/OpenMontage/pipeline_defs/*.yaml`.

| Pipeline | Produces | Use for a Handsel short when |
|---|---|---|
| `screen-demo` | screen recording + captions + narration | showing a real Handsel workflow (Pillar D) |
| `animated-explainer` | narrated motion graphics | explaining escrow, grading, credit (Pillar E) |
| `clip-factory` | many cuts from one source | slicing a long demo into a week of shorts |
| `documentary-montage` | real archival footage cut to a bed | Pillar G visual simulations, no narration |
| `talking-head` | one speaker, captions | founder POV (Pillar F) |
| `animation` / `character-animation` | SVG rigs, GSAP | agents-as-workers metaphors (Pillar G) |
| `podcast-repurpose` | long audio → shorts | if a Handsel talk ever exists |
| `avatar-spokesperson` | synthetic presenter | **avoid** — high cringe risk for a dev audience |
| `cinematic` · `hybrid` · `localization-dub` | see the YAML | |

## Nine stages and a gate

Brief → Research → Script → Scene Plan → **Gate** → Narration → Music → Compose
→ Render.

The Gate is a human approval checkpoint and it is not optional here. The Growth
Office's rule is stricter than OpenMontage's: nothing renders on a paid provider
and nothing publishes without explicit approval. See
`references/office-integration.md` for where this sits in the Office pipeline.

## Output contract for this workspace

Always render 1080×1920, 9:16, with burned-in captions. Deliver into
`office/production/<idea-id>/` so the Office memory can find it, not into
OpenMontage's own `projects/` tree.

## Failure modes

- **`ffmpeg: not found`** → run the installer; it drops a static build in
  `/usr/local/bin`.
- **A provider tool is listed but errors** → its key is unset. Do not invent
  one. Name the variable, fall back to the free path, and say which stage was
  degraded.
- **Render is silent** → check the narration stage produced audio before
  compose; Piper writes a WAV that the compose step must be pointed at.
- **Fonts look wrong in Remotion** → the composer needs `npm install` inside
  `vendor/OpenMontage/remotion-composer`; the installer does this only when Node
  is present.
