#!/usr/bin/env bash
# Install or repair the vendored OpenMontage render engine.
#
# Idempotent. Safe to re-run. Never touches .claude/skills/ or skills-lock.json —
# OpenMontage is AGPL-3.0 and stays outside this repo's skills tree.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
VENDOR="$ROOT/vendor/OpenMontage"
REPO="https://github.com/calesthio/OpenMontage"

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "OpenMontage → $VENDOR"

if [ -d "$VENDOR/.git" ]; then
  echo "already cloned; fetching latest"
  git -C "$VENDOR" pull --ff-only --depth 1 2>&1 | tail -2 || echo "pull skipped (shallow/detached is fine)"
else
  mkdir -p "$ROOT/vendor"
  GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 "$REPO" "$VENDOR" || {
    echo "ERROR: clone failed. Check network/proxy and retry." >&2; exit 1; }
fi

say "FFmpeg"
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  ffmpeg -version | head -1
else
  echo "installing a static build into /usr/local/bin"
  tmp=$(mktemp -d)
  if curl -fsSL -o "$tmp/ff.tar.xz" \
      https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz; then
    tar xf "$tmp/ff.tar.xz" -C "$tmp"
    d=$(find "$tmp" -maxdepth 1 -type d -name 'ffmpeg-*-static' | head -1)
    install -m755 "$d/ffmpeg" "$d/ffprobe" /usr/local/bin/ && echo "ok"
  else
    echo "static download failed; trying imageio-ffmpeg (ffmpeg only, no ffprobe)"
    pip3 install --quiet imageio-ffmpeg && \
      ln -sf "$(python3 -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')" \
        /usr/local/bin/ffmpeg
  fi
  rm -rf "$tmp"
fi

say "Python dependencies"
pip3 install --quiet -r "$VENDOR/requirements.txt" 2>&1 | tail -3
pip3 install --quiet piper-tts 2>&1 | tail -2 || echo "piper-tts unavailable — narration falls back to a cloud TTS provider"

say "Remotion composer"
if command -v npm >/dev/null; then
  ( cd "$VENDOR/remotion-composer" && npm install --silent 2>&1 | tail -3 ) \
    || echo "npm install failed — HyperFrames (HTML/GSAP) still works"
else
  echo "Node not found — Remotion unavailable, HyperFrames still works"
fi

say "Capability catalogue (what is actually reachable with the keys set)"
( cd "$VENDOR" && python3 -c "
from tools.tool_registry import registry
registry.discover()
cat = registry.capability_catalog()
for cap, tools in sorted(cat.items()):
    names = tools if isinstance(tools, list) else list(tools)
    print(f'{cap:24} {len(names)} tool(s)')
" 2>&1 | tail -30 ) || echo "registry probe failed — run it by hand to see the traceback"

say "Done"
