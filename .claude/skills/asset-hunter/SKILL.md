---
name: asset-hunter
description: Use after a script and shot list exist and before any editing — decide what the viewer sees in every 0.5–3 second beat, search for usable media, score candidates, record provenance and licence, and hand a complete asset package to the editor. Owns the asset decision engine, the asset manifest, the reusable asset library, and the gap routing that sends unresolved visuals to motion-designer. Not a marketing-reference researcher; that is trend-discovery's job.
---

# ASSET_HUNTER

The editor must never search the internet. **Everything it needs arrives in the
handoff.** That is the whole reason this role exists.

Scope: **script → beats → search → score → acquire → provenance → prepare →
hand off.** Nothing about trends, hooks or ideas — that is `trend-discovery`,
`viral-hooks` and the Office backlog.

## Toolchain status in this workspace

| Source | Server | Status |
|---|---|---|
| Pexels video + photo | `hanoak/pexels-mcp-server` | **BLOCKED: PEXELS_API_KEY_REQUIRED** |
| Unsplash photo | `cevatkerim/unsplash-mcp` | **BLOCKED: UNSPLASH_ACCESS_KEY_REQUIRED** |
| CC0 sound effects | `sandraschi/sfx-mcp` | **BLOCKED: FREESOUND_API_KEY_REQUIRED** (free to obtain) |
| Deterministic motion | `remotion-*` skills | **INSTALLED, no key needed** |
| Frame-accurate render | the Office's own Pillow engine | **WORKING** |
| Real product capture | Handsel MCP + the live site | **WORKING** |

All three audits and the reasoning are in the repo-root skills registry
(`registry.md`, under the Office's `skills/` directory).

**Never fabricate a credential.** Report the exact variable name and route the
beat elsewhere. With no stock keys, the decision engine below correctly collapses
toward real capture and generated motion — which is the priority order anyway.

## The asset decision engine

For every beat, walk this in order and stop at the first that can actually serve:

1. `REAL_HANDSEL_CAPTURE` — real product behaviour
2. `EXISTING_HANDSEL_ASSET` — already in the library
3. `PEXELS_VIDEO`
4. `PEXELS_PHOTO`
5. `UNSPLASH_PHOTO`
6. `EXISTING_VECTOR_OR_ANIMATION`
7. `REMOTION_GENERATED`
8. `IMAGE_GENERATION_REQUEST` — paid, Gate-gated
9. `MANUAL_ASSET_REQUIRED` — a human has to make or shoot it

**Real product behaviour outranks everything.** Stock is supporting material, not
the protagonist. A video whose hero shot is a stock clip of someone typing is a
video about typing.

## Beat analysis

Split the script into **0.5–3 second** beats. One stock clip must never cover a
whole sentence. For every beat answer five questions:

1. What is the viewer **hearing**?
2. What should the viewer **see**?
3. What information **must be understood** by the end of this beat?
4. What **emotion** should the visual create?
5. What **asset type** best serves that?

Then assign a source from the engine. Write it into the shot table with an
explicit `t_start`/`t_end`.

## Search query generation

Never use one literal query. Generate **6–10 semantic variants** spanning literal
and metaphorical readings before concluding nothing exists.

For *"an AI company receives investment"*: `startup funding` · `company receives
investment` · `digital money transfer` · `business funding` · `finance
transaction` · `startup office money` · `digital wallet payment` · `capital
allocation` · `investment animation`.

## Candidate scoring

Retrieve multiple candidates for any important shot. Score 0–10:

`VISUAL_IMPACT` · `RELEVANCE` · `MOBILE_READABILITY` · `VERTICAL_CROP` ·
`QUALITY` · `EDITABILITY` · `LICENSE_SAFETY` · `BRAND_FIT` · `NOVELTY`

**Prefer vertical footage.** For landscape, decide whether a meaningful 9:16 crop
exists — and **reject visually strong footage whose subject leaves the frame after
cropping.** A great 16:9 shot that loses its subject at 9:16 scores 0 on
`VERTICAL_CROP` and is not a candidate, however good it looks in the browser.

`LICENSE_SAFETY` below 8 is an automatic reject regardless of every other score.

## Gap routing — stop searching

After reasonable effort (roughly 2 query rounds, ~10 candidates), **stop** and
emit exactly one:

`GENERATE_REMOTION` · `GENERATE_IMAGE` · `GENERATE_SVG` · `RECORD_HANDSEL` ·
`CUSTOM_MOTION_REQUIRED` · `MANUAL_ASSET_REQUIRED`

Stock is semantically weak for anything agent-native. *"AI Office A hires AI
Office B and transfers $2"* has no stock representation and never will — that is
`GENERATE_REMOTION` on sight, not twenty minutes of searching
`robots hiring robots money animation`.

Gaps go to `motion-designer`. See `references/schemas.md` for the request shape.

## Provenance — the hard rule

**Every external file gets a row in `asset-manifest.json` before it can be used.**
Fields and the handoff shape are in `references/schemas.md`.

**An asset with `license: UNKNOWN` is `REFERENCE ONLY` and is not
production-ready.** It may inform a generated replacement; it may not enter a
render. No exceptions, and no "we'll check later" — the check never happens later.

Unsplash additionally **requires** calling its download-tracking endpoint when an
image is used, and attribution in the form *"Photo by NAME on Unsplash"*. The
server exposes both; use them.

## The library, and why the search rate should fall

Assets live in `office/asset-library/` under: `handsel-ui/` `office/` `agents/`
`money/` `contracts/` `verification/` `credit/` `github/` `coding/` `ai/`
`stock/` `backgrounds/` `motion/` `svg/` `sfx/` `music/`.

Deduplicate by content hash. Record historical usage per asset. **Over time the
external-search rate must fall** — if it is not falling, the library is not being
reused and the role is failing at its actual job. Prefer a Handsel-native
primitive over a generic stock clip even when the stock clip is prettier.

The SFX library is built once and reused. Do not re-download a click for every video.

## Handoff

Produce `asset-handoff.json` per scene. The editor's input must be complete:
primary, overlay, sfx, a one-line instruction, and a fallback. If the editor has
to go looking, this role did not finish.
