"""Live read-only collectors -> raw items in the inbox schema (see hunt.py). GET only, no auth, no writes.
Each collector returns (items, health). A blocked/failed source yields ([], {"ok": False, ...}); never workarounds."""
import datetime as dt
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fetch, fetch_json, html_to_text, now_utc  # noqa: E402

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


HANSA = "https://www.agenthansa.com"
OUT_OF_SCOPE = re.compile(r"twitter|\bx\.com|tweet|reddit|follower", re.I)  # X/Twitter is out of scope; social-growth tasks need accounts


def agenthansa(pages=1):
    """Public no-auth listings: /api/collective/bounties/public + /api/community/tasks. Reward is split among participants,
    so reward_usd = reward / max(participants,1) (honest per-head estimate). Currency 'USD' on the API; USDC payout comes from cached docs claim."""
    items, raw = [], 0
    for path, key in (("/api/collective/bounties/public", "bounties"), ("/api/community/tasks", "tasks")):
        u = f"{HANSA}{path}"
        st, d = fetch_json(u)
        if not isinstance(d, dict) or key not in d:
            return items, {"ok": False, "status": st, "note": f"{path} unreadable"}
        raw += len(d[key])
        for t in d[key]:
            if t.get("status") not in ("open", "in_progress", "active") or OUT_OF_SCOPE.search(f"{t.get('title')} {t.get('description')} {' '.join(t.get('tags') or [])}"):
                continue
            n = t.get("participant_count") or 0
            items.append({"kind": "task", "source": "agenthansa", "native_id": t["id"], "title": t["title"], "url": f"{HANSA}{path}#{t['id']}",
                          "text": f"{t.get('description') or ''}\n{t.get('goal') or ''}\nFully online.",
                          "reward_usd": round((t.get("reward_amount") or 0) / max(n, 1), 2), "deadline": t.get("deadline"), "competition": n,
                          "provenance": {"api": u, "total_reward": t.get("reward_amount"), "currency": t.get("currency"), "split": t.get("split_method"), "created_at": t.get("created_at")}})
    return items, {"ok": True, "raw": raw, "kept": len(items)}


def gigs_discovery():
    """Discovery only: gigs.sh directory -> out/gigs_discovery.json (platforms claiming kycRequired=no + crypto rail). These are CLAIMS,
    not evidence: nothing here changes any gate. Verify at the primary source, then add to evidence/claims.json."""
    from common import save
    rows = []
    for off in (0, 20, 40):
        st, d = fetch_json(f"https://gigs.sh/api/v1/gigs?offset={off}")
        if not isinstance(d, dict):
            return [], {"ok": False, "status": st, "note": "gigs.sh unreadable"}
        rows += d.get("results", [])
    keep = [{k: r.get(k) for k in ("slug", "url", "categories", "paymentRails", "kycRequired", "verifiedAt", "agentAllowed")} for r in rows
            if r.get("kycRequired") == "no" and any("usdc" in x or "usdt" in x or "btc" in x for x in r.get("paymentRails") or [])]
    save("gigs_discovery.json", {"claims_unverified": keep, "source": "https://gigs.sh/api/v1/gigs"})
    return [], {"ok": True, "platforms": len(rows), "claimed_no_kyc_crypto": len(keep)}


RISE = "https://www.risein.com"
RISE_TYPES = ("Hackathon", "Bounty", "Bounties", "Grant", "Challenge", "Competition")  # jobs/courses/events are not money-for-work opportunities here
_NOISE = (".gov/", "risein", "schema.org", "w3.org", "googletagmanager", "linkedin.com", "instagram.com", "facebook.com", "twitter.com", "x.com", "youtube.com", "lu.ma/riseincom", "files.risein")


def _txt(h):
    h = re.sub(r"(?s)<(script|style|svg)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"[ \t]*\n[ \t\n]*", "\n", re.sub(r"<[^>]+>", "\n", h))


def risein(max_detail=40):
    """Rise In /earn = DISCOVERY ONLY (listing is the platform's claim, never gate evidence). Each opportunity gets its own sponsor
    `rules_url` (external link in the detail page); gates are verified from that sponsor text. Rise In card text is used only to
    catch FAIL clauses (discovery_text)."""
    st, h = fetch("%s/earn" % RISE)
    if st != 200:
        return [], {"ok": False, "status": st, "note": "/earn unreadable"}
    seg = h[h.find("Ecosystem opportunities"):]
    items, seen, n_cards = [], set(), 0
    for href, body in re.findall(r'<a href="(/[a-z0-9_-]+/[a-z0-9_-]+)"[^>]*>(.*?)</a>', seg, flags=re.S):
        n_cards += 1
        spans = [s.strip() for s in re.findall(r"<span[^>]*>([^<]*)</span>", body)]
        typ = next((s for s in spans if s in RISE_TYPES + ("Job", "Course", "Event")), None)
        if typ not in RISE_TYPES or href in seen or "Open" not in body:
            continue
        seen.add(href)
        if len(items) >= max_detail:
            break
        st2, d = fetch(RISE + href)
        if st2 != 200:
            continue
        t = _txt(d)
        title = (re.search(r"<h1[^>]*>([^<]+)</h1>", d) or re.search(r"<title>([^<|]+)", d))
        title = html_to_text(title.group(1)).strip() if title else href
        def after(label):
            m = re.search(r"\n%s\n([^\n]+)" % label, t)
            return m.group(1).strip() if m else None
        ext = [u for u in re.findall(r'https?://[A-Za-z0-9./_#?=&%~:+-]+', d) if not any(n in u for n in _NOISE)]
        prize = after("Prize pool")
        usd = None
        if prize and re.search(r"\d", prize):
            usd = float(re.sub(r"[^\d.]", "", prize.replace(",", "")) or 0) or None
        deadline = after("Deadline")
        dl_iso = None
        try:
            dl_iso = dt.datetime.strptime(deadline, "%b %d, %Y").replace(tzinfo=dt.timezone.utc, hour=23, minute=59).isoformat()
        except Exception:  # noqa: BLE001
            pass
        start = after("Start date")
        loc = after("Location")
        about = t[t.find("About this opportunity"): t.find("More ways to")]
        items.append({"kind": "task", "lane": "BUILD" if typ != "Bounty" and typ != "Bounties" or (usd or 0) >= 1000 else "FAST",
                      "source": "risein", "native_id": href, "title": title[:120], "url": RISE + href,
                      "rules_url": ext[0] if ext else None,
                      "discovery_text": about[:6000] + ("\nIn-person event." if loc and loc.lower() != "online" else ""),
                      "text": "", "reward_usd": usd, "deadline": dl_iso, "competition": None,
                      "provenance": {"listing": RISE + "/earn", "type": typ, "location": loc, "start": start, "prize_claim": prize, "sponsor_urls": ext[:3]}})
    return items, {"ok": True, "cards": n_cards, "kept": len(items), "no_rules_url": sum(1 for i in items if not i["rules_url"])}


COLLECTORS = {"risein": risein, "taskmarket": taskmarket, "agenthansa": agenthansa, "hn": hn_signals, "github": github_bounties, "gigs": gigs_discovery}


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
