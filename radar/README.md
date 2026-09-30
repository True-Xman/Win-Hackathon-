# Hackathon Radar

Goal: find hackathons/bounties Saleh can actually **win and get paid for**, under hard constraints (see `constraints.md`), and take the chosen one from idea to submission.

## Run it
    bash radar/run.sh          # discover -> deep-read rules + gates -> radar/SHORTLIST.md   (safe to re-run daily)
    python3 radar/tools/gates.py <url-or-file> ...   # analyze any rules page/PDF on demand
    python3 radar/tools/test_gates.py                # regression tests for the analyzer

## Files
- `SHORTLIST.md`      generated board + per-event evidence dossiers (read this first)
- `constraints.md`    hard gates + PASS/RISK/UNKNOWN/FAIL rule (source of truth)
- `sources.md`        platform ecosystem with verified reachability / payout-KYC pattern
- `leads.md`          older unverified leads and their current status
- `tool-radar.md`     capability gaps and what was built
- `data/`             `candidates.json` (live discovery), `gates.json` (automated gate results), `verified.json` (curated evidence, source of truth for SHORTLIST), `source_health.json`
- `tools/`            `collect.py` `deep.py` `gates.py` `report.py` `common.py` `test_gates.py`
- `outreach/`         drafted (unsent) questions to organizers about payout/KYC

## Evidence rules
PASS needs explicit text. Absence of a KYC clause = UNKNOWN, never PASS. Verdicts can only get worse via platform policy overlays. Every critical claim in `verified.json` carries a quote and a source URL, dated.
