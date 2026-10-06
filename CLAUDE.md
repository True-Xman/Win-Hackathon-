# CLAUDE.md — permanent instructions for this repo

Precedence: this file overrides `radar/constraints.md`, `radar/README.md` and any older note where they conflict
(e.g. country questions, payout gate). Update those files to match when you next touch them.

## Project
Money Hunter: discovery + verification engine for real income opportunities (published tasks/bounties and public problem signals).
It does NOT submit, send outreach, create wallets, sign, spend, claim, or change payout addresses. It returns the best 1-3 candidates, then waits for user approval.
Current state and next task: `make_money/HANDOFF.md`. Older hackathon notes (historical, not controlling): `radar/*.md`.
TaskMarket/TaskForce is only one possible source; its earlier execution experiment (wallet, monitor, GO 5 pilot) is stale and must not be resumed.
X/Twitter is out of scope.

## USER OUTPUT + TOKEN EFFICIENCY POLICY

### Language
All user-facing output is Finglish only (Persian words in Latin script). No Persian script.
English only for: code, commands, file/paths, technical terms, field names, proper nouns.

### Core rule
Chat is for the user, not a debug log. Do NOT narrate routine work (testing, retries, regex fixes, reruns,
collector bugs, file rewrites, searching, test pass/fail) unless it materially affects a
decision, eligibility, cost, deadline, risk, or final result.
Raw evidence, debug logs, research notes, test history, source lists, competitor notes and implementation history
are saved in the repo, never in chat. Expand in chat only when the user asks.

### Default output
Very concise. Routine update ~50-120 words. Important phase update ~150-250 words.
Use only the relevant sections:
- NATIJE: what changed / what was found for the user.
- STATUS: PASS / FAIL / UNKNOWN or current state.
- ACTION AZ MAN: only things only the user can do. Drop section if none.
- BLOCKER: only real blockers. Drop section if none.
- NEXT: next highest-value action.

### Delta-only
Report only NEW or materially changed information. Do not re-summarize constraints, architecture, tools,
previous findings, previous shortlist or completed work unless explicitly asked.

### Work first, report after
Do everything doable autonomously first. No mid-task status messages, no long "I am going to..." messages.
Report once, after a meaningful chunk, with only the useful result.

### Token conservation
Avoid: repetition, tool/debug narration, intro/conclusion filler, copying data that already lives in the repo,
large tables unless needed for a decision, multiple examples when one is enough, obvious explanations,
restating the user's instructions.
Token saving must NEVER reduce research, verification, coding, testing or competitive-analysis quality.
Do deep work; keep the report short. The user should see DECISIONS + USEFUL RESULTS, not the work diary.

### User action requests
No long explanations. Say only: 1) where to go, 2) what to click/type, 3) what to send back or what result to look for.
If unsure about a UI/path, say explicitly that you are uncertain.

### Model / effort
Suggest a model/effort change only when it is materially worth it, never per small task. If truly needed, give only:
MODEL:
EFFORT:
CHAT: stay / new
WHY: one sentence

## Privacy / jurisdiction
The user does not share country, citizenship or residency. Do NOT ask for them and do NOT infer them.
Only use this fact: "User has jurisdiction and payment restrictions."
If eligibility can only be decided by knowing the exact country: country eligibility = UNKNOWN,
record the reason in the repo, and deprioritize the candidate — unless the official rules are clearly
global/worldwide with no relevant restriction.
Never recommend: fake country, fake residency, fake identity, VPN eligibility bypass, misrepresentation.

## Opportunity hard gates (serious opportunities)
Each must hold; evidence required (PASS needs explicit text; absence = UNKNOWN, never PASS):
- remote/online
- no mandatory KYC at: registration, participation, submission, winner verification, payout
- no mandatory out-of-pocket spending; no fake-eligibility workaround

PAYOUT (separate hard gate from no-KYC; BOTH must pass):
The user can receive prize money ONLY via crypto. Crypto payout is a HARD requirement, not a preference.
- Acceptable: USDT, USDC, reputable liquid crypto, direct wallet/on-chain payout.
- FAIL: fiat-only, bank-only, PayPal-only, Stripe-only, Wise-only, any mandatory identity-verified payout provider.
- Crypto payout stated but KYC unclear = UNKNOWN.
- Payout method not stated = UNKNOWN (and deprioritize).
Record the reason per candidate in the repo, not in chat.

## Session & Token Discipline
- Before every substantial task decide: CONTINUE CURRENT SESSION or NEW SESSION. If the session holds much old or unrelated context, prefer NEW SESSION.
- Before recommending NEW SESSION, update make_money/HANDOFF.md (rewrite as a current snapshot, not a log).
- For every substantial new task recommend the most appropriate currently available Claude model: strong reasoning only when genuinely needed, balanced coding model for normal implementation, cheapest suitable model for simple edits, tests, formatting, mechanical work.
- A fresh session reads make_money/HANDOFF.md first, then ONLY the source-of-truth files the task requires. Do not reread all docs by default and do not reconstruct old chat.
- Repository files are durable memory; chat context is temporary working memory.
- User-facing output defaults to ONLY: RESULT / BLOCKER / NEXT ACTION (language rule above still applies). No tool-by-tool logs, long narratives, repeated architecture explanations, or unrequested summaries.
- If more context is needed, load it selectively from the repo instead of asking for old conversation to be replayed.
