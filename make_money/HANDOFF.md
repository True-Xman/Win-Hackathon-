# HANDOFF (current snapshot, rewrite in place, do not append history)
Updated: 2026-10-06 | Branch: ccr-9e2308e2-f6k942

## Project
Money Hunter = discovery + verification engine. NOT an income lane, NOT an executor.

## Job
1. Search multiple sources for real income opportunities:
   - published tasks/bounties
   - public problem signals that could become a direct paid offer
2. Apply hard constraints: remote; crypto/stablecoin payout; no KYC (ID/selfie; email/username/wallet address is fine); no country restriction excluding the user; ideally zero upfront spend; ethical, no fake identity or bypass.
3. Verify payment reality and eligibility. Absence of evidence = UNKNOWN, never PASS.
4. Rank conservatively.
5. Return only the best 1-3 actionable candidates, then STOP and wait for user approval.
After approval, execution is handed to the appropriate case/lane.

## Money Hunter must NOT
Submit work, send outreach, create wallets, sign transactions, spend money, claim bounties, modify payout addresses, or run any risky external action.

## Locked decisions
- X/Twitter is fully out of scope.
- Agent Reach is not a core dependency; only selected patterns may be reused.
- User jurisdiction is private: never ask or infer it.
- User-facing output: minimal, Finglish, no long architecture reports.
- Do not reread whole chat/history unless required.
- TaskMarket is ONE possible source, not the system.

## Historical evidence (TaskMarket/TaskForce experiment, NOT controlling current workflow)
Facts only; the experiment's actions (wallet, withdrawal address, monitor routine, GO 5 pilot, filter loosening) are NOT part of the current task.
- TaskForce: marketplace was empty (7 tasks, 6 test probes, 1 expired). Recheck not before ~2026-11.
- TaskMarket (taskmarket.dev): live no-KYC USDC/Base market. Fee 7.5%; median 29 subs/task; ~2.9% of submissions paid; EV ~$0.07/submission; ~1 USDC/day expected at volume. Submit free; resubmit/pitch/identity cost 0.001 USDC.
- Requester stats (cheap tasks): 0x15E9722f data/CSV avg 1.9 subs, 7/7 settled (best); 0xa7BecFC0 $5 bounties avg 24 subs, 88% settled; 0xc0566E4F avg 46 subs, 99% settled; 0x436326b6 avg 89 subs (worst).
- 2026-10-06 snapshot: 5 USDC x2 (51-57 subs), 2 USDC x3 (13-17 subs), 199 USDC CUDA (needs GPU). All crowded.
- Platform sweep, KYC/fiat -> FAIL: Superteam, Algora, Opire, Code4rena, Sherlock, Immunefi. Dead/FAIL: Claw Earn (30% stake, 0 tasks), ClawTasks, AgentMarket, BountyBook, AgentPact. Bountycaster needs Farcaster (US phone or $5).
- Full detail (if it exists): radar/research/agent-task-markets.md on branch origin/ccr-ac2b1e05-n02epk.
- Old 5h monitor routine (trig_0189EEGZDnzqF41Smc8obPzd) belongs to the stale experiment: paused, not deleted, no replacement yet.

## Current state
V1 live: `python3 make_money/hunter/hunt.py --live` (stdlib; 8 tests pass). Collectors (hunter/collectors.py): taskmarket, agenthansa (public no-auth bounties/community tasks, X/Twitter items skipped), hn (demand signals), github (stub; 403 in cloud session, skipped), gigs (discovery only -> out/gigs_discovery.json: 16/46 platforms CLAIM no-KYC+crypto, unverified, affects no gate).
Policy (user, 2026-10-06): any upfront fee/spend, even 0.001 USDC = paid_action FAIL. Historical HANDOFF summary is NOT KYC evidence. KYC/country/payout PASS needs one primary-source check, cached in make_money/evidence/claims.json (url+quote+date+ttl); re-check only when stale/invalid. UNKNOWN entries there mean "already checked, nothing found".
Shortlist bar: no FAIL + payout PASS + kyc PASS; weak ones never forced in.
Last live run: 12 collected, 0 qualified, shortlist empty. TaskMarket: all fee-FAIL (>=5 subs), kyc UNKNOWN. Agent Hansa: payout PASS + no-fee PASS (cached), kyc/country UNKNOWN (llms docs silent; /terms JS-rendered). NEAR market: job list needs auth token -> no collector.

## Next task
Agent Hansa finished: rendered primary source (/terms via Playwright, read-only) has NO explicit no-KYC and NO country clause -> kyc/country stay UNKNOWN (cached in evidence/claims.json, ttl 60d, do not re-research). Also cached UNKNOWN: Stacker News, Dework, TaskMarket, NEAR market. Zero qualified candidates exist.
Next: only an explicit "no KYC"/"open worldwide" statement can flip a gate. Options: ask user whether "no KYC clause in terms + wallet-only payout" may count as acceptable-risk (policy change, user decides), or verify other gigs.sh-claimed platforms one at a time (clustly, encode-club, ethglobal). Playwright render recipe: node + /opt/node22/lib/node_modules/playwright, executablePath /opt/pw-browsers/chromium, --no-sandbox, GET only.

## Model
Sonnet 5.5 for implementation; escalate only if verification logic proves unreliable.
