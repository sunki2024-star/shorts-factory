#!/usr/bin/env bash
# 완성된 쇼츠 영상을 "아이클라우드 완성본 폴더"로 올린다.
#
#   bash scripts/push-shared.sh SUN-2026-08-09
#
# 렌더링은 항상 각 컴퓨터(교회 맥미니·집 아이맥)에서 그 자리에 하므로,
# 자막 파일은 여기 올리지 않는다 — 다 구워진 영상만 올려서, 어느 맥에서
# 만들었든 아이폰 '파일' 앱이나 다른 맥에서 바로 꺼내 SNS에 올릴 수 있게
# 한다. 기존 scripts/backup-icloud.sh 가 쓰는 "컴퓨터 이름별" 재해복구
# 백업 폴더와는 다른, 컴퓨터 구분 없는 별도의 폴더다.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
ID="${1:?회차 ID가 필요하다 (예: SUN-2026-08-09)}"

ICLOUD="${ICLOUD_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs}"
if [ ! -d "$ICLOUD" ]; then
  echo "iCloud Drive 폴더를 찾지 못했다: $ICLOUD" >&2
  exit 1
fi

SRC="$REPO/office/production/$ID/renders"
[ -d "$SRC" ] || { echo "렌더된 영상이 없다: $ID" >&2; exit 1; }

SHARED="$ICLOUD/쇼츠팩토리-완성본/$ID"
mkdir -p "$SHARED"

rsync -a --delete --exclude '.DS_Store' "$SRC/" "$SHARED/"

date "+%Y-%m-%d %H:%M" > "$SHARED/마지막-업데이트-시각.txt"
echo "완성본 폴더로 올림 → 쇼츠팩토리-완성본/$ID"
