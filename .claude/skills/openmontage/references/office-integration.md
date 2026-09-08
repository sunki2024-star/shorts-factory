# OpenMontage inside the Growth Office pipeline

The Office pipeline is longer than OpenMontage's. OpenMontage owns steps 6–10.

| Office step | Owner | Notes |
|---|---|---|
| 1. Research | `trend-discovery`, `youtube-research`, `tiktok-research`, `instagram-research` | live data |
| 2. Opportunity | `trend-radar`, `outlier-post-finder`, `hook-anatomy` | judgement |
| 3. Ideate | `viral-short-form-ideas` | writes to `office/memory/backlog.md` |
| 4. Hook variants | `viral-hooks` | 3–10 per concept, all logged |
| 5. Script | `viral-short-form` + the platform skill | |
| **6. Scene plan** | **OpenMontage** | pipeline choice locks `render_runtime` |
| **— GATE —** | **human** | nothing paid runs before this |
| **7. Narration** | **OpenMontage** + `voicebox` | free Piper/eSpeak by default |
| **8. Assets** | **OpenMontage** · `penpot` (static) · `aicron` (HUMAN, paid) | |
| **9. Compose** | **OpenMontage** | Remotion or HyperFrames |
| **10. Render** | **OpenMontage** | 1080×1920, captions burned in |
| 11. Quality control | `content-autopsy`, `hook-anatomy`, the QC SOP | reject freely |
| 12. Package | `viral-captions-and-ctas` | title, caption, hashtags per platform |
| 13. Publish | **human approval, always** | |
| 14. Measure → learn | `comment-mining`, `read-the-room`, `content-autopsy` | back into memory |

## The Gate

OpenMontage's own gate is an approval checkpoint between Scene Plan and
Narration. The Office keeps it and adds two rules:

1. **No paid provider runs before the Gate.** Free path only for anything
   pre-approval — Piper, eSpeak, Remotion, HyperFrames, FFmpeg, archive footage.
2. **The Gate approves a scene plan, not a concept.** Approving the idea at
   step 3 does not approve the shot list at step 6.

## Where files go

```
office/production/<idea-id>/
├── plan.md              the production plan (written at step 5)
├── script.md            final script with timings
├── hooks.md             every variant, which was chosen, why
├── narration.wav        from voicebox or OpenMontage TTS
├── refs/                style references
├── renders/final.mp4    1080x1920
├── aicron-brief.md      only if a HUMAN generation step was needed
└── qc.md                the quality-control verdict, including a reject
```

Never leave the deliverable inside `vendor/OpenMontage/projects/` — that tree is
gitignored and gets blown away by a reinstall.
