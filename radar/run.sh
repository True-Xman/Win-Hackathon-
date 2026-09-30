#!/usr/bin/env bash
# One command: discover -> deep-read rules + gates -> render SHORTLIST.md. Safe to run daily.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 radar/tools/test_gates.py >/dev/null && echo "gate tests OK"
python3 radar/tools/collect.py
python3 radar/tools/deep.py
python3 radar/tools/report.py
