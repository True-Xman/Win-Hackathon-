# Money Hunter V1 (read-only)
`python3 hunter/hunt.py` -> `out/shortlist.md` (max 3) + `out/candidates.json` (all, with gate evidence). Tests: `python3 hunter/test_hunt.py`.
Pipeline: inbox/*.json (tasks + signals) -> normalize -> gates (hunter/gates.py, evidence-first) -> reject FAIL/expired -> rank -> top 3.
VERIFIED = all of kyc/country/paid_action/onsite/payout explicit PASS; anything else = NEEDS_CHECK (UNKNOWN never PASS). Signals: payout always UNKNOWN until crypto agreed.
Live: `python3 hunter/hunt.py --live` runs hunter/collectors.py (taskmarket public /api/tasks, HN Algolia signals, github stub: 403 in cloud session -> skipped, no workaround). Shortlist bar = no FAIL + payout PASS + kyc PASS; dupes merged by URL; every item keeps `provenance`.
Never submits/spends/contacts. Add a source = drop a JSON file in inbox/ (schema in hunt.py docstring).
