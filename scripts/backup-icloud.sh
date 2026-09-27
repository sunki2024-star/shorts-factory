#!/usr/bin/env bash
# office/ 작업물을 iCloud Drive에 "복사본"으로 백업한다.
#
#   bash scripts/backup-icloud.sh                 기본 — 다른 맥에서 이어 하기에 충분 (약 15MB)
#   bash scripts/backup-icloud.sh --with-renders  완성된 쇼츠 영상까지 (약 +0.6GB)
#
# 왜 폴더 통째로 iCloud에 옮기지 않나:
#   iCloud는 파일을 하나씩 따로 동기화해서 .git 이 깨질 수 있고, "Mac 저장
#   공간 최적화"가 켜져 있으면 큰 영상을 맥에서 지워버려 렌더가 실패한다.
#   그래서 작업은 ~/shorts-factory 에서 그대로 하고, iCloud엔 복사본만 둔다.
#
# 무엇을 백업하나 (코드는 이미 GitHub에 있으니 제외):
#   office/            전사본, clips.json, 자막, 엔드카드, 제작 기록
#   Claude outputs/    Claude가 만들어 준 결과물
#   .env, church.json  (있으면) 키·교회 설정
#
# 영상은 빼고 "다시 만들 수 있는 재료"만 남긴다:
#   원본 설교 영상(source)  → 유튜브에서 다시 받으면 된다 (항상 제외)
#   완성 쇼츠(renders)      → 새 맥에서 bash scripts/shorts render <id> 로 다시 굽는다
#   전사본은 포함 — 전부 합쳐도 몇 MB인데, 다시 만들려면 whisper가 한참 걸린다.
#
# 백업은 지우지 않는다: 맥에서 파일을 지워도 iCloud 쪽 복사본은 남는다.
# 컴퓨터마다 따로 폴더를 쓴다 — 교회 맥미니와 집 아이맥이 서로 덮어쓰지 않도록.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

ICLOUD="${ICLOUD_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs}"
if [ ! -d "$ICLOUD" ]; then
  echo "iCloud Drive 폴더를 찾지 못했다: $ICLOUD" >&2
  echo "  시스템 설정 > Apple 계정 > iCloud > iCloud Drive 가 켜져 있는지 확인." >&2
  exit 1
fi

HOSTNAME_LABEL="$(scutil --get ComputerName 2>/dev/null || hostname -s)"
DEST="$ICLOUD/shorts-factory-백업/$HOSTNAME_LABEL"
mkdir -p "$DEST"

EXCL=(--exclude '.DS_Store' --exclude '.cache/' --exclude 'production/_smoketest/')
EXCL+=(--exclude 'production/*/source/')
if [ "${1:-}" != "--with-renders" ]; then
  EXCL+=(--exclude 'production/*/renders/')
fi

echo "iCloud 백업 중 → shorts-factory-백업/$HOSTNAME_LABEL"
rsync -a "${EXCL[@]}" "$REPO/office/" "$DEST/office/"
if [ -d "$REPO/Claude outputs" ]; then
  rsync -a --exclude '.DS_Store' "$REPO/Claude outputs/" "$DEST/Claude outputs/"
fi
for f in .env church.json; do
  [ -f "$REPO/$f" ] && cp -p "$REPO/$f" "$DEST/$f"
done
date "+%Y-%m-%d %H:%M" > "$DEST/마지막-백업-시각.txt"

echo "백업 완료 ($(du -sh "$DEST" | cut -f1))"
