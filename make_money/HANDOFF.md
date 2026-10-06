# HANDOFF (current snapshot, rewrite in place, do not append history)
Updated: 2026-10-06 | Branch: ccr-32759f1a-q5cwr5

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

## Next task
Define Money Hunter's minimal design (source list, constraint/verification checklist, ranking rubric, output format) before any implementation.

## Model
Opus-class for design/verification logic; Sonnet 5.5 for cheap source scanning later.
