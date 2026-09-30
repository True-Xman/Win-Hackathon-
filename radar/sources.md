# Source ecosystem (Phase 1) — first pass, 2026-09-30

CORRECTION (2026-09-30, second pass): the earlier note that fetching primary sites is blocked by network policy was WRONG or outdated.
Reachable now: lablab.ai, huggingface.co, superteam.fun + earn.superteam.fun JSON API, hackathon.genai.works, x.com, colosseum.com, ethglobal.com, `*.devpost.com`, hn.algolia.com, docs.superteam.fun.
Blocked by the SITES themselves (AWS WAF, not org policy): `devpost.com` root (403), `dorahacks.io` (captcha). Blocked by SESSION POLICY: `api.github.com/search` (session bound to its own repo; not bypassed).
Search snippets remain unreliable (e.g. a snippet said Agents for Humans closes Oct 14; the official page says it ended). Rows below marked VERIFIED were read from primary pages.

| Source | Type | AI/agent relevance | Payout/KYC pattern (evidence) | Monitor? |
|---|---|---|---|---|
| Devpost | general platform, sponsor-run (AWS, Google Cloud, GitLab, DataHub...) | High, many agent events, $20k-$75k pools | Cash winners must claim via form; non-US individuals upload W-8BEN (Devpost help article, via search). Sponsor rules may add ID checks -> per-event check. KYC = UNKNOWN until each rules page read | YES |
| DoraHacks | crypto-leaning platform | Medium-high (Injective AI, BNB Hack AI agents, Mantle, HashKey) | Some events require KYC-verified exchange accounts for winners (Polygon DevX terms, via search); platform uses Merit Systems for payouts/compliance. Per-event | YES (per-event KYC gate) |
| lablab.ai | AI-hackathon platform | Very high | **PARTIAL:** event pages say 'Prize distribution may take up to 90 days'; organizers 'contact winning teams to gather delivery details' (search snippet of Rule Book). Rule Book/Terms are client-rendered and unreadable to scripts => KYC UNKNOWN | YES (collector built) |
| Superteam Earn | bounty marketplace (Solana), USDC/USDG | Medium; `agentAccess` flag exists (AGENT_ALLOWED / HUMAN_ONLY) | **VERIFIED (docs.superteam.fun FAQ):** winners must complete KYC for Superteam/Solana-sponsored listings (`isFndnPaying=true` in API); external-sponsor listings pay to your Earn wallet, 'occasionally' ask KYC/invoices. Listings have a `region` field (Global vs country) | YES (JSON API collector built) |
| Kaggle | competitions | Medium (ARC Prize etc.) | Kaggle requires ID/tax info for prizes in many cases = UNKNOWN | Low |
| MLH / Cerebral Valley / AI Tinkerers | community hackathon networks | High (mostly in-person; some online) | mostly sponsor swag/credits | Low-Med |
| Labs/vendors: Anthropic, OpenAI (WebMCP Challenge), Google Cloud, GitLab, Microsoft Reactor, AWS | company-run | Very high | Prizes often credits or cash; company legal/tax forms | YES |
| Hugging Face org events (e.g. Agents-MCP-Hackathon) | open-source community | Very high | mostly credits/prizes, cash rare = UNKNOWN | YES |
| Internshala / StartupGrantsIndia / regional | regional | Medium | many are India-resident only -> likely FAIL for eligibility | Filter only |
| GitHub (Issues/Discussions/Sponsors bounties), Algora, X, Reddit, Discord | discovery + intel | High for intel | n/a | need access |

## Key structural finding
The dominant filter is not category but payout compliance: Devpost => tax forms (W-8BEN), DoraHacks => sometimes exchange KYC.
So Phase 2 must test the PAYOUT clause first, before spending time on ideas/competition.

## Added findings (second pass)
- **Devpost (sponsor-run US contests) — VERIFIED on one event (AWS Agents for Humans rules):** identity verification + prize affidavits + W-8BEN/W-9, long excluded-country list. Expect the same template on other Devpost sponsor events => usually FAIL for the no-KYC gate.
- **Colosseum (Solana) — VERIFIED (ToS PDF):** explicit KYC-consent clause + sanctions/PEP lists. 7,467 builders joined the current edition.
- **GenAI Works — VERIFIED (event page):** open worldwide 16+, free, bank-transfer payout. No KYC wording (UNKNOWN).
- **ETHGlobal:** event pages fetchable; online events are async and dated (ETHOnline 2026 already over). Payout/KYC not yet researched.
