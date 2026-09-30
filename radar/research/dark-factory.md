# Dark Factory — Phase 3 research (2026-09-30)
Sources: lablab event page (full text extracted); BAND docs https://docs.band.ai/jam ; public competitor repo https://github.com/metismuse/dark-factory (WebFetch summarizer -> medium confidence).

## Facts
- BAND Desktop: macOS/Windows/Linux; bundles `band` CLI, `jamd` daemon, `band-peer` plugin. **Prerequisite: Claude Code installed and signed in** (only runtime named in the docs page read). Needs a BAND account (docs don't say if a card is needed; lablab page says "no card needed").
- Concepts: peers = a Claude Code session with a BAND identity; rooms = conversations where agents exchange messages.
- Competitor repo shows: tracks nicknamed "tablekeeper" (reservation) and "pocketful" (wallet); Stage 1 ~ 30% of the full entry; Node stdlib-only API; proof of clean boot with **zero outbound network** via `unshare -rn`; tests for concurrency/idempotency (e.g. 500-transfer conservation storm); headless BAND sign-in via API key; Xvfb + ffmpeg to record the room.
- Spec + harness are only visible AFTER lablab enrollment (competitor notes "pulled from lablab.ai during enrollment").

## Scoring insight
60/100 = the factory (generic mandates, docs, measured cost, recovery from bad work). 40/100 = what it shipped. => Reusable generic mandate files are the biggest lever, and they can be prepared BEFORE seeing the spec.

## Disqualifier traps (from page)
Track-specific detail in mandates; video without BAND room recording; service that doesn't start from a clean container with no outbound network.

## Prepared in advance (no account needed): radar/build/dark-factory/
generic mandates, a mandate-lint that flags track-specific terms, a no-network clean-boot check.

## Go/no-go inputs still needed from Saleh
BAND + lablab account creation (I don't create accounts), Claude Code available locally (BAND Desktop runs on his machine), decision to spend ~5 days.
