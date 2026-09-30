#!/usr/bin/env python3
"""Capability Radar lookup. Event-driven helper: reuse before discovery.
  capradar.py find <keyword>   entries mentioning keyword (case-insensitive)
  capradar.py due              entries whose Re-eval contains a past date (YYYY-MM-DD) -> stale candidates
  capradar.py list             ids + titles
"""
import datetime as dt
import os
import re
import sys

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "CAPABILITY_RADAR.md")


def entries():
    t = open(P).read()
    t = t[t.index("## Entries"):]
    return [(m.group(1), m.group(2).strip(), m.group(0)) for m in re.finditer(r"### (CAP-\d+) ([^\n]*)\n(?:(?!### CAP-).*\n?)*", t)]


def main(a):
    cmd = a[0] if a else "list"
    es = entries()
    if cmd == "list":
        [print(i, "-", n) for i, n, _ in es]
    elif cmd == "find" and len(a) > 1:
        hits = [(i, n) for i, n, b in es if a[1].lower() in b.lower()]
        [print(i, "-", n) for i, n in hits] or print("no entry: discovery allowed (if gate passes)")
    elif cmd == "due":
        today = dt.date.today()
        for i, n, b in es:
            m = re.search(r"Re-eval:.*?\((?:.*?;\s*)?(\d{4}-\d{2}-\d{2})\)", b)
            if m and dt.date.fromisoformat(m.group(1)) <= today:
                print(i, "-", n, "- due", m.group(1))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
