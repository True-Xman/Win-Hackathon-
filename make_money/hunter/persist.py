"""Write-access preflight + verified persistence for the scheduled run (stdlib only; never touches anything but git refs/evidence).

preflight(): can this checkout push to its branch? Runs BEFORE the expensive hunt and before --ack-notify, so a run that cannot persist never
consumes a notification. persist(): commit evidence, push with retry on network errors, then verify that the remote branch really holds our commit.
A failed persist leaves the remote notify_state.json untouched (announcements stay `pending` and are repeated once), so a failed push can delay
a notification but never silently swallow it. Auth failures (403/denied) are not retried: they need `add_repo access=push`, not backoff."""
import os
import re
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PERSIST_PATHS = ("make_money/evidence", "make_money/HANDOFF.md")
BACKOFF = (2, 4, 8, 16)
AUTH_FAIL = re.compile(r"\b(403|401)\b|permission|denied|not authorized|authentication failed|unable to access|forbidden", re.I)
HINT = "call mcp__claude-code-remote__add_repo(owner=True-Xman, repo=Win-Hackathon-, access=push), then re-run"


def _git(args, cwd, timeout=90):
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"{type(e).__name__}: {e}"


def current_branch(cwd=ROOT):
    rc, out = _git(["symbolic-ref", "--short", "-q", "HEAD"], cwd)
    return out if rc == 0 and out else None


def preflight(branch=None, cwd=ROOT, remote="origin"):
    """-> (ok, reason). Checks git checkout, expected branch, read access and (dry-run) write access to that branch. Writes nothing."""
    rc, _ = _git(["rev-parse", "--git-dir"], cwd)
    if rc:
        return False, f"not a git checkout ({HINT})"
    cur = current_branch(cwd)
    if not cur:
        return False, "detached HEAD; check out the run branch first"
    if branch and cur != branch:
        return False, f"on branch {cur}, expected {branch}"
    rc, out = _git(["ls-remote", "--exit-code", "--heads", remote, cur], cwd)
    if rc == 2:
        pass  # branch not on the remote yet: the dry-run below still proves write access
    elif rc:
        return False, f"cannot read {remote}: {out[:200]} ({HINT if AUTH_FAIL.search(out) else 'network?'})"
    rc, out = _git(["push", "--dry-run", remote, f"HEAD:refs/heads/{cur}"], cwd)
    if rc:
        why = "NO WRITE ACCESS" if AUTH_FAIL.search(out) else "push would be rejected (behind remote? run git pull --rebase)"
        return False, f"{why} to {remote}/{cur}: {out[-200:]} ({HINT if AUTH_FAIL.search(out) else 'fix, then re-run'})"
    return True, f"can push to {remote}/{cur}"


def persist(message, branch=None, cwd=ROOT, remote="origin", paths=PERSIST_PATHS, backoff=BACKOFF):
    """Commit `paths`, push, verify on the remote. -> (ok, reason). Never pushes another branch; never force-pushes."""
    cur = current_branch(cwd)
    if not cur or (branch and cur != branch):
        return False, f"on branch {cur}, expected {branch}"
    _git(["add", "--", *[p for p in paths if os.path.exists(os.path.join(cwd, p))]], cwd)
    if _git(["diff", "--cached", "--quiet"], cwd)[0]:
        rc, out = _git(["commit", "-q", "-m", message], cwd)
        if rc:
            return False, f"commit failed: {out[-200:]}"
    last = ""
    for i in range(len(backoff) + 1):
        rc, last = _git(["push", "-u", remote, f"HEAD:refs/heads/{cur}"], cwd, timeout=180)
        if rc == 0:
            break
        if AUTH_FAIL.search(last):
            return False, f"push refused (auth): {last[-200:]} ({HINT})"
        if i < len(backoff):
            time.sleep(backoff[i])
    else:
        return False, f"push failed after {len(backoff) + 1} attempts: {last[-200:]}"
    rc, head = _git(["rev-parse", "HEAD"], cwd)
    rc2, ls = _git(["ls-remote", remote, f"refs/heads/{cur}"], cwd)
    if rc or rc2 or not ls.startswith(head):
        return False, f"push reported success but {remote}/{cur} != local HEAD {head[:8]}"
    return True, f"{remote}/{cur} = {head[:8]}"
