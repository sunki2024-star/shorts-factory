#!/usr/bin/env bash
# 완성된 자막·영상을 "아이클라우드 완성본 폴더"로 올린다 — 컴퓨터별로 폴더가
# 나뉜다.
#
#   bash scripts/push-shared.sh SUN-2026-08-09
#
# 쇼츠팩토리-완성본/<컴퓨터 이름>/<회차ID>/ 에 올라간다. 교회 맥미니가 만든
# 건 "교회 맥미니" 폴더에, 집 아이맥이 만든 건 그 쪽 폴더에 각각 쌓이므로
# 아이클라우드에서 보기만 해도 어디서 만든 건지 바로 안다. 아이폰 '파일'
# 앱이나 다른 맥에서 그 안의 자막(.srt)을 고쳐 저장해두면
# scripts/sync-shared-captions.sh 가 "자기 컴퓨터 폴더"만 지켜보다가 자동으로
# 반영한다. 기존 scripts/backup-icloud.sh 가 쓰는 재해복구 백업 폴더와는
# 다른, 별도의 폴더다.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
ID="${1:?회차 ID가 필요하다 (예: SUN-2026-08-09)}"
HOSTNAME_LABEL="$(scutil --get ComputerName 2>/dev/null || hostname -s)"

ICLOUD="${ICLOUD_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs}"
if [ ! -d "$ICLOUD" ]; then
  echo "iCloud Drive 폴더를 찾지 못했다: $ICLOUD" >&2
  exit 1
fi

SRC="$REPO/office/production/$ID"
[ -d "$SRC" ] || { echo "그런 회차가 없다: $ID" >&2; exit 1; }

SHARED="$ICLOUD/쇼츠팩토리-완성본/$HOSTNAME_LABEL/$ID"
mkdir -p "$SHARED/captions"

[ -d "$SRC/renders" ]  && rsync -a --delete --exclude '.DS_Store' "$SRC/renders/" "$SHARED/"
[ -d "$SRC/captions" ] && rsync -a --exclude '.DS_Store' "$SRC/captions/" "$SHARED/captions/"

rm -f "$SHARED"/.rendering-* 2>/dev/null || true
date "+%Y-%m-%d %H:%M" > "$SHARED/마지막-업데이트-시각.txt"
echo "완성본 폴더로 올림 → 쇼츠팩토리-완성본/$HOSTNAME_LABEL/$ID"
