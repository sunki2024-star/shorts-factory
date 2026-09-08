#!/usr/bin/env python3
"""Validate every skill under .claude/skills/.

Checks, per skill:
  * SKILL.md exists and has a parsable YAML frontmatter block
  * frontmatter carries name + description, and name matches the directory
  * every relative path SKILL.md points at actually exists in the skill folder
  * bundled Python scripts compile (a dry run that touches no network)
  * which environment variables and external binaries the skill expects

Exit code is non-zero if any ERROR is reported. WARNs do not fail the run.
Usage: python3 scripts/verify_skills.py [--json]
"""
import ast
import json
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"

# Paths referenced from prose. Deliberately narrow: a bare word is not a path.
PATH_RE = re.compile(
    r"(?<![\w/.-])((?:scripts|references|reference|assets|examples|templates)/[\w./{}-]+)"
)
ENV_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+){1,4})\b")
# Env names that show up in prose but are not credentials this repo needs.
ENV_IGNORE = {
    "SKILL_MD", "README_MD", "API_KEY", "YOUR_API_KEY", "HTTP_PROXY", "HTTPS_PROXY",
    "PYTHON_PATH", "PYTHONPATH", "NODE_ENV", "LC_ALL", "TZ", "PATH_TO",
}
ENV_HINT = re.compile(
    r"(?:os\.environ(?:\.get)?[\[(]\s*['\"]([A-Z0-9_]+)['\"]"
    r"|getenv\(\s*['\"]([A-Z0-9_]+)['\"]"
    r"|\$\{?([A-Z][A-Z0-9_]{3,})\}?"
    r"|export\s+([A-Z][A-Z0-9_]{3,})=)"
)
BIN_HINT = re.compile(r"\b(ffmpeg|ffprobe|yt-dlp|remotion|npx remotion|uv|pip)\b")


def frontmatter(text):
    if not text.startswith("---"):
        return None, "no leading '---' frontmatter fence"
    end = text.find("\n---", 3)
    if end == -1:
        return None, "unterminated frontmatter block"
    raw = text[3:end]
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:  # pragma: no cover - reported, not raised
        return None, f"invalid YAML frontmatter: {exc}"
    if not isinstance(data, dict):
        return None, "frontmatter is not a mapping"
    return data, None


PY_REQ_RE = re.compile(r"[Pp]ython[ _-]?3\.(\d{1,2})\s*\+")


def _declared_python(text):
    """Highest 'Python 3.N+' minimum a SKILL.md claims for itself, or None."""
    hits = [int(m) for m in PY_REQ_RE.findall(text)]
    return (3, max(hits)) if hits else None


def check_skill(d: Path):
    rec = {
        "skill": d.name, "errors": [], "warnings": [],
        "env": set(), "bins": set(), "python_scripts": 0, "refs_checked": 0,
    }
    md = d / "SKILL.md"
    if not md.is_file():
        rec["errors"].append("SKILL.md missing")
        return rec
    text = md.read_text(encoding="utf-8", errors="replace")

    fm, err = frontmatter(text)
    if err:
        rec["errors"].append(err)
    else:
        name = fm.get("name")
        desc = fm.get("description")
        if not name:
            rec["errors"].append("frontmatter has no 'name'")
        elif name != d.name:
            rec["warnings"].append(f"frontmatter name '{name}' != directory '{d.name}'")
        if not desc:
            rec["errors"].append("frontmatter has no 'description'")
        elif len(str(desc)) > 1024:
            rec["warnings"].append(f"description is {len(str(desc))} chars (>1024)")
        meta = fm.get("metadata") or {}
        oc = (meta.get("openclaw") or {}) if isinstance(meta, dict) else {}
        for e in ((oc.get("requires") or {}).get("env") or []):
            rec["env"].add(e)

    # Relative resources named in prose must exist inside the skill folder.
    for m in PATH_RE.finditer(text):
        rel = m.group(1).rstrip(".,;:)`\"'")
        if "*" in rel or rel.endswith("/"):
            continue
        rec["refs_checked"] += 1
        if (d / rel).exists():
            continue
        # A {placeholder} segment stands for a filename chosen at read time, so
        # the most we can check is that the directory holding it exists.
        if "{" in rel:
            parent = rel.rsplit("/", 1)[0]
            if (d / parent).is_dir():
                continue
            rec["errors"].append(f"SKILL.md references missing directory: {parent}/")
            continue
        rec["errors"].append(f"SKILL.md references missing path: {rel}")

    # Anything outside the folder cannot travel with the skill.
    for m in re.finditer(r"(?<![\w.])\.\./[\w./-]+", text):
        rec["warnings"].append(f"SKILL.md escapes the skill folder: {m.group(0)}")

    for src in (text,) + tuple(
        p.read_text(encoding="utf-8", errors="replace")
        for p in d.rglob("*") if p.is_file() and p.suffix in {".py", ".sh", ".md"}
    ):
        for groups in ENV_HINT.findall(src):
            for g in groups:
                if g and g not in ENV_IGNORE and not g.startswith("PATH"):
                    rec["env"].add(g)
        rec["bins"].update(BIN_HINT.findall(src))

    # Dry run: bundled Python must at least parse and compile.
    #
    # A skill may target a newer Python than the one running this check — the
    # syntax is then valid and only *this* interpreter cannot parse it. When
    # SKILL.md declares a higher minimum, a parse failure is reported as a
    # warning naming the requirement, not as an error, so a correctly installed
    # skill does not fail the build on an older host.
    needs = _declared_python(text)
    running = sys.version_info[:2]
    newer_ok = needs is not None and needs > running
    for py in d.rglob("*.py"):
        rec["python_scripts"] += 1
        try:
            ast.parse(py.read_text(encoding="utf-8", errors="replace"), filename=str(py))
        except SyntaxError as exc:
            if newer_ok:
                rec["warnings"].append(
                    f"{py.relative_to(d)} needs Python "
                    f"{needs[0]}.{needs[1]}+ (running {running[0]}.{running[1]}): {exc.msg}")
            else:
                rec["errors"].append(f"{py.relative_to(d)} does not compile: {exc}")

    for sh in d.rglob("*.sh"):
        if not os.access(sh, os.X_OK):
            rec["warnings"].append(f"{sh.relative_to(d)} is not executable")
    return rec


def main():
    if not SKILLS.is_dir():
        print(f"no skills directory at {SKILLS}", file=sys.stderr)
        return 1
    records = [check_skill(d) for d in sorted(SKILLS.iterdir()) if d.is_dir()]

    if "--json" in sys.argv:
        print(json.dumps(
            [{**r, "env": sorted(r["env"]), "bins": sorted(r["bins"])} for r in records],
            indent=2))
    else:
        for r in records:
            status = "FAIL" if r["errors"] else ("WARN" if r["warnings"] else "ok")
            print(f"[{status:4}] {r['skill']:<28} refs:{r['refs_checked']:<3} "
                  f"py:{r['python_scripts']:<2} env:{','.join(sorted(r['env'])) or '-'}")
            for e in r["errors"]:
                print(f"         ERROR: {e}")
            for w in r["warnings"]:
                print(f"         warn:  {w}")
        env_all = sorted({e for r in records for e in r["env"]})
        bins_all = sorted({b for r in records for b in r["bins"]})
        fails = sum(1 for r in records if r["errors"])
        print(f"\n{len(records)} skills, {fails} with errors")
        print(f"env vars referenced: {', '.join(env_all) or '-'}")
        print(f"external binaries referenced: {', '.join(bins_all) or '-'}")
    return 1 if any(r["errors"] for r in records) else 0


if __name__ == "__main__":
    sys.exit(main())
