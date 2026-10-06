"""Live read-only collectors -> raw items in the inbox schema (see hunt.py). GET only, no auth, no writes.
Each collector returns (items, health). A blocked/failed source yields ([], {"ok": False, ...}); never workarounds."""
import datetime as dt
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fetch_json, html_to_text, now_utc  # noqa: E402

TM = "https://taskmarket.dev"
PAY_WORDS = re.compile(r"i(?:'| wi)ll pay|we(?:'| wi)ll pay|paid (gig|work|project|bounty)|looking for (a |an )?(freelance|contract|developer|engineer)|need (a|an|someone)[^.]{0,40}(build|develop|script|automat)|\bbounty (of|for)|budget (of|is)|\$\s?\d{2,}\s?(/|for|per)", re.I)
SKIP_TITLE = re.compile(r"^(tell hn|would you pay|ask hn: (developer|engineer|freelancer)[^:]{0,20}looking|will .* (matter|still))", re.I)
HN_QUERIES = ("will pay", "paid bounty", "looking for freelancer", "need a developer")


def taskmarket(max_pages=3):
    """Public GET /api/tasks (verified live 2026-10-06). Only tasks still accepting submissions are kept."""
    items, cursor, seen, n_raw = [], None, 0, 0
    for _ in range(max_pages):
        url = f"{TM}/api/tasks?limit=100" + (f"&cursor={cursor}" if cursor else "")
        st, d = fetch_json(url)
        if not isinstance(d, dict) or "tasks" not in d:
            return items, {"ok": False, "status": st, "note": "tasks API unreadable"}
        n_raw += len(d["tasks"])
        for t in d["tasks"]:
            exp = t.get("expiryTime")
            if t.get("status") != "open" or t.get("phase") != "active" or not t.get("submissionWindowOpen"):
                continue
            usd = int(t["reward"]) / 1e6 if str(t.get("reward", "")).isdigit() else None
            subs = t.get("submissionCount")
            # Platform facts below come from the API itself (USDC escrow on Base, online-only) and skill.md (first 5 submissions free,
            # then 0.001 USDC each). The public docs say nothing about KYC or country -> those stay UNKNOWN (no text injected).
            facts = ["Prizes paid in USDC to the worker wallet (onchain escrow).", "Fully online."]
            facts.append("Free to enter (first 5 submissions free)." if (subs or 0) < 5 else
                         "Submission fee of 0.001 USDC applies (submissions beyond the first 5 are paid).")
            if t.get("stakeRequired"):
                facts.append("Worker must stake funds.")
            items.append({"kind": "task", "source": "taskmarket", "native_id": t["id"], "title": (t["description"].split("\n")[0].lstrip("# ").strip() or t["referenceCode"])[:120],
                          "url": f"{TM}/tasks/{t['id']}", "text": t["description"] + "\n" + " ".join(facts),
                          "reward_usd": usd, "deadline": exp, "competition": subs,
                          "provenance": {"api": url, "mode": t.get("mode"), "requester": t.get("requester"), "ref": t.get("referenceCode")}})
        if not d.get("hasMore") or not d.get("nextCursor"):
            break
        cursor = d["nextCursor"]
    return items, {"ok": True, "raw": n_raw, "kept": len(items)}


def hn_signals(days=30, per_query=30):
    """Ask HN / HN stories that look like paid-work requests (Algolia public API) -> problem signals."""
    since = int((now_utc() - dt.timedelta(days=days)).timestamp())
    items, seen = [], set()
    for q in HN_QUERIES:
        u = f"https://hn.algolia.com/api/v1/search_by_date?query={q.replace(' ', '+')}&tags=ask_hn&numericFilters=created_at_i>{since}&hitsPerPage={per_query}"
        st, d = fetch_json(u)
        if not isinstance(d, dict):
            return items, {"ok": False, "status": st, "note": "HN API unreadable"}
        for h in d.get("hits", []):
            if h["objectID"] in seen:
                continue
            seen.add(h["objectID"])
            text = html_to_text(h.get("story_text") or "")
            blob = f"{h.get('title', '')}\n{text}"
            if SKIP_TITLE.search(h.get("title") or "") or not PAY_WORDS.search(blob):
                continue
            items.append({"kind": "signal", "source": "hn", "native_id": h["objectID"], "title": h.get("title"),
                          "url": f"https://news.ycombinator.com/item?id={h['objectID']}", "text": blob, "reward_usd": None,
                          "signal": {"budget_mentioned": bool(re.search(r"\$\s?\d|\d+\s?(usd|usdc)\b|budget", blob, re.I)),
                                     "contact_public": bool(re.search(r"@\w+\.\w+|email|contact", blob, re.I)),
                                     "urgency": bool(re.search(r"asap|urgent|this week", blob, re.I))},
                          "provenance": {"api": u, "author": h.get("author"), "created_at": h.get("created_at"), "comments": h.get("num_comments")}})
    return items, {"ok": True, "kept": len(items)}


def github_bounties():
    """Interface only. This cloud session blocks api.github.com search (403: sessions bound to configured repos);
    no workaround/auth is attempted. Wire a real implementation when run where public GitHub search is reachable."""
    st, d = fetch_json("https://api.github.com/search/issues?q=label:bounty+state:open+is:issue&per_page=30")
    if st != 200 or not isinstance(d, dict) or "items" not in d:
        return [], {"ok": False, "status": st, "note": "GitHub public search blocked/unreachable; skipped"}
    items = []
    for i in d["items"]:
        text = f"{i['title']}\n{(i.get('body') or '')[:4000]}"
        items.append({"kind": "signal", "source": "github", "native_id": str(i["id"]), "title": i["title"], "url": i["html_url"], "text": text,
                      "signal": {"budget_mentioned": bool(re.search(r"\$\s?\d|\d+\s?(usd|usdc)", text, re.I)), "contact_public": True},
                      "provenance": {"api": "github search issues label:bounty", "repo": i.get("repository_url")}})
    return items, {"ok": True, "kept": len(items)}


COLLECTORS = {"taskmarket": taskmarket, "hn": hn_signals, "github": github_bounties}


def collect_live(names=None):
    items, health = [], {}
    for n, fn in COLLECTORS.items():
        if names and n not in names:
            continue
        try:
            it, h = fn()
        except Exception as e:  # noqa: BLE001
            it, h = [], {"ok": False, "note": repr(e)[:200]}
        items += it
        health[n] = h
    return items, health
