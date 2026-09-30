#!/usr/bin/env python3
"""Mandate lint: a mandate that names anything specific to the track/challenge DISQUALIFIES the entry (Dark Factory rules).
Flags: URL paths, HTTP status/error codes, snake/camel field-like tokens, and a domain deny-list you extend once the
official spec is known (add words to DOMAIN_WORDS in a local, UNCOMMITTED file: deny_extra.txt, one per line).
Usage: python3 lint_mandates.py [dir]     exit 1 if anything flagged."""
import os
import re
import sys

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "mandates")
DOMAIN_WORDS = ["reservation", "booking", "restaurant", "table", "diner", "guest", "party size", "wallet", "transfer",
                "payment", "balance", "ledger", "currency", "account", "opentable", "venmo", "tablekeeper", "pocketful"]
extra = os.path.join(os.path.dirname(__file__), "deny_extra.txt")
if os.path.exists(extra):
    DOMAIN_WORDS += [w.strip().lower() for w in open(extra) if w.strip()]
PATTERNS = {
    "url/path": r"(?<![\w])/[a-z0-9_\-]+(/[a-z0-9_\-{}:]+)+",
    "http code": r"\b(HTTP\s*)?[1-5]\d\d\b(?!\s*(ms|s|px|%|words|lines))",
    "field-like token": r"`[a-z]+(_[a-z0-9]+)+`|`[a-z]+([A-Z][a-z0-9]+)+`",
}
bad = 0
for f in sorted(os.listdir(D)):
    if not f.endswith(".md"):
        continue
    t = open(os.path.join(D, f)).read()
    for i, line in enumerate(t.splitlines(), 1):
        for name, pat in PATTERNS.items():
            if re.search(pat, line):
                print(f"{f}:{i}: [{name}] {line.strip()}"); bad += 1
        low = line.lower()
        for w in DOMAIN_WORDS:
            if re.search(r"\b" + re.escape(w) + r"s?\b", low):
                print(f"{f}:{i}: [domain word '{w}'] {line.strip()}"); bad += 1
print("LINT", "FAIL" if bad else "OK", f"({bad} findings)")
sys.exit(1 if bad else 0)
