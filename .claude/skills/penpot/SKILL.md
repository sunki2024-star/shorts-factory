---
name: penpot
description: Use when a short needs designed visual assets rather than generated ones — thumbnail frames, title cards, lower thirds, end cards, the agent/office/market illustrations for visual-simulation videos, or a reusable brand board so every video looks like the same channel. Covers the official Penpot MCP server (local and remote setup), its five tools, and when to design in Penpot versus generate in OpenMontage. Penpot MCP is NOT connected in this workspace.
---

# Penpot — the design layer

Penpot is the open-source design tool; it ships an **official MCP server** so an
agent can read and modify real design files. For this Office it is the answer to
"our shorts should look like they come from one channel."

Docs: <https://help.penpot.app/mcp/> · source lives in the main
[penpot/penpot](https://github.com/penpot/penpot) repo under `mcp/` (the old
standalone `penpot-mcp` repo was archived 2026-02-03 and folded in).

## Status in this workspace: NOT CONNECTED

No `penpot` tool is in the tool list. Setup below is a human step.

## Setup

**Local mode** — uses your active Penpot browser session, no key:

```bash
npx @penpot/mcp@stable      # keep it running
```

```bash
claude mcp add --transport http penpot "http://localhost:4401/mcp"
```

**Remote mode** — Penpot account → **Integrations → MCP Server** → generate a
key (shown once):

```bash
claude mcp add --transport http penpot \
  "https://<your-penpot-domain>/mcp/stream?userToken=<MCP_KEY>"
```

The token is in the URL, so it is a credential — never commit it.

## The five tools

| Tool | What it is for |
|---|---|
| `high_level_overview` | read a file's structure — **always start here** |
| `execute_code` | the real surface: query, transform, and create shapes |
| `penpot_api_info` | the API reference `execute_code` is written against |
| `export_shape` | pull a board or shape out as an image asset |
| `import_image` | push an image in (full support local; limited remote) |

Penpot exposes five tools where Figma's server exposes 15+. `execute_code` is
doing most of the work — read `penpot_api_info` before writing against it rather
than guessing method names.

## Penpot or OpenMontage?

They are not competitors; they own different layers.

- **Penpot** — anything that must be *pixel-identical every time*: the caption
  style, the logo lockup, the end card, the colour tokens, the recurring
  "agent" / "office" / "escrow" illustrations. Deterministic, versioned, editable.
- **OpenMontage** — anything that moves, and anything one-off: footage, motion,
  narration, generated imagery, the render itself.

The workflow: design the static furniture once in Penpot → `export_shape` to PNG
→ feed as an overlay/asset to OpenMontage's compose stage. Do **not** regenerate
the logo or title card with an image model per video; that is how a channel stops
looking like one channel.

## What to build first

A single Penpot file, `handsel-shorts-kit`, with one board per asset:

1. **Title card** — 1080×1920, hook text at 1/3 height, safe margins clear of
   TikTok's right rail and bottom caption bar.
2. **Caption style** — the exact font, weight, stroke, and highlight colour that
   the burned-in captions must match.
3. **Agent tokens** — the recurring visual for an agent, a job, an escrow, a
   verdict. These four nouns carry every Handsel explainer; give them one shape
   each and reuse them forever.
4. **End card** — the CTA frame. One per platform, since the safe area differs.
5. **Colour + type tokens** — so `brand-kit` has something concrete to point at.

Record the exported paths in the `brand-kit` skill's kit file so the rest of the
pipeline picks them up automatically.

## Rules

- `high_level_overview` before any mutation. Never write blind into a file
  someone else is editing.
- Design 1080×1920 natively. Do not design 16:9 and crop — the safe areas are
  different and text lands under platform UI.
- Export at 2× and let the composer downscale; upscaled PNGs read as soft against
  a sharp video track.
