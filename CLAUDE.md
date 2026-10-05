# CLAUDE.md

## Response verbosity (Claude Code session output)

This governs how Claude Code formats its own conversational output in this
session — separate from `TOKEN_COST_POLICY.md`, which governs the runtime
X Reply Agent's model calls, and `CONTEXT_ENGINEERING.md`, which governs what
context reaches the runtime model. This file exists to protect the token
quota of the Claude Code development session itself.

Rules:

- Return only the requested data. No preamble, no restating what was just
  done, no closing summary sentence unless asked.
- Prefer tables/lists over prose when reporting results (test runs, file
  counts, diffs, search hits).
- Do not narrate routine tool calls ("Reading X to check Y") — just do it.
- Do not re-explain code that well-named identifiers already make clear.

Does not apply to:

- Architecture decisions, tradeoffs, and anything `AGENTS.md` requires to be
  surfaced (proactive suggestions with what/why/tradeoff, `SOURCE UPDATE
  REQUIRED`, review-protocol writeups). This rule constrains chatter, not
  judgment or required disclosure.
