#!/usr/bin/env bash
# 쇼츠 3편 만들기 — 영상까지 알아서 고른다.
#
#   bash scripts/shorts-auto.sh
#
# 채널의 주일예배 중 아직 안 만든 편을 무작위로 하나 뽑아, 다운로드부터
# 렌더까지 사람 개입 없이 간다. 짝은 scripts/shorts-url.sh (URL을 직접 준다).
#
# 업로드는 하지 않는다. 렌더가 마지막이다.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$#" -gt 0 ]; then
  echo "shorts-auto.sh 는 인자를 받지 않는다. 받은 것: $*" >&2
  echo >&2
  echo "  붙여넣은 줄에 주석(# ...)이 딸려 오지 않았는지 보라 — zsh는" >&2
  echo "  bash와 달리 #를 주석으로 취급하지 않아 그대로 인자가 된다." >&2
  echo >&2
  echo "  영상을 직접 지정하려면 이쪽이다:" >&2
  echo "    bash scripts/shorts-url.sh <유튜브주소>" >&2
  exit 1
fi

exec bash scripts/weekly_run.sh --auto
