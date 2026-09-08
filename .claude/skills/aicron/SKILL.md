---
name: aicron
description: Use when a shot needs a generative image or video that the free pipeline cannot produce, and a human operator is available to drive a GUI — AICRON is a node-based AI canvas fronting 200+ generative models (Nano Banana, Seedance, Kling) with a timeline editor, under one subscription. Covers when to route a shot to AICRON versus OpenMontage, the operator handoff format, and the Korean-market angle. AICRON has NO public API; it is a human-in-the-loop station, not an automatable step.
---

# AICRON (에이크론) — the human-operated generation station

AICRON is an AI content-creation platform from Morpheus Studio (모피어스 스튜디오),
launched 2026-02-26 after an open beta from October. It unifies **200+
generative models** — Nano Banana, Seedance, Kling among them — behind one
account and one node-based canvas, and it shipped a **timeline video editor**,
which the major generative-video services had not.

Site: <https://aicron.io> · Docs: <https://docs.aicron.io>

## The constraint that shapes everything below

**AICRON has no public API, no MCP server, and no documented webhook or
automation interface.** The published docs cover Workspace, Canvas, AI Assistant,
Timeline, Nodes, Models and Policy — all end-user UI, no developer surface.

So AICRON **cannot be a step in an autonomous run.** It is a station a human
sits at. Any plan that says "generate the shot in AICRON" is a plan that stops
and waits for a person. Price that honestly: it costs a handoff, not a call.

If that changes — if an API appears — the right move is a proper data-layer
skill and an entry in `.env.example`, per the "adding a platform" procedure in
`CLAUDE.md`. Do not scrape the web app to fake one.

## When to route a shot here

Default to OpenMontage. Route to AICRON only when **all** of these hold:

1. The shot genuinely needs generative video or a stylised image the free path
   (Archive.org footage, Remotion, HyperFrames, Imagen) cannot produce.
2. A human operator is available in this cycle.
3. The shot is going into a video that already passed the Gate — never burn
   operator time on an unapproved concept.

Its real advantages over calling one model directly:

- **One subscription instead of five.** Comparing Kling against Seedance against
  Nano Banana for the same prompt normally means three accounts and three bills.
- **The node canvas keeps the graph.** Text → image → video is one visual map,
  so a shot can be re-run from any node when only the last step was wrong. That
  is the same reason this Office keeps hook variants separately from scripts.
- **The timeline.** Generated clips get trimmed and sequenced in place, so what
  comes back is a cut, not a pile of clips needing assembly.

## Operator handoff format

Never hand an operator a prose paragraph. Write this into
`office/production/<idea-id>/aicron-brief.md`:

```
SHOT ID        HS-000-s03
GOES IN        HS-000, between 0:11 and 0:15
DURATION       4.0s exactly — the cut is timed, not flexible
ASPECT         9:16, 1080x1920
PROMPT         <the literal prompt to paste>
NEGATIVE       <what must not appear>
STYLE REF      office/production/HS-000/refs/s03.png   (if any)
MODEL          try Seedance first, then Kling; stop when one is good enough
BUDGET         N generations max, then escalate
MUST CONTAIN   <the one thing the shot exists to show>
MUST NOT       no text in frame (captions are burned in later)
               no logos, no recognisable faces
RETURN AS      ProRes or high-bitrate H.264, no watermark, to renders/s03.mp4
```

`MUST CONTAIN` is the field that saves the cycle. A generated shot that is
beautiful and does not show the one thing is a failed shot.

## Korean-market angle

AICRON is a Korean product with Korean-language docs and a domestic creator base,
and its operator has been pushing into overseas markets. For the Office's Korea
track (a priority region in the charter) that is a content opportunity as much as
a tool: **a Handsel short about agents hiring agents, produced on a Korean AI
canvas, is a natural fit for Korean dev/AI communities** — and Handsel is itself
a Korean-built project. Two Korean AI-infrastructure projects in one frame is a
story that does not exist in English-language content.

Do not overclaim it. It is an angle to test, logged as a hypothesis like any
other, not a partnership.

## Rules

- **Never claim AICRON is automated.** If a plan routes through it, mark the step
  `HUMAN` in the production plan and count it in the cost.
- Generated footage is a paid, non-free asset. It falls under the cost gate in
  `CLAUDE.md` — say what a shot will cost before requesting it.
- Check the platform's commercial-use terms for the specific model used before
  publishing. AICRON markets commercial-grade output, but the terms are per-model
  and are the operator's to confirm, not something to assume.
- Anything generated here is AI-generated media and inherits the platform
  disclosure duties in `viral-tiktok-content` and `viral-instagram-reels`.
