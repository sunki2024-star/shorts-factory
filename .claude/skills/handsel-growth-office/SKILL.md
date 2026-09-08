---
name: handsel-growth-office
description: Invoke first for any Handsel promotion, marketing, or short-form content request — researching what to make, generating or ranking content ideas, writing hooks or scripts about Handsel, producing a video, quality-checking one, packaging it for publish, or reading results back into strategy. Owns the Office's fourteen-step pipeline, the role map, the autonomy boundary (nothing publishes without human approval), the factual-accuracy rule against inventing Handsel functionality, and routing to the 49 installed skills.
---

# Handsel Short-Form Growth Office

The Office is a **learning content machine** for growing awareness and adoption of
Handsel. It lives in `office/` at the repo root. Read `office/CHARTER.md` before
acting on anything below — it is the constitution; this file is the routing table.

> This skill sits **above** `shorts-factory`. `shorts-factory` owns the generic
> research pipeline and the 43 upstream skills. This one owns the Handsel mission,
> the Office's memory, and the approval boundary. For a Handsel request, start here.

## Before anything else

1. **Read `office/research/handsel-model.md`.** Every factual claim in every
   script must trace to a line in it. **Never invent Handsel functionality.** If
   a claim cannot be traced, it does not go in the video.
2. **Read its DO NOT CLAIM ledger.** Handsel is at a genuine cold start with no
   formal contract audit. Claiming traction or security would be false *and*
   off-brand for a project that ships a page called "the numbers that do not
   flatter us."
3. **Check `office/memory/`** — backlog, hooks, rejected, lessons. Do not
   regenerate a rejected concept or re-propose a discarded hook.

## The autonomy boundary — the one rule that never bends

**Nothing publishes without explicit human approval.** Not a draft to a live
account, not a scheduled post, not a "test" upload. Every time, no standing
pre-approval.

Also needs approval: spending on any metered API, contacting anyone outside the
Office, moving money, changing permissions, deleting a record.

Everything else — research, ideation, hooks, scripts, scene plans, free-tier
rendering, QC, writing to `office/memory/` — runs without asking.

**When blocked:** diagnose → find an alternative → take the safest reversible
action → continue. Never stall on a missing key. Name the variable, say what it
would have improved, run the open path, label which mode produced each number.

## Routing

| The ask | Go to |
|---|---|
| "what's working in AI/dev short-form" | `trend-discovery` → `trend-radar` |
| "why did that video pop" | `content-autopsy` → `hook-anatomy` |
| "give me Handsel video ideas" | **the incident ledger in `office/memory/backlog.md`** — see below |
| "write hooks" | `viral-hooks` → log every variant to `office/memory/hooks.md` |
| "critique this hook" | `hook-anatomy` |
| "write the script" | `viral-short-form` → the platform skill |
| "what should be on screen" / "find the footage" | **`asset-hunter`** — beats, search, provenance, handoff |
| "no asset exists for this shot" | **`motion-designer`** — reusable Remotion/SVG primitives |
| "make the video" | `openmontage` (+ `voicebox`, `penpot`, `aicron`) |
| "narration / which voice" | `voicebox` — its bundled voice-casting reference holds the standing cast |
| "title card, brand consistency" | `penpot` → `brand-kit` |
| "generative shot the free path can't do" | `aicron` — **HUMAN step, paid** |
| "is it good enough" | `office/sop/quality-control.md` |
| "write the caption" | `viral-captions-and-ctas` → `platform-fluency` |
| "publish it" | **stop. Package it and request approval.** |
| "how did it do" | `office/sop/analytics-loop.md` → `comment-mining`, `read-the-room` |
| "store this in a database" | `airtable` (schema) — Notion today, Airtable when connected |
| "make something happen outside" | `zapier-mcp` — **not connected**; read it before promising |

Pick the **narrowest** skill that matches. `viral-hooks` generates, `hook-anatomy`
diagnoses. `trend-discovery` finds, `trend-radar` judges.

## Where ideas come from — the generator

**Do not brainstorm.** The backlog is generated:

```
REAL INCIDENT  →  which Lawbook axis/code it lands on  →  one short
```

Start from the incident ledger at the top of `office/memory/backlog.md`. Every
entry is anchored to a checkable event — a job number, a query, a thread. When a
new incident appears (a job settles oddly, a verdict disagrees with itself, a
score moves, a thread blows up), add it to the ledger first; the backlog entry
follows from it. Lesson L-07: v1 of this backlog was generated from the product
and its top idea was beaten by an incident that had been sitting in the account's
own job history the whole time.

Every entry declares a **posture**, and it is load-bearing:

- **SHIPPED** — traceable to `office/research/handsel-model.md`. Real UI, real data.
- **CONCEPT** — the Verification Lawbook proposes it; the product does not emit
  it. May only appear with `CONCEPT` visible on screen.
- **GAP** — Handsel does not do this yet. A build-in-public video about the gap,
  never dressed as a feature.

**A CONCEPT entry shipped without its label is a fabricated feature.** The 16
Lawbook codes are a design proposal — the source document says so about itself
twice. See `office/research/verification-lawbook.md`.

Run the repo-root backlog verifier (`verify_backlog.py`, under the repo `scripts/`
 directory) after editing the backlog. The `Pri`
column is a formula over judgement scores; a wrong cell makes a judgement look
like a fact.

## The asset layer — a separate system from research

Trend research and asset acquisition are **different systems** and must not be
collapsed. `trend-discovery` and `last30days` study the internet; `asset-hunter`
studies the script.

```
SHOT_DESIGNER → ASSET_HUNTER ─┬─ real Handsel capture
                              ├─ library / stock (keys permitting)
                              └─ gap → MOTION_DESIGNER → clip
                                        ↓
                                  ASSET PACKAGE → VIDEO_EDITOR
```

**The editor never searches for media.** If it has to, `asset-hunter` did not
finish. If an asset is missing mid-edit: `VIDEO_EDITOR → ASSET_GAP →
ASSET_HUNTER`. If an animation is missing: `ASSET_HUNTER → MOTION_DESIGNER →
VIDEO_EDITOR`. This separation is not advisory.

Stock keys (`PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY`, `FREESOUND_API_KEY`) are
**unset**; all three servers are audited and approved in the Office's skills
registry. Being blocked costs texture and B-roll, not the ability to make videos
— the decision engine puts real capture and generated motion above stock anyway.

## The cycle

```
observe → ideate → score → GATE → produce → QC → package → APPROVE → publish
→ measure → bucket the failure → lesson → back to observe
```

Full step table: `.claude/skills/openmontage/references/office-integration.md`.
SOPs: `office/sop/`.

## Standing rules

- **One idea per video.** A second idea is a second video.
- **One variable per experiment.** Two arms. Hypothesis written *before* publishing.
- **Never optimise from one observation.** `Observations: 1` is a note, not a lesson.
- **`unmeasured` is written, never estimated.** A guessed retention figure poisons
  every lesson derived from it.
- **Never publish an untyped verdict.** One word that collapses outcome, cause,
  attribution and settlement is a guess wearing a verdict's clothes (L-09).
- **Tracing a claim to a source is not verifying it.** Where a claim rests on a
  system's own status string, query a second and third surface first (L-08).
- **Log the rejects.** Ideas, hooks, renders. In plain words, with what was worth
  keeping.
- Raw views are not performance — baseline-relative or it does not count.
- Never promise virality.

## Cost gate

Free: Piper · eSpeak · Remotion · HyperFrames · FFmpeg · archive footage · every
prose skill · `read-the-room`.

Metered: ScrapeCreators · Apify · TubeLab · Gemini · every generative provider ·
AICRON. Say roughly how many calls a plan makes **before** making them, and never
run a paid provider before the Gate.
