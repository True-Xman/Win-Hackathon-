# Source ecosystem (Phase 1) — first pass, 2026-09-30

Method: WebSearch snippets only. WebFetch to primary sites was BLOCKED by the sandbox network policy
(lablab.ai, dorahacks.io, hackathon.genai.works, kucoin.com; devpost.com/huggingface.co/x.com/reddit.com also unreachable via curl).
=> everything below is UNVERIFIED unless marked. Snippets also contained internal date inconsistencies, so treat dates as leads only.

| Source | Type | AI/agent relevance | Payout/KYC pattern (evidence) | Monitor? |
|---|---|---|---|---|
| Devpost | general platform, sponsor-run (AWS, Google Cloud, GitLab, DataHub...) | High, many agent events, $20k-$75k pools | Cash winners must claim via form; non-US individuals upload W-8BEN (Devpost help article, via search). Sponsor rules may add ID checks -> per-event check. KYC = UNKNOWN until each rules page read | YES |
| DoraHacks | crypto-leaning platform | Medium-high (Injective AI, BNB Hack AI agents, Mantle, HashKey) | Some events require KYC-verified exchange accounts for winners (Polygon DevX terms, via search); platform uses Merit Systems for payouts/compliance. Per-event | YES (per-event KYC gate) |
| lablab.ai | AI-hackathon platform | Very high | UNKNOWN | YES |
| Superteam Earn | bounty marketplace (Solana), USDC | Medium, has agent-focused bounties | USDC payouts; KYC rules per listing = UNKNOWN. Some listings are region-restricted | YES |
| Kaggle | competitions | Medium (ARC Prize etc.) | Kaggle requires ID/tax info for prizes in many cases = UNKNOWN | Low |
| MLH / Cerebral Valley / AI Tinkerers | community hackathon networks | High (mostly in-person; some online) | mostly sponsor swag/credits | Low-Med |
| Labs/vendors: Anthropic, OpenAI (WebMCP Challenge), Google Cloud, GitLab, Microsoft Reactor, AWS | company-run | Very high | Prizes often credits or cash; company legal/tax forms | YES |
| Hugging Face org events (e.g. Agents-MCP-Hackathon) | open-source community | Very high | mostly credits/prizes, cash rare = UNKNOWN | YES |
| Internshala / StartupGrantsIndia / regional | regional | Medium | many are India-resident only -> likely FAIL for eligibility | Filter only |
| GitHub (Issues/Discussions/Sponsors bounties), Algora, X, Reddit, Discord | discovery + intel | High for intel | n/a | need access |

## Key structural finding
The dominant filter is not category but payout compliance: Devpost => tax forms (W-8BEN), DoraHacks => sometimes exchange KYC.
So Phase 2 must test the PAYOUT clause first, before spending time on ideas/competition.
