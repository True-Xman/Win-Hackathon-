# Dark Factory prep kit (built before seeing the spec; safe to reuse for any multi-agent build)
- `mandates/` 3 generic seats: architect / builder / verifier. Written to make sense for ANY problem (the rules give 60/100 for a reusable factory and DISQUALIFY track-specific mandates).
- `lint_mandates.py` flags URL paths, HTTP codes, field-like tokens and domain words. After you see the official spec, put its vocabulary in `deny_extra.txt` (uncommitted) and re-run before every submit.
- `cleanboot_check.sh "<start cmd>" <port> [path]` proves the service boots with zero outbound network (Linux `unshare -rn`, no `ip` needed). Exit 0 = pass.
Tested: lint passes clean mandates and fails a bad one; cleanboot passes a real server and fails a dead command.
NOT done (needs Saleh): lablab + BAND account creation, reading the spec/harness (visible only after enrollment).
