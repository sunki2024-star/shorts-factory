#!/usr/bin/env bash
# Install the Tier 0 render toolchain: ffmpeg, yt-dlp, a Korean font, and
# optionally whisper.cpp. Idempotent — safe to re-run.
#
#   bash scripts/setup_render_env.sh                 render tools only
#   bash scripts/setup_render_env.sh --with-whisper  also build whisper.cpp
#
# Works on macOS and Linux. On macOS it uses Homebrew, which is both simpler
# and better than the workarounds below it: those exist only because this
# project's cloud container has a broken apt and a blocked CDN.
#
# whisper.cpp needs huggingface.co for the model, which the cloud container
# blocks — there, transcription falls back to Gemini. On your own machine
# whisper is free, unlimited, and its timings do not drift.
# See docs/porting-to-your-claude.md.
set -euo pipefail

say()  { printf '\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33m    %s\033[0m\n' "$*"; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Fonts live in the repo, not the system. libass is pointed at this directory
# explicitly, so the render looks identical on every machine and nothing has
# to be installed with admin rights.
FONT_DIR=${FONT_DIR:-$REPO_ROOT/assets/fonts}
WITH_WHISPER=0
[ "${1:-}" = "--with-whisper" ] && WITH_WHISPER=1

case "$(uname -s)" in
  Darwin)                 OS=mac ;;
  MINGW*|MSYS*|CYGWIN*)   OS=windows ;;   # Git Bash / MSYS2
  *)                      OS=linux ;;
esac
say "platform: $OS"

# pip on a system Python is often marked externally managed (PEP 668), which
# is a refusal rather than a failure — retry into the user site instead.
pip_install() {
  python3 -m pip install --quiet "$@" 2>/dev/null \
    || python3 -m pip install --quiet --user "$@" 2>/dev/null \
    || python3 -m pip install --quiet --break-system-packages "$@"
}

# ---------------------------------------------------------------- ffmpeg ----
say "ffmpeg"
if ! command -v ffmpeg >/dev/null 2>&1; then
  if [ "$OS" = windows ]; then
    # No symlink target and no package manager to rely on. The wheel carries a
    # static ffmpeg.exe, and sermon_shorts.py resolves it through Python, so
    # nothing has to land on PATH.
    pip_install imageio-ffmpeg
    python -c "import imageio_ffmpeg,sys; print(imageio_ffmpeg.get_ffmpeg_exe())" \
      || { echo "imageio-ffmpeg install failed"; exit 1; }
  elif [ "$OS" = mac ]; then
    command -v brew >/dev/null 2>&1 || {
      echo "Homebrew is required. Install it first:"
      echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
      exit 1; }
    brew install ffmpeg
  else
    # apt is unusable in the cloud container and the static-build host is
    # blocked there, but PyPI is not: the imageio-ffmpeg wheel carries the
    # same static build.
    pip_install imageio-ffmpeg
    FF=$(python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")
    ln -sf "$FF" /usr/local/bin/ffmpeg
  fi
fi
if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -hide_banner -version | head -1
else
  python -c "import imageio_ffmpeg as f,subprocess; subprocess.run([f.get_ffmpeg_exe(),'-version'])" 2>/dev/null | head -1
fi

# An ffmpeg built without libass has no `subtitles` filter, and every render
# here burns subtitles. It looks entirely healthy until the first clip dies, so
# check it now — an already-installed ffmpeg skips the branch above and would
# otherwise never be examined.
has_subs() { "$1" -hide_banner -filters 2>/dev/null | grep -qE '^ *[A-Z.]+ +subtitles '; }
FFBIN=$(command -v ffmpeg 2>/dev/null || true)
if [ -n "$FFBIN" ] && ! has_subs "$FFBIN"; then
  echo "  이 ffmpeg 는 libass 없이 빌드돼 자막을 못 입힌다 — 고치는 중"
  if [ "$OS" = mac ]; then
    # Homebrew's plain ffmpeg formula ships without libass; ffmpeg-full is the
    # one that carries it. Both install the same binary name, so the link may
    # have to be forced over the one already there.
    brew install ffmpeg-full || true
    has_subs "$(command -v ffmpeg 2>/dev/null || echo /nonexistent)" \
      || brew link --overwrite ffmpeg-full || true
  else
    pip_install imageio-ffmpeg
    FF=$(python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null || true)
    [ -n "$FF" ] && has_subs "$FF" && ln -sf "$FF" /usr/local/bin/ffmpeg
  fi
  FFBIN=$(command -v ffmpeg 2>/dev/null || true)
fi
if [ -n "$FFBIN" ] && has_subs "$FFBIN"; then
  echo "  자막 번인 OK (subtitles 필터 있음)"
elif [ -n "$FFBIN" ]; then
  echo "  ✗ 아직도 subtitles 필터가 없다. 이대로는 렌더가 안 된다."
  echo "    맥이면:  brew reinstall ffmpeg"
  echo "    확인:    ffmpeg -filters | grep subtitles"
fi

# ---------------------------------------------------------------- yt-dlp ----
say "yt-dlp"
if ! command -v yt-dlp >/dev/null 2>&1; then
  if [ "$OS" = mac ]; then brew install yt-dlp; else pip_install yt-dlp; fi
fi
# On Windows pip puts yt-dlp.exe in a Scripts folder that is often not on PATH;
# `python -m yt_dlp` always works, and that is the fallback the pipeline uses.
yt-dlp --version 2>/dev/null || python -m yt_dlp --version

# --------------------------------------------------------------- deno ------
# yt-dlp now has to run a bit of YouTube's own JavaScript to get past its "n"
# challenge before it can hand back a real download link. deno is the JS
# runtime yt-dlp looks for by default; without one, extraction is deprecated
# and yt-dlp warns that some formats may be missing or the download may fail
# outright. See https://github.com/yt-dlp/yt-dlp/wiki/EJS.
say "deno (yt-dlp's JS runtime for YouTube)"
if ! command -v deno >/dev/null 2>&1; then
  if [ "$OS" = mac ]; then
    brew install deno
  elif [ "$OS" = windows ]; then
    powershell -NoProfile -Command "irm https://deno.land/install.ps1 | iex" \
      || warn "deno 설치 실패 — https://docs.deno.com/runtime/getting_started/installation/ 참고"
  else
    curl -fsSL https://deno.land/install.sh | sh -s -- -y \
      || warn "deno 설치 실패 — https://docs.deno.com/runtime/getting_started/installation/ 참고"
    export PATH="$HOME/.deno/bin:$PATH"
  fi
fi
if command -v deno >/dev/null 2>&1; then
  deno --version | head -1
else
  warn "deno 못 찾음 — yt-dlp가 유튜브 다운로드 중 일부 화질을 못 받거나 실패할 수 있다"
fi

# ------------------------------------------------------------ Korean font ----
# Without a CJK face libass burns Korean as tofu. Google Fonts is blocked in
# the cloud container but the npm registry is not, and @fontsource ships the
# Korean subset as woff2, which fontTools converts back to TTF.
say "Korean font (Noto Sans KR) → $FONT_DIR"
# The repo ships these, so this whole block is a fallback for a checkout that
# somehow lacks them. Nothing normally needs npm.
if [ ! -f "$FONT_DIR/NotoSansKR-Regular.ttf" ]; then
  command -v npm >/dev/null 2>&1 || {
    echo "npm is required to fetch the font."
    [ "$OS" = mac ] && echo "  brew install node" || echo "  install Node.js first"
    exit 1; }
  pip_install fonttools brotli
  mkdir -p "$FONT_DIR"
  work=$(mktemp -d)
  ( cd "$work"
    npm pack @fontsource/noto-sans-kr@5 >/dev/null 2>&1
    tar xzf fontsource-noto-sans-kr-*.tgz )
  python3 - "$work" "$FONT_DIR" <<'PY'
import sys
from fontTools.ttLib import TTFont
work, out = sys.argv[1], sys.argv[2]
for weight, name in (("400", "Regular"), ("700", "Bold")):
    f = TTFont(f"{work}/package/files/noto-sans-kr-korean-{weight}-normal.woff2")
    f.flavor = None
    f.save(f"{out}/NotoSansKR-{name}.ttf")
    print(f"  wrote {out}/NotoSansKR-{name}.ttf")
PY
  rm -rf "$work"
fi
ls -1 "$FONT_DIR"/NotoSansKR-*.ttf

# ---------------------------------------------------------- whisper.cpp ----
if [ "$WITH_WHISPER" = 1 ] && [ "$OS" = windows ]; then
  say "whisper.cpp + large-v3 (Windows prebuilt)"
  # Building whisper.cpp on Windows needs Visual Studio. The project publishes
  # a ready-made x64 binary, which is the same thing without the toolchain.
  WHISPER_DIR=${WHISPER_DIR:-$HOME/whisper}
  mkdir -p "$WHISPER_DIR"
  if [ ! -f "$WHISPER_DIR/whisper-cli.exe" ]; then
    ZIP="$WHISPER_DIR/whisper-bin-x64.zip"
    curl -fL -o "$ZIP" \
      https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-x64.zip \
      || { echo "다운로드 실패 — 브라우저로 받아 $WHISPER_DIR 에 풀어라:"; \
           echo "  https://github.com/ggml-org/whisper.cpp/releases"; exit 1; }
    ( cd "$WHISPER_DIR" && unzip -o -q "$ZIP" && rm -f "$ZIP" )
    # The zip nests its binaries; lift them so the folder itself is the PATH entry.
    find "$WHISPER_DIR" -name "whisper-cli.exe" -not -path "$WHISPER_DIR/whisper-cli.exe" \
      -exec sh -c 'cp "$(dirname "$1")"/*.exe "$(dirname "$1")"/*.dll "$2"/ 2>/dev/null' _ {} "$WHISPER_DIR" \;
  fi
  MODEL="$WHISPER_DIR/ggml-large-v3.bin"
  if [ ! -f "$MODEL" ]; then
    say "large-v3 모델 내려받는 중 (약 3GB, 한 번만)"
    curl -fL -o "$MODEL" \
      https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin
  fi
  echo
  echo "이 두 줄을 ~/.bashrc 에 넣고 Git Bash 를 새로 열어라:"
  echo "  export PATH=\"$WHISPER_DIR:\$PATH\""
  echo "  export WHISPER_MODEL=\"$MODEL\""
elif [ "$WITH_WHISPER" = 1 ]; then
  say "whisper.cpp + large-v3"
  if [ "$OS" = mac ]; then
    command -v cmake >/dev/null 2>&1 || brew install cmake
  else
    command -v cmake >/dev/null 2>&1 || warn "cmake not found — install it and re-run"
  fi
  WHISPER_DIR=${WHISPER_DIR:-$HOME/whisper.cpp}
  [ -d "$WHISPER_DIR" ] || git clone --depth 1 https://github.com/ggml-org/whisper.cpp "$WHISPER_DIR"
  ( cd "$WHISPER_DIR"
    cmake -B build -DCMAKE_BUILD_TYPE=Release >/dev/null
    cmake --build build -j --config Release >/dev/null
    # large-v3, never a *.en model — those are English-only and cannot read Korean.
    [ -f models/ggml-large-v3.bin ] || bash ./models/download-ggml-model.sh large-v3 )
  echo
  echo "Add these two lines to ~/.zshrc, then open a new terminal:"
  echo "  export PATH=\"$WHISPER_DIR/build/bin:\$PATH\""
  echo "  export WHISPER_MODEL=\"$WHISPER_DIR/models/ggml-large-v3.bin\""
fi

say "Done."
echo "Font dir: $FONT_DIR  (FontName=Noto Sans KR)"
[ "$WITH_WHISPER" = 1 ] || echo "Transcription: add --with-whisper for the free offline route."
