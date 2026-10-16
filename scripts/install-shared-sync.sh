#!/usr/bin/env bash
# 아이클라우드 자막 공유 폴더 자동 감시를 이 맥에 등록한다.
# 교회 맥미니, 집 아이맥 각각에서 한 번씩만 실행하면 된다.
#
#   bash scripts/install-shared-sync.sh
#
# 하는 일: 2분마다 scripts/sync-shared-captions.sh 를 돌리는 LaunchAgent를
# 등록하고, 터미널에서 직접 렌더링할 때도 공유 폴더에 올라가도록
# ~/.zshrc 에 SHORTS_SHARED_EDIT=1 을 추가한다. 이 둘 다 이미 돼 있으면
# 다시 실행해도 중복되지 않는다 (덮어쓰기/건너뜀).
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
LABEL="kr.yeshim.shorts-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/shorts-sync.log"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO/scripts/sync-shared-captions.sh</string>
  </array>
  <key>StartInterval</key><integer>120</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST_EOF

launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"

ZRC="$HOME/.zshrc"
if ! grep -q "SHORTS_SHARED_EDIT" "$ZRC" 2>/dev/null; then
  { echo ""; echo "# 쇼츠 자막 아이클라우드 공유 폴더 — scripts/install-shared-sync.sh 가 추가함"; \
    echo "export SHORTS_SHARED_EDIT=1"; } >> "$ZRC"
  echo "~/.zshrc 에 SHORTS_SHARED_EDIT=1 추가함 (새 터미널부터 적용됨)"
else
  echo "~/.zshrc 에 이미 SHORTS_SHARED_EDIT 설정이 있다 — 그대로 둠"
fi

echo
echo "등록 완료 — 이 맥이 2분마다 아이클라우드 공유 폴더를 확인한다."
echo "로그 확인: tail -f \"$LOG\""
echo
echo "macOS가 '백그라운드 항목이 추가되었다'는 알림을 띄우면, 시스템 설정 >"
echo "일반 > 로그인 항목 및 확장 프로그램 에서 켜져 있는지 한 번 확인해 주면 된다."
