#!/usr/bin/env bash
# Make this project's skills available in every Claude Code session by
# symlinking them into ~/.claude/skills/.
#
# Project-level skills (.claude/skills/) are already discovered automatically
# when Claude Code runs inside this repo — you only need this if you want them
# outside it.
#
#   ./scripts/install_global.sh            link every skill
#   ./scripts/install_global.sh --dry-run  show what would happen
#   ./scripts/install_global.sh --prefix   link as shorts-factory--<name>
#
# Refuses to replace anything that is not a symlink this script created, so an
# existing skill of the same name is reported and left alone.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_DIR/.claude/skills"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
DRY=0
PREFIX=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --prefix)  PREFIX="shorts-factory--" ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

[ -d "$SRC" ] || { echo "no skills at $SRC" >&2; exit 1; }
[ $DRY -eq 1 ] || mkdir -p "$DEST"

linked=0 skipped=0 conflict=0
for dir in "$SRC"/*/; do
  [ -f "$dir/SKILL.md" ] || continue
  name="$PREFIX$(basename "$dir")"
  target="$DEST/$name"

  if [ -L "$target" ]; then
    # Ours already, or someone else's link to the same place: re-point is safe.
    if [ "$(readlink "$target")" = "${dir%/}" ]; then
      skipped=$((skipped + 1)); continue
    fi
  elif [ -e "$target" ]; then
    echo "  CONFLICT: $name already exists at $target (real directory) — left untouched"
    conflict=$((conflict + 1)); continue
  fi

  if [ $DRY -eq 1 ]; then
    echo "  would link: $name"
  else
    ln -sfn "${dir%/}" "$target"
    echo "  linked: $name"
  fi
  linked=$((linked + 1))
done

echo ""
echo "$linked linked, $skipped already current, $conflict conflicts -> $DEST"
[ $conflict -gt 0 ] && echo "Re-run with --prefix to install conflicting names side by side."
exit 0
