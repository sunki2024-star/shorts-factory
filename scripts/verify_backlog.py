#!/usr/bin/env python3
"""Check office/memory/backlog.md: priority arithmetic, ordering, ids, postures.

The Pri column looks objective and is not — it is a formula over judgement
scores. That is fine, but a wrong cell makes a judgement look like a fact, so
the arithmetic at least has to be right. Run after any backlog edit.

Usage: python3 scripts/verify_backlog.py
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "office" / "memory" / "backlog.md"
LEDGER = ROOT / "office" / "research"
POSTURES = {"SHIPPED", "CONCEPT", "GAP"}


def main():
    if not BACKLOG.is_file():
        print(f"no backlog at {BACKLOG}", file=sys.stderr)
        return 1
    text = BACKLOG.read_text(encoding="utf-8")

    rows, errors, warnings = [], [], []
    for line in text.splitlines():
        if not line.startswith("| HS-"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) != 15:      # the retired table is narrower and not scored
            continue
        rows.append(c)

    incidents = set(re.findall(r"\*\*(I-\d{2})\*\*", text))
    seen, prev = set(), None

    for c in rows:
        rid, pillar, inc, code, posture = c[0], c[2], c[3], c[4].strip("`"), c[5]
        try:
            h, v, n, u, r, d = (int(c[i]) for i in (6, 7, 8, 9, 10, 11))
            pri = int(c[12].strip("*"))
        except ValueError:
            errors.append(f"{rid}: non-numeric score cell")
            continue

        calc = h * 3 + v * 2 + r * 2 + n + u - d * 2
        if calc != pri:
            errors.append(f"{rid}: Pri says {pri}, formula gives {calc}")
        if any(not 0 <= x <= 10 for x in (h, v, n, u, r, d)):
            errors.append(f"{rid}: a score is outside 0-10")
        if rid in seen:
            errors.append(f"{rid}: duplicate id — ids are never reused")
        seen.add(rid)
        if prev is not None and pri > prev:
            errors.append(f"{rid}: out of order ({pri} after {prev})")
        prev = pri

        if posture not in POSTURES:
            errors.append(f"{rid}: posture {posture!r} not one of {sorted(POSTURES)}")
        if pillar not in set("ABCDEFGH"):
            warnings.append(f"{rid}: pillar {pillar!r} is not A-H")
        if inc != "—" and inc not in incidents:
            errors.append(f"{rid}: incident {inc} is not in the ledger")
        # A CONCEPT entry describes something the product does not emit. Saying so
        # in the entry is the only thing standing between it and a fabricated
        # feature, so the file has to say it somewhere.
        if posture == "CONCEPT" and "CONCEPT" not in text:
            errors.append(f"{rid}: CONCEPT posture with no on-screen-label rule stated")

    print(f"{len(rows)} scored entries · {len(incidents)} incidents in the ledger")
    for e in errors:
        print(f"  ERROR: {e}")
    for w in warnings:
        print(f"  warn:  {w}")
    if not errors:
        print("backlog ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
