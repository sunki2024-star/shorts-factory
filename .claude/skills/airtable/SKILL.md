---
name: airtable
description: Use when the Office's content backlog, experiment log, or analytics need to live in a queryable database rather than Markdown — designing the base schema, moving ideas through workflow stages, or reading performance back for the learning loop. Covers the Airtable connector's tools, the exact base schema this Office uses, and the Notion fallback while Airtable is unconnected. Airtable is NOT connected in this workspace.
---

# Airtable — the Office database

Markdown memory in `office/memory/` is the durable, git-versioned copy of Office
state. Airtable is the **queryable** copy: the thing that answers "show me every
hook variant we have shipped under Pillar E that beat a 30% completion rate."

## Status in this workspace: NOT CONNECTED

Airtable is in the connector registry (`installState: not_installed`). Its tools
— `list_bases`, `list_tables_for_base`, `get_table_schema`,
`list_records_for_table`, `create_records_for_table`, `create_table`,
`create_field`, `ping` and others — are **not** in the tool list. Connect it at
claude.ai → Connectors before writing any step that calls them.

**Notion is connected and covers this today.** The schema below is written so it
ports to a Notion database unchanged; build it there now, migrate if Airtable
arrives.

## The base: `Handsel Growth Office`

Five tables. This mirrors `office/memory/` exactly — same field names, so a sync
is a straight copy and never a translation.

### 1. `Backlog` — every idea ever had

| Field | Type | Notes |
|---|---|---|
| `ID` | text | `HS-000`, primary. Never reused, never renumbered |
| `Title` | text | |
| `Hook` | long text | the winning variant, verbatim |
| `Pillar` | single select | A–H (see the Office charter) |
| `Audience` | multi select | Developers · Agent builders · Web3 · General |
| `Format` | single select | screen-demo · explainer · montage · talking-head · animation · meme |
| `Length` | number | seconds, target |
| `Visual concept` | long text | |
| `Script concept` | long text | |
| `Why it may work` | long text | the hypothesis being tested |
| `Hook strength` … `Production difficulty` | number 0–10 | six scores |
| `Priority` | formula | see scoring below |
| `Production cost` | single select | free · low (<$1) · med (<$5) · high |
| `Confidence` / `Novelty` / `Handsel relevance` | number 0–10 | |
| `Status` | single select | idea → approved → in-production → QC → ready → published → **rejected** · **retired** |
| `Rejection reason` | long text | required when Status = rejected |

### 2. `Hooks` — hook variants, one row each

`ID` · `Backlog ID` (link) · `Variant` (A/B/C…) · `Text` · `Archetype` ·
`Selected` (checkbox) · `Result` (link to Published). Hooks outlive their videos.
The point of this table is that a hook that failed on one concept can be
recognised when someone proposes it again on another.

### 3. `Published` — one row per published asset

`ID` · `Backlog ID` · `Platform` · `URL` · `Published at` · `Hook used` ·
`Length` · then metrics: `Views` `Watch time` `Completion rate` `Retention @3s`
`Likes` `Comments` `Shares` `Saves` `CTR` `Followers gained`. Every metric
column also gets a `— measured?` companion: **API · native-insights · unmeasured**.
Never leave a metric blank-but-implied-zero and never fill one by estimating.

### 4. `Experiments` — the controlled tests

`ID` · `Hypothesis` · `Variable` (single select: hook · visual · length · POV ·
tone · platform) · `Arm A` / `Arm B` (link to Published) · `Metric` ·
`Result` · `Verdict` (single select: **A · B · no-difference · inconclusive**) ·
`Observations` (number — how many independent runs this verdict rests on).

`inconclusive` and `Observations = 1` are the two most useful values in the
whole base. One observation is never a conclusion.

### 5. `Lessons` — what was learned, and from what

`ID` · `Lesson` · `Evidence` (link to Experiments — **required**) ·
`Confidence` · `Supersedes` (link to a previous Lesson) · `Date`.

A lesson with no linked experiment is an opinion. Store it, but mark
`Confidence: speculative` and never let it override a lesson with evidence.

## Priority scoring

```
Priority = (Hook strength × 3) + (Visual strength × 2) + (Handsel relevance × 2)
         + Novelty + Understandability − (Production difficulty × 2)
```

Hook is weighted hardest because it gates everything downstream — a 9/10 script
behind a 3/10 hook is not seen. Difficulty is subtracted, doubled, because the
Office's constraint is cycles, not ideas: three cheap experiments teach more than
one expensive video.

## Rules

- **`office/memory/*.md` is the source of truth.** The base is a projection of
  it. On a conflict, git wins.
- **Never delete a row.** `rejected` and `retired` are statuses. A deleted bad
  idea gets regenerated in six weeks by an Office with no memory of it.
- Writing to the Office's own base is pre-approved. Reading another base, or
  writing outside this base, is not.
- Log the `Rejection reason` in the idea's own words, not a code. "Cringe risk —
  reads as crypto-shill" is retrievable; "QC-3" is not.
