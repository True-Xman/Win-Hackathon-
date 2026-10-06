#!/usr/bin/env python3
"""Money Hunter V1: collect -> normalize -> verify -> filter -> rank -> top 1-3. Read-only: never acts.

Usage: python3 hunt.py [inbox_dir] [--live]   (default inbox: ../inbox/*.json; --live adds read-only collectors)
Sources are plain JSON lists (one file per source). Each item:
  {"kind": "task"|"signal", "source": str, "title": str, "url": str,
   "text": str (rules/description; or "rules_url" to fetch), "reward_usd": num|null,
   "deadline": iso|null, "competition": int|null (submissions so far),
   "signal": {"budget_mentioned": bool, "contact_public": bool, "urgency": bool}}   # signals only
Output: ../out/candidates.json (everything, with evidence) + ../out/shortlist.md (<=3).
"""
import hashlib
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, days_left, fetch, html_to_text, load, render_text, save  # noqa: E402
from gates import analyze, load_text  # noqa: E402
from collectors import COLLECTORS, collect_live  # noqa: E402

CLAIMS = {}
HARD = ("kyc", "country", "paid_action", "onsite", "payout")  # + student (FAIL only)


def normalize(raw, src_file):
    kind = raw.get("kind") if raw.get("kind") in ("task", "signal") else "task"
    return {"id": f"{raw.get('source', src_file)}:{raw.get('title', '')[:60]}", "kind": kind,
            "source": raw.get("source", src_file), "title": raw.get("title"), "url": raw.get("url"),
            "text": raw.get("text") or "", "rules_url": raw.get("rules_url"),
            "reward_usd": raw.get("reward_usd"), "deadline": raw.get("deadline"),
            "competition": raw.get("competition"), "signal": raw.get("signal") or {},
            "native_id": raw.get("native_id"), "discovery_text": raw.get("discovery_text") or "",
            "lane": raw.get("lane") or "FAST", "provenance": raw.get("provenance") or {"file": src_file}}


def collect(inbox):
    out = []
    for f in sorted(os.listdir(inbox)):
        if f.endswith(".json"):
            import json
            for raw in json.load(open(os.path.join(inbox, f))):
                out.append(normalize(raw, f[:-5]))
    return out


def dedupe(cands):
    """Same URL (or same source+native title) twice -> keep first. Provenance of dropped dupes is merged in."""
    seen, out = {}, []
    for c in cands:
        k = f"{c['source']}#{c['native_id']}" if c.get("native_id") else (c["url"] or "").rstrip("/").lower() or c["id"]
        if k in seen:
            seen[k]["provenance"].setdefault("duplicates", []).append(c["provenance"])
            continue
        seen[k] = c
        out.append(c)
    return out


def load_claims():
    """Cached primary-source evidence (make_money/evidence/claims.json) -> {(source, gate): claim}. Stale PASS/FAIL claims are dropped."""
    import datetime as dt
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evidence", "claims.json")
    out = {}
    if os.path.exists(p):
        import json
        for cl in json.load(open(p))["claims"]:
            age = (dt.date.today() - dt.date.fromisoformat(cl["checked_at"])).days
            cl["stale"] = age > cl.get("ttl_days", 30)
            out[(cl["source"], cl["gate"])] = cl
    return out


LOGIN_WALL = re.compile(r"continue with (github|google|discord|email)|sign in to (continue|view|see)|log ?in to (continue|view|see)|sign up to (view|see)", re.I)
EVID = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evidence")
RULES_TTL_DAYS = 7


def rules_text(url):
    """Sponsor/primary rules text for ONE opportunity. Cached in evidence/rules_cache (re-fetched only when older than RULES_TTL_DAYS).
    Static GET first; if the page is a JS shell (<800 chars) fall back to read-only headless render. Returns (text, how)."""
    import datetime as dt
    os.makedirs(os.path.join(EVID, "rules_cache"), exist_ok=True)
    f = os.path.join(EVID, "rules_cache", hashlib.sha256(url.encode()).hexdigest()[:16] + ".json")
    if os.path.exists(f):
        d = json.load(open(f))
        if (dt.date.today() - dt.date.fromisoformat(d["checked_at"])).days <= RULES_TTL_DAYS and d["chars"] > 0:
            return d["text"], d["how"] + "+cache"
    st, body = fetch(url)
    text, how = (html_to_text(body) if st == 200 and not body.startswith("%PDF") else ""), "static"
    if len(text) < 2500:
        r = render_text(url)
        if len(r) > len(text):
            text, how = r, "rendered"
    d = {"url": url, "checked_at": dt.date.today().isoformat(), "how": how, "chars": len(text), "text": text[:40000]}
    json.dump(d, open(f, "w"), ensure_ascii=False)
    return d["text"], how


GAS_BUDGET_F = os.path.join(EVID, "wallet_budget.json")
GAS_MARGIN = 3.0  # balance must be >= GAS_MARGIN x estimated cost
RPC = {"base": "https://mainnet.base.org", "arbitrum": "https://arb1.arbitrum.io/rpc"}


def rpc_gas_price_wei(net):
    """Read-only eth_gasPrice. None on failure."""
    import urllib.request
    try:
        r = urllib.request.Request(RPC[net], json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_gasPrice", "params": []}).encode(),
                                   {"content-type": "application/json", "user-agent": "MoneyHunter/1.0"})
        return int(json.load(urllib.request.urlopen(r, timeout=15))["result"], 16)
    except Exception:  # noqa: BLE001
        return None


def gas_assess(text):
    """-> {verdict: GAS-COVERED|FAIL|UNKNOWN, network, txs, est_eth, balance_eth, margin}. Estimate = txs x 150k gas x live gasPrice x 2 (L1 data fee headroom)."""
    nets = [n for n in ("base", "arbitrum") if re.search(r"\b%s\b" % n, text, re.I)]
    other = re.search(r"ethereum mainnet|\bmainnet\b(?! (of )?(base|arbitrum))|\bbsc\b|bnb chain|polygon|optimism|solana|avalanche|\bl1\b", text, re.I)
    if not nets:
        return {"verdict": "FAIL", "why": "gas on unsupported network (only Base/Arbitrum covered)"} if other else {"verdict": "UNKNOWN", "why": "network not stated"}
    bal = json.load(open(GAS_BUDGET_F))["gas_eth"]
    txs = max(1, min(5, len(re.findall(r"\b(transactions?|claim|mint|approve|register|deploy|transfer)\b", text, re.I))))
    best = None
    for n in nets:
        price = rpc_gas_price_wei(n)
        if price is None:
            continue
        est = txs * 150_000 * price * 2 / 1e18
        ok = bal[n] >= GAS_MARGIN * est
        cur = {"network": n, "txs": txs, "est_eth": est, "balance_eth": bal[n], "margin_x": round(bal[n] / est, 1) if est else None, "ok": ok}
        if ok:
            best = cur
            break
        best = best or cur
    if best is None:
        return {"verdict": "UNKNOWN", "why": "gas price unreadable"}
    best["verdict"] = "GAS-COVERED" if best["ok"] else "FAIL"
    return best


def verify(c):
    rules, how = (rules_text(c["rules_url"]) if c["rules_url"] else ("", None))
    c["rules_read"] = {"url": c["rules_url"], "how": how, "chars": len(rules)}
    c["login_required"] = bool(c["rules_url"]) and len(rules) < 2500 and bool(LOGIN_WALL.search(rules))
    c["_blob"] = f"{c['discovery_text']}\n{c['text']}\n{rules}"[:60000]
    g = analyze(c["text"] + "\n" + rules, c["url"] or c["title"])["gates"]
    if c["discovery_text"]:  # listing text is the platform's claim: it may only ADD a FAIL, never a PASS
        for k, x in analyze(c["discovery_text"], c["url"])["gates"].items():
            if x["verdict"] == "FAIL" and g[k]["verdict"] != "FAIL":
                g[k] = {"verdict": "FAIL", "evidence": [f"[listing] {e}" for e in x["evidence"]], "positive_evidence": []}
    v = {k: g[k]["verdict"] for k in (*HARD, "student")}
    ev = {k: g[k]["evidence"][:2] + g[k]["positive_evidence"][:1] for k in v if g[k]["evidence"] or g[k]["positive_evidence"]}
    for gate in v:  # cached primary-source claims: PASS never overrides a FAIL found in the item text itself
        cl = CLAIMS.get((f"{c['source']}:{c['native_id']}", gate)) or CLAIMS.get((c["source"], gate))  # per-opportunity claim wins
        if not cl or cl["stale"] or cl["verdict"] not in ("PASS", "FAIL"):
            continue
        if cl["verdict"] == "FAIL" or v[gate] != "FAIL":
            v[gate] = cl["verdict"]
            ev.setdefault(gate, []).append(f"[claim {cl['checked_at']}] {cl['quote']} ({cl['url']})")
    if c["kind"] == "signal" and v["payout"] != "FAIL":
        # a signal has no stated payout rail: crypto must be agreed later -> UNKNOWN, never PASS
        v["payout"] = "PASS" if v["payout"] == "PASS" else "UNKNOWN"
    # gas-only spend: NOT a PASS by itself. Network must be Base/Arbitrum, estimated gas (live eth_gasPrice, read-only RPC) must fit the
    # user-reported balance with a safety margin; any other fee/stake/deposit stays FAIL. Even when covered, every tx needs user approval.
    c["gas_only"], c["gas"] = False, None
    if v["paid_action"] == "FAIL":
        t = " ".join(ev.get("paid_action", []))
        if re.search(r"\bgas\b", t, re.I) and not re.search(r"entry fee|registration fee|submission fee|stake|deposit|purchase|\bpay\b[^.]{0,40}(USDC|USDT|\$|usd)|\d+(\.\d+)? ?(USDC|USDT|USD)", t, re.I):
            c["gas_only"] = True
            c["gas"] = gas_assess(c["_blob"])
            v["paid_action"] = c["gas"]["verdict"]
    c["gates"], c["evidence"] = v, ev
    return c


def status(c):
    v = c["gates"]
    fails = [k for k, x in v.items() if x == "FAIL"]
    dl = days_left(c["deadline"])
    if dl is not None and dl < 0:
        fails.append("expired")
    if fails:
        return "REJECTED", fails
    if c.get("login_required") and not (v["payout"] == "PASS" and v["paid_action"] == "PASS"):
        return "LOGIN-REQUIRED-FOR-VERIFY", ["rules behind login (not read; login is never done by Hunter)"]
    unk = [k for k in ("kyc", "country", "paid_action", "onsite", "payout") if v[k] not in ("PASS", "GAS-COVERED")]
    return ("VERIFIED" if not unk else "NEEDS_CHECK"), unk  # RISK/INFO/UNKNOWN all count as unverified


def _n(pat, text):
    return len(re.findall(pat, text, re.I))


def build_value(c):
    """BUILD MONEY value parts (heuristics over opportunity text; each part is capped, so no single factor dominates).
    ai_leverage 0-10 | technical_fit 0-4 | prize 0-10 | win_chance 0-8 | timing 0-5 | outside_control 0..-9. Gates/KYC/spend/payout are scored in score()."""
    t = c.get("_blob") or ""
    ai = min(10, 2 * _n(r"\b(ai|agents?|llm|mcp|claude|gpt|automation|copilot)\b", t) + 2 * _n(r"\b(tutorial|documentation|content|research|write|report|demo|prototype)\b", t))
    ai -= 4 * bool(re.search(r"hardware|physical|in[- ]person|on-?site|video (recording|call)", t, re.I))
    fit = min(4, _n(r"\b(software|app|dapp|smart contract|api|sdk|tool|code|build|prototype|frontend|backend|bug)\b", t))
    usd = c["reward_usd"] or 0
    prize = round(min(10, max(0, (math.log10(usd) - 2) * 3.3)), 1) if usd >= 100 else 0
    comp = c["competition"]
    win = round(8 * min(1, 5 / comp), 1) if comp else 3.0  # competition unknown -> neutral-low prior, never optimistic
    dl = days_left(c["deadline"])
    timing = 0 if dl is None else (0 if dl < 2 else 5 if dl <= 45 else 3 if dl <= 120 else 2)
    out = -3 * min(3, _n(r"team of \d|teams? (only|required)|existing (users|customers|audience)|traction|monthly active|audited|mainnet (deploy|launch)|in[- ]person|on-?site", t))
    return {"ai_leverage": max(0, ai), "technical_fit": fit, "prize": prize, "win_chance": win, "timing": timing, "outside_control": out}


def score(c):
    v, s = c["gates"], 0.0
    s += sum(10 for k in ("kyc", "country", "paid_action", "onsite", "payout") if v[k] == "PASS")
    s -= sum(6 for k in ("kyc", "country", "paid_action", "onsite") if v[k] == "RISK")
    s += 15 if v["payout"] == "PASS" else 0  # crypto payout is a hard requirement: weight it
    r = c["reward_usd"] or 0
    if c["lane"] == "BUILD":
        c["build"] = build_value(c)
        return round(s + sum(c["build"].values()), 1)
    if c["kind"] == "task":
        s += min(15, 5 * math.log10(1 + fast_value(c)["ev_per_hour"]))  # reward-to-hassle, not raw dollars
    if c["kind"] == "signal":
        sg = c["signal"]
        s += 4 * bool(sg.get("budget_mentioned")) + 3 * bool(sg.get("contact_public")) + 2 * bool(sg.get("urgency"))
    return round(s, 1)


MIN_EV_PER_HOUR = 2.0  # expected USD per hour of effort*friction; no minimum dollar amount (a $2 task with ~no hassle is fine)


def fast_value(c):
    """Reward-to-hassle for FAST tasks. p_win falls with competition (unknown -> 0.3, never optimistic); effort_hours is a text-size/keyword
    estimate; friction grows with unverified KYC/country and unclear payout path. ev_per_hour = reward*p_win / (hours*friction)."""
    t = c.get("_blob") or (c.get("text") or "")
    comp = c.get("competition")
    p = 0.3 if comp is None else 1 / (1 + comp / 3)
    hours = max(0.25, len(t) / 1500)
    hours *= 2 if re.search(r"\b(video|design|logo|illustrat|animation|research|build|prototype|code|script)\b", t, re.I) else 1
    v = c["gates"]
    friction = 1 + 0.4 * sum(v[k] not in ("PASS",) for k in ("kyc", "country")) + (0.5 if v["payout"] != "PASS" else 0) + (0.5 if v["onsite"] == "RISK" else 0)
    ev = (c["reward_usd"] or 0) * p / (hours * friction)
    return {"p_win": round(p, 2), "hours": round(hours, 2), "friction": round(friction, 2), "ev_per_hour": round(ev, 2)}


def worthy(c):
    if c["lane"] == "BUILD":
        return sum(c.get("build", {}).values()) >= 15
    c["hassle"] = fast_value(c)
    return (c["reward_usd"] or 0) > 0 and c["hassle"]["ev_per_hour"] >= MIN_EV_PER_HOUR


def qualified(c):
    """Shortlist bar: no FAIL; crypto payout PASS and zero-spend (paid_action) PASS, each from explicit text; onsite not RISK.
    KYC/country UNKNOWN is allowed (absence of a clause is neither PASS nor FAIL) but is flagged and must be user-checked."""
    v = c["gates"]
    return worthy(c) and c["status"] != "REJECTED" and v["payout"] == "PASS" and v["paid_action"] in ("PASS", "GAS-COVERED") and v["onsite"] != "RISK"


def run(inbox, live=None, health=None):
    global CLAIMS
    CLAIMS = load_claims()
    raw = collect(inbox) if inbox else []
    cands = [verify(c) for c in dedupe(raw + [normalize(r, r.get("source", "live")) for r in (live or [])])]
    for c in cands:
        c["status"], c["why"] = status(c)
        c["score"] = score(c)
    cands.sort(key=lambda c: (c["status"] != "VERIFIED", c["status"] == "REJECTED", -c["score"]))
    queue = [{"title": c["title"], "lane": c["lane"], "url": c["url"], "rules_url": c["rules_url"], "reward_usd": c["reward_usd"],
              "deadline": c["deadline"], "score": c["score"]} for c in cands if c["status"] == "LOGIN-REQUIRED-FOR-VERIFY" and worthy(c)]
    json.dump({"note": "valuable leads whose rules need a manual login (user does it, not Hunter)", "queue": queue},
              open(os.path.join(EVID, "login_queue.json"), "w"), indent=2)
    top = [c for c in cands if qualified(c)][:3]  # weak candidates are never forced in
    for c in cands:
        c.pop("_blob", None)
    save("candidates.json", cands)
    if health is not None:
        save("source_health.json", health)
    lines = ["# Shortlist (read-only; waits for user approval)\n"]
    for i, c in enumerate(top, 1):
        lines.append(f"{i}. [{'BUILD MONEY' if c['lane'] == 'BUILD' else 'FAST MONEY'}] {c['title']} - {c['status']} score={c['score']}\n   {c['url']}\n"
                     f"   gates: {c['gates']}\n   unverified (user must check): {c['why'] if c['status'] != 'VERIFIED' else '-'}"
                     + (f"\n   build value: {c['build']}" if c.get('build') else "")
                     + (f"\n   GAS-COVERED: {c['gas']} -- every tx still needs your approval" if c["gates"]["paid_action"] == "GAS-COVERED" else ""))
    if not top:
        lines.append("Hich candidate-e qualified nist (payout=PASS + paid_action=PASS + no FAIL lazem). Leads: out/candidates.json.")
    open(os.path.join(DATA, "shortlist.md"), "w").write("\n".join(lines) + "\n")
    return cands, top


STATE_F = os.path.join(EVID, "source_state.json")
COOLDOWN_AFTER, COOLDOWN_DAYS, NO_COOLDOWN = 3, 7, ("gigs", "github")  # discovery-only/stub sources never cool down


def cooling_down():
    import datetime as dt
    st = json.load(open(STATE_F)) if os.path.exists(STATE_F) else {}
    now = dt.date.today().isoformat()
    return st, {n for n, v in st.items() if v.get("cooldown_until", "") > now}


def update_state(st, ran, cands):
    """A source with no usable candidate (qualified or valuable login-queue lead) COOLDOWN_AFTER runs in a row sleeps COOLDOWN_DAYS days."""
    import datetime as dt
    usable = {c["source"] for c in cands if qualified(c) or (c["status"] == "LOGIN-REQUIRED-FOR-VERIFY" and worthy(c))}
    for n in ran:
        if n in NO_COOLDOWN:
            continue
        v = st.setdefault(n, {})
        v["empty_runs"] = 0 if n in usable else v.get("empty_runs", 0) + 1
        if v["empty_runs"] >= COOLDOWN_AFTER:
            v["cooldown_until"] = (dt.date.today() + dt.timedelta(days=COOLDOWN_DAYS)).isoformat()
            v["empty_runs"] = 0
    json.dump(st, open(STATE_F, "w"), indent=2)


if __name__ == "__main__":
    args = sys.argv[1:]
    live, force = "--live" in args, "--force" in args
    args = [a for a in args if not a.startswith("--")]
    inbox = args[0] if args else os.path.join(os.path.dirname(DATA), "inbox")
    st, cool = ({}, set()) if not live else cooling_down()
    names = [n for n in COLLECTORS if force or n not in cool]
    items, health = collect_live(names) if live else ([], None)
    for n in cool - set(names):
        health[n] = {"skipped": "cooldown until " + st[n]["cooldown_until"]}
    cands, top = run(inbox, items, health)
    if live:
        update_state(st, names, cands)
    print(f"{len(cands)} collected, {sum(c['status'] != 'REJECTED' for c in cands)} alive, {sum(qualified(c) for c in cands)} qualified, {len(top)} shortlisted; cooling={sorted(cool)}")
