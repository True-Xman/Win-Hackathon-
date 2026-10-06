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
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, days_left, load, save  # noqa: E402
from gates import analyze, load_text  # noqa: E402
from collectors import collect_live  # noqa: E402

CLAIMS = {}
HARD = ("kyc", "country", "paid_action", "onsite", "payout")  # + student (FAIL only)


def normalize(raw, src_file):
    kind = raw.get("kind") if raw.get("kind") in ("task", "signal") else "task"
    return {"id": f"{raw.get('source', src_file)}:{raw.get('title', '')[:60]}", "kind": kind,
            "source": raw.get("source", src_file), "title": raw.get("title"), "url": raw.get("url"),
            "text": raw.get("text") or "", "rules_url": raw.get("rules_url"),
            "reward_usd": raw.get("reward_usd"), "deadline": raw.get("deadline"),
            "competition": raw.get("competition"), "signal": raw.get("signal") or {},
            "native_id": raw.get("native_id"), "provenance": raw.get("provenance") or {"file": src_file}}


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


def verify(c):
    text = c["text"] + ("\n" + load_text(c["rules_url"]) if c["rules_url"] else "")
    g = analyze(text, c["url"] or c["title"])["gates"]
    v = {k: g[k]["verdict"] for k in (*HARD, "student")}
    ev = {k: g[k]["evidence"][:2] + g[k]["positive_evidence"][:1] for k in v if g[k]["evidence"] or g[k]["positive_evidence"]}
    for gate in v:  # cached primary-source claims: PASS never overrides a FAIL found in the item text itself
        cl = CLAIMS.get((c["source"], gate))
        if not cl or cl["stale"] or cl["verdict"] not in ("PASS", "FAIL"):
            continue
        if cl["verdict"] == "FAIL" or v[gate] != "FAIL":
            v[gate] = cl["verdict"]
            ev.setdefault(gate, []).append(f"[claim {cl['checked_at']}] {cl['quote']} ({cl['url']})")
    if c["kind"] == "signal" and v["payout"] != "FAIL":
        # a signal has no stated payout rail: crypto must be agreed later -> UNKNOWN, never PASS
        v["payout"] = "PASS" if v["payout"] == "PASS" else "UNKNOWN"
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
    unk = [k for k in ("kyc", "country", "paid_action", "onsite", "payout") if v[k] != "PASS"]
    return ("VERIFIED" if not unk else "NEEDS_CHECK"), unk  # RISK/INFO/UNKNOWN all count as unverified


def score(c):
    v, s = c["gates"], 0.0
    s += sum(10 for k in ("kyc", "country", "paid_action", "onsite", "payout") if v[k] == "PASS")
    s -= sum(6 for k in ("kyc", "country", "paid_action", "onsite") if v[k] == "RISK")
    s += 15 if v["payout"] == "PASS" else 0  # crypto payout is a hard requirement: weight it
    r = c["reward_usd"] or 0
    s += min(r, 500) / 50
    if c["kind"] == "task" and c["competition"] is not None:
        s -= min(c["competition"], 100) / 10
    if c["kind"] == "signal":
        sg = c["signal"]
        s += 4 * bool(sg.get("budget_mentioned")) + 3 * bool(sg.get("contact_public")) + 2 * bool(sg.get("urgency"))
    return round(s, 1)


def qualified(c):
    """Shortlist bar: no FAIL, and the two user-critical gates explicitly PASS (crypto payout + no KYC). Others may stay unverified (shown)."""
    return c["status"] != "REJECTED" and c["gates"]["payout"] == "PASS" and c["gates"]["kyc"] == "PASS"


def run(inbox, live=None, health=None):
    global CLAIMS
    CLAIMS = load_claims()
    raw = collect(inbox) if inbox else []
    cands = [verify(c) for c in dedupe(raw + [normalize(r, r.get("source", "live")) for r in (live or [])])]
    for c in cands:
        c["status"], c["why"] = status(c)
        c["score"] = score(c)
    cands.sort(key=lambda c: (c["status"] != "VERIFIED", c["status"] == "REJECTED", -c["score"]))
    top = [c for c in cands if qualified(c)][:3]  # weak candidates are never forced in
    save("candidates.json", cands)
    if health is not None:
        save("source_health.json", health)
    lines = ["# Shortlist (read-only; waits for user approval)\n"]
    for i, c in enumerate(top, 1):
        lines.append(f"{i}. [{c['kind']}] {c['title']} - {c['status']} score={c['score']}\n   {c['url']}\n"
                     f"   gates: {c['gates']}\n   unverified: {c['why'] if c['status'] != 'VERIFIED' else '-'}")
    if not top:
        lines.append("Hich candidate-e qualified nist (payout=PASS + kyc=PASS lazem). Leads: out/candidates.json.")
    open(os.path.join(DATA, "shortlist.md"), "w").write("\n".join(lines) + "\n")
    return cands, top


if __name__ == "__main__":
    args = sys.argv[1:]
    live = "--live" in args
    args = [a for a in args if a != "--live"]
    inbox = args[0] if args else os.path.join(os.path.dirname(DATA), "inbox")
    items, health = (collect_live() if live else ([], None))
    cands, top = run(inbox, items, health)
    print(f"{len(cands)} collected, {sum(c['status'] != 'REJECTED' for c in cands)} alive, {sum(qualified(c) for c in cands)} qualified, {len(top)} shortlisted; health={health}")
