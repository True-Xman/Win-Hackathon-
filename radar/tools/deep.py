#!/usr/bin/env python3
"""Per-platform adapters that pull the FULL rules text for a candidate, then run gates.analyze.

Why: many event pages are JS apps whose visible text is a shell; the real rules sit in embedded JSON.
Output: data/gates.json  {candidate_id: {"text_chars":..., "gates":{...}, "sources":[...]}}
Usage: python3 radar/tools/deep.py [candidate_id ...]   (no args = every candidate that passes prefilter)
"""
import json
import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import fetch, html_to_text, load, save  # noqa: E402
from gates import analyze  # noqa: E402


def _unescape(h):
    return h.replace('\\"', '"').replace("\\n", "\n").replace("\\u0026", "&").replace("\\u003c", "<").replace("\\u003e", ">").replace("\\\\", "\\")


def lablab_text(url):
    """Event bodies are HTML blobs inside a Next.js flight payload. Text nodes between tags = the human-readable rules."""
    st, h = fetch(url)
    u = re.sub(r"(?is)<style.*?</style>", " ", _unescape(h))
    seen = []
    for n in re.findall(r'>([^<>{}\[\]"\\]{25,}?)<', u):
        n = html_to_text(n).strip()
        if n and n not in seen:
            seen.append(n)
    notes = re.findall(r"<!--(.*?)-->", _unescape(h), re.S)  # organizer comments sometimes leak internal status
    return "\n".join(seen) + "\n[organizer HTML comments]\n" + "\n".join(re.sub(r"\s+", " ", n)[:500] for n in notes), st


def genai_text(url):
    st, h = fetch(url)
    u = h.replace('\\"', '"').replace("\\\\", "\\")
    i = u.find('[{"number":1,"title":"Eligibility"')
    if i < 0:
        return html_to_text(h), st
    depth = 0
    for j in range(i, len(u)):
        depth += (u[j] == "[") - (u[j] == "]")
        if depth == 0:
            break
    rules = json.loads(u[i:j + 1])
    out = []
    for r in rules:
        out.append(f"## {r['number']}. {r['title']}")
        for b in r["blocks"]:
            out += ["- " + x for x in b.get("items", [])]
    for q, a in re.findall(r'\{"question":"(.*?)","answer":"(.*?)"\}', u):
        out.append(f"Q: {q}\nA: {a}")
    return "\n".join(out), st


def superteam_text(cid):
    d = load("superteam_details.json", {}).get(cid.split(":", 1)[1], {})
    parts = [html_to_text(d.get("description") or ""), f"region: {d.get('region')}", f"isFndnPaying: {d.get('isFndnPaying')}"]
    return "\n".join(parts), 200 if d else 0


def get_text(c):
    if c["platform"] == "lablab.ai":
        return lablab_text(c["url"])
    if c["platform"] == "genai.works":
        return genai_text("https://hackathon.genai.works/event/open-agent-hackathon-2026")
    if c["platform"] == "Superteam Earn":
        return superteam_text(c["id"])
    st, h = fetch(c["url"])
    return html_to_text(h), st


SEVERITY = {"PASS": 0, "INFO": 0, "UNKNOWN": 1, "RISK": 2, "FAIL": 3}
FAQ = "https://docs.superteam.fun/the-superteam-handbook/community/faqs/superteam-earn-faq"
COLO = "https://colosseum.com/legal/Colosseum%20-%20Terms%20of%20Service.pdf"


def platform_overlay(c, gates):
    """Platform-level clauses that per-listing text never repeats. Each overlay cites the verified source (checked 2026-09-30).
    A verdict can only get WORSE from an overlay, never better."""
    def bump(g, verdict, ev, src):
        cur = gates[g]
        if SEVERITY[verdict] > SEVERITY[cur["verdict"]]:
            cur["verdict"] = verdict
        cur["evidence"] = [f"[platform policy] {ev} (src: {src})"] + cur["evidence"]

    if c["platform"] == "Superteam Earn":
        d = load("superteam_details.json", {}).get(c["id"].split(":", 1)[1], {})
        if d.get("isFndnPaying"):
            bump("kyc", "FAIL", "Listing is Solana-Foundation-paid (isFndnPaying=true). FAQ: 'the winner needs to complete KYC to receive money for Superteam / Solana-sponsored listings.'", FAQ)
        else:
            bump("kyc", "RISK", "External-sponsor listing: paid to your Superteam Earn wallet, but FAQ: 'Occasionally, some sponsors might ask for invoices, KYC, etc.'", FAQ)
        if not d.get("isFndnPaying") and gates["payout"]["verdict"] in ("UNKNOWN", "INFO"):
            gates["payout"]["verdict"] = "PASS"
            gates["payout"]["evidence"] = [f"[platform policy] FAQ: 'rewards for listings sponsored by external companies... will be paid out to the wallet associated with the winner's Superteam Earn account' (src: {FAQ})"]
        if (d.get("Hackathon") or {}).get("slug") == "crypto-worlds-fair":
            bump("kyc", "RISK", "Colosseum ToS: 'the operator and its partners may perform Know Your Customer (KYC) procedures... You consent.'", COLO)
            bump("country", "RISK", "Colosseum ToS excludes residents/nationals of Crimea, Cuba, Iran, North Korea, Syria + any US/UK/EU-sanctioned country.", COLO)
    return gates


def prefilter(c):
    """Cheap first cut so we don't deep-read 60 content bounties. Keep hackathons + AI/dev bounties >= $1000 or agent-flagged."""
    if c["platform"] != "Superteam Earn":
        return c["platform"] in ("lablab.ai", "genai.works")
    d = load("superteam_details.json", {}).get(c["id"].split(":", 1)[1], {})
    region_ok = (d.get("region") or "") == "Global"
    dev = any(s["skills"] in ("Frontend", "Backend", "Blockchain", "Other") for s in (d.get("skills") or []))
    return region_ok and dev and (c["prize_usd"] or 0) >= 500 and d.get("type") in ("hackathon", "bounty")


if __name__ == "__main__":
    cands = load("candidates.json", {})
    ids = sys.argv[1:] or [k for k, c in cands.items() if prefilter(c)]
    out = load("gates.json", {})
    for cid in ids:
        c = cands[cid]
        text, st = get_text(c)
        a = analyze(text, c["url"])
        a["gates"] = platform_overlay(c, a["gates"])
        out[cid] = dict(name=c["name"], fetch_status=st, text_chars=len(text), gates=a["gates"])
        print(f"{cid[:55]:55} {len(text):6}ch  " + " ".join(f"{g[:4]}={d['verdict']}" for g, d in a["gates"].items()))
    save("gates.json", out)
