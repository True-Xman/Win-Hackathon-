#!/usr/bin/env python3
"""Money Hunter V1: collect -> normalize -> verify -> filter -> rank -> top 1-3. Read-only: never acts.

Usage: python3 hunt.py [inbox_dir] [--live]   (default inbox: ../inbox/*.json; --live adds read-only collectors)
       --preflight [--branch B] | --ack-notify | --persist "msg" [--branch B]   (scheduled run: write-access check, ack, verified commit+push)
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
import persist  # noqa: E402

REQUIRE_WRITE_ACCESS = True  # --live / --ack-notify refuse to start when this checkout cannot push (tests switch it off: no network)

CLAIMS = {}
HARD = ("kyc", "country", "paid_action", "onsite", "payout")  # + student (FAIL only)


def normalize(raw, src_file):
    kind = raw.get("kind") if raw.get("kind") in ("task", "signal") else "task"
    return {"id": f"{raw.get('source', src_file)}:{raw.get('title', '')[:60]}", "kind": kind,
            "source": raw.get("source", src_file), "title": raw.get("title"), "url": raw.get("url"),
            "text": raw.get("text") or "", "rules_url": raw.get("rules_url"), "rules_urls": raw.get("rules_urls") or [],
            "reward_usd": raw.get("reward_usd"), "deadline": raw.get("deadline"),
            "competition": raw.get("competition"), "signal": raw.get("signal") or {},
            "native_id": raw.get("native_id"), "gas_tx": raw.get("gas_tx"), "discovery_text": raw.get("discovery_text") or "",
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


BOT_WALL = re.compile(r"just a moment|checking your browser|verify(ies)? you are (a )?(human|not a bot)|performing security verification|protect against malicious bots|enable javascript and cookies|attention required|cf-challenge", re.I)
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
        age = (dt.date.today() - dt.date.fromisoformat(d["checked_at"])).days
        if d["how"] == "blocked" and age < 1:  # anti-bot wall: retry daily, not on every run
            return "", "blocked+cache"
        if age <= RULES_TTL_DAYS and d["chars"] > 0 and not (len(d["text"]) < 2500 and BOT_WALL.search(d["text"])):  # a cached anti-bot page is never "rules"
            return d["text"], d["how"] + "+cache"
    st, body = fetch(url)
    text, how = (html_to_text(body) if st == 200 and not body.startswith("%PDF") else ""), "static"
    if len(text) < 2500:
        r = render_text(url)
        if len(r) > len(text):
            text, how = r, "rendered"
    if len(text) < 2500 and BOT_WALL.search(text):  # anti-bot challenge page is NOT rules text: unreadable -> UNKNOWN (no bypass attempted)
        text, how = "", "blocked"
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
    best["verdict"] = "GAS-PREFILTER-OK" if best["ok"] else "FAIL"  # generic estimate = pre-filter ONLY, never GAS-COVERED
    return best


def _rpc(net, method, params):
    import urllib.request
    r = urllib.request.Request(RPC[net], json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                               {"content-type": "application/json", "user-agent": "MoneyHunter/1.0"})
    d = json.load(urllib.request.urlopen(r, timeout=20))
    if "error" in d:
        raise RuntimeError(d["error"].get("message", "rpc error"))
    return d["result"]


def tx_estimate(spec):
    """Transaction-specific, read-only estimate (eth_estimateGas + gasPrice + L1 data fee on Base via GasPriceOracle.getL1Fee; on Arbitrum the
    L1 component is already inside estimateGas units). Needs spec {network,to,data[,value,from]}. Safety: total x1.5 (price/size drift),
    balance must be >= GAS_MARGIN x that. Never signs/sends. -> dict with verdict GAS-COVERED|FAIL|UNKNOWN."""
    net = (spec or {}).get("network", "").lower()
    if net not in RPC or not spec.get("to"):
        return {"verdict": "UNKNOWN", "why": "tx spec missing/unsupported network"}
    call = {k: spec[k] for k in ("from", "to", "data", "value") if spec.get(k)}
    try:
        gas = int(_rpc(net, "eth_estimateGas", [call]), 16)
        price = int(_rpc(net, "eth_gasPrice", []), 16)
        l1 = 0
        if net == "base":
            raw = bytes.fromhex((spec.get("data") or "0x")[2:]) + b"\x00" * 110  # unsigned-tx envelope padding
            enc = "49948e0e" + "%064x" % 32 + "%064x" % len(raw) + raw.hex() + "00" * ((32 - len(raw) % 32) % 32)
            l1 = int(_rpc(net, "eth_call", [{"to": "0x420000000000000000000000000000000000000F", "data": "0x" + enc}, "latest"]), 16)
    except Exception as e:  # noqa: BLE001 - simulation needs the right sender/state; unknown is the honest answer
        return {"verdict": "UNKNOWN", "why": f"tx simulation failed: {str(e)[:120]}", "network": net}
    est = (gas * price + l1) * 1.5 / 1e18
    bal = json.load(open(GAS_BUDGET_F))["gas_eth"][net]
    return {"verdict": "GAS-COVERED" if bal >= GAS_MARGIN * est else "FAIL", "network": net, "gas_units": gas, "gas_price_wei": price, "l1_fee_wei": l1,
            "est_eth": est, "balance_eth": bal, "margin_x": round(bal / est, 1) if est else None, "basis": "tx-specific"}


def verify(c):
    # Every ranked sponsor/platform link is read (a bounty platform page can carry the binding KYC clause that the sponsor homepage lacks).
    urls = list(dict.fromkeys(([c["rules_url"]] if c["rules_url"] else []) + list(c.get("rules_urls") or [])))
    reads = [(u,) + rules_text(u) for u in urls]
    reads = [(u, t, "blocked" if h == "blocked+cache" else h) for u, t, h in reads]
    rules = "\n".join(f"[rules source: {u}]\n{t}" for u, t, _ in reads if t)
    c["rules_read"] = {"url": c["rules_url"], "how": (reads[0][2] if reads else None), "chars": len(rules),
                       "sources": [{"url": u, "how": h, "chars": len(t)} for u, t, h in reads]}
    c["rules_blocked"] = [u for u, t, h in reads if h == "blocked"]
    c["login_required"] = bool(reads) and len(rules) < 2500 and bool(LOGIN_WALL.search(rules))
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
            c["gas"] = gas_assess(c["_blob"])  # generic pre-filter
            if c["gas"]["verdict"] == "GAS-PREFILTER-OK":
                c["gas"] = tx_estimate(c.get("gas_tx")) if c.get("gas_tx") else dict(c["gas"], need="tx-specific estimate (gas_tx: network,to,data[,from]) before GAS-COVERED")
            v["paid_action"] = c["gas"]["verdict"] if c["gas"]["verdict"] in ("GAS-COVERED", "FAIL", "UNKNOWN") else "GAS-PREFILTER-OK"
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


def opportunity_tier(c):
    """Read-only visibility: explicit blockers reject; unanswered gates remain visible.

    VERIFIED requires explicit positive evidence across all relevant gates.
    PROMISING keeps worthwhile opportunities that still require manual checks.
    Neither category authorizes participation, financial operations, or claims.
    """
    if not worthy(c) or c["status"] == "REJECTED":
        return None
    return "VERIFIED" if c["status"] == "VERIFIED" else "PROMISING"


def qualified(c):
    """Eligible for read-only review, NOT cleared for participation."""
    return opportunity_tier(c) is not None


CRITICAL_DAYS = 3  # deadline within this many days (once per candidate) counts as a material change
NOTIFY_KEEP_DAYS = 90
MAX_NOTIFY_ATTEMPTS = 2  # unconfirmed announcements are repeated at most once; delivery is best-effort with NO guarantee (can be lost or duplicated)
LAST_DELTA = None


def notify_path():
    return os.path.join(EVID, "notify_state.json")


def load_notify_state():
    """Persistent (committed with evidence/) record of what the user was told.
    candidates[key] = {title, first_seen, last_seen, told: {tier, sig, deadline_alerted}, pending: None | {attempts, tier, sig, deadline_alerted}}
    login[key] = {title, first_seen, last_seen, told: bool, pending: None | {attempts}}; ack_enabled switches on the two-phase protocol."""
    try:
        ns = json.load(open(notify_path()))
    except (OSError, ValueError):
        ns = {}
    for k, v in (("candidates", {}), ("login", {}), ("ack_enabled", False)):
        ns.setdefault(k, v)
    return ns


def save_notify_state(ns):
    os.makedirs(EVID, exist_ok=True)
    json.dump(dict(ns, note="notification dedupe state, keyed by stable id (source#native_id or normalized URL, never title). "
                            "'pending' = announced but not yet acknowledged (hunt.py --ack-notify)"),
              open(notify_path(), "w"), indent=2, sort_keys=True)


def stable_key(c):
    """Same identity rule as dedupe(): source#native_id, else normalized URL, else source:title. Title alone is never the identity when an id/URL exists."""
    if c.get("native_id"):
        return f"{c['source']}#{c['native_id']}"
    u = (c.get("url") or "").split("#")[0].split("?")[0].rstrip("/").lower()
    return u or c["id"]


GATE_NAMES = ("kyc", "country", "paid_action", "onsite", "payout", "student")


def _gate_sig(c):
    """Eligibility signature: only PASS / FAIL / not-yet-known matter. UNKNOWN<->RISK<->INFO flips and repeated UNKNOWN are noise."""
    f = {"PASS": "PASS", "GAS-COVERED": "PASS", "FAIL": "FAIL"}
    return "".join(f.get(c["gates"][k], "?")[0] for k in GATE_NAMES)


def _announce(rec, snap, ack):
    """Record that an announcement is being made. Without ack protocol (legacy) or after MAX attempts the user counts as told; otherwise it stays
    pending until --ack-notify, so an announcement whose run died before the ack is repeated once next run (it can still be lost after the ack, or
    after MAX attempts). -> attempt number."""
    n = ((rec.get("pending") or {}).get("attempts") or 0) + 1
    if not ack or n >= MAX_NOTIFY_ATTEMPTS:
        rec["told"], rec["pending"] = snap, None
    else:
        rec["pending"] = dict(snap, attempts=n)
    return n


def notify_delta(top, ns, all_cands=(), login_items=(), today=None):
    """Compare current state with what the user was TOLD. Mutates `ns`; returns {new, changed, deadline, rejected, login}.
    Notifies ONLY for: new candidate, tier change (e.g. PROMISING->VERIFIED), a gate flipping to PASS/FAIL, deadline entering CRITICAL_DAYS (once),
    a previously-told candidate that is now REJECTED by a confirmed FAIL (correction; plain expiry is silent), and a NEW login-queue lead.
    Score / order / title / repeated UNKNOWN never notify; nothing is hidden from the shortlist."""
    import datetime as dt
    today = today or dt.date.today().isoformat()
    ns.setdefault("candidates", {}); ns.setdefault("login", {})
    ack = bool(ns.get("ack_enabled"))
    delta = {k: [] for k in ("new", "changed", "deadline", "rejected", "login")}
    seen = set()
    for c in top:
        k, sig, dl = stable_key(c), _gate_sig(c), days_left(c["deadline"])
        crit = dl is not None and 0 <= dl <= CRITICAL_DAYS
        seen.add(k)
        rec = ns["candidates"].setdefault(k, {"first_seen": today, "told": None, "pending": None})
        told = rec["told"]
        item = {"key": k, "title": c["title"], "lane": c["lane"], "tier": c["tier"], "url": c["url"], "reward_usd": c["reward_usd"],
                "pending_gates": [g for g, v in c["gates"].items() if v not in ("PASS", "GAS-COVERED")]}
        kind = why = None
        if told is None:
            kind = "new"
        else:
            why = ([f"{told['tier']}->{c['tier']}"] if told["tier"] != c["tier"] else []) + \
                  [f"{n} {told['sig'][i]}->{sig[i]}" for i, n in enumerate(GATE_NAMES) if told["sig"][i] != sig[i]]
            if why:
                kind = "changed"
            elif crit and not told["deadline_alerted"]:
                kind = "deadline"
        rec.update(title=c["title"], last_seen=today)
        if kind is None:
            rec["pending"] = None
            continue
        n = _announce(rec, {"tier": c["tier"], "sig": sig, "deadline_alerted": crit or bool(told and told["deadline_alerted"])}, ack)
        delta[kind].append(dict(item, why=why or [], days_left=dl if crit else None, reminder=n > 1))
    # correction: told earlier, now REJECTED (e.g. KYC=FAIL) -> it left the shortlist, so detect it from the full candidate list
    rejected = {stable_key(c): c for c in all_cands if c["status"] == "REJECTED"}
    for k, rec in ns["candidates"].items():
        c = rejected.get(k)
        if k in seen or c is None or rec["told"] is None or rec["told"]["tier"] == "REJECTED":
            continue
        snap = {"tier": "REJECTED", "sig": _gate_sig(c), "deadline_alerted": rec["told"]["deadline_alerted"]}
        if c["why"] == ["expired"]:  # routine expiry: no correction needed
            rec["told"], rec["pending"] = snap, None
            continue
        n = _announce(rec, snap, ack)
        delta["rejected"].append({"key": k, "title": c["title"], "lane": c["lane"], "tier": "REJECTED", "url": c["url"], "reward_usd": c["reward_usd"],
                                  "why": [w for w in c["why"] if w != "expired"], "reminder": n > 1})
    for k, q in login_items:
        rec = ns["login"].setdefault(k, {"first_seen": today, "told": False, "pending": None})
        rec.update(title=q["title"], last_seen=today)
        if rec["told"]:
            continue
        n = ((rec.get("pending") or {}).get("attempts") or 0) + 1
        rec["told"], rec["pending"] = (True, None) if (not ack or n >= MAX_NOTIFY_ATTEMPTS) else (False, {"attempts": n})
        delta["login"].append({"key": k, "title": q["title"], "lane": q["lane"], "url": q["url"], "reward_usd": q["reward_usd"], "reminder": n > 1})
    cutoff = (dt.date.fromisoformat(today) - dt.timedelta(days=NOTIFY_KEEP_DAYS)).isoformat()
    for group in (ns["candidates"], ns["login"]):
        for k in [k for k, v in group.items() if v.get("last_seen", today) < cutoff]:
            del group[k]
    return delta


def ack_notify(ns):
    """Called by the scheduled agent right BEFORE it sends its notification message (then commit+push evidence): marks every outstanding
    announcement as told and enables the two-phase protocol. If the agent never gets here (crash, push failure) the items stay pending and are
    repeated once in the next run. There is NO delivery receipt from the cloud and the ack precedes the actual send: a message can still be lost
    (ack done, send failed) or duplicated (send done, ack/push failed). This reduces loss; it guarantees neither exactly-once nor at-least-once."""
    n = 0
    for rec in ns.get("candidates", {}).values():
        if rec.get("pending"):
            rec["told"] = {k: rec["pending"][k] for k in ("tier", "sig", "deadline_alerted")}
            rec["pending"] = None
            n += 1
    for rec in ns.get("login", {}).values():
        if rec.get("pending"):
            rec["told"], rec["pending"] = True, None
            n += 1
    ns["ack_enabled"] = True
    return n


def notify_lines(delta):
    """Header for shortlist.md: ONE consolidated message or an explicit NONE (agent ends with NIST for this part)."""
    n = sum(len(v) for v in delta.values())
    if not n:
        return ["NOTIFY: NONE (no new or materially changed candidate/login lead since the last notification) -> nothing to send for candidates; "
                "if there is also no blocker and no user-action item, end the run with NIST.",
                "The lists below are reference only: do NOT notify for already-notified candidates (even PROMISING ones). "
                "A real blocker (collectors failing, push failing) or a user-action request must still be reported.", ""]
    def tag(i):
        base = f"[{'BUILD' if i['lane'] == 'BUILD' else 'FAST'}] {i['title']} ({i['tier']}" + (f", ${i['reward_usd']:,.0f}" if i.get("reward_usd") else "") + ")"
        return ("REMINDER (unconfirmed earlier) " if i.get("reminder") else "") + base
    lines = [f"NOTIFY: {len(delta['new'])} new, {len(delta['changed'])} changed, {len(delta['deadline'])} deadline, {len(delta['rejected'])} rejected, "
             f"{len(delta['login'])} login -> send ONE short consolidated message (no per-candidate messages); run `hunt.py --ack-notify` first:"]
    lines += [f"- NEW {tag(i)} | check: {','.join(i['pending_gates']) or '-'} | {i['url']}" for i in delta["new"]]
    lines += [f"- CHANGED {tag(i)} | {'; '.join(i['why'])} | {i['url']}" for i in delta["changed"]]
    lines += [f"- DEADLINE <={CRITICAL_DAYS}d ({i['days_left']}d left) {tag(i)} | {i['url']}" for i in delta["deadline"]]
    lines += [f"- CORRECTION: no longer qualified, FAIL on {','.join(i['why'])} {tag(i)} | {i['url']}" for i in delta["rejected"]]
    lines += [f"- LOGIN-QUEUE (needs manual login by the user) {tag(dict(i, tier='LOGIN'))} | {i['url']}" for i in delta["login"]]
    return lines + [""]


def run(inbox, live=None, health=None, notify=None):
    """notify = persistent notification state dict (mutated in place) or None (no dedupe header)."""
    global CLAIMS, LAST_DELTA
    CLAIMS = load_claims()
    raw = collect(inbox) if inbox else []
    cands = [verify(c) for c in dedupe(raw + [normalize(r, r.get("source", "live")) for r in (live or [])])]
    for c in cands:
        c["status"], c["why"] = status(c)
        c["score"] = score(c)
        c["tier"] = opportunity_tier(c)
    priority = {"VERIFIED": 0, "PROMISING": 1, None: 2}
    cands.sort(key=lambda c: (priority[c["tier"]], c["status"] == "LOGIN-REQUIRED-FOR-VERIFY", -c["score"]))
    queue = [{"title": c["title"], "lane": c["lane"], "url": c["url"], "rules_url": c["rules_url"], "reward_usd": c["reward_usd"],
              "deadline": c["deadline"], "score": c["score"]} for c in cands if c["status"] == "LOGIN-REQUIRED-FOR-VERIFY" and worthy(c)]
    login_items = [(stable_key(c), q) for c, q in zip([c for c in cands if c["status"] == "LOGIN-REQUIRED-FOR-VERIFY" and worthy(c)], queue)]
    json.dump({"note": "valuable leads whose rules need a manual login (user does it, not Hunter)", "queue": queue},
              open(os.path.join(EVID, "login_queue.json"), "w"), indent=2)
    verified = [c for c in cands if c["tier"] == "VERIFIED"]
    promising = [c for c in cands if c["tier"] == "PROMISING"]
    # At most three: preserve one discovery slot when both tiers exist.
    top = (verified[:2] + promising[:1]) if verified and promising else (verified or promising)[:3]
    for c in cands:
        c.pop("_blob", None)
    save("candidates.json", cands)
    if health is not None:
        save("source_health.json", health)
    LAST_DELTA = notify_delta(top, notify, cands, login_items) if notify is not None else None
    lines = (notify_lines(LAST_DELTA) if LAST_DELTA is not None else []) + ["# Shortlist (read-only; user approval required)\n",
             "VERIFIED = all required gates explicitly supported.",
             "PROMISING = worthwhile without explicit blocker; UNKNOWN/RISK requires checking.",
             "Neither tier authorizes submission, payment, signing, or claiming.\n"]
    for tier in ("VERIFIED", "PROMISING"):
        lines.append(f"## {tier}")
        group = [c for c in top if c["tier"] == tier]
        if not group:
            lines.append("- None selected.")
        for c in group:
            pending = [f"{k}={v}" for k, v in c["gates"].items() if v not in ("PASS", "GAS-COVERED")]
            if c.get("rules_blocked"):
                pending.append("rules UNREADABLE (anti-bot wall): " + ", ".join(c["rules_blocked"]))
            lines.append(f"- [{'BUILD MONEY' if c['lane'] == 'BUILD' else 'FAST MONEY'}] {c['title']} | score={c['score']} | {c['status']}\n"
                         f"  {c['url']}\n"
                         f"  gates: {c['gates']}\n"
                         f"  check before participation/payout: {', '.join(pending) if pending else '-'}"
                         + (f"\n  build value: {c['build']}" if c.get("build") else "")
                         + (f"\n  GAS-COVERED (tx-specific): {c['gas']} -- every tx needs user approval"
                            if c["gates"]["paid_action"] == "GAS-COVERED" else ""))
    if not top:
        lines.append("Hich lead-e worthwhile bedune blocker-e confirmed peyda nashod. Details: out/candidates.json.")
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


def main(args):
    """CLI entry (testable). --force checks EVERY source (ignores cooldown) but is a manual probe: it never touches source_state.json
    (empty_runs / cooldown_until belong to the scheduled run)."""
    live, force = "--live" in args, "--force" in args
    opt = lambda name: next((a for a in args[args.index(name) + 1:][:1] if not a.startswith("--")), None) if name in args else None
    branch = opt("--branch")
    if "--preflight" in args or "--persist" in args or (REQUIRE_WRITE_ACCESS and ("--ack-notify" in args or (live and not force))):
        if "--persist" in args:  # scheduled agent, last step: commit evidence + push + verify on the remote
            ok, why = persist.persist(opt("--persist") or "hunter run", branch)
            print(f"PERSIST: {'OK' if ok else 'FAILED'} {why}")
            if not ok:
                print("PERSIST FAILED = BLOCKER: remote notify_state.json is unchanged, so pending announcements are repeated next run. "
                      "Still send the notification, and report this blocker in the same message.")
                raise SystemExit(2)
            return [], []
        ok, why = persist.preflight(branch)
        print(f"PREFLIGHT: {'OK' if ok else 'FAIL'} {why}")
        if not ok:
            print("PREFLIGHT FAIL = BLOCKER: hunt NOT started" + (", notification NOT acknowledged" if "--ack-notify" in args else "") + ". Report it; do not work around it.")
            raise SystemExit(1)
        if "--preflight" in args:
            return [], []
    if "--ack-notify" in args:  # scheduled agent: call right before sending the notification, then commit+push evidence/
        ns = load_notify_state()
        n = ack_notify(ns)
        save_notify_state(ns)
        print(f"acknowledged {n} announcement(s)")
        return [], []
    args = [a for a in args if not a.startswith("--") and a not in (opt("--branch"), opt("--persist"))]
    inbox = args[0] if args else os.path.join(os.path.dirname(DATA), "inbox")
    st, cool = ({}, set()) if not live else cooling_down()
    names = [n for n in COLLECTORS if force or n not in cool]
    items, health = collect_live(names) if live else ([], None)
    for n in cool - set(names):
        health[n] = {"skipped": "cooldown until " + st[n]["cooldown_until"]}
    nstate = load_notify_state() if live else None
    cands, top = run(inbox, items, health, nstate)
    if live and not force:  # --force is a manual probe: it must not consume notifications or touch cooldown state
        update_state(st, names, cands)
        save_notify_state(nstate)
    if LAST_DELTA is not None:
        print("\n".join(notify_lines(LAST_DELTA)[:-1]))
    print(f"{len(cands)} collected, {sum(c['status'] != 'REJECTED' for c in cands)} alive, {sum(qualified(c) for c in cands)} qualified, {len(top)} shortlisted; cooling={sorted(cool)}")
    return cands, top


if __name__ == "__main__":
    main(sys.argv[1:])
