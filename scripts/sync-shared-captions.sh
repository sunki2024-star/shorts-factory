#!/usr/bin/env bash
# 아이클라우드 "쇼츠팩토리-완성본/<이 컴퓨터 이름>" 폴더를 둘러보고, 자막이
# 바뀐 회차를 찾아 이 맥의 작업 폴더로 가져와 다시 굽고, 다시 그 폴더로
# 올린다. LaunchAgent(kr.yeshim.shorts-sync)가 2분마다 이 스크립트를 실행한다.
#
# 컴퓨터마다 자기 이름의 폴더만 보므로, 교회 맥미니와 집 아이맥이 서로의
# 회차를 건드리는 일은 없다. 아이폰이든 다른 맥이든 그 폴더 안의
# clip-01.srt 같은 파일만 고쳐서 저장해 두면, 이 컴퓨터가(그 회차를 만든
# 바로 그 컴퓨터가) 켜져 있을 때 알아서 반영된다. 사람이 칠 명령은 없다.
set -euo pipefail

# 홈브류가 /opt/homebrew(실리콘) 나 /usr/local(인텔)에 있을 수 있는데,
# 로그인 시 자동 실행(LaunchAgent)은 터미널과 달리 이 경로들을 모른다.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

cd "$(dirname "$0")/.."
REPO="$(pwd)"
HOSTNAME_LABEL="$(scutil --get ComputerName 2>/dev/null || hostname -s)"
LOG="$HOME/Library/Logs/shorts-sync.log"
mkdir -p "$(dirname "$LOG")"

ICLOUD="${ICLOUD_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs}"
SHARED="$ICLOUD/쇼츠팩토리-완성본/$HOSTNAME_LABEL"
[ -d "$SHARED" ] || exit 0   # 이 컴퓨터가 아직 아무것도 안 올렸으면 조용히 끝낸다

LOCK="$SHARED/.sync.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  exit 0   # 이미 다른 실행이 돌고 있다 — 조용히 넘어간다
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

for idpath in "$SHARED"/*/; do
  [ -d "$idpath" ] || continue
  id="$(basename "$idpath")"
  local_dir="$REPO/office/production/$id"
  [ -d "$local_dir/captions" ] || continue   # 이 맥이 만든 적 없는 회차는 건드리지 않는다

  changed=0
  for shared_srt in "$idpath"captions/*.srt; do
    [ -e "$shared_srt" ] || continue
    name="$(basename "$shared_srt")"
    local_srt="$local_dir/captions/$name"
    if [ ! -f "$local_srt" ] || ! cmp -s "$shared_srt" "$local_srt"; then
      cp "$shared_srt" "$local_srt"
      changed=1
      echo "[$(date '+%F %T')] [$id] $name 수정 발견 → 반영" >>"$LOG"
    fi
  done

  if [ "$changed" -eq 1 ]; then
    echo "[$(date '+%F %T')] [$id] 다시 굽는 중…" >>"$LOG"
    if bash scripts/shorts render "$id" >>"$LOG" 2>&1; then
      bash scripts/push-shared.sh "$id" >>"$LOG" 2>&1
      echo "[$(date '+%F %T')] [$id] 완료" >>"$LOG"
    else
      echo "[$(date '+%F %T')] [$id] 렌더 실패 — 로그 확인 필요" >>"$LOG"
    fi
  fi
done
