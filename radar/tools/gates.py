#!/usr/bin/env python3
"""Rules/KYC/payout gate analyzer. Evidence-first: every verdict carries quoted snippets.

Verdict semantics (UNKNOWN is never silently upgraded to PASS):
  FAIL    = text contains a blocking/mandatory clause for this gate
  RISK    = text mentions the gate in a way that may apply (verify manually / depends on user's country)
  PASS    = text contains an explicit positive statement (e.g. "no KYC required", "open worldwide")
  UNKNOWN = nothing found in the text we could read (absence of evidence != PASS)

Usage:
  python3 gates.py <url-or-file> [more ...]         # analyze pages / PDFs, print report
  python3 gates.py --json <url-or-file>              # machine-readable
Library: analyze(text, source) -> dict
"""
import io
import json
import re
import subprocess
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import fetch, html_to_text  # noqa: E402

VENV_PY = "/tmp/venv_radar/bin/python"  # has pypdf; system cryptography was broken on this box

GATES = {
    "kyc": dict(
        strong=r"\bKYC\b|know[- ]your[- ](customer|client)|identity verification|verify your identity|government[- ]issued|passport|proof of (identity|residen)|background check|Sumsub|Onfido|W-?8BEN|W-?9\b",
        risk=r"\bKYC\b|know[- ]your[- ](customer|client)|identity verification|verify your identity|government[- ]issued|passport|proof of (identity|residen)|background check|Sumsub|Onfido|Persona\b|W-?8BEN|W-?9\b|tax (form|id|information)|OFAC|sanction|politically exposed",
        fail=r"(must|shall|will need to|need to|mandatory|is required to|are required to)[^.]{0,80}(KYC|verify your identity|identity verification|government[- ]issued|passport|W-?8BEN|W-?9)|(KYC|identity verification)[^.]{0,40}\b(is|are) (required|mandatory)",
        pass_=r"no KYC|KYC[- ]free|KYC (is )?not (required|needed)|without (KYC|identity verification)"),
    "country": dict(
        strong=r"(not|never) (a )?(resident|national|citizen)|resident of|residents of|national of|only open to|open only to|must (reside|be located)|not eligible|ineligible|excluded|Crimea|Cuba|Iran|North Korea|Syria",
        risk=r"resident of|residents of|national of|citizen(s)? of|not eligible|ineligible|excluded|prohibited (countr|jurisdiction)|embargo|Crimea|Cuba|Iran|North Korea|Syria|Russia|Belarus|only open to|open only to|limited to (residents|citizens)|must (reside|be located)",
        fail=r"(open|available|limited|restricted) (only )?to (residents|citizens) of|must be (a )?(resident|citizen) of|only (residents|citizens)",
        pass_=r"open to (developers|builders|participants|anyone|everyone)[^.]{0,40}(worldwide|globally|anywhere|in the world)|open worldwide|open to all countries|open to everyone, anywhere"),
    "student": dict(
        risk=r"\bstudents?\b|university|enrolled",
        fail=r"(only|exclusively) (for |open to )?(current )?students|must be (a |an )?(current )?(enrolled )?student|students only",
        pass_=r"students? (and|to) (professionals|senior)|from students to"),
    "paid_action": dict(
        risk=r"mainnet|entry fee|registration fee|submission fee|purchase|paid (plan|tier|api|subscription)|credit card|must (pay|deposit|stake)|minimum (trade|deposit)|at least \d+ (qualifying )?trades?|swaps? of at least",
        fail=r"(must|required to|need to)[^.]{0,60}(pay|purchase|deposit|stake|execute[^.]{0,30}(mainnet|trades?))|entry fee|registration fee|submission fee|(execute|make|complete|perform)[^.]{0,30}at least \d+ (qualifying )?(trades?|transactions?|swaps?)|(swaps?|trades?) of at least \d+ ?(USDC|USDT|SOL|ETH|USD)",
        pass_=r"free to (enter|participate|join)|no (entry|registration) fee"),
    # CLAUDE.md hard gate: crypto payout is REQUIRED. Crypto stated near prize wording = PASS; fiat-only = FAIL; silent = UNKNOWN.
    "payout": dict(
        risk=r"cash prize|prize (pool|money)|credits?\b",
        fail=r"(prize|payout|paid|reward|distribut|payable)[^.]{0,80}(bank (transfer|account)|\bwire\b|PayPal|Stripe|\bWise\b|Payoneer|\bACH\b|direct deposit|cheque|gift card)|(bank transfer|wire transfer|PayPal|Stripe|Payoneer)[^.]{0,60}(prize|payout)",
        pass_=r"(prize|payout|paid|reward|distribut|payable|sent|settle)[^.]{0,80}(USDC|USDT|USDG|stablecoin|on-?chain|crypto(currency)?|wallet)|(USDC|USDT|USDG|stablecoin|crypto(currency)?)[^.]{0,60}(prize|payout|paid|reward|distribut)"),
    "age": dict(risk=r"\b18\b|age of majority|at least \d+ years|minors?", fail=r"", pass_=r""),
    "onsite": dict(
        risk=r"on-?site|in[- ]person|finals? (will be )?(held|at)|attend in",
        fail=r"(must|required to) (attend|be present)[^.]{0,40}(in person|on-?site|venue)",
        pass_=r"fully (online|remote|virtual)|100% (online|remote)|online only|remote only"),
}


def snippets(text, pat, n=3, w=130):
    out, last_end = [], -1
    for m in re.finditer(pat, text, re.I):
        if m.start() < last_end:  # overlaps previous snippet window -> same clause, skip
            continue
        out.append(re.sub(r"\s+", " ", text[max(0, m.start() - w): m.end() + w]).strip())
        last_end = m.end() + w
        if len(out) >= n:
            break
    return out


def analyze(text, source=""):
    res = {"source": source, "chars": len(text), "gates": {}}
    for g, p in GATES.items():
        fail = snippets(text, p["fail"]) if p["fail"] else []
        pas = snippets(text, p["pass_"], 2) if p["pass_"] else []
        scan = re.sub(p["pass_"], " ", text, flags=re.I) if p["pass_"] else text  # positive phrases don't self-trigger risk
        risk = snippets(scan, p["strong"], 3) if p.get("strong") else []
        risk += [x for x in snippets(scan, p["risk"], 3) if x not in risk][: max(0, 4 - len(risk))]
        if fail:
            v, ev = "FAIL", fail
        elif risk and g in ("kyc", "country", "paid_action", "onsite", "student"):
            v, ev = "RISK", risk
        elif pas:
            v, ev = "PASS", pas
        elif risk:
            v, ev = "INFO", risk
        else:
            v, ev = "UNKNOWN", []
        if g == "payout" and pas:  # a stated crypto route satisfies the gate even if a fiat route is also offered
            v, ev = "PASS", pas
            res["gates"][g] = {"verdict": v, "evidence": ev, "positive_evidence": []}
            continue
        # explicit positive evidence is shown alongside a RISK verdict but never overrides it
        res["gates"][g] = {"verdict": v, "evidence": ev, "positive_evidence": pas if v in ("RISK", "FAIL") else []}
    return res


def load_text(src):
    """URL or local path -> plain text. PDFs are extracted via the venv's pypdf."""
    if not src.startswith("http"):
        return open(src, "rb").read().decode("utf-8", "replace") if not src.endswith(".pdf") else _pdf_local(src)
    st, body = fetch(src)
    if st != 200:
        return f"[[FETCH FAILED status={st}]]"
    if body.startswith("%PDF"):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(body.encode("latin-1", "replace"))
        return _pdf_local(f.name)
    return html_to_text(body)


def _pdf_local(path):
    code = "import sys;from pypdf import PdfReader;print('\\n'.join(p.extract_text() for p in PdfReader(sys.argv[1]).pages))"
    r = subprocess.run([VENV_PY, "-c", code, path], capture_output=True, text=True)
    return r.stdout or f"[[PDF EXTRACT FAILED: {r.stderr[:200]}]]"


def report(res):
    lines = [f"## {res['source']}  ({res['chars']} chars)"]
    for g, d in res["gates"].items():
        lines.append(f"- **{g}: {d['verdict']}**")
        for e in d["evidence"][:3]:
            lines.append(f"    - \"{e[:300]}\"")
        for e in d["positive_evidence"][:1]:
            lines.append(f"    - (positive, does not override) \"{e[:200]}\"")
    return "\n".join(lines)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--json"]
    out = [analyze(load_text(a), a) for a in args]
    print(json.dumps(out, indent=2) if "--json" in sys.argv else "\n\n".join(report(r) for r in out))
