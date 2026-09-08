#!/usr/bin/env python3
"""Check which API keys are present and whether they actually work.

Every call this script makes is a free account/metadata endpoint — it never
scrapes, never fetches content, and never spends a credit:

  ScrapeCreators  GET /v1/account/credit-balance   (documented as free)
  Apify           GET /v2/users/me                  (account info, free)
  Gemini          GET /v1beta/models                (model list, free)
  TubeLab         presence check only — no free probe endpoint is documented,
                  so this script will not call it rather than risk billing you.

Usage:
  python3 scripts/check_keys.py            presence + live validation
  python3 scripts/check_keys.py --offline  presence only, zero network
"""
import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT = 15


def _get(url, headers):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, json.loads(r.read().decode("utf-8", "replace") or "{}")


def check_scrapecreators(key):
    status, body = _get(
        "https://api.scrapecreators.com/v1/account/credit-balance",
        {"x-api-key": key},
    )
    credits = body.get("creditsRemaining", body.get("credits", body))
    return f"valid — credits remaining: {credits}"


def check_apify(token):
    status, body = _get(
        "https://api.apify.com/v2/users/me",
        {"Authorization": f"Bearer {token}"},
    )
    d = body.get("data", {})
    plan = (d.get("plan") or {}).get("id", "unknown")
    return f"valid — user: {d.get('username', '?')}, plan: {plan}"


def check_gemini(key):
    status, body = _get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", {}
    )
    return f"valid — {len(body.get('models', []))} models visible"


CHECKS = {
    "SCRAPECREATORS_API_KEY": ("ScrapeCreators", check_scrapecreators,
                               "stages 1,3,4,5 — best return per key"),
    "APIFY_TOKEN":            ("Apify", check_apify,
                               "tiktok/instagram/x-research"),
    "GEMINI_API_KEY":         ("Gemini", check_gemini,
                               "video-content-analyzer"),
    "TUBELAB_API_KEY":        ("TubeLab", None,
                               "youtube-research (no free probe — presence only)"),
}


def main():
    offline = "--offline" in sys.argv
    any_set = False

    for var, (name, probe, purpose) in CHECKS.items():
        val = os.environ.get(var, "").strip()
        if not val:
            print(f"  [ unset ] {var:<26} {name} — {purpose}")
            continue
        any_set = True
        if offline or probe is None:
            print(f"  [ set   ] {var:<26} {name} — not probed")
            continue
        try:
            print(f"  [  OK   ] {var:<26} {probe(val)}")
        except urllib.error.HTTPError as e:
            hint = "key rejected" if e.code in (401, 403) else f"HTTP {e.code}"
            print(f"  [ FAIL  ] {var:<26} {name} — {hint}")
        except Exception as e:
            print(f"  [ ERROR ] {var:<26} {name} — {type(e).__name__}: {e}")

    print()
    if not any_set:
        print("No keys set. Skills run in open mode: stages 6-9 at full strength,")
        print("stages 1-2 from public web sources. See README for where keys go.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
