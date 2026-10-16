#!/usr/bin/env bash
# 완성된 자막·영상을 "아이클라우드 완성본 폴더"로 올린다.
#
#   bash scripts/push-shared.sh SUN-2026-08-09
#
# 교회 맥미니든 집 아이맥이든 같은 폴더(쇼츠팩토리-완성본)를 보므로, 아이폰
# '파일' 앱이나 다른 맥에서 그 안의 자막(.srt)을 고쳐 저장해두면
# scripts/sync-shared-captions.sh 가 지켜보다가 자동으로 반영한다. 어느
# 컴퓨터가 이 회차를 만들었는지 헷갈리지 않도록 만든컴퓨터.txt 도 같이 남긴다.
# 기존 scripts/backup-icloud.sh 가 쓰는 "컴퓨터 이름별" 재해복구 백업
# 폴더와는 다른, 컴퓨터 구분 없는 별도의 폴더다.
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

SHARED="$ICLOUD/쇼츠팩토리-완성본/$ID"
mkdir -p "$SHARED/captions"

[ -d "$SRC/renders" ]  && rsync -a --delete --exclude '.DS_Store' "$SRC/renders/" "$SHARED/"
[ -d "$SRC/captions" ] && rsync -a --exclude '.DS_Store' "$SRC/captions/" "$SHARED/captions/"

rm -f "$SHARED"/.rendering-* 2>/dev/null || true
echo "$HOSTNAME_LABEL" > "$SHARED/만든컴퓨터.txt"
date "+%Y-%m-%d %H:%M" > "$SHARED/마지막-업데이트-시각.txt"
echo "완성본 폴더로 올림 → 쇼츠팩토리-완성본/$ID ($HOSTNAME_LABEL)"
