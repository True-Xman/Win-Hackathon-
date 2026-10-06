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
`python3 make_money/hunter/hunt.py --live` (stdlib + node/playwright render for JS pages; 12 tests pass). Collectors: risein (NEW, discovery-only), taskmarket, agenthansa, hn, github (stub, 403), gigs (discovery, unverified claims).
Lanes: FAST MONEY / BUILD MONEY (build_value in hunt.py: ai_leverage, technical_fit, prize, win_chance, timing, outside_control). Policy now in CLAUDE.md "Lanes + policy update".
Rise In: /earn cards -> per-opportunity sponsor rules_url -> gates from sponsor text (cached evidence/rules_cache, 7d TTL); Rise In text can only add FAIL. 7 hackathon/bounty/grant found: Monad Metropolis ($250k, ends Oct 12; sponsor site behind login -> UNKNOWN), Agent Visa/Celo ($15k), Granite ($100k), Stellar-OZ bounty, Prezenti Grants, Midnight bounty, Stacks Bug Bounty (explicit "Undergo full KYC" -> FAIL).
Shortlist bar: no FAIL + payout PASS + paid_action PASS (explicit) + onsite not RISK + worth (FAST reward>=$1, BUILD value>=15). KYC/country UNKNOWN allowed but flagged. Last live run: 18 collected, 0 qualified, shortlist empty (nothing forced).
Cached UNKNOWN: Hansa, TaskMarket, NEAR, Stacker News, Dework (see evidence/claims.json).

## Next task
Gas budget (user-reported, evidence/wallet_budget.json): Base ~0.0000399 ETH, Arbitrum ~0.0000207 ETH; ignore ETH mainnet dust + USDT BEP20. GAS-ONLY is not a PASS. hunt.py gas_assess (generic 150k x gasPrice) is a PRE-FILTER only -> GAS-PREFILTER-OK (not qualifying). GAS-COVERED needs a tx-specific read-only estimate (item field gas_tx {network,to,data[,from]}: eth_estimateGas + gasPrice + Base L1 data fee via GasPriceOracle, x1.5, balance >= 3x); simulation failure = UNKNOWN. Other fee/stake/deposit = FAIL. Hunter never signs/sends; every tx needs user approval.
FAST worthiness = reward-to-hassle (hunt.py fast_value, MIN_EV_PER_HOUR=2), no dollar floor.
Cooldown live: a source with no usable candidate (qualified or valuable login-queue lead) 3 runs in a row sleeps 7 days (evidence/source_state.json; `--force` ignores). gigs/github exempt.
Crypto-native checks 2026-10-06: Stacker News bounties (sats, public GraphQL) = FAIL spend (comments cost sats) + tiny; ETHGlobal = Cloudflare wall (skipped); DoraHacks = bot wall. Monad stays in login_queue.
Next: only report on a promising candidate / real blocker / user action. Periodic `hunt.py --live`.

## Model
Sonnet 5.5 for implementation; escalate only if verification logic proves unreliable.
