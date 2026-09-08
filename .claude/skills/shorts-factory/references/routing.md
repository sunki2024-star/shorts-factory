# Ask → skill routing

The narrowest skill that matches the ask wins. `(key)` marks a skill that needs
a credential; everything unmarked runs free and offline.

## Research

| The user asks | Run |
|---|---|
| "what's blowing up in <niche>" | `trend-discovery` (key) → `trend-radar` |
| "is this trend worth riding / am I too late" | `trend-radar` |
| "what is <competitor> doing" | `competitor-social-research` (key) |
| "why does <creator> work / what can I copy" | `creator-profile-teardown` (key) |
| "find their best performing posts" | `outlier-post-finder` (key) — baseline-relative |
| "who should I partner with" | `influencer-prospecting` (key) |
| "does their audience match mine" | `audience-research` (key) |
| "what are people saying about <brand/topic>" | `social-listening-brief` (key) |
| "will anyone buy this / what are the objections" | `product-demand-research` (key) |
| "tear down their ads" | `ad-library-teardown` (key) |
| raw endpoint / "just fetch me X" | `scrapecreators-api` (key) |

## Collection

| The user asks | Run |
|---|---|
| "research YouTube for <niche>" | `youtube-research` (TUBELAB) |
| "research TikTok / Instagram / X accounts" | `tiktok-research` / `instagram-research` / `x-research` (APIFY) |
| "watch this video and tell me why it works" | `video-content-analyzer` (GEMINI) |
| "plan across all four platforms" | `content-planner` (all keys) — most expensive, confirm first |

## Analysis — no key needed

| The user asks | Run |
|---|---|
| "why did this flop / why did this pop" | `content-autopsy` |
| "critique this hook" | `hook-anatomy` |
| "what do these comments actually mean" | `read-the-room` |
| "how does <platform> work" | `platform-fluency` |
| "does this sound like me" | `voice-matching` |
| "get transcript insights" | `transcript-intelligence` (key) |
| "mine these comments" | `comment-mining` (key) |

## Creation — no key needed

| The user asks | Run |
|---|---|
| "give me hooks" | `viral-hooks` |
| "I'm out of ideas" | `viral-short-form-ideas` |
| "write the script" | `viral-short-form` + platform skill |
| "make it Shorts / TikTok / Reels specific" | `viral-youtube-shorts` / `viral-tiktok-content` / `viral-instagram-reels` |
| "caption, hashtags, CTA" | `viral-captions-and-ctas` |
| "put this on another platform" | `repurpose-engine` (strategy) / `content-repurposing` (assets, key) |
| "structure the video" | `video-formats` |
| "keep it on brand" | `brand-kit` |

## Meta

| The user asks | Run |
|---|---|
| "walk me through setup" | `agent-interview` |
| "can this machine render video" | `studio-setup` |
| "add a new platform" | `skill-creator`, or `mcp-builder` if it needs a real API integration |

## Not routable

抖音 Douyin, 小红书 Xiaohongshu, 哔哩哔哩 Bilibili — no skill reaches them.
Say NOT SUPPORTED. Do not route these to `tiktok-research` or
`scrapecreators-api`; those endpoints do not cover Chinese platforms.
