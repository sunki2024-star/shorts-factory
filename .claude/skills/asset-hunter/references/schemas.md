# Asset layer schemas

Three files. All JSON, all committed with the video.

## `asset-manifest.json` — provenance, one row per external file

Nothing external enters a render without a row here.

```json
{
  "assets": [{
    "asset_id": "px-video-8412",
    "scene_id": "HS-024-s03",
    "type": "video | photo | sfx | music | svg | generated | capture",
    "local_path": "office/asset-library/stock/px-video-8412.mp4",
    "source": "pexels | unsplash | freesound | handsel-capture | remotion | manual",
    "source_url": "https://www.pexels.com/video/8412/",
    "creator": "Jane Doe",
    "license": "Pexels License | Unsplash License | CC0 | proprietary-owned | UNKNOWN",
    "attribution": "Video by Jane Doe on Pexels",
    "commercial_use": true,
    "download_time": "2026-08-27T21:14:03Z",
    "original_resolution": "3840x2160",
    "duration": 12.4,
    "recommended_segment": "00:03.10-00:05.40",
    "recommended_crop": "9:16 centre, subject holds frame",
    "reason_selected": "only candidate whose subject survives the vertical crop",
    "content_hash": "sha256:...",
    "used_in": ["HS-024"]
  }]
}
```

**`license: "UNKNOWN"` ⇒ `REFERENCE ONLY`, never production.** `commercial_use:
false` is the same. `content_hash` is what deduplication runs on; `used_in` is
what proves the library is being reused.

## `asset-handoff.json` — what the editor receives

One object per scene. The editor should never need anything not in here.

```json
{
  "scene": "verification_failure",
  "timeline": "00:11.2-00:13.7",
  "primary": "handsel/verifier-reject.mp4",
  "overlay": "generated/rejected-stamp.webm",
  "sfx": "sfx/error-03.wav",
  "instruction": "Punch in 115% when REJECTED appears.",
  "fallback": "generated/verifier-failure-v2.webm"
}
```

`fallback` is not optional. Every scene has a second path, because the first one
fails on render day often enough to matter.

## The motion request — ASSET_HUNTER → MOTION_DESIGNER

```json
{
  "request_id": "mo-014",
  "scene_id": "HS-024-s05",
  "gap_code": "GENERATE_REMOTION",
  "duration": 2.2,
  "must_contain": "$100 leaving escrow and NOT arriving anywhere",
  "must_not": "no text (captions are burned in later), no logos, no faces",
  "emotion": "tension, then anticlimax",
  "data": { "amount": "100.00", "from": "escrow", "to": null },
  "reuse_check": "MoneyTransfer with a null destination — extend, do not fork",
  "deadline_beat": "00:14.0-00:16.2"
}
```

`reuse_check` is mandatory. It forces the question *"does a primitive already do
this?"* before a new component is written, which is the only thing that stops the
component library turning into forty near-identical animations.
