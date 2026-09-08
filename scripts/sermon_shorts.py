#!/usr/bin/env python3
"""Tier 0 sermon-to-Shorts pipeline — 방배동 예심교회.

Four stages, each runnable on its own so a failure never costs you the
stages that already succeeded:

  fetch       yt-dlp the sermon into office/production/<id>/source/
  transcribe  find the sermon inside the service, then transcribe just that
  clips       print the transcript for reading, then validate clips.json
  render      cut → 9:16 crop → Korean subtitle burn-in → MP4

A Sunday recording is the whole service, not a sermon: 60-85 minutes of which
the sermon is well under half, the rest worship, prayer, offering and notices.
`transcribe` therefore locates the sermon first and works only inside it —
cheaper, and it keeps every later stage away from the worship music, which is
where Content ID lives.

Clip selection is deliberately NOT automated. Stage `clips` prints a
timecoded transcript and stops; a human (or Claude) reads it and writes
clips.json with a stated reason per clip. A keyword heuristic cannot tell
the difference between a pastor's throwaway aside and the line the whole
sermon turns on, and guessing badly here is worse than not guessing.

Nothing in this file uploads anything. Rendering is the last step; publishing
is a human decision, every time.

Usage:
  python3 scripts/sermon_shorts.py sermons    [--pick]
  python3 scripts/sermon_shorts.py fetch      SUN-2026-08-30 --url <youtube-url>
  python3 scripts/sermon_shorts.py transcribe SUN-2026-08-30 [--backend auto] [--whole]
  python3 scripts/sermon_shorts.py clips      SUN-2026-08-30 [--window 12]
  python3 scripts/sermon_shorts.py render     SUN-2026-08-30 [--only clip-01]
  python3 scripts/sermon_shorts.py captions   SUN-2026-08-30      자막 고치기
  python3 scripts/sermon_shorts.py fix        SUN-2026-08-30 혜성교회 예심교회
  python3 scripts/sermon_shorts.py doctor
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROD = REPO / "office" / "production"
# Fonts ship with the repo rather than the system, so a render looks the same
# on every machine and needs no admin rights to set up. A system path still
# works if FONT_DIR is set.
FONT_DIR = os.environ.get("FONT_DIR", str(REPO / "assets" / "fonts"))
FONT_NAME = "Noto Sans KR"

# 9:16 at the resolution YouTube Shorts actually wants.
OUT_W, OUT_H = 1080, 1920

# Sermon delivery is slower than short-form pacing tolerates. 1.5x keeps the
# preacher's voice natural while cutting dead air; per-clip `speed` overrides.
DEFAULT_SPEED = 1.5

# ASS colours are &HAABBGGRR — byte-reversed from hex RGB, so yellow #FFFF00
# is written 00FFFF. Captions sit over the pulpit, which is white and brightly
# lit; white text washed out against it even with an outline. Yellow separates
# from both the pulpit and the dark green backdrop.
SUBTITLE_COLOUR = "&H0000FFFF"   # #FFFF00

# The Shorts player draws its own furniture over the bottom of the frame —
# channel handle, title, description, progress bar — so the bottom of a
# 1920-tall video is not ours to use. Captions are lifted clear of it.
SUBTITLE_MARGIN_V = 480

# The on-screen title. Chars-per-line is derived from the size rather than set
# beside it: Korean glyphs are close to one em wide, so a title that fits at one
# size overflows the frame at the next one up if the two drift apart.
TITLE_SIZE = int(os.environ.get("TITLE_SIZE", 92))
TITLE_SIDE_MARGIN = 60
TITLE_MAX_LINES = 3


def title_per_line(size: int) -> int:
    return max(5, (OUT_W - 2 * TITLE_SIDE_MARGIN) // size)

# Usable caption width is 1080 minus the side margins; at 64px a Korean glyph
# is about as wide as it is tall, so ~14 fit. Lines longer than this get wrapped
# again by libass, which quietly doubles the line count.
SUB_PER_LINE = 14


# --------------------------------------------------------------- helpers ---
def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


# --------------------------------------------------------- tool discovery ---
# On Windows these arrive as a pip wheel or a folder someone unzipped, not as
# something on PATH, so nothing here assumes a bare command name resolves.
# Resolving through Python also means one install path works on all three
# platforms instead of three sets of instructions.
_TOOLS: dict[str, list[str]] = {}


def _windows() -> bool:
    return sys.platform.startswith("win") or os.name == "nt"


def _exe(name: str) -> str | None:
    return shutil.which(name) or (shutil.which(f"{name}.exe") if _windows() else None)


def has_subtitles_filter(exe: str) -> bool:
    """Whether this ffmpeg can burn subtitles at all.

    The filter comes from libass, which a build can be compiled without — and
    an ffmpeg without it looks completely healthy until the first render dies
    with "No such filter: \'subtitles\'". Every burn in this pipeline needs it,
    so it is worth one cheap probe.
    """
    try:
        out = subprocess.run([exe, "-hide_banner", "-filters"],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:              # noqa: BLE001 — a broken binary is not usable
        return False
    return any(ln.split()[1:2] == ["subtitles"] for ln in out.splitlines() if ln.strip())


def ffmpeg_candidates() -> list[str]:
    """Every ffmpeg on this machine, best guess first."""
    out = []
    for c in (_exe("ffmpeg"), os.environ.get("FFMPEG_BIN")):
        if c and c not in out:
            out.append(c)
    try:                           # the wheel ships a static build of its own
        import imageio_ffmpeg
        c = imageio_ffmpeg.get_ffmpeg_exe()
        if c and c not in out:
            out.append(c)
    except Exception:              # noqa: BLE001 — not installed, that is fine
        pass
    return out


NO_LIBASS = ("이 ffmpeg 는 자막을 입힐 수 없다 — libass 없이 빌드된 것이다.\n"
             "  맥:     brew install ffmpeg-full\n"
             "          (Homebrew의 기본 ffmpeg 는 libass 를 뺀 채로 온다.\n"
             "           링크 충돌이 나면 brew link --overwrite ffmpeg-full)\n"
             "  윈도우:  bash scripts/setup_render_env.sh 를 다시 돌린다\n"
             "  확인:   ffmpeg -filters | grep subtitles  (한 줄이라도 나와야 한다)")


def ffmpeg_cmd() -> list[str]:
    """ffmpeg, wherever it actually is — and one that can burn subtitles.

    A machine can have two: the one on PATH and the static build inside the
    imageio-ffmpeg wheel. If the first cannot burn subtitles the second often
    can, so prefer a usable one over the nearest one.
    """
    if "ffmpeg" in _TOOLS:
        return _TOOLS["ffmpeg"]
    found = ffmpeg_candidates()
    if not found:
        die("ffmpeg을 찾지 못했다 — bash scripts/setup_render_env.sh 를 돌려라\n"
            "  (윈도우면 Git Bash 에서 돌린다)")
    best = next((c for c in found if has_subtitles_filter(c)), None)
    if best and best != found[0]:
        print(f"    {found[0]} 는 자막을 못 입혀서 {best} 를 쓴다")
    _TOOLS["ffmpeg"] = [best or found[0]]
    return _TOOLS["ffmpeg"]


def require_subtitles_filter() -> None:
    """Refuse to start a render that is going to die on the first clip."""
    if not has_subtitles_filter(ffmpeg_cmd()[0]):
        die(NO_LIBASS)


def ytdlp_cmd() -> list[str] | None:
    """yt-dlp as a command, or as a module, or not at all."""
    if "yt-dlp" in _TOOLS:
        return _TOOLS["yt-dlp"] or None
    found = _exe("yt-dlp")
    cmd = [found] if found else None
    if cmd is None:
        probe = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                               capture_output=True, text=True)
        if probe.returncode == 0:
            cmd = [sys.executable, "-m", "yt_dlp"]
    _TOOLS["yt-dlp"] = cmd or []
    return cmd


def whisper_cmd() -> str | None:
    for name in ("whisper-cli", "main", "whisper"):
        found = _exe(name)
        if found:
            return found
    return None


def idea_dir(idea_id: str) -> Path:
    return PROD / idea_id


def need(idea_id: str) -> Path:
    d = idea_dir(idea_id)
    if not d.exists():
        die(f"{d.relative_to(REPO)} does not exist — run `fetch` first")
    return d


def ts(seconds: float) -> str:
    """Seconds → SRT timestamp."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def hhmmss(seconds: float) -> str:
    s = int(seconds)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"


def parse_time(v) -> float:
    """Accept 90, '90', '1:30' or '00:01:30.5'."""
    if isinstance(v, (int, float)):
        return float(v)
    parts = str(v).strip().split(":")
    return sum(float(p) * 60**i for i, p in enumerate(reversed(parts)))


# ----------------------------------------------------------------- fetch ---
APIFY_ACTOR = "epctex~youtube-video-downloader"


def fetch_via_apify(url: str, dest: Path, quality: str = "480") -> Path:
    """Download the service through an Apify actor instead of locally.

    Only needed where yt-dlp cannot reach YouTube's media servers. In this
    hosted container it cannot: YouTube signs each media URL to the IP that
    asked for the metadata, and the request then egresses from a different
    proxy address, so the download 403s no matter which client yt-dlp
    pretends to be. The actor runs on Apify's own machines and hands back a
    file, which sidesteps the whole problem.

    It costs real money, per second of footage — see docs/porting-to-your-claude.md.
    On a normal machine use the default yt-dlp path and pay nothing.
    """
    import time
    import urllib.request

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN not set")
    api = "https://api.apify.com/v2"
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    body = json.dumps({"startUrls": [url], "quality": quality,
                       "storageType": "apify"}).encode()
    req = urllib.request.Request(f"{api}/acts/{APIFY_ACTOR}/runs", data=body,
                                 headers=hdr, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        run_info = json.load(r)["data"]
    run_id, dataset = run_info["id"], run_info["defaultDatasetId"]
    print(f"  apify run {run_id} — quality {quality}")

    while True:
        with urllib.request.urlopen(
                urllib.request.Request(f"{api}/actor-runs/{run_id}", headers=hdr),
                timeout=60) as r:
            status = json.load(r)["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break
        time.sleep(20)
    if status != "SUCCEEDED":
        raise RuntimeError(f"apify run {status}")

    with urllib.request.urlopen(
            urllib.request.Request(f"{api}/datasets/{dataset}/items", headers=hdr),
            timeout=60) as r:
        items = json.load(r)
    if not items or items[0].get("error"):
        raise RuntimeError(f"apify returned no file: {items[:1]}")
    item = items[0]
    print(f"  {item.get('durationSeconds')}s, charged ${item.get('totalCost')}")

    with urllib.request.urlopen(
            urllib.request.Request(item["output"]["url"], headers=hdr), timeout=1800) as r, \
            dest.open("wb") as f:
        shutil.copyfileobj(r, f)
    return dest


def note_fetched(idea_id: str, url: str) -> None:
    """Record the video the moment it is downloaded, not when it is finished —
    a run abandoned halfway should still not be picked again by accident."""
    m = re.search(r"(?:watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if m:
        record_produced(m.group(1), idea_id, source_title(idea_dir(idea_id)))


def cmd_fetch(args):
    d = idea_dir(args.idea_id)
    src = d / "source"
    src.mkdir(parents=True, exist_ok=True)

    if args.via == "apify":
        print(f"==> fetching {args.url} via Apify (paid)")
        try:
            fetch_via_apify(args.url, src / "sermon.mp4", args.quality)
        except Exception as e:  # noqa: BLE001 — a paid step failing deserves a plain answer
            die(f"Apify fetch failed: {e}\n"
                "  APIFY_TOKEN is set in the environment, not in a file — see\n"
                "  docs/porting-to-your-claude.md. On a machine where yt-dlp can\n"
                "  reach YouTube, drop --via apify and pay nothing.")
        (d / "meta.json").write_text(
            json.dumps({"idea_id": args.idea_id, "source_url": args.url,
                        "fetched_via": "apify", "quality": args.quality},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        note_fetched(args.idea_id, args.url)
        print(f"==> source in {src.relative_to(REPO)}")
        return

    ydl = ytdlp_cmd()
    if not ydl:
        die("yt-dlp not installed — run: bash scripts/setup_render_env.sh")

    print(f"==> fetching {args.url}")
    try:
        run([
            *ydl,
            "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
            "--merge-output-format", "mp4",
            "--write-info-json", "--no-playlist",
            "-o", str(src / "sermon.%(ext)s"),
            args.url,
        ])
    except subprocess.CalledProcessError:
        die(
            "yt-dlp failed.\n"
            "  If the error mentions 'Tunnel connection failed: 403', YouTube is\n"
            "  blocked by this environment's egress policy, not by yt-dlp.\n"
            "  See docs/environment-constraints.md for the two ways around it."
        )

    (d / "meta.json").write_text(
        json.dumps({"idea_id": args.idea_id, "source_url": args.url}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    note_fetched(args.idea_id, args.url)
    print(f"==> source in {src.relative_to(REPO)}")


# ------------------------------------------------------------ transcribe ---
def find_source(d: Path) -> Path:
    for p in sorted((d / "source").glob("sermon.*")):
        if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".wav"):
            return p
    die(f"no source media in {(d / 'source').relative_to(REPO)} — run `fetch` first")


def extract_audio(video: Path, out: Path) -> Path:
    """16 kHz mono WAV — what every ASR backend wants."""
    if out.exists():
        return out
    run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(out)])
    return out


def transcribe_whisper(wav: Path, model: str) -> list[dict]:
    """whisper.cpp with a multilingual model. large-v3, never *.en —
    the .en models are English-only and cannot read Korean."""
    exe = whisper_cmd()
    if not exe:
        raise RuntimeError("whisper.cpp binary not found")
    if not Path(model).exists():
        raise RuntimeError(f"model not found: {model}")
    if ".en" in Path(model).name:
        raise RuntimeError(f"{Path(model).name} is English-only; Korean needs large-v3")

    out = wav.with_suffix("")
    run([exe, "-m", model, "-f", str(wav), "-l", "ko", "-oj", "-of", str(out)])
    data = json.loads(Path(f"{out}.json").read_text(encoding="utf-8"))
    segs = []
    for s in data.get("transcription", []):
        off = s.get("offsets", {})
        segs.append({
            "start": off.get("from", 0) / 1000.0,
            "end": off.get("to", 0) / 1000.0,
            "text": s.get("text", "").strip(),
        })
    return segs


# Model ids move; the first that answers wins. A 503 here means the model is
# busy, not that the audio is bad, so the caller retries down this list.
GEMINI_MODELS = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-pro"]

CHUNK_SECONDS = 540      # ~9 min per call
CHUNK_OVERLAP = 30       # trailing seconds re-sent with the next chunk


def _gemini_call(client, types, path: Path, prompt: str, max_tokens: int = 32000):
    """One generate_content, walking GEMINI_MODELS on overload."""
    import time
    f = client.files.upload(file=str(path))
    while f.state.name == "PROCESSING":
        time.sleep(4)
        f = client.files.get(name=f.name)
    last = None
    for attempt in range(len(GEMINI_MODELS) * 3):
        model = GEMINI_MODELS[min(attempt // 3, len(GEMINI_MODELS) - 1)]
        try:
            return client.models.generate_content(
                model=model, contents=[f, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", max_output_tokens=max_tokens))
        except Exception as e:  # noqa: BLE001 — overload is transient; try the next model
            last = e
            print(f"    {model}: {str(e)[:80]}")
            time.sleep(15)
    raise RuntimeError(f"every Gemini model failed: {last}")


def _gemini_client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("pip3 install google-genai")
    return genai.Client(api_key=key), types


TRANSCRIBE_PROMPT = (
    "한국 개신교 설교 오디오다. 들리는 그대로 한국어로 전사하라.\n"
    "- 요약하거나 문장을 다듬지 말 것. 실제 발화를 그대로 옮긴다.\n"
    "- 성경 인용, 예화, 반복 어구도 빠짐없이 옮긴다.\n"
    "- 한 원소는 한 문장 또는 8초 이내로 끊는다.\n"
    '- JSON 배열만 출력. 각 원소는 {"start": 초(float), "end": 초(float), "text": "발화"}\n'
    "  시간은 이 오디오 조각의 시작을 0으로 한 상대시간이다.\n"
    "- 설명 문장을 쓰지 말 것."
)


def transcribe_gemini(wav: Path, start: float = 0.0, end: float | None = None) -> list[dict]:
    """Gemini transcription, in overlapping chunks.

    A full service is over an hour, and one call for the whole thing gets
    truncated well before the end. Chunking fixes that but drops audio at
    every seam — the model reliably loses the last seconds of a clip — so
    each chunk re-sends CHUNK_OVERLAP seconds of the previous one and the
    duplicate segments are dropped on the way out.

    Paid: one call per chunk.
    """
    client, types = _gemini_client()
    total = (end if end is not None else probe_duration(wav)) - start
    n = max(1, int(total // (CHUNK_SECONDS - CHUNK_OVERLAP)) + 1)
    print(f"  {total/60:.0f}분 → {n} chunk(s), {n} paid call(s)")

    out: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(n):
            off = start + i * (CHUNK_SECONDS - CHUNK_OVERLAP)
            if off >= start + total:
                break
            piece = Path(tmp) / f"c{i}.mp3"
            run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
                 "-ss", f"{off}", "-t", f"{CHUNK_SECONDS}", "-i", str(wav),
                 "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k",
                 str(piece)])
            resp = _gemini_call(client, types, piece, TRANSCRIBE_PROMPT)
            for s in json.loads(resp.text):
                seg = {"start": float(s["start"]) + off, "end": float(s["end"]) + off,
                       "text": str(s["text"]).strip()}
                # Overlap means the same words arrive twice; keep the first copy.
                if out and seg["start"] < out[-1]["end"] - 1.0:
                    continue
                out.append(seg)
            print(f"    chunk {i+1}/{n} ok ({len(out)} segments so far)")
    out.sort(key=lambda s: s["start"])
    return out


# Korean speech runs roughly 4-5 characters a second. A segment claiming far
# more time than its text needs means the model skipped audio inside it.
CHARS_PER_SECOND = 4.0
HOLE_SLACK = 8.0          # seconds of pause allowed before it counts as a hole
MIN_HOLE = 10.0           # don't bother re-transcribing anything shorter


def _norm(text: str) -> str:
    return "".join(text.split())


def dedupe_segments(segs: list[dict]) -> list[dict]:
    """Drop text the model transcribed twice at a chunk seam.

    The chunks overlap on purpose, so the seam audio is sent twice. Comparing
    timestamps is not enough to catch the repeat: the model's timings drift
    near the end of a chunk, and the second copy can start after the first
    copy's stated end, which makes the duplicate look like new material.
    Comparing the words themselves does catch it.
    """
    out: list[dict] = []
    for s in segs:
        key = _norm(s["text"])
        if not key:
            continue
        # Only look back over the seam-sized window, so a genuinely repeated
        # phrase far later in the sermon is left alone.
        if any(_norm(p["text"]) == key for p in out if s["start"] - p["start"] < 90):
            continue
        out.append(s)
    return out


def find_holes(segs: list[dict], window: tuple[float, float] | None = None) -> list[tuple[float, float]]:
    """Stretches of the sermon with no transcript against them.

    Two shapes: an outright gap between consecutive segments, and a segment
    whose stated duration is far longer than its own text could fill — the
    model quietly swallowed audio inside it and stretched the end timestamp
    to cover the loss.
    """
    holes = []
    for i, s in enumerate(segs):
        spoken = len(_norm(s["text"])) / CHARS_PER_SECOND
        if (s["end"] - s["start"]) - spoken > HOLE_SLACK:
            holes.append((s["start"] + spoken, s["end"]))
        if i + 1 < len(segs):
            gap = segs[i + 1]["start"] - s["end"]
            if gap > HOLE_SLACK:
                holes.append((s["end"], segs[i + 1]["start"]))
    if window:
        holes = [(max(a, window[0]), min(b, window[1])) for a, b in holes]
    return [(a, b) for a, b in holes if b - a >= MIN_HOLE]


def repair_transcript(wav: Path, segs: list[dict],
                      window: tuple[float, float] | None = None,
                      fill_holes: bool = False) -> list[dict]:
    """Clean a transcript: drop seam duplicates, clamp impossible durations.

    Hole-filling is off by default and rarely what you want. An over-long
    segment usually means the model's timestamps have drifted late rather
    than that it skipped audio — re-transcribing the "hole" then returns the
    same words a second time under different timings, which is worse than
    the gap. Measured on SUN-2026-04-26: what the transcript placed at 62:50
    is actually spoken at 62:22.
    """
    segs = dedupe_segments(sorted(segs, key=lambda s: s["start"]))
    # A cue must never outlive the next one, nor sit far longer than its own
    # words could fill — either way it would hang on screen over later speech.
    for i, s in enumerate(segs):
        cap = s["start"] + len(_norm(s["text"])) / CHARS_PER_SECOND + HOLE_SLACK
        s["end"] = min(s["end"], cap)
        if i + 1 < len(segs):
            s["end"] = min(s["end"], segs[i + 1]["start"])
    if not fill_holes:
        return segs

    holes = find_holes(segs, window)
    if not holes:
        return segs

    print(f"  전사 누락 {len(holes)}곳 재전사 ({len(holes)} paid call(s))")
    client, types = _gemini_client()
    with tempfile.TemporaryDirectory() as tmp:
        for a, b in holes:
            print(f"    {hhmmss(a)}–{hhmmss(b)} ({b-a:.0f}s)")
            piece = Path(tmp) / f"h{int(a)}.mp3"
            run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
                 "-ss", f"{a}", "-t", f"{b - a}", "-i", str(wav),
                 "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k",
                 str(piece)])
            try:
                resp = _gemini_call(client, types, piece, TRANSCRIBE_PROMPT)
                for s in json.loads(resp.text):
                    segs.append({"start": float(s["start"]) + a,
                                 "end": float(s["end"]) + a,
                                 "text": str(s["text"]).strip()})
            except Exception as e:  # noqa: BLE001 — a hole we cannot fill is still worth reporting
                print(f"      재전사 실패: {str(e)[:70]}")

    segs = dedupe_segments(sorted(segs, key=lambda s: s["start"]))
    # Never let a cue outlive the next one starting.
    for i in range(len(segs) - 1):
        segs[i]["end"] = min(segs[i]["end"], segs[i + 1]["start"])
    return segs


def retime_window(wav: Path, start: float, end: float) -> list[dict]:
    """Re-transcribe one clip's window for accurate caption timings.

    The pass that produces the reading transcript works in nine-minute chunks,
    and the model's timestamps drift late across a chunk — measured at four to
    five seconds by the middle of one. That is invisible while reading the
    transcript and very visible once the words are burned under the picture.
    A short window re-transcribed on its own has almost nothing to drift over.

    One paid Gemini call per clip.
    """
    with tempfile.TemporaryDirectory() as tmp:
        piece = Path(tmp) / "w.mp3"
        run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
             "-ss", f"{start}", "-t", f"{end - start}", "-i", str(wav),
             "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", str(piece)])
        client, types = _gemini_client()
        resp = _gemini_call(client, types, piece, TRANSCRIBE_PROMPT)
    segs = [{"start": float(s["start"]) + start, "end": float(s["end"]) + start,
             "text": str(s["text"]).strip()} for s in json.loads(resp.text)]
    segs.sort(key=lambda s: s["start"])
    for i in range(len(segs) - 1):
        segs[i]["end"] = min(segs[i]["end"], segs[i + 1]["start"])
    return [s for s in segs if s["text"]]


def probe_duration(media: Path) -> float:
    """Duration in seconds. ffprobe is not in the static ffmpeg build here, so
    this parses ffmpeg's own banner instead of assuming ffprobe exists."""
    p = subprocess.run([*ffmpeg_cmd(), "-hide_banner", "-i", str(media)],
                       capture_output=True, text=True)
    for line in p.stderr.splitlines():
        if "Duration:" in line:
            hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(hh) * 3600 + int(mm) * 60 + float(ss)
    raise RuntimeError(f"could not read duration of {media}")


SERMON_WINDOW_PROMPT = """이것은 한국 개신교 교회의 주일예배 실황 녹음 전체다.
예배 순서를 시간대별로 구분하라. 특히 다음을 정확히 찾아라:

1. 찬양/찬송이 나오는 모든 구간 (반주만 있는 구간 포함)
2. 대표기도, 봉헌, 광고 구간
3. **설교(말씀)가 시작되는 시점과 끝나는 시점** — 가장 중요하다.
   설교는 보통 성경 본문 봉독 직후 시작해 마침기도 직전에 끝난다.

JSON 배열만 출력. 각 원소는
{"start": 초(정수), "end": 초(정수), "type": "찬양|기도|봉헌|광고|성경봉독|설교|축도|기타", "note": "간단한 근거"}
설명 문장 쓰지 말 것."""


def detect_service_structure(audio: Path) -> list[dict] | None:
    """Split a full service recording into its parts by listening to it.

    Gemini only — it is the one backend here that takes audio directly. On a
    machine without a key this returns None and the caller falls back to
    reading the transcript instead, which is free and nearly as good.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    client, types = _gemini_client()
    resp = _gemini_call(client, types, audio, SERMON_WINDOW_PROMPT, max_tokens=8000)
    return json.loads(resp.text)


SERMON_WINDOW_TEXT_PROMPT = """이것은 한국 개신교 교회의 주일예배 실황 전체 전사본을
시간순으로 요약한 것이다. 각 줄은 [초] 형식의 절대 시각과 그 무렵의 발화다.

{outline}

전체 길이는 {total}초다.

**설교(말씀)가 시작되는 시각과 끝나는 시각**을 찾아라.

- 설교는 보통 성경 본문 봉독 직후에 시작하고, 마침기도나 축도 직전에 끝난다.
- 앞부분의 찬양·경배·대표기도·환영·광고·봉헌은 설교가 아니다.
- 설교 뒤의 마침 찬송·헌금·광고·축도도 설교가 아니다.
- 찬양 구간은 같은 가사가 반복되거나 전사가 듬성듬성한 편이다.
- 설교는 보통 25~45분이다. 그보다 훨씬 짧게 잡았다면 잘못 잡은 것이다.

JSON 객체 하나만 출력한다. 설명 문장, 코드펜스, 그 외 아무것도 붙이지 말 것.
{{"start": 초(정수), "end": 초(정수), "note": "무엇을 근거로 잡았는지 한 문장"}}
"""


def outline_transcript(segs: list[dict], every: float = 60.0) -> str:
    """One line per minute — enough for a model to see the shape of a service
    without paying to read 100 minutes of speech word by word."""
    lines, next_at = [], 0.0
    for sg in segs:
        if sg["start"] >= next_at:
            lines.append(f"[{int(sg['start'])}] {sg['text'][:70]}")
            next_at = sg["start"] + every
    return "\n".join(lines)


def ff_path(path) -> str:
    """A path as a value inside an ffmpeg filter, from the repo when possible.

    libavfilter splits filters on "," and their options on ":", then unescapes
    the value once more, and no combination of quoting and backslashes gets an
    apostrophe through — a home folder like /Users/장선기's Mac/ has no spelling
    that parses. So paths are made relative to the repository and ffmpeg is run
    from there: what reaches the filter is "assets/fonts", which has nothing to
    escape. A Windows drive letter disappears the same way.
    """
    q = Path(path)
    try:
        return q.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        # Outside the repo: quote it and escape the option separator. Good for
        # spaces, commas and drive letters; an apostrophe here is unwinnable.
        return "'" + str(q).replace("\\", "/").replace(":", "\\:") + "'"


def subtitles_filter(ass: Path) -> str:
    """The burn-in filter, with every option named — run it with cwd=REPO.

    ffmpeg used to let a filter's first option go unnamed (`subtitles=<file>`).
    Newer builds refuse it and say "No option name near …", which is how a
    render that works everywhere else dies on a freshly installed Mac. Naming
    the options works on every version.
    """
    return f"subtitles=filename={ff_path(ass)}:fontsdir={ff_path(FONT_DIR)}"


def read_srt(path: Path) -> list[dict]:
    """Minimal SRT reader — enough to locate a sermon, not to caption one."""
    segs, block = [], []
    for raw in read_text_any(path).split("\n\n"):
        block = [ln for ln in raw.strip().splitlines() if ln.strip()]
        if len(block) < 2:
            continue
        stamp = next((ln for ln in block if "-->" in ln), None)
        if not stamp:
            continue
        a, b = (x.strip().replace(",", ".") for x in stamp.split("-->")[:2])
        text = " ".join(block[block.index(stamp) + 1:]).strip()
        if text:
            segs.append({"start": parse_time(a), "end": parse_time(b), "text": text})
    return segs


def rel(path: Path) -> str:
    """Path for humans. Never raises — an error message that crashes while
    being built is worse than a long path."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def read_text_any(path: Path) -> str:
    """Read a subtitle file whatever the editor saved it as.

    Notepad on older Windows writes CP949 for Korean, and some editors add a
    BOM. Reading those as plain UTF-8 turns every Korean character into
    mojibake, which then gets burned into the video — so try the encodings
    that actually occur before giving up.
    """
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").replace("\r\n", "\n")


def _plain(text: str) -> str:
    """Text stripped to what a comparison should care about."""
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", text)


def _similar(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    a, b = _plain(a), _plain(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def caption_offset(cues: list[dict], segs: list[dict], clip_start: float,
                   clip_end: float) -> tuple[float, float] | None:
    """How far an edited caption file has drifted from the recording.

    Answers the question a wrong-looking video actually poses — "are these
    the right words at the wrong time?" — by finding, for a handful of cues,
    the transcript segment that says the same thing, and reading off the gap.
    A file made for a different cut of the same sermon lands on a consistent
    non-zero gap; a file that simply had its words corrected lands on zero.

    Returns (seconds of drift, how well the words matched), or None when the
    words do not match the transcript well enough anywhere to tell.
    """
    if not cues or not segs:
        return None
    # A few cues spread across the clip, not the first few: an opening line is
    # often short ("그렇습니다") and matches half the sermon.
    picks = [c for c in cues if len(_plain(c["text"])) >= 8]
    if len(picks) > 6:
        step = len(picks) / 6
        picks = [picks[int(i * step)] for i in range(6)]
    near = [g for g in segs
            if g["end"] > clip_start - 900 and g["start"] < clip_end + 900] or segs

    gaps, scores = [], []
    for c in picks:
        best = max(near, key=lambda g: _similar(c["text"], g["text"]))
        r = _similar(c["text"], best["text"])
        if r < 0.55:
            continue
        gaps.append(best["start"] - (clip_start + c["start"]))
        scores.append(r)
    if len(gaps) < 2:
        return None
    gaps.sort()
    mid = gaps[len(gaps) // 2] if len(gaps) % 2 else (gaps[len(gaps) // 2 - 1]
                                                     + gaps[len(gaps) // 2]) / 2
    return mid, sum(scores) / len(scores)


def caption_sync(d: Path, clip: dict, segs: list[dict]) -> tuple[str, str]:
    """One clip's caption file judged against the transcript.

    Returns (verdict, one line for a person). Verdicts: ok · drift · unknown ·
    none.
    """
    f = caption_override(d, clip["id"])
    if not f.exists():
        return "none", "자막 파일 없음"
    try:
        cues = read_srt(f)
    except Exception as e:  # noqa: BLE001 — a report must not raise
        return "unknown", f"읽을 수 없다: {str(e)[:60]}"
    start, end = parse_time(clip["start"]), parse_time(clip["end"])
    hit = caption_offset(cues, segs, start, end)
    if hit is None:
        return "unknown", ("전사본과 대조가 안 된다 — 자막을 많이 고쳤거나 "
                           "전사본이 그 사이 바뀌었다")
    gap, score = hit
    if abs(gap) <= 1.0:
        return "ok", f"영상과 맞는다 (어긋남 {gap:+.1f}초, 일치도 {score:.0%})"
    # gap is where the speech really is minus where this file puts it, so a
    # negative gap means the subtitle arrives after the words were spoken.
    where = "빨리" if gap > 0 else "늦게"
    return "drift", (f"✗ {abs(gap):.0f}초 {where} 나온다 — 이 자막은 다른 구간에 "
                     f"맞춰진 파일이다 (일치도 {score:.0%})")


def check_caption_file(path: Path, clip_seconds: float) -> list[dict]:
    """Read an edited caption file, refusing one that would render wrong.

    A silently broken caption file is worse than none: the render succeeds and
    the mistake is only visible in the finished MP4.
    """
    cues = read_srt(path)
    if not cues:
        die(f"{rel(path)} 에서 자막을 하나도 못 읽었다.\n"
            "  시간 줄(00:00:00,000 --> 00:00:03,400)의 모양이 깨졌을 수 있다.\n"
            "  이 파일을 지우고 다시 꺼내면 원래대로 돌아간다:\n"
            f"    rm {rel(path)}\n"
            f"    python3 scripts/sermon_shorts.py captions {path.parent.parent.name}")
    if any("\ufffd" in c["text"] for c in cues):
        die(f"{rel(path)} 의 글자가 깨졌다.\n"
            "  메모장에서 저장할 때 인코딩을 UTF-8 로 골라야 한다.\n"
            "  (다른 이름으로 저장 → 아래 인코딩 칸 → UTF-8)")
    bad = [c for c in cues if c["end"] <= c["start"]]
    if bad:
        die(f"{rel(path)}: 끝나는 시각이 시작보다 빠른 자막이 "
            f"{len(bad)}개 있다. 시간 줄은 건드리지 말 것 — 글자만 고친다.")
    over = [c for c in cues if c["start"] > clip_seconds + 1]
    if over:
        print(f"    경고: {len(over)}개 자막이 클립 길이({clip_seconds:.0f}초)를 "
              f"넘는 시각에 있다 — 화면에 안 나온다")
    return cues


def autosub_path(d: Path) -> Path | None:
    """YouTube's own Korean auto-captions, fetched if they are not here yet.

    They are far too rough to burn in, but locating a sermon inside a service
    does not need accuracy — and having them turns whisper's job from 100
    minutes of audio into the 35 that matter. Free, and no download.
    """
    hit = sorted((d / "source").glob("sermon*.ko*.srt"))
    if hit:
        return hit[0]
    meta = d / "meta.json"
    ydl = ytdlp_cmd()
    if not meta.exists() or not ydl:
        return None
    url = json.loads(meta.read_text(encoding="utf-8")).get("source_url")
    if not url:
        return None
    print("    유튜브 자동자막 받는 중 (무료, 영상은 다시 안 받는다)")
    subprocess.run(
        [*ydl, "--skip-download", "--write-auto-subs", "--sub-langs", "ko",
         "--convert-subs", "srt", "--no-playlist",
         "-o", str(d / "source" / "sermon.%(ext)s"), url],
        capture_output=True, text=True)
    hit = sorted((d / "source").glob("sermon*.ko*.srt"))
    return hit[0] if hit else None


def find_sermon_window_from_text(segs: list[dict], total: float,
                                 backend: str = "auto") -> tuple[float, float] | None:
    """Locate the sermon by reading the transcript rather than the audio.

    This is the route on a machine with no Gemini key: whisper transcribes the
    whole service for free, and the window is found afterwards. Costs nothing
    where the Claude CLI is installed.
    """
    prompt = SERMON_WINDOW_TEXT_PROMPT.format(
        outline=outline_transcript(segs), total=int(total))
    try:
        got = ask_json(prompt, backend)
    except Exception as e:  # noqa: BLE001 — a missing window is not fatal
        print(f"    설교 구간을 못 잡았다: {str(e)[:120]}")
        return None
    if isinstance(got, list) and got:
        got = got[0]
    try:
        start, end = float(got["start"]), float(got["end"])
    except (KeyError, TypeError, ValueError):
        print(f"    설교 구간 응답을 못 읽었다: {str(got)[:120]}")
        return None
    # A window that runs backwards, spills past the recording, or claims the
    # sermon was five minutes long is a misread, not a sermon. Say so and let
    # the caller keep the whole transcript rather than clamping to nonsense.
    if not (0 <= start < end <= total + 1) or (end - start) < 600:
        print(f"    설교 구간 {hhmmss(start)}–{hhmmss(end)} 은 말이 안 된다 — 무시한다")
        return None
    if got.get("note"):
        print(f"    근거: {got['note']}")
    return start, end


def transcribe_whisper_window(wav: Path, model: str,
                             start: float, end: float) -> list[dict]:
    """whisper over one slice, with timestamps shifted back to the recording's
    own clock so every later stage still speaks in absolute seconds."""
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "window.wav"
        run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav),
             "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
             "-vn", "-ac", "1", "-ar", "16000", str(clip)])
        segs = transcribe_whisper(clip, model)
    for sg in segs:
        sg["start"] += start
        sg["end"] += start
    return segs


def cmd_transcribe(args):
    d = need(args.idea_id)
    video = find_source(d)
    wav = extract_audio(video, d / "source" / "audio16k.wav")
    print(f"==> audio: {wav.relative_to(REPO)}")

    total = probe_duration(wav)

    # Find the sermon inside the service. Two routes, and which one is
    # available decides the order of the next two stages:
    #
    #   Gemini  — listens to the audio, so the window is known before
    #             transcription and only the sermon gets transcribed (it bills
    #             per minute, so that matters).
    #   whisper — free and offline, so transcribe the whole service and read
    #             the window out of the transcript afterwards. Handled below,
    #             after the transcript exists.
    window = None
    sp = d / "service-structure.json"
    if args.sermon_window:
        window = tuple(parse_time(x) for x in args.sermon_window)
        print(f"==> 설교 구간 {hhmmss(window[0])}–{hhmmss(window[1])} (직접 지정)")
    elif not args.whole and not args.no_structure:
        structure = None
        if sp.exists():
            structure = json.loads(sp.read_text(encoding="utf-8"))
            print(f"==> reusing {sp.relative_to(REPO)}")
        elif os.environ.get("GEMINI_API_KEY"):
            print("==> detecting service structure (1 paid call)")
            structure = detect_service_structure(wav)
            if structure:
                sp.write_text(json.dumps(structure, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        else:
            # No Gemini, so nothing here can listen to the audio. Try YouTube's
            # own auto-captions instead: rough, free, and quite good enough to
            # say where the sermon starts. Failing that, the window is found
            # after transcription instead.
            sub = autosub_path(d)
            if sub:
                print(f"==> 자동자막으로 설교 구간 찾는 중 ({sub.name})")
                window = find_sermon_window_from_text(
                    read_srt(sub), total, args.select_backend)
                if window:
                    print(f"==> 설교 구간 {hhmmss(window[0])}–{hhmmss(window[1])} "
                          f"(전체 {hhmmss(total)}) — 이 구간만 전사한다")
            if not window:
                print("==> 예배 구조는 전사 뒤에 전사본을 읽어 잡는다 (무료)")

        sermon = [x for x in (structure or []) if x.get("type") == "설교"]
        if sermon:
            window = (float(min(x["start"] for x in sermon)),
                      float(max(x["end"] for x in sermon)))
            print(f"==> 설교 구간 {hhmmss(window[0])}–{hhmmss(window[1])} "
                  f"(전체 {hhmmss(total)})")
            for x in structure:
                if x.get("type") == "찬양":
                    print(f"    [찬양] {hhmmss(x['start'])}–{hhmmss(x['end'])} — 클립 금지 구간")
        elif structure is not None:
            print("    설교 구간을 못 찾음 — 전체를 전사한다")

    model = os.environ.get("WHISPER_MODEL", "models/ggml-large-v3.bin")
    backends = [args.backend] if args.backend != "auto" else ["whisper", "gemini"]
    start, end = window if window else (0.0, None)
    if window:
        end = min(float(end), total)

    segs, used, errs = None, None, []
    for b in backends:
        try:
            print(f"==> transcribing via {b}")
            if b == "whisper":
                segs = (transcribe_whisper_window(wav, model, start, end)
                        if window else transcribe_whisper(wav, model))
            else:
                segs = transcribe_gemini(wav, start, end)
            used = b
            break
        except Exception as e:  # noqa: BLE001 — report and try the next backend
            errs.append(f"  {b}: {e}")
            print(f"    {b} unavailable: {e}")

    if segs is None:
        die("no transcription backend worked:\n" + "\n".join(errs))

    # whisper route: the transcript exists but the window does not yet.
    if window is None and not args.whole and not args.no_structure:
        print("==> 전사본에서 설교 구간 찾는 중")
        window = find_sermon_window_from_text(segs, total, args.select_backend)
        if window:
            print(f"==> 설교 구간 {hhmmss(window[0])}–{hhmmss(window[1])} "
                  f"(전체 {hhmmss(total)})")
        else:
            print("    못 잡았다 — 전사본 전체를 남긴다. 구간을 아는 경우\n"
                  "    --sermon-window 시작 끝 으로 직접 넘길 수 있다 (예: 0:45:00 1:20:00)")

    if used == "gemini" and not args.no_repair:
        print("==> 중복·누락 점검")
        before = len(segs)
        segs = repair_transcript(wav, segs, window)
        print(f"    {before} → {len(segs)} segments")

    fixed = apply_lexicon(segs)
    if fixed:
        print(f"==> 사전 적용 — {fixed}개 자막의 잘못 들린 말을 고쳤다 "
              f"({LEXICON.relative_to(REPO)})")

    out = {"backend": used, "language": "ko", "segments": segs}
    if window:
        out["sermon_window"] = {"start": window[0], "end": window[1]}
    (d / "transcript.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    write_srt(segs, d / "transcript.srt")
    print(f"==> {len(segs)} segments via {used} → transcript.json / transcript.srt")


def write_srt(segs: list[dict], path: Path, offset: float = 0.0):
    lines = []
    for i, s in enumerate(segs, 1):
        start, end = s["start"] - offset, s["end"] - offset
        if end <= 0:
            continue
        lines += [str(i), f"{ts(max(0.0, start))} --> {ts(end)}", s["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def ass_ts(seconds: float) -> str:
    """Seconds → ASS timestamp (H:MM:SS.cc)."""
    cs = int(round(max(0.0, seconds) * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def wrap_lines(text: str, per_line: int) -> list[str]:
    """Break on word boundaries into short lines.

    Korean has spaces between 어절, so wrapping on them is safe and reads far
    better than libass's own greedy fill at this font size. Never drops text —
    the caller decides what to do with more lines than it wants.
    """
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > per_line:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def wrap_korean(text: str, per_line: int = SUB_PER_LINE, max_lines: int = 3) -> str:
    """Wrap to at most `max_lines`, keeping every word.

    `max_lines` is a layout hint, not a budget to spend text against: if the
    text needs more lines it gets them. Silently dropping the tail of a
    sentence is the worst possible failure here — it was cutting the payoff
    off the end of the preacher's own sentences.
    """
    return "\\N".join(wrap_lines(text, per_line))


def split_for_display(seg: dict, per_line: int = SUB_PER_LINE,
                      max_lines: int = 3) -> list[dict]:
    """One transcript segment → one or more subtitle cues.

    A segment can be eight seconds of speech, far more than fits on screen at
    a readable size. Rather than truncate it, split it into consecutive cues
    and share the segment's own duration between them in proportion to how
    much text each carries, so the words stay under the voice saying them.
    """
    lines = wrap_lines(seg["text"], per_line)
    if len(lines) <= max_lines:
        return [seg]

    groups = [lines[i:i + max_lines] for i in range(0, len(lines), max_lines)]
    weights = [sum(len(x) for x in g) for g in groups]
    total = sum(weights) or 1
    span = seg["end"] - seg["start"]

    out, t = [], seg["start"]
    for i, (g, w) in enumerate(zip(groups, weights)):
        end = seg["end"] if i == len(groups) - 1 else t + span * w / total
        out.append({"start": t, "end": end, "text": " ".join(g)})
        t = end
    return out


def write_ass(segs: list[dict], path: Path, offset: float = 0.0,
              font_size: int = 64, margin_v: int = SUBTITLE_MARGIN_V,
              title: str = "", duration: float = 0.0,
              title_size: int = TITLE_SIZE):
    """Burn-in subtitles as ASS, with an optional standing title card.

    SRT carries no resolution, so libass falls back to a 384x288 script and
    scales every style number up from there — a Fontsize/MarginV tuned in real
    pixels lands in the wrong place. ASS lets us state PlayRes explicitly, so
    the numbers below mean what they say at 1080x1920.

    The title sits at the top for the clip's whole length, not just the open:
    most viewers arrive mid-clip, and a sermon excerpt with no frame around it
    reads as a stranger talking. `duration` is the clip's length *before* any
    speed change, because the subtitle burn happens before the retime.
    """
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT_NAME},{font_size},{SUBTITLE_COLOUR},&H000000FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,5,2,2,70,70,{margin_v},1
Style: Title,{FONT_NAME},{title_size},&H00FFFFFF,&H000000FF,&H00202020,&H00000000,1,0,0,0,100,100,0,0,1,6,0,8,{TITLE_SIDE_MARGIN},{TITLE_SIDE_MARGIN},110,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    cues = []
    for s_ in segs:
        cues.extend(split_for_display(s_))

    rows = []
    if title and duration > 0:
        rows.append(f"Dialogue: 1,{ass_ts(0)},{ass_ts(duration)},Title,,0,0,0,,"
                    f"{wrap_korean(title, per_line=title_per_line(title_size), max_lines=TITLE_MAX_LINES)}")
    for s in cues:
        start, end = s["start"] - offset, s["end"] - offset
        if end <= 0:
            continue
        text = wrap_korean(s["text"].replace("\n", " ").strip())
        rows.append(f"Dialogue: 0,{ass_ts(start)},{ass_ts(end)},Default,,0,0,0,,{text}")
    path.write_text(head + "\n".join(rows) + "\n", encoding="utf-8")


# -------------------------------------------------------------- captions ---
# Whisper mishears the same handful of words every week — a church name, a
# preacher's name, a book of the Bible. Correcting one once here means never
# correcting it again.
LEXICON = REPO / "office" / "lexicon.json"


def load_lexicon() -> list[dict]:
    if not LEXICON.exists():
        return []
    try:
        return json.loads(LEXICON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"    {LEXICON.name} 을 못 읽었다 — 무시한다")
        return []


def apply_lexicon(segs: list[dict]) -> int:
    """Fix known mishearings in place. Returns how many cues changed."""
    pairs = [(e["wrong"], e["right"]) for e in load_lexicon()
             if e.get("wrong") and e.get("right")]
    if not pairs:
        return 0
    n = 0
    for sg in segs:
        before = sg["text"]
        for wrong, right in pairs:
            sg["text"] = sg["text"].replace(wrong, right)
        n += sg["text"] != before
    return n


def open_in_file_manager(path: Path) -> bool:
    """Show a folder in Finder / File Explorer.

    Typing the path is the tedious part of every fix — the folder is five
    levels down and named after a date. SHORTS_NO_OPEN=1 turns this off for
    anyone working over ssh or in a container, where there is no desktop to
    open it on.
    """
    if os.environ.get("SHORTS_NO_OPEN") or not path.exists():
        return False
    cmd = (["open", str(path)] if sys.platform == "darwin"
           else ["explorer", str(path)] if _windows()
           else ["xdg-open", str(path)])
    if not _exe(cmd[0]):
        return False
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
        return True
    except Exception:   # noqa: BLE001 — a window that will not open is not an error
        return False


def cmd_open(args):
    """Open one of a production's folders without typing the path."""
    d = need(args.idea_id)
    target = d if args.what == "." else d / args.what
    if not target.exists():
        if args.what == "captions":
            die(f"{rel(target)} 가 아직 없다. 먼저 자막을 꺼낸다:\n"
                f"  bash scripts/shorts captions {args.idea_id}")
        die(f"{rel(target)} 가 없다")
    print(rel(target))
    if not open_in_file_manager(target):
        print("  (이 환경에서는 창을 못 연다 — 위 경로를 직접 열어라)")


def caption_override(d: Path, clip_id: str) -> Path:
    return d / "captions" / f"{clip_id}.srt"


def show_captions(d: Path, clips: list[dict], segs: list[dict] | None = None) -> None:
    """Answer "I edited the subtitle and the video did not change".

    There are only a few places that can break, and each leaves a trace on
    disk: no override file, an override that does not parse, or an mp4 older
    than the edit — meaning the render simply has not been run since.
    """
    import time

    segs = segs or []
    any_found = False
    for c in clips:
        cid = c["id"]
        f, mp4 = caption_override(d, cid), d / "renders" / f"{cid}.mp4"
        print(f"\n  {cid}")
        if not f.exists():
            print(f"    자막 파일 없음 — captions 를 --show 없이 한 번 돌려라")
            continue
        any_found = True
        try:
            cues = read_srt(f)
        except Exception as e:  # noqa: BLE001 — report, do not raise
            print(f"    ✗ 읽을 수 없다: {str(e)[:70]}")
            continue
        if not cues:
            print(f"    ✗ 줄을 하나도 못 읽었다 — 시간 줄이 깨졌거나 "
                  f"편집기가 다른 형식(RTF 등)으로 저장했다")
            print(f"       {rel(f)}")
            continue

        edited = f.stat().st_mtime
        print(f"    {rel(f)}  ({len(cues)}줄, "
              f"{time.strftime('%m-%d %H:%M', time.localtime(edited))} 저장)")
        for cue in cues[:3]:
            print(f"      {hhmmss(cue['start'])}  {cue['text'][:42]}")
        if len(cues) > 3:
            print(f"      … {len(cues) - 3}줄 더")

        clip = next((x for x in clips if x["id"] == cid), None)
        if clip is not None and segs:
            verdict, line = caption_sync(d, clip, segs)
            print(f"    {line}")
            if verdict == "drift":
                print(f"      이 구간에 맞춰 다시 만들려면:")
                print(f"        rm {rel(f)}")
                print(f"        bash scripts/shorts captions {d.name}")

        if not mp4.exists():
            print("    → 아직 렌더한 적이 없다")
        elif mp4.stat().st_mtime < edited:
            print(f"    → ✗ 영상이 자막보다 오래됐다 "
                  f"({time.strftime('%m-%d %H:%M', time.localtime(mp4.stat().st_mtime))} 렌더). "
                  f"고친 뒤 렌더를 안 돌린 것이다:")
            print(f"         bash scripts/shorts render {d.name} --only {cid}")
        else:
            print("    → 영상이 이 자막보다 나중에 만들어졌다 (반영됨)")

    if not any_found:
        print("\n아직 꺼낸 자막 파일이 없다 — captions 를 --show 없이 한 번 돌려라.")


CAPTIONS_README = """이 폴더의 파일을 고치면 자막이 바뀝니다.

1. clip-01.srt 를 오른쪽 버튼 → 다음으로 열기 → 텍스트편집기
2. 맨 아랫줄 글자만 고칩니다. 숫자와 --> 줄은 그대로 둡니다
3. command + S 로 저장합니다 (이걸 빼먹으면 안 바뀝니다)
4. 터미널에서:  bash scripts/shorts render {idea} --only clip-01

여기 파일이 있으면 렌더가 이것을 씁니다.
다시 전사해도 고친 자막은 그대로 남습니다.
다만 구간(시작·끝 시각)을 바꾸면 시간이 안 맞게 되므로 새 구간에 맞춰
다시 만들고, 고쳤던 파일은 clip-01.srt.이전 으로 남겨 둡니다.
"""


def caption_stamps(d: Path) -> dict:
    """What window each caption file was written for.

    Kept beside the files because the failure it prevents is invisible
    otherwise: change a clip's start in clips.json, re-render, and the old
    subtitle file — which render prefers over the transcript, on purpose —
    gets burned onto a cut it no longer matches.
    """
    f = d / "captions" / ".window.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a broken stamp file is not fatal
        return {}


def write_caption_stamp(d: Path, cid: str, start: float, end: float,
                        path: Path) -> None:
    import hashlib
    st = caption_stamps(d)
    st[cid] = {"start": round(start, 3), "end": round(end, 3),
               "sha": hashlib.sha256(path.read_bytes()).hexdigest()[:16]}
    (d / "captions" / ".window.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def caption_edited(stamp: dict, path: Path) -> bool:
    import hashlib
    if not stamp or "sha" not in stamp:
        return True
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] != stamp["sha"]


def export_captions(d: Path, idea_id: str, force: bool = False,
                    repair_only: bool = False) -> list[str]:
    """Put each clip's subtitles where a person can edit them.

    Written by render as well as by the captions command: the folder has to be
    sitting there in Finder when the video is watched, because that is the
    moment a wrong word is noticed. Having to run a command first to make the
    folder appear is a step at exactly the wrong time.
    """
    clips_f = d / "clips.json"
    if not clips_f.exists():
        return []
    clips = json.loads(clips_f.read_text(encoding="utf-8"))
    tj = d / "transcript.json"
    segs = (json.loads(tj.read_text(encoding="utf-8"))["segments"]
            if tj.exists() else [])
    out = d / "captions"
    out.mkdir(exist_ok=True)
    (out / "여기서 자막을 고칩니다.txt").write_text(
        CAPTIONS_README.format(idea=idea_id), encoding="utf-8")

    stamps = caption_stamps(d)
    made, moved = [], []
    for c in clips:
        cid, dst = c["id"], caption_override(d, c["id"])
        start, end = parse_time(c["start"]), parse_time(c["end"])
        stamp = stamps.get(cid)
        if repair_only and not dst.exists():
            # Called from render, whose job here is to repair a caption file
            # that no longer matches its clip — not to create one and thereby
            # take the clip off the transcript path before it is even burned.
            continue
        if dst.exists() and not force:
            # A file written for this exact cut stays untouched — that is the
            # whole point of the folder.
            if stamp and (abs(stamp.get("start", -1) - start) < 0.05
                          and abs(stamp.get("end", -1) - end) < 0.05):
                continue
            # No stamp at all means the file predates this check. Leave it —
            # `captions --show` reports whether it still matches.
            if not stamp:
                continue
            # The clip moved. The words on disk are timed to the old cut, so
            # burning them now puts the subtitles out of sync with the video.
            if caption_edited(stamp, dst):
                keep = dst.with_name(f"{cid}.srt.이전")
                shutil.move(str(dst), str(keep))
                moved.append((cid, keep))

        rendered = d / "renders" / "subs" / f"{cid}.srt"
        # renders/subs is a copy of the last burn. It only describes the
        # current cut if clips.json has not been edited since.
        fresh_burn = (rendered.exists()
                      and rendered.stat().st_mtime >= clips_f.stat().st_mtime)
        if fresh_burn and not stamp:
            shutil.copyfile(rendered, dst)      # exactly what was burned in
        elif segs:
            window = [{"start": max(x["start"], start), "end": min(x["end"], end),
                       "text": x["text"]}
                      for x in segs if x["end"] > start and x["start"] < end]
            write_srt(window, dst, offset=start)
        elif rendered.exists():
            shutil.copyfile(rendered, dst)
        else:
            continue
        write_caption_stamp(d, cid, start, end, dst)
        made.append(cid)

    for cid, keep in moved:
        print(f"    ⚠ {cid} 구간이 바뀌어 자막을 새 구간에 맞춰 다시 만들었다.")
        print(f"      고쳤던 파일은 {rel(keep)} 에 남겨 뒀다 — 필요하면 글자만 옮겨 온다.")

    # macOS refuses to open a quarantined file without a malware dialog. These
    # are plain text files this script wrote seconds ago on this machine.
    if sys.platform == "darwin":
        for f in out.glob("*"):
            subprocess.run(["xattr", "-d", "com.apple.quarantine", str(f)],
                           capture_output=True)
    return made


def cmd_captions(args):
    """Put each clip's subtitles somewhere a person can edit them.

    renders/subs/ is regenerated on every render, so editing there is lost
    work. captions/ is the copy render reads back — edit the words, re-render,
    and nothing else about the clip changes.
    """
    d = need(args.idea_id)
    clips = json.loads((d / "clips.json").read_text(encoding="utf-8"))
    segs = json.loads((d / "transcript.json").read_text(encoding="utf-8"))["segments"]
    out = d / "captions"
    if args.show:
        show_captions(d, clips, segs)
        print("\n위 내용이 고친 것과 다르면 편집기에서 저장이 안 된 것이다.\n"
              "(맥 텍스트편집기: command+S · 메모장: Ctrl+S)")
        return

    made = export_captions(d, args.idea_id, force=args.force)
    for c in clips:
        mark = "새로 꺼냄" if c["id"] in made else "이미 있음 — 그대로 둔다"
        print(f"    {c['id']}  {mark}  {rel(caption_override(d, c['id']))}")

    first = out / "clip-01.srt"
    opener = ("open -e" if sys.platform == "darwin"
              else "notepad" if _windows() else "xdg-open")
    print(f"\n글자를 고치고 다시 렌더하면 고친 대로 나온다:\n"
          f"  {opener} {rel(first)}\n"
          f"  bash scripts/shorts render {args.idea_id}\n"
          f"\n시간(-->)은 건드리지 말 것. 맨 아랫줄 글자만 고친다.")
    if sys.platform == "darwin":
        print("파인더에서 더블클릭하면 macOS가 경고를 띄운다. 위 open -e 로 연다.")
    if not args.no_open and open_in_file_manager(out):
        print(f"\n==> {rel(out)} 폴더를 열었다")
    else:
        print(f"\n폴더를 다시 열려면:  bash scripts/shorts open {args.idea_id} captions")


def cmd_fix(args):
    """Replace a misheard word everywhere in one service.

    The same mistake lands in the transcript and in every clip cut from it, so
    fixing it in one place and not the other is how a clip ends up disagreeing
    with itself.
    """
    d = need(args.idea_id)
    wrong, right = args.wrong, args.right
    if not wrong:
        die("바꿀 말이 비어 있다")
    hits = 0

    tj = d / "transcript.json"
    if tj.exists():
        data = json.loads(tj.read_text(encoding="utf-8"))
        for sg in data["segments"]:
            if wrong in sg["text"]:
                print(f"  전사본 {hhmmss(sg['start'])}  {sg['text'].strip()[:60]}")
                sg["text"] = sg["text"].replace(wrong, right)
                hits += 1
        tj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        write_srt(data["segments"], d / "transcript.srt")

    for srt in sorted((d / "captions").glob("*.srt")) if (d / "captions").exists() else []:
        text = srt.read_text(encoding="utf-8")
        if wrong in text:
            n = text.count(wrong)
            srt.write_text(text.replace(wrong, right), encoding="utf-8")
            print(f"  {srt.name} {n}곳")
            hits += n

    if not hits:
        print(f"'{wrong}' 을 찾지 못했다. 띄어쓰기까지 정확히 맞는지 보라.")
        return
    print(f"\n{hits}곳 고쳤다: '{wrong}' → '{right}'")

    if args.remember:
        lex = load_lexicon()
        if not any(e.get("wrong") == wrong for e in lex):
            lex.append({"wrong": wrong, "right": right})
            LEXICON.parent.mkdir(parents=True, exist_ok=True)
            LEXICON.write_text(json.dumps(lex, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
            print(f"기억했다 — 앞으로 전사할 때마다 자동으로 고친다 "
                  f"({LEXICON.relative_to(REPO)})")

    print(f"다시 렌더: bash scripts/shorts render {args.idea_id}")


# ----------------------------------------------------------------- clips ---
PLACEHOLDER_REASON = "왜 이 구간인가 — 근거를 문장으로"

CLIPS_TEMPLATE = [{
    "id": "clip-01",
    "start": "00:00:00",
    "end": "00:00:45",
    "title": "",
    "hook": "",
    "description": "",
    "reason": PLACEHOLDER_REASON,
    "has_worship_music": False,
    "congregation_visible": False,
    "crop": "center",
}]


SELECT_PROMPT = """너는 한국 개신교 교회의 주일설교에서 유튜브 쇼츠로 쓸 구간을 고른다.

아래는 설교 전사본이다. 각 줄은 [초] 형식의 절대 시각과 발화다.

{transcript}

여기서 쇼츠 {count}편을 고른다. 규칙:

1. **반드시 {win_start}초 ~ {win_end}초 사이에서만 고른다.** 그 바깥은 찬양·기도·
   봉헌이라 저작권에 걸린다.
2. 각 구간은 **40~70초**. 배속이 걸려 실제로는 27~47초가 된다.
3. 한 구간은 **그 자체로 완결**되어야 한다. 문장 중간에서 시작하거나 끝나지 말 것.
4. **성경 지식이 없는 사람도 첫 문장부터 이해되는 대목**을 고른다. 인명·지명이
   많이 나오는 성경 서사 설명보다, 목사님이 일상 예화를 들거나 청중에게 직접
   말을 거는 대목이 낫다.
5. {count}편이 서로 **다른 각도**여야 한다. 같은 이야기를 잘라 붙이지 말 것.
6. 전사본에 시간 공백이 큰 곳(앞 줄의 끝과 다음 줄의 시작이 10초 이상 벌어진 곳)은
   자막이 비므로 그 구간을 걸치지 말 것.

각 편에 대해 쓴다:
- start, end: 초 단위 숫자 (전사본의 시각을 그대로 쓴다)
- title: 화면 상단과 유튜브 제목에 쓸 12자 내외의 문장. 그 구간의 말에서 뽑는다.
- hook: 그 구간에서 가장 강한 실제 발화 한 문장 (전사본에서 그대로 인용)
- reason: 왜 이 구간인가. 한두 문장으로 구체적으로. "좋아서"처럼 쓰지 말 것.

**JSON 배열만 출력한다. 설명 문장, 코드펜스, 그 외 아무것도 붙이지 말 것.**
형식: [{{"start": 3304.5, "end": 3354.0, "title": "...", "hook": "...", "reason": "..."}}]
"""


def _extract_json(text: str):
    """Pull the JSON out of a model reply that may be wrapped in prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for pat in (r"\[.*\]", r"\{.*\}"):
            m = re.search(pat, text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue
        raise


def _ask_claude(prompt: str) -> str:
    """Ask the locally installed Claude Code.

    Uses the subscription already signed in on this machine, so it costs
    nothing extra and needs no API key. `-p` runs one query and exits.
    """
    exe = _exe("claude")
    if not exe:
        raise RuntimeError("claude CLI not found")
    p = subprocess.run([exe, "-p", prompt], capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        raise RuntimeError(f"claude -p failed: {p.stderr[:200]}")
    return p.stdout


def _ask_gemini(prompt: str) -> str:
    """Fallback where the Claude CLI is not installed — the cloud container."""
    client, types = _gemini_client()
    for model in GEMINI_MODELS:
        try:
            r = client.models.generate_content(
                model=model, contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", max_output_tokens=8000))
            return r.text
        except Exception as e:  # noqa: BLE001 — try the next model on overload
            print(f"    {model}: {str(e)[:70]}")
    raise RuntimeError("no Gemini model answered")


def ask_json(prompt: str, backend: str = "auto"):
    """Put a question to whichever model this machine has. Claude first: on a
    laptop it is already signed in and costs nothing beyond the subscription."""
    order = {"claude": ["claude"], "gemini": ["gemini"]}.get(
        backend, ["claude", "gemini"])
    errs = []
    for b in order:
        try:
            return _extract_json(_ask_claude(prompt) if b == "claude"
                                 else _ask_gemini(prompt))
        except Exception as e:  # noqa: BLE001 — report and try the next one
            errs.append(f"  {b}: {str(e)[:160]}")
            print(f"    {b} 사용 불가: {str(e)[:80]}")
    raise RuntimeError("판단할 모델이 없다:\n" + "\n".join(errs))


def select_with_claude(prompt: str) -> list[dict]:
    return _extract_json(_ask_claude(prompt))


def select_with_gemini(prompt: str) -> list[dict]:
    return _extract_json(_ask_gemini(prompt))


def cmd_select(args):
    """Choose the clips automatically instead of stopping for a person.

    The gate exists so that a *keyword heuristic* never picks the segments —
    it cannot tell a throwaway aside from the line a sermon turns on. A model
    that has read the whole transcript can, which is exactly what happens when
    a person asks Claude to do it by hand. This just removes the round trip.

    What stays enforced regardless of what the selector returns: clips must
    land inside the sermon window, run 15-180 seconds, and carry a reason.
    The copyright rule is structural, not a matter of the selector's judgement.
    """
    d = need(args.idea_id)
    data = json.loads((d / "transcript.json").read_text(encoding="utf-8"))
    segs = data["segments"]
    w = data.get("sermon_window")
    win = (w["start"], w["end"]) if w else (segs[0]["start"], segs[-1]["end"])

    lines = "\n".join(f"[{s['start']:.1f}] {s['text']}"
                      for s in segs if win[0] <= s["start"] <= win[1])
    prompt = SELECT_PROMPT.format(transcript=lines, count=args.count,
                                  win_start=int(win[0]), win_end=int(win[1]))

    backends = ([select_with_claude, select_with_gemini] if args.backend == "auto"
                else [select_with_claude] if args.backend == "claude"
                else [select_with_gemini])
    picked, errs = None, []
    for fn in backends:
        try:
            print(f"==> 구간 선별 — {fn.__name__}")
            picked = fn(prompt)
            break
        except Exception as e:  # noqa: BLE001 — report and try the next backend
            errs.append(f"  {fn.__name__}: {e}")
            print(f"    사용 불가: {str(e)[:90]}")
    if picked is None:
        die("구간 선별 실패:\n" + "\n".join(errs))

    # The pulpit moves between Sunday services, not within one, so this is
    # measured once per video — over the sermon window, because during the
    # worship set the camera is on the congregation and the band.
    src = find_source(d)
    print("==> 화면에서 설교자 위치 찾는 중")
    crop = auto_crop(src, win[0], win[1], fallback=(win[0], win[1]))
    ec = ensure_end_card(d, args.idea_id) or (d / "end-card.json")
    meta = json.loads(ec.read_text(encoding="utf-8")) if ec.exists() else {}
    # WED/DAWN productions were shipping with "주일예배" hardcoded here even
    # though end_card_from_title already knows better (SUN/WED/DAWN prefix on
    # the idea-id) — read it from the same place rather than assuming Sunday.
    kind_m = re.match(r"(SUN|WED|DAWN)-", args.idea_id)
    service_label = {"SUN": "주일예배", "WED": "수요예배",
                      "DAWN": "새벽기도"}.get(kind_m.group(1) if kind_m else "", "주일예배")
    desc_tail = (f"{meta.get('church','')} {service_label} | {meta.get('scripture','')} | "
                 f"{meta.get('preacher','')}").strip(" |")

    clips = []
    for i, c in enumerate(picked[:args.count], 1):
        start, end = float(c["start"]), float(c["end"])
        # The selector proposes; the window is not negotiable.
        start, end = max(start, win[0]), min(end, win[1])
        if end - start < 15:
            print(f"    clip-{i:02d} 건너뜀 — 설교 구간으로 자르니 {end-start:.0f}초")
            continue
        clips.append({
            "id": f"clip-{len(clips)+1:02d}",
            "start": round(start, 1), "end": round(end, 1),
            "title": str(c.get("title", "")).strip(),
            "hook": str(c.get("hook", "")).strip(),
            "description": desc_tail,
            "reason": str(c.get("reason", "")).strip(),
            "has_worship_music": False,
            "congregation_visible": False,
            "crop": crop,
        })

    if not clips:
        die("설교 구간 안에서 쓸 만한 구간이 나오지 않았다")
    (d / "clips.json").write_text(json.dumps(clips, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    print(f"==> {len(clips)}편 선별 → clips.json")
    for c in clips:
        print(f"    {c['id']}  {hhmmss(c['start'])}–{hhmmss(c['end'])}  {c['title']}")
    validate_clips(d / "clips.json", segs, strict=True)


def cmd_repair(args):
    """Run the duplicate/hole pass over a transcript that already exists."""
    d = need(args.idea_id)
    tj = d / "transcript.json"
    if not tj.exists():
        die("no transcript.json — run `transcribe` first")
    data = json.loads(tj.read_text(encoding="utf-8"))
    wav = extract_audio(find_source(d), d / "source" / "audio16k.wav")
    w = data.get("sermon_window")
    window = (w["start"], w["end"]) if w else None

    before = len(data["segments"])
    segs = repair_transcript(wav, data["segments"], window, fill_holes=args.fill_holes)
    data["segments"] = segs
    tj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_srt(segs, d / "transcript.srt")
    print(f"==> {before} → {len(segs)} segments")


def cmd_validate(args):
    """Is clips.json ready to render? Exit 0 yes, 1 no. No side effects —
    weekly_run.sh uses this to decide whether a human still has to read the
    transcript, so it must not write anything."""
    d = need(args.idea_id)
    cj = d / "clips.json"
    if not cj.exists():
        print("clips.json not written yet")
        sys.exit(1)
    tj = d / "transcript.json"
    segs = json.loads(tj.read_text(encoding="utf-8"))["segments"] if tj.exists() else []
    clips = validate_clips(cj, segs, strict=True)  # exits 1 on any problem
    print(f"ok — {len(clips)} clip(s) ready to render")


def cmd_clips(args):
    d = need(args.idea_id)
    tj = d / "transcript.json"
    if not tj.exists():
        die("no transcript.json — run `transcribe` first")
    segs = json.loads(tj.read_text(encoding="utf-8"))["segments"]

    clips_path = d / "clips.json"
    if not clips_path.exists():
        clips_path.write_text(json.dumps(CLIPS_TEMPLATE, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        print(f"==> wrote template {clips_path.relative_to(REPO)}")

    # Group segments into readable blocks so a person can actually scan it.
    print(f"\n=== transcript: {args.idea_id} "
          f"({len(segs)} segments, {hhmmss(segs[-1]['end']) if segs else '0'}) ===\n")
    block, block_start = [], segs[0]["start"] if segs else 0.0
    for s in segs:
        block.append(s["text"])
        if s["end"] - block_start >= args.window:
            print(f"[{hhmmss(block_start)}] {' '.join(block)}")
            block, block_start = [], s["end"]
    if block:
        print(f"[{hhmmss(block_start)}] {' '.join(block)}")

    print(f"\n=== now edit {clips_path.relative_to(REPO)} ===")
    print("clip 3개, 각 30~90초. reason 필드에 왜 그 구간인지 반드시 적을 것.")
    validate_clips(clips_path, segs, strict=False)


def validate_clips(path: Path, segs: list[dict], strict: bool = True) -> list[dict]:
    clips = json.loads(path.read_text(encoding="utf-8"))
    total = segs[-1]["end"] if segs else 0.0
    problems, flags = [], []

    for c in clips:
        cid = c.get("id", "?")
        start, end = parse_time(c["start"]), parse_time(c["end"])
        dur = end - start
        if dur <= 0:
            problems.append(f"{cid}: end is not after start")
        elif not 15 <= dur <= 180:
            problems.append(f"{cid}: {dur:.0f}s is outside 15–180s")
        if total and end > total + 1:
            problems.append(f"{cid}: ends at {hhmmss(end)}, past the source ({hhmmss(total)})")
        if strict:
            # An untouched template must not render. Its placeholder reason is
            # non-empty, so an "is it blank" check alone would wave it through.
            reason = c.get("reason", "").strip()
            if not reason or reason == PLACEHOLDER_REASON:
                problems.append(f"{cid}: reason is still the template placeholder — "
                                "write why this segment was chosen")
            for field in ("title", "hook"):
                if not c.get(field, "").strip():
                    problems.append(f"{cid}: {field} is empty")
        if c.get("has_worship_music"):
            flags.append(f"{cid}: 찬양 음원 포함 — Content ID 위험. 배포 전 개별 확인 필요")
        if c.get("congregation_visible"):
            flags.append(f"{cid}: 회중석 노출 — 크롭 확인 또는 동의 필요")

    for f in flags:
        print(f"  [FLAG] {f}")
    if problems:
        msg = "clips.json problems:\n" + "\n".join(f"  - {p}" for p in problems)
        if strict:
            die(msg)
        print(msg)
    return clips


# ---------------------------------------------------------------- render ---
# The channel abbreviates the passage in its titles. Spelled out, the card
# reads as something a viewer can type into YouTube search and find.
BOOKS = {
    "창": "창세기", "출": "출애굽기", "레": "레위기", "민": "민수기", "신": "신명기",
    "수": "여호수아", "삿": "사사기", "룻": "룻기",
    "삼상": "사무엘상", "삼하": "사무엘하", "왕상": "열왕기상", "왕하": "열왕기하",
    "대상": "역대상", "대하": "역대하", "스": "에스라", "느": "느헤미야", "에": "에스더",
    "욥": "욥기", "시": "시편", "잠": "잠언", "전": "전도서", "아": "아가",
    "사": "이사야", "렘": "예레미야", "애": "예레미야애가", "겔": "에스겔", "단": "다니엘",
    "호": "호세아", "욜": "요엘", "암": "아모스", "옵": "오바댜", "욘": "요나",
    "미": "미가", "나": "나훔", "합": "하박국", "습": "스바냐", "학": "학개",
    "슥": "스가랴", "말": "말라기",
    "마": "마태복음", "막": "마가복음", "눅": "누가복음", "요": "요한복음",
    "행": "사도행전", "롬": "로마서", "고전": "고린도전서", "고후": "고린도후서",
    "갈": "갈라디아서", "엡": "에베소서", "빌": "빌립보서", "골": "골로새서",
    "살전": "데살로니가전서", "살후": "데살로니가후서",
    "딤전": "디모데전서", "딤후": "디모데후서", "딛": "디도서", "몬": "빌레몬서",
    "히": "히브리서", "약": "야고보서", "벧전": "베드로전서", "벧후": "베드로후서",
    "요일": "요한일서", "요이": "요한이서", "요삼": "요한삼서", "유": "유다서",
    "계": "요한계시록",
}


def expand_scripture(ref: str) -> str:
    """[삼하 2:24-32] → 사무엘하 2:24-32. Left alone if the book is unknown —
    the older titles already spell the book out."""
    m = re.match(r"\s*([가-힣]{1,5})\s*([\d:\-–,\s]+)\s*$", ref.strip())
    if not m:
        return ref.strip()
    book, verses = m.group(1), re.sub(r"\s+", "", m.group(2))
    return f"{BOOKS.get(book, book)} {verses}"


# The channel has used two title shapes over the years:
#   2026-08-09 [삼하 19:31-39] 나이 들면 바르실래처럼 / 장선기 목사
#   2024.06.23 택하신 곳으로 나아가야 하는 이유 신명기 12:1-8 장선기목사
# The second has no brackets and no slash, so the passage and the preacher
# have to be recognised by their own shape rather than by punctuation.
BARE_SCRIPTURE = re.compile(
    r"([가-힣]{1,5}\s*\d{1,3}\s*:\s*\d{1,3}(?:\s*[-–~]\s*\d{1,3})?"
    r"(?:\s*,\s*\d{1,3}(?:\s*[-–~]\s*\d{1,3})?)*)")
TRAILING_PREACHER = re.compile(r"([가-힣]{2,4})\s*(원로목사|목사|전도사|강도사)\s*$")


def end_card_from_title(idea_id: str, video_title: str) -> dict:
    """Build the closing card out of the channel's own video title.

    Titles run "2026-08-09 [삼하 19:31-39] 나이 들면 바르실래처럼 / 장선기 목사".
    The date comes from the idea-id rather than the title, because the title
    has been wrong before and the idea-id is already corrected.
    """
    m = re.match(r"(SUN|WED|DAWN)-(\d{4})-(\d{2})-(\d{2})", idea_id)
    if m:
        label = {"SUN": "주일예배", "WED": "수요예배", "DAWN": "새벽기도"}[m.group(1)]
        date = (f"{int(m.group(2))}년 {int(m.group(3))}월 {int(m.group(4))}일 {label}")
    else:
        date = ""

    ref = TITLE_SCRIPTURE.search(video_title)
    if ref:
        scripture = expand_scripture(ref.group(1))
        body = video_title[ref.end():]
    else:
        scripture = ""
        body = TITLE_DATE.sub("", video_title)

    preacher, body = "", body.strip()
    if "/" in body:
        body, tail = body.rsplit("/", 1)
    else:
        pm = TRAILING_PREACHER.search(body)
        tail = pm.group(0) if pm else ""
        body = body[:pm.start()] if pm else body
    tail = tail.strip()
    if tail:
        # "장선기목사" and "장선기 목사" are both in use on this channel.
        preacher = "설교 · " + TRAILING_PREACHER.sub(r"\1 \2", tail).strip()
    if not preacher:
        # 이 채널은 영상 제목에 설교자 이름이 없다. 엔드카드에는 고정값을 쓴다.
        preacher = "설교 · 이재용 목사"

    if not scripture:                       # older titles spell it out inline
        bm = BARE_SCRIPTURE.search(body)
        if bm:
            scripture = expand_scripture(bm.group(1))
            body = body[:bm.start()] + body[bm.end():]

    title = re.sub(r"\s{2,}", " ", body).strip(" \t-·|,/")
    if title in ("새벽기도", "수요예배", "주일예배", ""):
        title = ""      # no sermon title of its own; the passage carries the card

    return {"date": date, "scripture": scripture, "title": title,
            "preacher": preacher, "church": CHURCH_NAME,
            "handle": channel_handle()}


def source_title(d: Path) -> str:
    """The video's own title — from yt-dlp's info file, else the channel list."""
    for info in sorted((d / "source").glob("*.info.json")):
        try:
            t = json.loads(info.read_text(encoding="utf-8")).get("title")
            if t:
                return t
        except (OSError, json.JSONDecodeError):
            pass
    meta = d / "meta.json"
    if not meta.exists():
        return ""
    url = json.loads(meta.read_text(encoding="utf-8")).get("source_url", "")
    m = VIDEO_ID.search(url)
    if not m:
        return ""
    vid = m.group(1) or m.group(2)
    try:
        hit = next((x for x in list_sermons("") if x["id"] == vid), None)
    except SystemExit:
        return ""
    return hit["title"] if hit else ""


def ensure_end_card(d: Path, idea_id: str) -> Path | None:
    """Write end-card.json if it is not there yet.

    A short travels away from the channel that made it, so every clip closes
    on the service it came from. Nothing in the automated path used to create
    this file, which meant an unattended run shipped clips with no card at
    all. A file already on disk is left alone — a person may have fixed it.
    """
    ec = d / "end-card.json"
    if ec.exists():
        return ec
    title = source_title(d)
    if not title:
        print("    엔드카드: 원본 제목을 못 찾아 건너뛴다 "
              "(end-card.json 을 직접 만들면 붙는다)")
        return None
    cfg = end_card_from_title(idea_id, title)
    ec.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"    엔드카드 생성 — {cfg['date']} · {cfg['scripture']} · {cfg['title']}")
    return ec


END_CARD_SECONDS = 4.0
END_CARD_BG = "0x123A34"   # the sanctuary's stage green, so the cut reads as one piece


def _ass_escape(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").strip()


def build_end_card(cfg: dict, out: Path, seconds: float = END_CARD_SECONDS) -> Path:
    """A card naming the service, so a viewer can go and find the full sermon.

    A short travels away from the channel that made it. Without this, an
    excerpt is an unattributed stranger talking; with it, the sermon is
    searchable by title and passage, which are exact and unique.
    """
    lines = [
        # (text, y, size, colour, bold)
        (cfg.get("date", ""),      560,  54, "&H00C8D8D4", 0),
        (cfg.get("scripture", ""), 690,  60, "&H0090E0C8", 1),
        (cfg.get("title", ""),     880,  78, "&H00FFFFFF", 1),
        (cfg.get("preacher", ""), 1180,  58, "&H00E8F0EE", 0),
        (cfg.get("church", ""),   1360,  68, "&H00FFFFFF", 1),
        (cfg.get("handle", ""),   1470,  48, "&H0098B0AC", 0),
    ]
    rows, styles = [], []
    for i, (text, y, size, colour, bold) in enumerate(lines):
        if not text:
            continue
        styles.append(
            f"Style: E{i},{FONT_NAME},{size},{colour},&H000000FF,&H00000000,&H00000000,"
            f"{bold},0,0,0,100,100,0,0,1,0,0,5,60,60,0,1")
        wrapped = wrap_korean(_ass_escape(text), per_line=14, max_lines=2)
        rows.append(f"Dialogue: 0,{ass_ts(0)},{ass_ts(seconds)},E{i},,0,0,0,,"
                    f"{{\\pos({OUT_W//2},{y})}}{wrapped}")

    ass = out.with_suffix(".ass")
    ass.write_text(
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {OUT_W}\nPlayResY: {OUT_H}\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + "\n".join(styles)
        + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
          "MarginV, Effect, Text\n" + "\n".join(rows) + "\n",
        encoding="utf-8")

    # Encoded to match the clip exactly, so the two concatenate without a re-encode.
    run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c={END_CARD_BG}:s={OUT_W}x{OUT_H}:r=30:d={seconds}",
         "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:d={seconds}",
         "-vf", subtitles_filter(ass),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-r", "30",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
         "-shortest", str(out)], cwd=REPO)
    return out


# This channel's stream has a fixed layout, measured on the 720p and 360p
# sources and identical in both once expressed as fractions of the frame:
#   - a graphic sidebar (passage, sermon title, logo) owns the right third
#   - a scripture caption band is burned across the top during readings
# Both are dead weight in a 9:16 crop — the sidebar pushes the preacher off
# centre, and the caption band gets sliced mid-word. Cutting them away also
# removes the empty air above his head, which frames him better on a phone.
LIVE_AREA_RIGHT = 0.634    # sidebar starts here (x=812 of 1280)
TOP_BAND = 0.243           # caption band height (y=175 of 720)

# Where the preacher is, found by looking rather than assumed. The channel's
# layout is not one layout: the 2026 streams put him centre-left with a graphic
# sidebar on the right, while the 2025 ones key him into the left quarter over
# a full-frame illustration. A crop tuned to either puts him half out of frame
# in the other, so his position is measured per video.
#
# What separates him from the set is that he moves. Sampling frames across the
# sermon and summing the differences leaves a bright patch where the preacher
# is and near-nothing on backdrop, captions and graphics.
MOTION_W, MOTION_H = 96, 54     # coarse enough to be cheap, fine enough to place him
MOTION_POINTS = 8               # moments sampled across the sermon
# A second, not a fraction of one: a preacher at a lectern barely moves in
# 0.4s and three of three measured clips fell under the detection floor at that
# gap, while all three cleared it comfortably at 1.0s.
MOTION_GAP = 1.0
# Measured, not guessed: a still image with audio over it scores exactly 0,
# while the quietest real footage here (a 360p sermon, one preacher at a
# lectern) scores 2597 per pair. 300 sits an order of magnitude below that and
# well above any encoder shimmer.
STILL_ENERGY = 300
MAX_TOP_TRIM = 0.30             # never throw away more than this much of the height
HEADROOM = 0.12                 # keep this much of the frame above him


def _gray_frame(video: Path, at: float) -> bytes | None:
    p = subprocess.run(
        [*ffmpeg_cmd(), "-hide_banner", "-loglevel", "error", "-ss", f"{at:.2f}",
         "-i", str(video), "-frames:v", "1",
         "-vf", f"scale={MOTION_W}:{MOTION_H},format=gray", "-f", "rawvideo", "-"],
        capture_output=True)
    return p.stdout if len(p.stdout) == MOTION_W * MOTION_H else None


def _span(profile: list[int], rel: float = 0.12) -> tuple[int, int] | None:
    """The busiest contiguous run in the profile.

    Not the run around the single highest cell: a blinking LIVE badge or a
    caption animating can out-peak a preacher in one column while covering
    almost no area. Taking the run with the most total motion picks the person
    over the badge, and being contiguous keeps a second moving thing elsewhere
    in the frame from dragging the centre between the two.

    The threshold has to sit well below the peak for the same reason — a spike
    ten times the preacher's own level would otherwise put the cut above him
    and leave only the spike standing.
    """
    peak = max(profile)
    if peak <= 0:
        return None
    cut = peak * rel
    best, run = None, None
    for i, v in enumerate(profile + [0]):
        if v >= cut and i < len(profile):
            run = (i, i) if run is None else (run[0], i)
            continue
        if run:
            total = sum(profile[run[0]:run[1] + 1])
            if best is None or total > best[0]:
                best = (total, run[0], run[1])
            run = None
    return (best[1], best[2]) if best else None


def motion_box(video: Path, start: float = 0.0, end: float | None = None):
    """Bounding box of the moving subject, in fractions of the frame.

    Frames are compared in pairs a fraction of a second apart, not minutes:
    over minutes a camera cut changes the whole picture and everything reads as
    motion, while within half a second only the preacher moves and the set,
    captions and graphics hold still.

    Returns (x0, y0, x1, y1); "still" when the picture never moves at all — a
    thumbnail with audio over it, which 새벽기도 is posted as — or None when it
    moves but nothing in it looks like a person.
    """
    try:
        total = probe_duration(video)
    except Exception:  # noqa: BLE001
        return None
    a, b = max(0.0, start), min(end if end else total, total)
    if b - a < 20:
        a, b = 0.0, total

    cols = [0] * MOTION_W
    rows = [0] * MOTION_H
    pairs = 0
    for i in range(MOTION_POINTS):
        t = a + (b - a - MOTION_GAP) * i / max(MOTION_POINTS - 1, 1)
        f, g = _gray_frame(video, t), _gray_frame(video, t + MOTION_GAP)
        if not f or not g:
            continue
        pairs += 1
        for j in range(MOTION_W * MOTION_H):
            d = abs(f[j] - g[j])
            if d > 8:                       # ignore compression shimmer
                cols[j % MOTION_W] += d
                rows[j // MOTION_W] += d
    if pairs < 3:
        return None
    energy = sum(cols) / pairs
    if energy < STILL_ENERGY:                # a still image with audio over it
        return "still"
    if max(cols) < 200 * pairs:              # moving, but nothing subject-like
        return None

    cx, cy = _span(cols), _span(rows)
    if not cx or not cy:
        return None
    return (cx[0] / MOTION_W, cy[0] / MOTION_H,
            (cx[1] + 1) / MOTION_W, (cy[1] + 1) / MOTION_H)


def frame_size(video: Path) -> tuple[int, int]:
    p = subprocess.run([*ffmpeg_cmd(), "-hide_banner", "-i", str(video)],
                       capture_output=True, text=True)
    m = re.search(r"(\d{3,4})x(\d{3,4})", p.stderr)
    if not m:
        die(f"could not read frame size of {video}")
    return int(m.group(1)), int(m.group(2))


def sermon_window_of(d: Path) -> tuple[float, float] | None:
    """The sermon's own start and end, as transcribe recorded them."""
    tj = d / "transcript.json"
    if not tj.exists():
        return None
    try:
        w = json.loads(tj.read_text(encoding="utf-8")).get("sermon_window")
    except json.JSONDecodeError:
        return None
    return (float(w["start"]), float(w["end"])) if w else None


def auto_crop(video: Path, start: float = 0.0, end: float | None = None,
              fallback: tuple[float, float] | None = None):
    """Put the preacher in the middle of a 9:16 window.

    Three outcomes, decided by what the picture actually does:
      a preacher who moves  → crop centred on him
      a still image + audio → the whole picture fitted into 9:16 (새벽기도)
      neither               → the middle of the frame
    """
    w, h = frame_size(video)
    box = motion_box(video, start, end)
    if box is None and fallback:
        # A single clip can be 40 seconds of a man standing still. Widen — but
        # only to the sermon, never to the whole recording: during the worship
        # set the camera is on the band and the congregation, and measuring
        # there centres the crop on the wrong half of the room.
        print("    이 구간에서는 못 찾았다 — 설교 구간 전체에서 다시 찾는다")
        box = motion_box(video, fallback[0], fallback[1])

    if box == "still":
        print("    정지 이미지 영상 — 잘라내지 않고 9:16에 맞춘다")
        return "fit"
    if box is None:
        # Someone is there but nothing reads as a person. The middle of the
        # picture is the neutral choice — it cannot put a subject half out of
        # frame the way a guessed offset can.
        print("    움직이는 사람을 못 찾았다 — 화면 중앙을 쓴다")
        return "center"

    x0, y0, x1, y1 = box
    # Trim dead air above him, but never so much that the shot becomes a
    # close-up: a keyed-in speaker sits low in the frame and would otherwise be
    # cropped to a sliver.
    top = int(min(max(0.0, y0 - HEADROOM), MAX_TOP_TRIM) * h)
    ch = h - top
    cw = int(ch * 9 / 16)
    centre = int((x0 + x1) / 2 * w)
    x = max(0, min(centre - cw // 2, w - cw))
    print(f"    설교자 위치 x {x0:.2f}–{x1:.2f} · y {y0:.2f}–{y1:.2f} "
          f"→ 크롭 x={x} y={top} h={ch}")
    return {"x": x, "y": top, "h": ch}


# A still image gets the whole frame, not a slice of it: the picture is scaled
# to the full width and centred, over a blurred blow-up of itself so the 9:16
# frame is filled rather than letterboxed black.
FIT_FILTER = (
    "split[bg][fg];"
    f"[bg]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,"
    f"crop={OUT_W}:{OUT_H},gblur=sigma=32,eq=brightness=-0.09[bgb];"
    f"[fg]scale={OUT_W}:-2[fgs];"
    "[bgb][fgs]overlay=(W-w)/2:(H-h)/2-180"
)


def crop_filter(mode) -> str:
    """16:9 → 9:16.

    Three forms, increasingly specific:

    - `"center"` / `"left"` / `"right"` — full-height window, nudged sideways.
    - a number — the exact left edge in source pixels. A broadcast layout is
      rarely centred in the file: this church's stream parks a graphic sidebar
      over the right third, so `center` slices the preacher off.
    - `{"x":…, "y":…, "h":…}` — an explicit window. Needed when the stream
      burns a caption band across the top: a full-height crop clips that band
      mid-word, and cutting below it also drops the dead air above the
      preacher, which frames him far better for a phone.

    The window is always forced to 9:16 from its height, so only x/y/h are
    ever specified and the aspect can't be got wrong by hand.
    """
    if mode == "fit":
        return FIT_FILTER
    if isinstance(mode, dict):
        if mode.get("fit"):
            return FIT_FILTER
        h = int(mode["h"])
        return (f"crop=w={h}*9/16:h={h}:x={int(mode.get('x', 0))}:y={int(mode.get('y', 0))},"
                f"scale={OUT_W}:{OUT_H}")
    if isinstance(mode, (int, float)):
        x = str(int(mode))
    else:
        x = {"center": "(iw-ow)/2", "left": "0", "right": "iw-ow"}.get(mode, "(iw-ow)/2")
    return f"crop=w=ih*9/16:h=ih:x={x}:y=0,scale={OUT_W}:{OUT_H}"


def cmd_render(args):
    d = need(args.idea_id)
    video = find_source(d)
    segs = json.loads((d / "transcript.json").read_text(encoding="utf-8"))["segments"]
    clips = validate_clips(d / "clips.json", segs, strict=True)

    audio = extract_audio(video, d / "source" / "audio16k.wav") if args.retime else None

    out_dir = d / "renders"
    out_dir.mkdir(exist_ok=True)
    sub_dir = out_dir / "subs"
    sub_dir.mkdir(exist_ok=True)
    # These are outputs, rewritten on every render. Someone who finds them in
    # Finder before finding captions/ will edit them and wonder why nothing
    # changed, so the folder says so itself.
    (sub_dir / "이_폴더는_고쳐도_소용없습니다.txt").write_text(
        "이 폴더의 파일은 렌더할 때마다 새로 만들어집니다.\n"
        "여기서 자막을 고치면 다음 렌더에서 그대로 덮어써집니다.\n\n"
        "자막 글자를 고치려면:\n"
        "  1. bash scripts/shorts captions <idea-id>\n"
        "  2. captions/ 폴더의 srt 를 고친다\n"
        "  3. bash scripts/shorts render <idea-id>\n",
        encoding="utf-8")

    # Built once and appended to every clip — each short is discovered on its
    # own, so each one needs to say where it came from.
    end_card = None
    ec_path = d / "end-card.json"
    if not args.no_end_card:
        ensure_end_card(d, args.idea_id)
    if ec_path.exists() and not args.no_end_card:
        cfg = json.loads(ec_path.read_text(encoding="utf-8"))
        end_card = build_end_card(cfg, out_dir / "_endcard.mp4")
        print(f"==> 엔드카드 {END_CARD_SECONDS:.0f}초 — {cfg.get('title','')}")

    # Nothing below works without libass, and finding that out on clip-01
    # after the crop analysis has run is a waste of everyone's minute.
    require_subtitles_filter()

    # Before anything is burned: a clip whose window moved since its caption
    # file was written gets that file remade for the new window. Only that —
    # clips without a caption file stay on the transcript path below.
    export_captions(d, args.idea_id, repair_only=True)

    made, used_override = [], 0
    for c in clips:
        cid = c["id"]
        if args.only and cid != args.only:
            continue
        start, end = parse_time(c["start"]), parse_time(c["end"])

        # Subtitles for just this window, clamped to the cut and retimed so the
        # clip starts at zero.
        override = caption_override(d, cid)
        if override.exists():
            # Someone corrected these words by hand. Nothing regenerates over
            # that — not retiming, not a fresh transcript.
            print(f"    {cid} 자막 수정본 사용 — {rel(override)}")
            window, sub_offset = check_caption_file(override, end - start), 0.0
            used_override += 1
            # …but the words being right does not make the times right. A file
            # kept from an earlier cut of the same sermon burns cleanly and is
            # wrong only on screen, so say it here, before the burn.
            verdict, line = caption_sync(d, c, segs)
            if verdict == "drift":
                print(f"      {line}")
                print(f"      → 이 구간에 맞춰 다시 만들려면: "
                      f"rm {rel(override)} 후 다시 render")
            # Show what is actually on disk. TextEdit keeps edits in the window
            # until you save, so "I changed it and nothing happened" is almost
            # always an unsaved file — this makes that visible before the burn.
            print(f"      첫 자막: {window[0]['text'][:34]}")
        else:
            if args.retime:
                print(f"    {cid} 자막 재타이밍 (1 paid call)")
                src_segs = retime_window(audio, start, end)
            else:
                src_segs = segs
            window = [
                {"start": max(s["start"], start), "end": min(s["end"], end),
                 "text": s["text"]}
                for s in src_segs if s["end"] > start and s["start"] < end
            ]
            sub_offset = start
        if "crop" not in c:
            print(f"    {cid} 크롭 없음 — 이 구간에서 화면을 분석한다")
            c["crop"] = auto_crop(video, start, end, fallback=sermon_window_of(d))
        if c.get("crop") == "center":
            # Nothing was found to centre on, so the middle of the frame is a
            # guess. Say so — a preacher cropped out of shot is only visible in
            # the finished file otherwise.
            print(f"    ⚠ {cid} 설교자를 못 찾아 화면 중앙을 쓴다. 렌더 전에 확인하려면:")
            print(f"        bash scripts/shorts preview {args.idea_id}")
        speed = float(c.get("speed", DEFAULT_SPEED))
        if not 0.5 <= speed <= 2.0:
            die(f"{cid}: speed {speed} is outside atempo's 0.5–2.0 range")

        ass = sub_dir / f"{cid}.ass"
        write_ass(window, ass, offset=sub_offset,
                  title=c.get("title", "") if c.get("show_title", True) else "",
                  duration=end - start,
                  title_size=int(c.get("title_size", TITLE_SIZE)))
        write_srt(window, sub_dir / f"{cid}.srt", offset=sub_offset)  # for YouTube upload

        out = out_dir / f"{cid}.mp4"
        # Subtitles and title are burned at the original timing, then the whole
        # picture is retimed. Doing it this way keeps captions in sync for free:
        # each frame already carries its text, and setpts only moves the frame.
        vf = f"{crop_filter(c.get('crop', 'center'))},{subtitles_filter(ass)}"
        af = None
        if speed != 1.0:
            vf += f",setpts=PTS/{speed}"
            af = f"atempo={speed}"

        dur = (end - start) / speed
        print(f"==> {cid}  {hhmmss(start)}–{hhmmss(end)}  "
              f"({end-start:.0f}s → {dur:.0f}s @ {speed}x)")
        cmd = [
            *ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start}", "-to", f"{end}", "-i", str(video),
            "-vf", vf,
        ]
        if af:
            cmd += ["-af", af]
        body = out if end_card is None else out.with_name(f"{cid}.body.mp4")
        cmd += [
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            str(body),
        ]
        run(cmd, cwd=REPO)   # 필터 안의 경로가 저장소 기준이다

        if end_card is not None:
            lst = out_dir / f"{cid}.concat.txt"
            lst.write_text(f"file '{body.resolve()}'\nfile '{end_card.resolve()}'\n",
                           encoding="utf-8")
            run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
                 "-f", "concat", "-safe", "0", "-i", str(lst),
                 "-c", "copy", "-movflags", "+faststart", str(out)])
            lst.unlink()
            body.unlink()

        # 인스타그램 등 컴퓨터 업로드 화면은 자동 썸네일 후보 중 하나가
        # 종종 검은 프레임으로 잘못 뽑힌다 (모바일 앱 업로드에서는 안 그런다).
        # 커버 프레임을 정지 이미지로 따로 뽑아두면, 업로드 화면에서 영상
        # 타임라인을 긁는 대신 "컴퓨터에서 선택"으로 이 파일을 바로 커버로
        # 올릴 수 있어 그 문제를 완전히 우회한다.
        cover = out.with_name(f"{cid}-cover.jpg")
        run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
             "-ss", "0.05", "-i", str(out), "-frames:v", "1", "-q:v", "2",
             str(cover)])

        made.append((cid, out, c))

    # Human-facing package. Renders are gitignored; this file is the record.
    # It is written from every clip in clips.json, not just the ones rendered
    # this run — a `--only` re-render used to leave a package listing one clip
    # and silently drop the rest of the approval notes.
    rendered = {cid for cid, _, _ in made}
    pkg = ["# 발행 패키지 — " + args.idea_id, "",
           "**업로드는 사람이 한다. 이 파일은 승인용 초안이다.**", ""]
    for c in clips:
        cid = c["id"]
        out = out_dir / f"{cid}.mp4"
        if cid not in rendered and not out.exists():
            continue
        pkg += [
            f"## {cid}",
            f"- 파일: `renders/{out.name}` (gitignored)",
            f"- 구간: {c['start']} – {c['end']}"
            + (f"  ({float(c.get('speed', DEFAULT_SPEED))}배속)"
               if float(c.get("speed", DEFAULT_SPEED)) != 1.0 else ""),
            f"- 제목: {c.get('title','')}",
            f"- 후킹: {c.get('hook','')}",
            f"- 설명: {c.get('description','')}",
            f"- 선정 근거: {c.get('reason','')}",
        ]
        if c.get("has_worship_music"):
            pkg.append("- ⚠️ 찬양 음원 포함 — Content ID 확인 전 업로드 금지")
        if c.get("congregation_visible"):
            pkg.append("- ⚠️ 회중석 노출 — 크롭/동의 확인 필요")
        pkg.append("")
    (d / "publish-package.md").write_text("\n".join(pkg), encoding="utf-8")

    print(f"\n==> {len(made)} clip(s) in {rel(out_dir)}")
    print(f"==> 승인용 패키지: {rel(d / 'publish-package.md')}")
    if used_override:
        print(f"==> 자막은 {rel(d / 'captions')} 의 수정본을 썼다 "
              f"({used_override}개 클립)")
    else:
        print("==> 자막은 전사본 그대로다 (아직 고친 것 없음)")
    # A wrong word is noticed while watching the render, so the folder that
    # fixes it has to be sitting there already — not behind a command you have
    # to know about at exactly that moment.
    export_captions(d, args.idea_id)
    print(f"==> 자막 고칠 파일: {rel(d / 'captions')}")
    print("==> 업로드하지 않았다. 사람이 확인하고 직접 올린다.")

    if not args.no_open and open_in_file_manager(d):
        print(f"==> {rel(d)} 폴더를 열었다 — renders 와 captions 가 같이 보인다")
    else:
        print(f"==> 폴더를 열려면:  bash scripts/shorts open {args.idea_id}")


# ---------------------------------------------------------------- doctor ---
def cmd_preview(args):
    """Show what the crop will look like before spending a render on it.

    Two pictures per clip: the 9:16 frame that would be burned, and the whole
    source frame with that window drawn on it. The second is what tells you
    *why* — whether the preacher was found and simply framed tight, or missed
    and something else centred instead.
    """
    d = need(args.idea_id)
    video = find_source(d)
    clips_f = d / "clips.json"
    if not clips_f.exists():
        die(f"{rel(clips_f)} 가 없다 — 먼저 구간을 고른다:\n"
            f"  bash scripts/shorts select {args.idea_id} --count 3")
    clips = json.loads(clips_f.read_text(encoding="utf-8"))
    out = d / "preview"
    out.mkdir(exist_ok=True)
    W, H = frame_size(video)

    for c in clips:
        cid = c["id"]
        start, end = parse_time(c["start"]), parse_time(c["end"])
        crop = c.get("crop")
        if crop is None:
            print(f"    {cid} 화면 분석 중")
            crop = auto_crop(video, start, end, fallback=sermon_window_of(d))
        at = start + (end - start) / 2

        run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
             "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", crop_filter(crop), "-q:v", "3", str(out / f"{cid}.jpg")])

        # The same moment uncropped, with the window drawn on it.
        if isinstance(crop, dict):
            cw = int(crop["h"] * 9 / 16)
            box = (f"drawbox=x={crop['x']}:y={crop.get('y', 0)}:w={cw}:"
                   f"h={crop['h']}:color=yellow@1:t=4")
        else:
            box = "null"
        run([*ffmpeg_cmd(), "-y", "-hide_banner", "-loglevel", "error",
             "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", box, "-q:v", "3", str(out / f"{cid}-전체화면.jpg")])
        print(f"    {cid}  {hhmmss(at)}  crop={crop}")

    print(f"\n==> {rel(out)} 에 미리보기 {len(clips) * 2}장")
    print("    <클립>.jpg          실제로 나올 세로 화면")
    print("    <클립>-전체화면.jpg  원본 전체 + 노란 네모가 잘라낼 구간")
    print("\n설교자가 가운데 있으면 그대로 렌더한다:")
    print(f"    bash scripts/shorts render {args.idea_id}")
    print("어긋났으면 clips.json 의 crop 을 고치고 다시 이 명령으로 확인한다.")
    if not args.no_open:
        open_in_file_manager(out)


def cmd_config(args):
    """Point this at another church without editing any code."""
    f = REPO / "church.json"
    cfg = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    changed = False
    for key, val in (("channel", args.channel), ("preacher", args.preacher),
                     ("church", args.church)):
        if val:
            cfg[key] = val.rstrip("/") if key == "channel" else val
            changed = True

    if changed:
        if "youtube.com/" not in cfg.get("channel", "youtube.com/"):
            die(f"채널 주소가 아니다: {cfg.get('channel')}\n"
                "  예: https://www.youtube.com/@yeshim1126")
        f.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
        # A stale listing belongs to the old channel.
        for old in CACHE_DIR.glob("*.tsv"):
            old.unlink()
        print(f"==> {rel(f)} 에 저장했다\n")

    print("지금 설정")
    print(f"  채널   {cfg.get('channel', CHANNEL)}")
    print(f"  설교자  {cfg.get('preacher', SERMON_PREACHER)}")
    print(f"  교회명  {cfg.get('church', CHURCH_NAME)}")
    if not changed:
        print("\n바꾸려면:")
        print("  bash scripts/shorts config --channel https://www.youtube.com/@내채널 \\")
        print("                            --preacher 홍길동 --church 서울○○교회")
    else:
        print("\n확인:  bash scripts/shorts sermons")


def cmd_doctor(_args):
    print(f"=== Tier 0 toolchain ({'Windows' if _windows() else sys.platform}) ===")
    try:
        ff = ffmpeg_cmd()[0]
    except SystemExit:
        ff = None
    print(f"  {'OK  ' if ff else 'MISS'}  {'ffmpeg':<12} {ff or '— not installed'}")

    ydl = ytdlp_cmd()
    print(f"  {'OK  ' if ydl else 'MISS'}  {'yt-dlp':<12} "
          f"{' '.join(ydl) if ydl else '— not installed'}")

    dn = _exe("deno")
    print(f"  {'OK  ' if dn else 'MISS'}  {'deno':<12} "
          f"{dn or '— yt-dlp가 유튜브 JS 챌린지를 못 풀어 다운로드가 실패할 수 있다 (brew install deno)'}")

    wh = whisper_cmd()
    print(f"  {'OK  ' if wh else 'MISS'}  {'whisper':<12} {wh or '— not installed'}")

    if ff:
        burn = has_subtitles_filter(ff)
        print(f"  {'OK  ' if burn else 'MISS'}  {'subtitles':<12} "
              f"{'자막을 입힐 수 있다 (libass)' if burn else 'libass 없이 빌드된 ffmpeg — 렌더가 안 된다'}")

    cl = _exe("claude")
    print(f"  {'OK  ' if cl else 'n/a '}  {'claude':<12} "
          f"{cl or '— 없으면 Gemini로 넘어간다'}")

    fonts = list(Path(FONT_DIR).glob("NotoSansKR-*.ttf")) if Path(FONT_DIR).exists() else []
    print(f"\n  채널   {CHANNEL}")
    print(f"  설교자  {SERMON_PREACHER}")
    print(f"  교회명  {CHURCH_NAME}\n")

    print(f"  {'OK  ' if fonts else 'MISS'}  {'korean font':<12} "
          f"{len(fonts)} file(s) in {FONT_DIR}")

    model = os.environ.get("WHISPER_MODEL", "models/ggml-large-v3.bin")
    print(f"  {'OK  ' if Path(model).exists() else 'MISS'}  {'whisper model':<12} {model}")

    has_whisper = bool(whisper_cmd()) and Path(model).exists()
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    # Gemini is only the fallback. With whisper present its absence is not a
    # problem, and reporting it as MISS reads like a broken setup.
    if has_gemini:
        print(f"  OK    {'GEMINI_API_KEY':<12} (fallback / cloud transcription)")
    elif has_whisper:
        print(f"  n/a   {'GEMINI_API_KEY':<12} not needed — whisper handles transcription")
    else:
        print(f"  MISS  {'GEMINI_API_KEY':<12} needed: no whisper, so nothing can transcribe")

    print()
    if has_whisper:
        print("전사: whisper large-v3 (무료·오프라인). 준비 완료.")
    elif has_gemini:
        print("전사: Gemini (유료). whisper를 깔면 무료로 바뀐다 —")
        print("      bash scripts/setup_render_env.sh --with-whisper")
    else:
        print("전사 수단이 없다 → bash scripts/setup_render_env.sh --with-whisper")
    if not (ff and ydl and dn and fonts):
        print("렌더 도구가 빠졌다 → bash scripts/setup_render_env.sh")
    if ff and not has_subtitles_filter(ff):
        print()
        print(NO_LIBASS)


# ---------------------------------------------------------------- sermons ---
# The Sunday services live in the streams tab, not the videos tab — the videos
# tab is Wednesday services by other pastors, daily 새벽기도 and the children's
# ministry. See .claude/context/youtube-channel.md.
CHANNEL = os.environ.get("SERMON_CHANNEL", "https://www.youtube.com/@yeshim1126")
CHANNEL_STREAMS = CHANNEL.rstrip("/") + "/streams"
CHANNEL_VIDEOS = CHANNEL.rstrip("/") + "/videos"
SERMON_PREACHER = os.environ.get("SERMON_PREACHER", "")  # 양재 드림의 교회: 제목에 설교자 이름이 없어 기본값을 비워 전체를 대상으로 한다
CHURCH_NAME = os.environ.get("CHURCH_NAME", "방배동 예심교회")


def load_church_config() -> None:
    """Let another church point this at itself without editing any code.

    church.json in the repo root, or the same three environment variables.
    An explicit environment variable wins, so a one-off run can override the
    file without changing it.
    """
    global CHANNEL, CHANNEL_STREAMS, CHANNEL_VIDEOS, SERMON_PREACHER, CHURCH_NAME
    f = REPO / "church.json"
    if f.exists():
        try:
            cfg = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            die(f"church.json 을 못 읽었다: {e}")
        if not os.environ.get("SERMON_CHANNEL") and cfg.get("channel"):
            CHANNEL = cfg["channel"].rstrip("/")
            CHANNEL_STREAMS = CHANNEL + "/streams"
            CHANNEL_VIDEOS = CHANNEL + "/videos"
        if not os.environ.get("SERMON_PREACHER") and cfg.get("preacher"):
            SERMON_PREACHER = cfg["preacher"]
        if not os.environ.get("CHURCH_NAME") and cfg.get("church"):
            CHURCH_NAME = cfg["church"]


def channel_handle() -> str:
    m = re.search(r"(@[\w.-]+)", CHANNEL)
    return f"youtube.com/{m.group(1)}" if m else CHANNEL.replace("https://", "")

# Everything this preacher has up, across both tabs:
#
#   streams tab — the Sunday service, 60-85 min, the sermon a part of it.
#   videos tab  — 새벽기도 most days (~35 min, and usually a still image with
#                 audio over it rather than a camera feed), plus his 수요예배.
#
# The videos tab also holds Wednesday services by other pastors and the
# children's ministry — minors, never to be cut — and requiring his name in the
# title excludes all of it. What the tab does NOT do is label the kind
# consistently: 새벽기도 is in some titles and not others, so the kind is
# settled by weekday and length below, and the guess is printed rather than
# hidden. It only picks the words on the end card; nothing downstream depends
# on it, and end-card.json can be corrected by hand.
KIND_LABEL = {"sunday": "주일예배", "wed": "수요예배", "dawn": "새벽기도"}
KIND_PREFIX = {"sunday": "SUN", "wed": "WED", "dawn": "DAWN"}

CACHE_DIR = REPO / "office" / ".cache"
CACHE_TTL = 12 * 3600      # the channel gains a video a day; twice daily is plenty

# Titles date themselves inconsistently: 2026-08-30, 2025-9-28, 2025.8.31.
TITLE_DATE = re.compile(r"(20\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")
TITLE_SCRIPTURE = re.compile(r"\[([^\]]+)\]")


def fetch_tab(url: str) -> str:
    """yt-dlp's flat listing of one channel tab, cached for half a day.

    The videos tab is over a thousand entries and takes minutes to walk, and
    the channel gains one a day — re-reading it every command is pure waiting.
    """
    import time as _t
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / (re.sub(r"[^a-z]+", "-", url.lower()).strip("-") + ".tsv")
    if cache.exists() and _t.time() - cache.stat().st_mtime < CACHE_TTL:
        return cache.read_text(encoding="utf-8")

    ydl = ytdlp_cmd()
    if not ydl:
        die("yt-dlp not installed — run: bash scripts/setup_render_env.sh")
    print(f"    채널 목록 읽는 중 — {url.rsplit('/', 1)[-1]} 탭 (처음엔 몇 분 걸린다)",
          file=sys.stderr)
    p = subprocess.run(
        [*ydl, "--flat-playlist", "--print", "%(id)s\t%(title)s\t%(duration)s", url],
        capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        if cache.exists():          # stale beats nothing when the network is down
            print("    새로 못 읽어 지난 목록을 쓴다", file=sys.stderr)
            return cache.read_text(encoding="utf-8")
        die("could not list the channel.\n"
            f"  {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else 'no output'}\n"
            "  If this mentions 403 or a tunnel, YouTube is blocked by this\n"
            "  environment's egress policy — see docs/environment-constraints.md.")
    cache.write_text(p.stdout, encoding="utf-8")
    return p.stdout


def classify(title: str, day, duration: int, from_streams: bool) -> str:
    """Which service this is. A guess, and only the end card's wording rides
    on it."""
    if from_streams:
        return "sunday"
    if "새벽기도" in title:
        return "dawn"
    if duration >= 3600 or day.weekday() == 6:      # too long for a weekday service
        return "sunday"
    if day.weekday() == 2 and duration >= 2400:     # Wednesday, and longer than his dawn hour
        return "wed"
    return "dawn"


def list_sermons(preacher: str = SERMON_PREACHER,
                 kind: str = "all") -> list[dict]:
    """Everything this preacher has up, newest first. Metadata only — yt-dlp's
    flat listing costs nothing and downloads nothing."""
    import datetime as _dt

    lines = [(l, True) for l in fetch_tab(CHANNEL_STREAMS).splitlines()]
    if kind != "sunday":
        lines += [(l, False) for l in fetch_tab(CHANNEL_VIDEOS).splitlines()]

    out = []
    for line, from_streams in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        vid, title = parts[0], parts[1]
        dur = int(float(parts[2])) if len(parts) > 2 and parts[2] not in ("NA", "") else 0
        m = TITLE_DATE.search(title)
        if not m:                       # concerts, specials — no service date
            continue
        if preacher and preacher not in title:
            continue
        y, mo, dd = (int(x) for x in m.groups())
        try:
            d = _dt.date(y, mo, dd)
        except ValueError:
            continue

        k = classify(title, d, dur, from_streams)
        if kind not in ("all", k):
            continue
        # A Sunday service not dated a Sunday is a typo — the channel has done
        # it (2026-07-14 was a Tuesday; the service was the 12th) — so trust the
        # weekday and say so. Daily services keep their own date.
        held = (d - _dt.timedelta(days=(d.weekday() + 1) % 7)
                if k == "sunday" else d)
        sm = TITLE_SCRIPTURE.search(title)
        out.append({
            "id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": title,
            "kind": k,
            "kind_label": KIND_LABEL[k],
            "title_date": d.isoformat(),
            "date": held.isoformat(),
            "date_suspect": held != d,
            "idea_id": f"{KIND_PREFIX[k]}-{held.isoformat()}",
            "duration": dur,
            "scripture": sm.group(1).strip() if sm else "",
        })
    out.sort(key=lambda x: x["date"], reverse=True)
    # One id can appear in both tabs; keep the first (streams wins).
    seen, uniq = set(), []
    for x in out:
        if x["id"] not in seen:
            seen.add(x["id"]); uniq.append(x)
    return uniq


# The record of what has been made must outlive the folders. A finished
# production is 300 MB of source video, and the obvious way to reclaim that is
# to delete the folder — which, when the folder *was* the record, quietly made
# that sermon eligible to be picked again.
LEDGER = REPO / "office" / "produced.json"


def scan_folders_for_ids() -> dict[str, dict]:
    """Video ids mentioned by any production folder, with what is known of them."""
    found: dict[str, dict] = {}
    if not PROD.exists():
        return found
    for d in sorted(PROD.iterdir()):
        if not d.is_dir():
            continue
        for f in list(d.glob("*.json")) + list(d.glob("*.md")):
            if f.stat().st_size > 2_000_000:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for vid in re.findall(r"(?:watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})", text):
                found.setdefault(vid, {"video_id": vid, "idea_id": d.name})
    return found


def load_ledger() -> dict[str, dict]:
    if not LEDGER.exists():
        return {}
    try:
        return {e["video_id"]: e for e in json.loads(LEDGER.read_text(encoding="utf-8"))
                if e.get("video_id")}
    except (json.JSONDecodeError, TypeError, KeyError):
        print(f"    {rel(LEDGER)} 를 못 읽었다 — 폴더만 보고 판단한다")
        return {}


def record_produced(video_id: str, idea_id: str, title: str = "") -> None:
    """Write one entry into the ledger. Idempotent."""
    led = load_ledger()
    if video_id in led and led[video_id].get("title"):
        return
    import datetime as _dt
    led[video_id] = {"video_id": video_id, "idea_id": idea_id, "title": title,
                     "recorded": _dt.date.today().isoformat()}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(
        json.dumps(sorted(led.values(), key=lambda e: e["idea_id"]),
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def already_produced() -> set[str]:
    """Every video already made, whether or not its folder still exists.

    Folders are still scanned, so a checkout that predates the ledger keeps
    working, and anything found there is folded into the ledger on the way
    past — deleting the folder afterwards is then safe.
    """
    from_folders = scan_folders_for_ids()
    led = load_ledger()
    for vid, info in from_folders.items():
        if vid not in led:
            record_produced(vid, info["idea_id"])
    return set(led) | set(from_folders)


VIDEO_ID = re.compile(r"(?:watch\?v=|youtu\.be/|shorts/|live/)([A-Za-z0-9_-]{11})"
                      r"|^([A-Za-z0-9_-]{11})$")


def cmd_sermons(args):
    import random

    items = list_sermons(args.preacher, args.kind)
    if not items:
        die("아무것도 못 찾았다 — --preacher / --kind / SERMON_CHANNEL 을 보라")

    # `--find` exists so a hand-pasted URL still gets its folder named after the
    # service date. Naming it after today is how SUN-2026-09-01 (a Tuesday)
    # happened.
    if args.find:
        m = VIDEO_ID.search(args.find.strip())
        if not m:
            die(f"not a YouTube URL or video id: {args.find}")
        vid = m.group(1) or m.group(2)
        hit = next((s for s in items if s["id"] == vid), None)
        if hit is None:
            # Not a Sunday service on this channel — a Wednesday service, a
            # 새벽기도, another channel entirely. The caller decides.
            print(f"# {vid} 는 이 채널의 장선기 목사 주일예배 목록에 없다",
                  file=sys.stderr)
            sys.exit(3)
        print(json.dumps(hit, ensure_ascii=False) if args.json else hit["url"])
        if not args.json:
            print(hit["idea_id"])
            print(f"# {hit['title']}", file=sys.stderr)
            if hit["date_suspect"]:
                print(f"# ⚠ 제목의 날짜 {hit['title_date']} 는 일요일이 아니다 → "
                      f"{hit['date']} 로 잡았다", file=sys.stderr)
        return

    done = already_produced()
    fresh = [s for s in items if s["id"] not in done]
    pool = items if args.include_done else fresh

    if args.pick:
        if not pool:
            die("목록의 모든 편을 이미 만들었다 — 반복하려면 --include-done")
        rng = random.Random(args.seed)
        # Pick the kind first, then within it. He records 새벽기도 most days and
        # 주일예배 once a week, so drawing straight from the pool would return a
        # dawn prayer four times out of five.
        by_kind = {}
        for x in pool:
            by_kind.setdefault(x["kind"], []).append(x)
        s = rng.choice(by_kind[rng.choice(sorted(by_kind))])
        if args.json:
            print(json.dumps(s, ensure_ascii=False))
        else:
            print(s["url"])
            print(s["idea_id"])
        if not args.json:
            print(f"# [{s['kind_label']}] {s['title']}", file=sys.stderr)
            print(f"# {s['duration'] // 60}분"
                  + (f" · 본문 {s['scripture']}" if s["scripture"] else ""), file=sys.stderr)
            if s["date_suspect"]:
                print(f"# ⚠ 제목의 날짜 {s['title_date']} 는 일요일이 아니다 → "
                      f"{s['date']} 로 잡았다", file=sys.stderr)
        return

    if args.json:
        print(json.dumps(pool[:args.limit], ensure_ascii=False, indent=2))
        return

    counts = {}
    for x in items:
        counts[x["kind_label"]] = counts.get(x["kind_label"], 0) + 1
    print(f"{CHANNEL}  ·  {args.preacher} "
          + " · ".join(f"{k} {v}편" for k, v in sorted(counts.items()))
          + f"  (미제작 {len(fresh)}편)\n")
    for s in pool[:args.limit]:
        mark = "  " if s["id"] not in done else "✓ "
        flag = " ⚠날짜" if s["date_suspect"] else ""
        print(f"{mark}{s['date']}  {s['kind_label']}  {s['duration'] // 60:>2}분  "
              f"{s['id']}{flag}  {s['title'][:52]}")
    if not args.include_done:
        print(f"\n제작된 {len(items) - len(fresh)}편은 숨겼다 (--include-done 로 표시).")
    print("\n무작위로 하나 뽑아 그대로 돌리려면:  bash scripts/weekly_run.sh --auto")


# ------------------------------------------------------------------ main ---
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sm = sub.add_parser("sermons", help="list the channel's Sunday services, or pick one")
    sm.add_argument("--pick", action="store_true",
                    help="choose one at random and print its URL and idea-id")
    sm.add_argument("--seed", type=int, default=None, help="make --pick reproducible")
    sm.add_argument("--limit", type=int, default=20)
    sm.add_argument("--kind", choices=["all", "sunday", "wed", "dawn"], default="all",
                    help="어떤 예배를 대상으로 할지 (기본: 전부)")
    sm.add_argument("--preacher", default=SERMON_PREACHER,
                    help="title must contain this name; '' for no filter")
    sm.add_argument("--include-done", action="store_true",
                    help="do not hide services already produced")
    sm.add_argument("--find", metavar="URL",
                    help="look one URL up in the listing and print its idea-id")
    sm.add_argument("--json", action="store_true")
    sm.set_defaults(func=cmd_sermons)

    f = sub.add_parser("fetch"); f.add_argument("idea_id"); f.add_argument("--url", required=True)
    f.add_argument("--via", choices=["yt-dlp", "apify"], default="yt-dlp",
                   help="apify downloads on Apify's machines (paid); use only where "
                        "yt-dlp cannot reach YouTube's media servers")
    f.add_argument("--quality", default="480",
                   help="apify only: 360/480/720/1080. Billed per second of footage, "
                        "so this is the cost dial. Note 480 actually returns 640x360.")
    f.set_defaults(func=cmd_fetch)

    t = sub.add_parser("transcribe"); t.add_argument("idea_id")
    t.add_argument("--backend", choices=["auto", "whisper", "gemini"], default="auto")
    t.add_argument("--whole", action="store_true",
                   help="transcribe the whole recording, not just the sermon")
    t.add_argument("--no-structure", action="store_true",
                   help="skip service-structure detection (saves one paid call)")
    t.add_argument("--no-repair", action="store_true",
                   help="skip the duplicate/hole repair pass")
    t.add_argument("--sermon-window", nargs=2, metavar=("START", "END"),
                   help="give the sermon's start and end yourself, e.g. 0:45:00 1:20:00")
    t.add_argument("--select-backend", choices=["auto", "claude", "gemini"],
                   default="auto",
                   help="which model reads the transcript to find the sermon")
    t.set_defaults(func=cmd_transcribe)

    c = sub.add_parser("clips"); c.add_argument("idea_id")
    c.add_argument("--window", type=float, default=12.0, help="seconds per printed block")
    c.set_defaults(func=cmd_clips)

    r = sub.add_parser("render"); r.add_argument("idea_id")
    r.add_argument("--only", help="render just this clip id")
    r.add_argument("--no-end-card", action="store_true",
                   help="skip the closing service card")
    r.add_argument("--no-open", action="store_true",
                   help="끝나고 결과 폴더 창을 열지 않는다")
    r.add_argument("--retime", action="store_true",
                   help="re-transcribe each clip window for exact caption sync "
                        "(one paid Gemini call per clip)")
    r.set_defaults(func=cmd_render)

    sel = sub.add_parser("select", help="pick the clips automatically instead of stopping")
    sel.add_argument("idea_id")
    sel.add_argument("--count", type=int, default=3)
    sel.add_argument("--backend", choices=["auto", "claude", "gemini"], default="auto")
    sel.set_defaults(func=cmd_select)

    rp = sub.add_parser("repair", help="drop seam duplicates and clamp impossible cue lengths")
    rp.add_argument("idea_id")
    rp.add_argument("--fill-holes", action="store_true",
                    help="also re-transcribe gaps (usually timestamp drift, not real gaps)")
    rp.set_defaults(func=cmd_repair)

    cap = sub.add_parser("captions",
                         help="쇼츠 자막을 고칠 수 있는 파일로 꺼낸다")
    cap.add_argument("idea_id")
    cap.add_argument("--force", action="store_true",
                     help="이미 고쳐 둔 파일을 원본으로 되돌린다")
    cap.add_argument("--no-open", action="store_true",
                     help="폴더 창을 자동으로 열지 않는다")
    cap.add_argument("--show", action="store_true",
                     help="지금 파일에 뭐라고 적혀 있는지 그대로 보여준다")
    cap.set_defaults(func=cmd_captions)

    fx = sub.add_parser("fix", help="잘못 들린 말을 전사본과 자막에서 한 번에 바꾼다")
    fx.add_argument("idea_id")
    fx.add_argument("wrong")
    fx.add_argument("right")
    fx.add_argument("--remember", action="store_true",
                    help="앞으로 전사할 때마다 자동으로 고치도록 기억한다")
    fx.set_defaults(func=cmd_fix)

    v = sub.add_parser("validate"); v.add_argument("idea_id")
    v.set_defaults(func=cmd_validate)

    op = sub.add_parser("open", help="그 편의 폴더를 파인더/탐색기로 연다")
    op.add_argument("idea_id")
    op.add_argument("what", nargs="?", default=".",
                    choices=[".", "captions", "renders", "source"],
                    help="열 폴더 (기본: 편 폴더 전체)")
    op.set_defaults(func=cmd_open)

    pv = sub.add_parser("preview", help="렌더 전에 크롭이 맞는지 사진으로 확인한다")
    pv.add_argument("idea_id")
    pv.add_argument("--no-open", action="store_true")
    pv.set_defaults(func=cmd_preview)

    cf = sub.add_parser("config", help="채널·설교자·교회명을 정한다 (다른 교회용)")
    cf.add_argument("--channel", help="유튜브 채널 주소 (@핸들 주소)")
    cf.add_argument("--preacher", help="제목에서 찾을 설교자 이름")
    cf.add_argument("--church", help="엔드카드에 넣을 교회명")
    cf.set_defaults(func=cmd_config)

    sub.add_parser("doctor").set_defaults(func=cmd_doctor)

    load_church_config()
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        # A failed ffmpeg or yt-dlp is an ordinary outcome here, not a bug in
        # this script. A Python traceback buries the one line that says what
        # actually broke, which is the line the user is going to send us.
        tool = Path(str(exc.cmd[0])).name if exc.cmd else "외부 프로그램"
        print(f"\nerror: {tool} 이(가) 실패했다 (코드 {exc.returncode}).",
              file=sys.stderr)
        print("  바로 위에 나온 빨간 줄이 이유다. 그 줄을 그대로 복사해서 물어보면 된다.",
              file=sys.stderr)
        sys.exit(exc.returncode or 1)
    except KeyboardInterrupt:
        print("\n중단했다.", file=sys.stderr)
        sys.exit(130)
