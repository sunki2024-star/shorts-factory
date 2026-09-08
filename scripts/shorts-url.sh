#!/usr/bin/env bash
# 쇼츠 3편 만들기 — 영상은 내가 지정한다.
#
#   bash scripts/shorts-url.sh "https://www.youtube.com/watch?v=..."
#
# 폴더 이름은 그 예배의 날짜에서 나온다(오늘 날짜가 아니다). 채널의 주일예배
# 목록에서 찾지 못하면 경고하고 오늘 날짜를 쓴다.
# 짝은 scripts/shorts-auto.sh (채널에서 알아서 고른다).
#
# 업로드는 하지 않는다. 렌더가 마지막이다.
set -euo pipefail
cd "$(dirname "$0")/.."

URL=${1:-}

if [ -z "$URL" ]; then
  echo "유튜브 주소가 필요하다." >&2
  echo >&2
  echo "  bash scripts/shorts-url.sh \"https://www.youtube.com/watch?v=...\"" >&2
  echo >&2
  echo "  주소를 따옴표로 감싸라 — 유튜브 주소의 ? 와 & 는 셸이 먼저 해석한다." >&2
  echo >&2
  echo "  어떤 편이 남았는지 보려면:" >&2
  echo "    python3 scripts/sermon_shorts.py sermons" >&2
  echo "  아무거나 알아서 고르게 하려면:" >&2
  echo "    bash scripts/shorts-auto.sh" >&2
  exit 1
fi

exec bash scripts/weekly_run.sh --auto "$URL"
