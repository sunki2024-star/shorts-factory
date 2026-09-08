---
name: shorts-factory
description: Run a short-form video research pipeline end to end — discover what is working in a niche, collect posts, find outliers, pull transcripts, mine comments, analyse hooks, cluster trends, then produce content ideas and finished scripts for YouTube Shorts, TikTok or Instagram Reels. Use when someone asks to research a niche or a competitor for short-form, wants to know why a video went viral, asks for shorts/Reels/TikTok ideas or scripts grounded in real data, or wants a full content plan rather than a single answer. Also use to decide which of the 43 installed research skills to run for a given ask, and to route around missing API keys without stalling.
---

# shorts-factory

The orchestrator for this workspace. Nine stages, each owned by a named skill.
Your job is to pick the shortest path through them that answers the ask, not to
run all nine every time.

## Before anything: establish the run mode

Check which credentials exist:

```bash
for k in SCRAPECREATORS_API_KEY APIFY_TOKEN TUBELAB_API_KEY GEMINI_API_KEY; do
  printf '%-26s %s\n' "$k" "$(printenv "$k" >/dev/null && echo SET || echo unset)"
done
```

That single check decides the mode. Say which mode you are in **before** you
start, in one line — never let a user believe they got API-backed data when
they got a web-sourced approximation.

| Mode | When | What you can do |
|---|---|---|
| **API mode** | the relevant key is set | Every stage. Full metric fidelity, baseline-relative outliers, real transcripts and comments |
| **Open mode** | keys missing | Stages 1 and 2 from public web sources; stages 6–9 at full strength. Outliers become *reported* performance, not measured baselines |

Open mode is a legitimate run, not a failure — most of the analytic value in
this workspace needs no key. Do not stall waiting for credentials, and do not
invent one. Name the missing variable, say what it would have improved, continue.

**Cost gate.** ScrapeCreators, Apify, TubeLab and Gemini bill per request. Before
the first paid call of a run, state roughly how many calls the plan makes and
get a yes. Never fan out `content-planner` across every tracked account without
asking — it is the most expensive entry point here.

## The nine stages

| # | Stage | API mode | Open mode |
|---|---|---|---|
| 1 | Discover | `trend-discovery`, `competitor-social-research` | WebSearch, then `platform-fluency` for what the numbers mean |
| 2 | Collect | `youtube-research`, `tiktok-research`, `instagram-research`, `x-research` | WebSearch/WebFetch for named, verifiable posts |
| 3 | Outlier detection | `outlier-post-finder` | Reported view counts, labelled as reported |
| 4 | Transcript | `transcript-intelligence`, `video-content-analyzer` | Published transcripts and quoted hooks only |
| 5 | Comment mining | `comment-mining`, `audience-research` | `read-the-room` on whatever comment text is quotable |
| 6 | Hook analysis | `hook-anatomy` to diagnose, `content-autopsy` for post-mortem | identical — no key needed |
| 7 | Trend clustering | `trend-radar` | identical |
| 8 | Content idea | `viral-short-form-ideas`, `repurpose-engine` | identical |
| 9 | Script | `viral-short-form` + the platform skill, then `viral-captions-and-ctas`, `voice-matching` | identical |

Stages 6–9 never need a credential. When keys are missing, that is where the
run should spend its effort.

## Routing

Pick the narrowest skill that matches. Full ask-to-skill table:
`references/routing.md`. The pairs that look duplicated and are not:

- `hook-anatomy` diagnoses a hook; `viral-hooks` generates batches of them.
- `trend-discovery` finds trends from data; `trend-radar` judges whether to ride
  one and when. Discovery feeds judgement.
- `repurpose-engine` is cross-platform strategy; `content-repurposing` turns one
  fetched video into concrete assets.
- `content-planner` plans from tracked accounts; `viral-short-form-ideas`
  ideates from pillars and mining with no API at all.

## Hard rules

1. **Cite or drop it.** Every performance claim carries a source URL, or it does
   not appear. A number you cannot point at is a guess.
2. **Say which mode produced each number.** Measured against a creator's own
   baseline, or reported by a third party — these are not the same claim.
3. **Raw views are not performance.** A 2M-view post on a 5M-follower account
   underperformed. Judge against the account's own normal; if you lack the
   baseline, say the comparison is missing rather than implying one.
4. **Preserve exact language.** Hooks, captions, comments and transcript lines
   are quoted verbatim. Paraphrase destroys the thing being studied.
5. **Never promise virality.** These are pattern-based odds. Every upstream
   skill says so; do not overwrite that with confidence you have not earned.
6. **Small samples get small claims.** Under ~10 posts, report observations, not
   patterns. State n.

## Output

Write to `research/{topic-slug}-{YYYY-MM-DD}/` — `report.md` always, plus
`raw.json` / `outliers.json` / `video-analysis.json` when a stage produced them.
API-mode platform skills write their own timestamped folders at the repo root
instead; leave that convention alone.

Every report opens with a **Method** block: mode, sources, sample size, date,
and what was not checked. A reader who cannot tell how solid a finding is will
trust the weak ones as much as the strong ones.

## Platform coverage

Covered: YouTube (+Shorts), TikTok, Instagram (+Reels), X, Reddit, LinkedIn,
Facebook, Threads, Bluesky, Pinterest, Rumble.

**Not covered: 抖音 Douyin, 小红书 Xiaohongshu, 哔哩哔哩 Bilibili.** No installed
skill reaches them. TikTok support is not Douyin support — separate apps,
separate infrastructure, separate catalogues, separate ranking. If asked for
these, say NOT SUPPORTED and offer the extension path in `README.md`; do not
substitute TikTok data and call it Douyin.
