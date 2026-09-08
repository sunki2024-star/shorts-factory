---
name: zapier-mcp
description: Use when the Growth Office needs to act on the outside world — scheduling or publishing a short, writing a row to a content database, sending an approval request, pulling analytics back in, or syncing assets across services. Covers Zapier MCP setup for Claude Code, tool discovery, the approval policy for irreversible actions, and what to do while it is not connected. Zapier MCP is NOT connected in this workspace; read this before promising any external action.
---

# Zapier MCP — the execution layer

Everything else in this workspace **thinks**. Zapier MCP is the only capability
that would let the Office **act** on ~8,000 external apps: post to a scheduler,
append to a content database, notify a human, read analytics back.

## Status in this workspace: NOT CONNECTED

`ListConnectors` shows Handsel, Notion, Slack and Vercel connected. Zapier is in
the connector registry but `installState: not_installed`. **No Zapier tool is in
the tool list, so no Zapier action can be performed right now.** Do not write a
plan step that assumes one exists.

Meanwhile, the Office is not blocked. See "Fallbacks" below — Slack and Notion
are connected and cover notification and database duties today.

## Connecting it (a human step, not an agent step)

1. Zapier account → **Settings → MCP**. A paid Zapier plan is required for MCP.
2. Create a server and **choose the specific actions to expose**. Zapier MCP is
   allowlist-based: the server only offers the actions you add. Add the minimum.
3. Copy the URL — it looks like
   `https://mcp.zapier.com/api/mcp/a/<ACCOUNT_ID>/mcp`. **It is a bearer
   credential in URL form.** Anyone holding it can run every action you exposed.
4. Add it to Claude Code:

```bash
claude mcp add --transport http zapier "https://mcp.zapier.com/api/mcp/a/<ACCOUNT_ID>/mcp"
```

Never paste that URL into a committed file. `.env`/`.mcp.json` with the real URL
stay out of git — the repo's pre-commit hook blocks env files, but it cannot
catch a URL pasted into Markdown, so do not.

## Discover before you call

Never assume an action exists — the server only exposes what was allowlisted,
and that set changes without notice. Once connected:

1. Read the actual tool list for the session.
2. If the action you need is absent, say so and name it. Do not substitute a
   different action that "seems close" — a wrong Zap fires for real.
3. Prefer one specific action over a generic `run_any_action` passthrough.

## Approval policy — binding

The Office's autonomy stops at the edge of the org. Requires **explicit human
approval every time**, no standing pre-approval:

- publishing or scheduling anything public (any platform, any account)
- sending email, DMs, or messages to anyone outside the Office
- anything that moves money or changes a subscription
- deleting or overwriting records
- granting access, changing permissions, or touching credentials

Runs without asking:

- reading analytics, comments, metrics
- writing to the Office's **own** backlog/experiment databases
- posting a draft **into an internal review channel** for a human to look at

Rule of thumb: if undoing it requires apologising to someone, ask first.

## Fallbacks while Zapier is unconnected

| Need | Zapier would do | Use instead today |
|---|---|---|
| Notify a human for approval | Slack/email Zap | **Slack MCP** — connected |
| Content database | Airtable Zap | **Notion MCP** — connected (see the `airtable` skill for the schema; it ports) |
| Store the backlog | Airtable | `office/memory/*.md` in git — the durable copy regardless |
| Publish/schedule | Buffer/Later Zap | **none — manual.** Produce the publishing package, hand it over |
| Pull analytics | platform Zaps | manual entry into `office/memory/analytics.md`, or the ScrapeCreators skills for public metrics |

The analytics loop is the one that hurts. Without Zapier, retention and
completion-rate numbers have to be typed in by a human from each platform's
native insights — public scraping gives views, likes and comments but **not**
watch time, completion rate or skip rate. Design experiments so they are still
readable from public metrics alone, and mark private metrics as `unmeasured`
rather than guessing.
