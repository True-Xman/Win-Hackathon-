# Skill + Tool Radar (updated 2026-09-30)

| Gap | Status | What exists now |
|---|---|---|
| Fetch primary hackathon pages | **SOLVED (old note was wrong)** | Most hosts reachable: lablab, huggingface, superteam, genai.works, x.com, colosseum, ethglobal, `*.devpost.com`. Blocked BY THE SITES (not policy): `devpost.com` root (403 WAF), `dorahacks.io` (AWS WAF captcha). Blocked BY POLICY: `api.github.com/search` (session bound to its repo) — not bypassed. See `data/source_health.json` |
| Discovery/normalization | BUILT | `tools/collect.py` (Superteam JSON API, lablab payload, genai.works, HN) -> `data/candidates.json` |
| Rules/KYC/payout parser | BUILT + tested | `tools/gates.py` (evidence snippets, PASS/RISK/UNKNOWN/FAIL) + `tools/test_gates.py` (9 regression tests from real mistakes) |
| Deep rules extraction from JS apps | BUILT | `tools/deep.py` adapters: lablab (payload text nodes + organizer HTML comments), genai.works (embedded rules JSON), Superteam (details API) |
| Platform-level policy overlay | BUILT | `deep.py:platform_overlay` — Superteam FAQ KYC rule (Foundation-paid => FAIL), Colosseum ToS (KYC consent + sanctions) |
| Deadline clock | BUILT | `tools/report.py` recomputes days-left each run; uses registration-close, never results date |
| PDF reading | WORKS via venv | `/tmp/venv_radar` + pypdf (system `cryptography` is broken on this box; venv avoids it). Recreate: `python3 -m venv /tmp/venv_radar && /tmp/venv_radar/bin/pip install pypdf` |
| DoraHacks / Devpost-root discovery | GAP | WAF blocks scripts. Workaround: WebSearch -> individual `*.devpost.com` pages (fetchable). DoraHacks: search snippets only; per-event rules unreadable => everything from DoraHacks stays UNKNOWN |
| lablab Rule Book / Terms | GAP | Client-rendered (Builder.io) — empty for scripts. Need Saleh to open https://lablab.ai/hackathon-rules once and paste the prize/KYC clauses, or ask organizer (draft in outreach/) |
| Payment-reliability intel (did winners get paid?) | GAP | No web evidence found for lablab/GenAI Works. Needs X/Reddit/Discord search — x.com fetch not yet tried in depth |
| Previous-winner / competitor analyzer | TODO (Phase 3) | Public GitHub repos of competitors visible via search; GitHub API blocked -> use WebSearch/WebFetch on github.com pages |
| Build-phase tooling (spec parser, QA harness, demo/submission audit) | TODO after event chosen | Will build per chosen event |

| Dark Factory prep kit | BUILT + tested | `build/dark-factory/` mandates + mandate-lint + zero-network clean-boot check |
| Open Agent + Dark Factory research | WRITTEN | `research/*.md` |
