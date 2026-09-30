# Capability Radar — state (event-driven, NOT per-turn)

## Gate (read before running any discovery)
Run discovery ONLY on a real trigger: new phase | new blocker | architecture/tool decision | current capability insufficient |
materially better build/test/research/demo quality possible | judging rule needs new capability | reusable solution saves significant time/cost.
Never for: simple questions, navigation, tiny edits, routine coding, tasks whose tool is already chosen, every message, curiosity.
Ask first: is expected value > token + time + integration cost? If no -> do not run.

## Workflow
1. Name the need. 2. `python3 radar/tools/capradar.py find <keyword>` (reuse before discovery). 3. Discover only if nothing fits.
4. Compare: value, quality, maturity, integration cost, time saved, maintenance risk, security risk, reliability, docs, project fit.
5. Pick; integrate/configure/build it yourself if reasonable. 6. Test. 7. Record an entry below (evidence in repo, not chat).
8. Chat only for: important capability found, user decision/action needed, security/cost/risk, material project impact.
Do not re-research an entry unless: stale (`capradar.py due`), requirement changed, integration failed, major new evidence, or solution insufficient.

## Entry template
### CAP-NN <need>
- Trigger: | Candidates: | Selected: | Why: | Status: | Evidence: | Rejected: | Risk: | Re-eval: (trigger; date)

## Entries

### CAP-01 Fetch primary hackathon pages/APIs
- Trigger: Phase 1 (earlier note claimed fetch blocked)
- Candidates: stdlib urllib (+retry), WebFetch tool (summarizer), Playwright (installed in env, not tried)
- Selected: stdlib `radar/tools/common.py:fetch` for structured pulls; WebFetch only for quick reads (medium confidence, small-model summary)
- Why: zero deps, reproducible, retries transient failures
- Status: INTEGRATED | Evidence: `data/source_health.json`, `tool-radar.md`
- Rejected: devpost.com root (403 WAF), dorahacks.io (captcha WAF) — not scripted around; api.github.com/search (session policy)
- Risk: site layout changes break adapters | Re-eval: adapter returns 0 records or status != 200 (2026-10-30)

### CAP-02 Rules/KYC/payout gate analyzer
- Trigger: hard gates need evidence, not guesses
- Candidates: in-house regex analyzer; external libs NOT researched (lightweight need)
- Selected: `radar/tools/gates.py` + `test_gates.py` (regression tests from real mistakes); payout gate = crypto-only per CLAUDE.md
- Status: INTEGRATED | Evidence: tests in repo | Risk: regex misses phrasing -> UNKNOWN by design, never PASS
- Re-eval: false verdict found in a real event, or LLM-judge option needed for nuanced clauses (2026-11-15)

### CAP-03 Extract rules from JS-rendered pages
- Trigger: lablab/genai.works show empty text to scripts
- Candidates: embedded JSON/payload parsing, Builder.io public API (returned empty), Playwright (not tried)
- Selected: payload adapters in `radar/tools/deep.py` (lablab text nodes + organizer HTML comments, genai rules JSON)
- Status: INTEGRATED for lablab event pages + genai.works; OPEN GAP: lablab Rule Book/Terms (client-rendered)
- Rejected: captcha/WAF bypass of any kind
- Re-eval: OPEN GAP -> try Playwright (preinstalled Chromium) on lablab.ai/hackathon-rules only, no captcha involved (when a lablab event passes shortlist)

### CAP-04 PDF text extraction
- Candidates: pdftotext (absent), system pypdf (crashes: broken `cryptography`), venv pypdf
- Selected: venv `/tmp/venv_radar` + pypdf | Status: INTEGRATED (`gates.py:_pdf_local`) | Risk: venv is ephemeral, recreate cmd in `tool-radar.md`
- Re-eval: new PDF fails to parse

### CAP-05 Zero-network clean-boot proof (Dark Factory requirement)
- Candidates: `unshare -rn` + ioctl loopback, docker (present, unused)
- Selected: `radar/build/dark-factory/cleanboot_check.sh` | Status: INTEGRATED, self-tested pass+fail cases
- Risk: needs user namespaces (works here) | Re-eval: judging environment differs from local check

### CAP-06 Generic multi-agent mandates + lint (Dark Factory)
- Selected: `radar/build/dark-factory/` (3 seats, `lint_mandates.py`) | Status: PREPARED, unused until go decision + spec seen
- Risk: event is UNKNOWN on crypto payout -> may be deprioritized | Re-eval: go/no-go decision, or spec published

### CAP-07 Discovery sources
- Selected: Superteam Earn JSON API, lablab payload, genai.works, HN Algolia (`radar/tools/collect.py`)
- Gaps: DoraHacks, Devpost root (WAF), GitHub search (policy), X/Reddit intel (fetch not yet tried in depth)
- Re-eval: new source needed for crypto-payout events (e.g. Superteam-style USDC bounties are the current best fit) (2026-10-15)

### CAP-09 Crypto-payout source discovery (trigger: crypto-only hard gate)
- Candidates: Superteam Earn API (wallet payouts, FAQ-verified), HackList aggregator (hacklist.io; no feed/API seen, WebFetch-readable), Monad/Hedera/Colosseum org pages, X-Agent (USDT, closed)
- Selected: Superteam collector (existing) + HackList as manual lead source + per-org pages; `gates.py` payout gate = crypto-only
- Status: INTEGRATED (Superteam) / MANUAL (HackList) | Evidence: research/crypto-first-discovery.md
- Rejected: Devpost sponsor-run contests (W-8BEN/identity), bank-only events (GenAI Works, lablab default)
- Risk: login-gated official rules (Monad) force secondary sources | Re-eval: new crypto hackathon wave or HackList exposes a feed (2026-10-20)

### CAP-08 Payment-reliability intel (did winners actually get paid?)
- Status: OPEN GAP, no evidence found for lablab/GenAI Works | Re-eval: before committing build time to any event with UNKNOWN payout
