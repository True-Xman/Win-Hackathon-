#!/usr/bin/env python3
"""Discover open opportunities from every reachable source -> data/candidates.json.

Usage: python3 radar/tools/collect.py [source ...]     (no args = all)
Each collector returns normalized records via common.candidate(). Collectors that hit
a wall record it in data/source_health.json so blocked sources are visible, not silent.
"""
import re
import sys
import urllib.parse

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import candidate, days_left, fetch, fetch_json, html_to_text, load, now_utc, parse_dt, save  # noqa: E402

AI_WORDS = re.compile(r"\b(ai|agent|agents|agentic|mcp|llm|claude|gpt|openai|anthropic|coding|devtool|voice|automation|copilot|rag)\b", re.I)


def tag_ai(*texts):
    return ["ai-relevant"] if AI_WORDS.search(" ".join(t for t in texts if t)) else []


# ---------------- Superteam Earn (public JSON API, USDC/USDG payouts) ----------------
def superteam():
    st, items = fetch_json("https://earn.superteam.fun/api/listings?tab=open&take=200")
    if not isinstance(items, list):
        return [], dict(status=st, ok=False, note="listing API failed")
    out, details = [], {}
    for it in items:
        if it.get("status") != "OPEN" or (days_left(it.get("deadline")) or 0) < 0:
            continue
        _, det = fetch_json(f"https://earn.superteam.fun/api/listings/details/{it['slug']}")  # region/eligibility/description live only here
        if det:
            details[it["slug"]] = det
        url = f"https://earn.superteam.fun/listing/{it['slug']}"
        out.append(candidate(
            id=f"superteam:{it['slug']}", name=it["title"], organizer=(it.get("sponsor") or {}).get("name"),
            platform="Superteam Earn", url=url, deadline=it.get("deadline"), mode="online",
            prize_text=f"{it.get('rewardAmount')} {it.get('token')}", prize_usd=it.get("rewardAmount"),
            payout=f"on-chain {it.get('token')} (Solana)", tags=[it["type"]] + tag_ai(it["title"]),
            notes=[f"agentAccess={it.get('agentAccess')}", f"submissions={(it.get('_count') or {}).get('Submission')}"],
            source_evidence="earn.superteam.fun/api/listings?tab=open"))
    save("superteam_details.json", details)
    return out, dict(status=st, ok=True, n=len(out), details=len(details))


# ---------------- lablab.ai (event list embedded in page payload) ----------------
def lablab():
    st, h = fetch("https://lablab.ai/event")
    if st != 200:
        return [], dict(status=st, ok=False)
    h = h.replace('\\"', '"').replace("\\u0026", "&")
    out, seen = [], set()
    for m in re.finditer(r'"endAt":"([^"]+)","startAt":"([^"]+)"', h):
        s = re.search(r'"slug":"([a-z0-9\-]+)"', h[m.end():m.end() + 6000])
        names = re.findall(r'"name":"([^"]+)"', h[max(0, m.start() - 6000):m.start()])
        if not s or s.group(1) in seen or (days_left(m.group(1)) or -1) < 0:
            continue
        seen.add(s.group(1))
        nm = names[-1] if names else s.group(1)
        out.append(candidate(
            id=f"lablab:{s.group(1)}", name=nm, platform="lablab.ai", organizer="lablab.ai (+sponsors)",
            url=f"https://lablab.ai/ai-hackathons/{s.group(1)}", start=m.group(2), deadline=m.group(1),
            tags=["hackathon"] + tag_ai(nm), source_evidence="lablab.ai/event page payload"))
    return out, dict(status=st, ok=True, n=len(out))


# ---------------- GenAI Works ----------------
def genai_works():
    st, h = fetch("https://hackathon.genai.works/")
    if st != 200:
        return [], dict(status=st, ok=False)
    t = html_to_text(h)
    if "Open Agent Hackathon" not in t:
        return [], dict(status=st, ok=True, n=0, note="event text not found; page changed?")
    return [candidate(id="genai:open-agent-2026", name="Open Agent Hackathon 2026", organizer="GenAI Works",
                      platform="genai.works", url="https://hackathon.genai.works/", deadline="2026-10-13T00:00:00+00:00",
                      start="2026-10-15T00:00:00+00:00", mode="online", tags=["hackathon", "ai-relevant"],
                      notes=["dates from homepage text; registration closes Oct 13 00:00 UTC"],
                      source_evidence="hackathon.genai.works homepage")], dict(status=st, ok=True, n=1)


# ---------------- Hacker News (Algolia) : recent hackathon posts ----------------
def hackernews():
    since = int(now_utc().timestamp()) - 30 * 86400
    out, st = {}, 0
    for q in ["hackathon", "bounty"]:
        st, d = fetch_json(f"https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&numericFilters=created_at_i%3E{since}&hitsPerPage=40")
        for h in (d or {}).get("hits", []):
            out[h["objectID"]] = candidate(id=f"hn:{h['objectID']}", name=h.get("title"), platform="HN", tags=["lead-only"] + tag_ai(h.get("title")),
                                           url=h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}", source_evidence="hn.algolia.com")
    return list(out.values()), dict(status=st, ok=bool(out), n=len(out))


SOURCES = dict(superteam=superteam, lablab=lablab, genai_works=genai_works, hackernews=hackernews)

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(SOURCES)
    allc, health = [], {}
    for name in wanted:
        try:
            recs, h = SOURCES[name]()
        except Exception as e:  # noqa: BLE001
            recs, h = [], dict(ok=False, error=repr(e))
        health[name] = {**h, "checked": now_utc().isoformat()}
        for r in recs:
            r["collector"] = name
        allc += recs
        print(f"{name:12} ok={h.get('ok')} n={len(recs)}" + ("" if h.get("ok") else f"  !! status={h.get('status')} {h.get('note', '')} {h.get('error', '')}"))
    # blocked-by-site sources are recorded explicitly (checked 2026-09-30)
    health["devpost"] = dict(ok=False, note="403 from site WAF (awselb) on browse + /api/hackathons; use WebSearch or per-page fetch")
    health["github_search"] = dict(ok=False, note="BLOCKED by session policy: api.github.com/search returns 403 'sessions are bound to their configured repositories'. Not bypassed.")
    health["dorahacks"] = dict(ok=False, note="405 + x-amzn-waf-action: captcha; API not scriptable")
    # partial runs must not clobber other sources: keep records/health from collectors we did not run
    kept = {k: v for k, v in (load("candidates.json", {}) or {}).items() if v.get("collector") not in wanted}
    save("candidates.json", {**kept, **{c["id"]: c for c in allc}})
    save("source_health.json", {**{k: v for k, v in (load("source_health.json", {}) or {}).items() if k not in wanted}, **health})
    print("total", len(allc))
