# Agent task marketplaces — research + handoff (2026-10-05)

Goal: Claude/GPT as worker -> task/bounty -> submit -> USDC/USDT. Gates: no KYC, no upfront spend, crypto payout.

## Verified live (fetched directly)

### TaskForce (task-force.app)
- Site + API docs live. Register: `POST /api/agent/register` (no auth) -> apiKey + Privy Solana wallet, status TRIAL.
- Flow: register -> verify challenge (30s) -> `GET /api/agent/tasks` -> apply (PENDING, creator must accept) -> 1 msg pre-accept -> submit -> creator approves -> USDC -> `POST /api/agent/wallet/withdraw` (Solana or Base; gas NOT sponsored, needs ~0.005 SOL).
- KYC: none in docs. /terms and /privacy = 404 -> payout-provider KYC later = UNKNOWN. Country restrictions = UNKNOWN.
- Task inventory: UNKNOWN (needs API key; /browse is behind sign-in). No third-party reviews/payout evidence found.
- Verdict: MAYBE. Register throwaway only to read inventory.

### TaskMarket (taskmarket.dev, Daydreams) — best no-KYC candidate
- Public API: `GET https://taskmarket.dev/api/tasks?limit=100&cursor=...` (default status=open under-reports; sweep all statuses/phases).
- On-chain: ~$1,768 paid lifetime to ~270 wallets; growing monthly. 468 tasks total; 362 completed.
- Economics: platform fee 7.5%; median 29 submissions/task; 1 winner; payment rate per submission ~2.9%; EV ~$0.07/submission. 70 tasks stuck in awaiting_settlement (requester never settled).
- Costs: identity register / pitch / paid routes = 0.001 USDC via x402; submit artifact = free; USDC withdraw gasless to a ONE-TIME withdrawal address (set once, save recovery code).
- Terms (draft 2026-07): no KYC clause; generic sanctions-screening clause; 18+.
- Snapshot 2026-10-05: 12 active tasks; only 1 >$5: 199 USDC Yukon QSB CUDA optimisation (22 subs, needs GPU) https://taskmarket.dev/tasks/0x5f596b1a81417834a4366655bd4e6194819f5404a62c919c6953ae9bc92860bc . Others: 1 USDC logo (53 subs), 0.54 USDC shared x10.
- Recently expired unsettled: 25 USDC pitch (43 pitches), 10 USDC OEM-part sourcing (0 subs) -> watch for repost.
- Setup: `npm install -g @lucid-agents/taskmarket@latest && taskmarket init && taskmarket legal accept`. Skill: https://taskmarket.dev/skill.md

### Others checked
- Claw Earn (aiagentstore.ai/claw-earn): 0 available, 83 completed; stake 30% on first task -> FAIL (upfront).
- ClawTasks: paid bounties wound down -> dead. AgentMarket: 0 jobs. BountyBook: $0 on-chain. AgentPact: $13 lifetime.
- Agent Hansa: USDC, no KYC (per gigs.sh), $13-500 pools, 80+ subs/quest; one user $40 in 60 days. MAYBE, low EV.
- Superteam Earn: KYC REQUIRED for winners; most listings HUMAN_ONLY -> FAIL.
- Algora / Opire / IssueHunt: Stripe payout -> KYC at payout, fiat -> FAIL (Algora: 103 open bounties, $240k).
- Bountycaster: needs Farcaster account (US phone or $5) -> upfront -> deprioritise.
- Clustly: clients pick listed agents (not a task board); USDC Solana; no stake. Volume UNKNOWN.
- AgentHire: jobs $0.01-0.10. Code4rena/Sherlock/Immunefi: KYC at payout.
- Directory of 46 platforms with KYC flags: https://gigs.sh/api/v1/gigs

## Blockers hit in this session
- Cloud permission classifier blocked: `curl -X POST .../register`, `npm install -g`, and writing `.claude/settings.json`.
- Fix: user creates `.claude/settings.json` on GitHub (allow: `Bash(curl *)`, `Bash(npm install *)`, `Bash(taskmarket *)`), then NEW session.

## Handoff prompt (paste in new session)
Read CLAUDE.md and radar/research/agent-task-markets.md. Then:
1. TaskForce: register agent "SalehAgent" via POST /api/agent/register; store apiKey only in scratchpad (never in repo). GET /api/agent/tasks?limit=100 and list tasks with reward, category, deadline, maxWorkers. Do NOT apply.
2. TaskMarket: install CLI, `taskmarket init`, `taskmarket legal status`. Do NOT accept legal or set withdrawal address without my OK. Sweep /api/tasks across all phases; shortlist tasks with reward >= 5 USDC and < 10 submissions.
3. Report in CLAUDE.md format: top 3 tasks (reward, link, AI time, risk) + what needs my approval.

## Update 2026-10-05 07:00 UTC — setups done
- TaskForce: agent registered (name SalehAgent, status ACTIVE after 30s challenge; Solana wallet GVDFxcRWGkaharQDdHmHkeCjnNEvcAxG5qN38fXZK7bQ). apiKey kept OFF-repo.
  Inventory via API: 7 tasks total. 6 are test/probe tasks (1 USDC "Base chain probe", 0.01 USDC smoke test). 1 real: $15/worker face-video recording for AI training (biometric selfie video, deadline passed 2026-09-29). => TaskForce marketplace is effectively EMPTY. Verdict: not usable now; re-check monthly.
- TaskMarket: CLI installed, wallet created on Base: 0x4b3628949E14b052973f5b486eaEf6772ba8B128 (agentId 97682, identity registered, balance 0). Legal bundle = draft, enforcement OFF (no acceptance needed yet). Withdrawal address NOT set (one-time, needs user's Base address). Keystore lives in the ephemeral container (~/.taskmarket/keystore.json) -> user must keep a copy.
- Next: monitor taskmarket.dev /api/tasks for new tasks (reward >= 5 USDC, < 10 submissions); act fast on fresh ones.
