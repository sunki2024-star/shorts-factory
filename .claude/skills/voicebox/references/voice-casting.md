# Standing voice cast — Handsel Growth Office

One decision made once, so every short sounds like it came from the same place.
Change it here, not per video.

## The cast

| Role | Engine | Config | Effects | When |
|---|---|---|---|---|
| **NARRATOR** | Parler TTS (free, local) → ElevenLabs when a key exists | dry, close-mic, mid-pace ~165 wpm | `Normalize()` | explainer VO, founder-adjacent narration |
| **AGENT-A (hirer)** | eSpeak NG | `speed=165 pitch=50 voice=en-us` | `Filter` band-pass 300–3400 Hz, `Normalize` | the agent that posts the job |
| **AGENT-B (worker)** | eSpeak NG | `speed=175 pitch=35 voice=en-gb` | `RingMod` (subtle), `Filter`, `Normalize` | the agent that claims and delivers |
| **GRADER** | eSpeak NG | `speed=150 pitch=25 voice=en-us` | `Vocoder`, `Normalize` | the independent verdict — colder, slower, final |
| **SCRATCH** | Pico TTS | default | `Normalize` | timing passes only, never published |

Three distinct machine voices matter because the whole Handsel story is *who is
talking to whom*. If the hirer, the worker and the grader sound identical, the
one idea the video exists to convey — that grading is done by a third party — is
invisible on the audio track.

## Rules

- **GRADER never sounds friendly.** It is the trust mechanism; warmth undercuts it.
- **Agents are synthetic on purpose.** Do not cast a realistic cloned voice as an
  AI agent. Leaning into the machine timbre is legible; a near-human agent voice
  is uncanny and reads as a cheap deepfake.
- The **NARRATOR is the only voice allowed to make a claim**. Agent voices only
  say things an agent would actually emit. Keeps the factual-accuracy check in
  quality control simple: audit narrator lines, not dialogue.
- Korean-language cuts: Google Cloud TTS (`ko-KR-Neural2`) for narration, eSpeak
  NG `voice=ko` for agents. Same effects chain so the cast stays recognisable.

## Loudness

Target roughly −14 LUFS integrated after mixing, true peak under −1 dBTP. Both
TikTok and YouTube normalise toward that neighbourhood; delivering hotter buys
nothing and delivering quieter costs retention in the first second.
