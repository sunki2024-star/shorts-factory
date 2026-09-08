---
name: voicebox
description: Use when a short needs narration and the question is which voice, which engine, and how it should sound — casting a narrator, generating a WAV from a script, A/B-testing two reads of the same hook, or applying voice effects (robot, radio, glitch) to make an AI agent sound like an AI agent. Wraps the installed voicebox-tts Python library across eleven TTS engines, free-offline through paid-cloned. Use with openmontage, which consumes the WAV it produces.
---

# Voicebox — the narration layer

`voicebox-tts` **1.0.0** is installed and importable. It is one API in front of
eleven TTS engines plus an effects chain, so a script can be read by a free
offline voice for an experiment and re-read by a cloned voice for the winner
without rewriting the pipeline.

Upstream: [austin-bowen/voicebox](https://github.com/austin-bowen/voicebox), MIT.
Docs: <https://voicebox.readthedocs.io/>.

```bash
pip3 install voicebox-tts          # already done in this workspace
```

## Engines, and what each costs

| Engine | Import | Key | Cost | Use it for |
|---|---|---|---|---|
| eSpeak NG | `voicebox.tts.espeakng` | none | free | robot/agent voice **on purpose** |
| Pico TTS | `voicebox.tts.picotts` | none | free | quick offline drafts |
| pyttsx3 | `voicebox.tts.pyttsx3` | none | free | system voices |
| Parler TTS | `voicebox.tts.parlertts` | none | free, local GPU | promptable voice ("calm male, close mic") |
| gTTS | `voicebox.tts.gtts` | none | free, rate-limited | scratch reads only — do not ship |
| Google Cloud | `voicebox.tts.googlecloudtts` | `GOOGLE_APPLICATION_CREDENTIALS` | paid | 700+ voices, 50+ languages |
| Amazon Polly | `voicebox.tts.amazonpolly` | AWS creds | paid | neural voices, SSML control |
| ElevenLabs | `voicebox.tts.elevenlabs` | `ELEVENLABS_API_KEY` | paid | the realistic one; voice cloning |
| Voice.ai | `voicebox.tts.voiceai` | key | paid | cloning |

Wrappers that matter more than they look: `CachedTTS` (never pay twice for the
same line — put it around every paid engine), `FallbackTTS` (paid → free when a
key is missing or the API is down), `RetryTTS`.

**Nothing but eSpeak NG, Pico, pyttsx3 and Parler is free.** In this workspace
`ELEVENLABS_API_KEY` and AWS credentials are **unset**. Say which variable is
missing and use the free path rather than inventing a key.

## Writing a file, not playing one

PortAudio is not installed here, so `sinks.SoundDevice` warns and playback is
unavailable. That is fine — this pipeline wants files:

```python
from voicebox.tts.espeakng import ESpeakNG, ESpeakConfig
from voicebox.sinks import WaveFile
from voicebox.effects import Normalize
from voicebox import Voicebox

vb = Voicebox(
    tts=ESpeakNG(ESpeakConfig(speed=170, pitch=45, voice="en-us")),
    effects=[Normalize()],
    sink=WaveFile("office/production/HS-000/narration.wav"),
)
vb.say("Two AI agents just negotiated a price. Neither of them is a person.")
```

Hand that WAV to `openmontage` at its narration stage.

## Effects — the reason this beats calling a TTS API directly

`Flanger`, `Glitch`, `RingMod`, `Vocoder`, `Filter`, `Tail`, `Normalize`, plus
`SeriesChain` / `ParallelChain` and any Pedalboard effect.

This matters for Handsel specifically. A short about **agents hiring agents**
has two speakers and they must not sound alike:

- **The agent voice** — eSpeak NG through `RingMod` + a band-pass `Filter`.
  Deliberately synthetic. Cheap, free, and *reads as a machine on purpose*,
  which is the opposite of the uncanny-valley problem a bad cloned voice has.
- **The human/narrator voice** — a neural engine, dry, `Normalize` only.

That contrast is a content decision, not an audio one. See
`references/voice-casting.md` for the Office's standing cast.

## Rules

- **Always `Normalize()`.** Platforms normalise loudness anyway; an unnormalised
  read gets quieter after upload and quiet shorts get skipped.
- **Cache paid engines.** Wrap in `CachedTTS`. Hook A/B tests re-render the same
  script many times and each render is a fresh bill otherwise.
- **Never ship a gTTS read.** It is a scratch voice; its prosody is flat enough
  to read as low-effort, which is a retention risk on a dev audience.
- **Disclose synthetic voices** where the platform requires it (TikTok's AI
  disclosure regime — see `viral-tiktok-content`).
- Write to `office/production/<idea-id>/` so Office memory can find the asset.
