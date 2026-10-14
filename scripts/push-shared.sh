#!/usr/bin/env bash
# 완성된 자막·영상을 "아이클라우드 공유 작업 폴더"로 올린다.
#
#   bash scripts/push-shared.sh SUN-2026-08-09
#
# 여기는 scripts/sync-shared-captions.sh 가 지켜보는 바로 그 자리라서,
# 교회 맥미니든 집 아이맥이든 같은 경로를 본다 — 기존 scripts/backup-icloud.sh
# 가 쓰는 "컴퓨터 이름별" 백업 폴더와는 다른, 별도의 공유 폴더다.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
ID="${1:?회차 ID가 필요하다 (예: SUN-2026-08-09)}"

ICLOUD="${ICLOUD_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs}"
if [ ! -d "$ICLOUD" ]; then
  echo "iCloud Drive 폴더를 찾지 못했다: $ICLOUD" >&2
  exit 1
fi

SRC="$REPO/office/production/$ID"
[ -d "$SRC" ] || { echo "그런 회차가 없다: $ID" >&2; exit 1; }

SHARED="$ICLOUD/쇼츠팩토리-자막작업/$ID"
mkdir -p "$SHARED/captions" "$SHARED/renders"

[ -d "$SRC/captions" ] && rsync -a --exclude '.DS_Store' "$SRC/captions/" "$SHARED/captions/"
[ -d "$SRC/renders" ]  && rsync -a --exclude '.DS_Store' "$SRC/renders/"  "$SHARED/renders/"

rm -f "$SHARED"/.rendering-* 2>/dev/null || true
date "+%Y-%m-%d %H:%M" > "$SHARED/마지막-업데이트-시각.txt"
echo "공유 작업 폴더로 올림 → 쇼츠팩토리-자막작업/$ID"
