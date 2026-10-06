# HANDOFF (current snapshot, rewrite in place, do not append history)
Updated: 2026-10-06 | Branch: ccr-ac2b1e05-n02epk

## Goal
Earn USDC/USDT fast with Claude as worker: task/bounty -> AI does it -> submit -> crypto. User supervises. Target first $10-50.

## Status
- TaskForce (task-force.app): agent registered + ACTIVE, but marketplace is empty (7 tasks, 6 test probes, 1 expired selfie-video task). Verdict: not usable now. Do not recheck before ~2026-11.
- TaskMarket (taskmarket.dev): only live no-KYC USDC/Base market. Wallet 0x4b3628949E14b052973f5b486eaEf6772ba8B128 (agentId 97682), balance 0. Withdrawal address SET (one-time) to user's SafePal 0x371E7DF0c58DBb7D57b911BCb89F1C87F94290d7 on Base. Earned so far: 0 USDC. Nothing submitted yet.
- Monitor routine trig_0189EEGZDnzqF41Smc8obPzd: every 5h (cron 29 */5, UTC), read-only, reports tasks >=5 USDC, <10 submissions, created <6h ago, else "NIST". Ran OK; found nothing.
- 2026-10-06 live snapshot: 5 USDC x2 (51-57 subs), 2 USDC x3 (13-17 subs, requester 0x436326b6), 199 USDC Yukon CUDA (needs GPU). All crowded.

## Locked decisions / constraints
- Hard gates: remote, no KYC at any step, no upfront spend, crypto payout only. Absence of evidence = UNKNOWN, never PASS.
- User jurisdiction is private: never ask or infer country. Never suggest fake identity/country/VPN bypass.
- NO signup, wallet action, claim, submit, or payment without explicit user approval in chat.
- User output: Finglish only, very short (see CLAUDE.md).
- "KYC" = ID/selfie verification. Email/username/wallet address is fine.

## Do NOT repeat (already decided, details in radar/research/agent-task-markets.md)
- Platform sweep: Superteam, Algora, Opire, Code4rena, Sherlock, Immunefi = KYC/fiat -> FAIL. Claw Earn (30% stake, 0 tasks), ClawTasks (wound down), AgentMarket, BountyBook, AgentPact = dead/FAIL. Bountycaster needs Farcaster (US phone or $5).
- TaskMarket economics: fee 7.5%, median 29 subs/task, ~2.9% of submissions paid, EV ~$0.07/submission. Submit is free; resubmit/pitch/identity cost 0.001 USDC.
- Requester stats (historical, cheap tasks): 0x15E9722f data/CSV tasks avg 1.9 subs, 7/7 settled (best EV, none open now). 0xa7BecFC0 $5 bounties avg 24 subs, 88% settled. 0xc0566E4F avg 46 subs, 99% settled. 0x436326b6 avg 89 subs (worst).
- Volume math: 2 USDC task, ~7% win chance = ~0.12 USDC/attempt; ~1 USDC/day expected. 10-50 USD target NOT realistic here. Token cost per attempt: UNKNOWN (measure).

## Blockers / unresolved
- Wallet keystore (~/.taskmarket/keystore.json) lives only in the old ephemeral container and in the user's saved backup. New session likely has no wallet: either user supplies keystore (never commit it) or run `taskmarket init` for a fresh wallet (then set withdrawal address again, with approval, new recovery code).
- `.claude/settings.json` (allow curl, npm install, taskmarket) exists on origin/ccr-0846c454-nnyy0v and origin/ccr-fc602b02-kikqtp, NOT on this branch. Not merged. Do not broaden it.
- User has not chosen: (A) loosen monitor filter to >=1 USDC and <20 subs plus requester score, and/or (B) pilot `GO 5` = 5 attempts with stop-loss.
- make_money docs 00/03/04/05 were NOT found on any branch of this repo.

## Exact next task
Ask user: A, B, or both. Then: update the routine prompt (update_trigger) per A, and for B build 5 submissions on the open 2 USDC/5 USDC tasks, log token cost per attempt in radar/research/agent-task-markets.md, stop if 0 wins after the pilot.

## Read first
CLAUDE.md, this file. Then only if needed: radar/research/agent-task-markets.md.

## Do NOT reread
radar/*.md hackathon notes (constraints, sources, leads, tool-radar), the old chat, TaskForce API docs, TaskMarket skill.md (CLI usage: `taskmarket task list|get|submit --help`).

## Model for next task
Sonnet 5.5: balanced, good enough for SVG/data deliverables at low cost; escalate to a stronger model only if the pilot shows quality is the reason for losing.
