"""Shared helpers for Money Hunter. Stdlib only, so it runs anywhere."""
import datetime as dt
import html
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "out")
UA = "Mozilla/5.0 (X11; Linux x86_64) MoneyHunter/1.0"


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def _ctx():
    ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
    return ssl.create_default_context(cafile=ca) if os.path.exists(ca) else ssl.create_default_context()


def fetch(url, timeout=30, headers=None, retries=3):
    """GET url -> (status, text). Never raises; status 0 means network error (text = reason).
    Transient failures (network error, 429, 5xx) are retried with backoff so one blip can't silently thin out the radar."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    status, text = 0, ""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, text = e.code, e.read().decode("utf-8", "replace")
            if status not in (429, 500, 502, 503, 504):
                return status, text  # 403/404/405 etc are answers, not blips
        except Exception as e:  # noqa: BLE001
            status, text = 0, repr(e)
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
    return status, text


def fetch_json(url, **kw):
    status, text = fetch(url, **kw)
    try:
        return status, json.loads(text)
    except Exception:  # noqa: BLE001
        return status, None


def html_to_text(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|section)>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t\r\f\v]+", " ", h)
    return re.sub(r"\n\s*\n+", "\n", h).strip()


def parse_dt(s):
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)  # naive stamps are treated as UTC


# Static, approximate FX (USD per 1 unit) used ONLY to rank prize size; the original amount/currency always stays in provenance.
# A currency we cannot identify is never assumed to be USD -> reward_usd=None.
FX_USD = {"USD": 1.0, "USDC": 1.0, "USDT": 1.0, "INR": 0.011, "EUR": 1.05, "GBP": 1.25, "CAD": 0.72, "AUD": 0.65, "SGD": 0.74, "CHF": 1.1, "JPY": 0.0065, "BRL": 0.18, "NGN": 0.0006}
_SYMBOLS = (("US$", "USD"), ("A$", "AUD"), ("C$", "CAD"), ("S$", "SGD"), ("\u20b9", "INR"), ("\u20ac", "EUR"), ("\u00a3", "GBP"), ("\u00a5", "JPY"), ("R$", "BRL"), ("\u20a6", "NGN"), ("$", "USD"))


def parse_money(raw):
    """Prize/reward string -> {"amount", "currency", "usd"}. Handles symbols (\u20b9, \u20ac, $...), ISO codes and Indian digit grouping.
    Unknown currency -> usd None (never silently USD)."""
    t = re.sub(r"<[^>]+>", "", raw or "").strip()
    m = re.search(r"\d[\d,]*(?:\.\d+)?", t)
    if not m:
        return {"amount": None, "currency": None, "usd": None}
    amount = float(m.group(0).replace(",", ""))
    cur = None
    iso = re.search(r"\b(USDC|USDT|USD|INR|EUR|GBP|CAD|AUD|SGD|CHF|JPY|BRL|NGN)\b", t, re.I)
    if iso:
        cur = iso.group(1).upper()
    else:
        for sym, code in _SYMBOLS:
            if sym in t:
                cur = code
                break
    if re.search(r"\d\s*(lakhs?|L)\b", t, re.I):
        amount *= 100_000
    elif re.search(r"\d\s*(crores?|cr)\b", t, re.I):
        amount *= 10_000_000
    elif re.search(r"\d\s*(k)\b", t, re.I):
        amount *= 1_000
    usd = round(amount * FX_USD[cur], 2) if cur in FX_USD else None
    return {"amount": amount, "currency": cur, "usd": usd}


def days_left(s):
    d = parse_dt(s)
    return None if d is None else round((d - now_utc()).total_seconds() / 86400, 1)


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)


def load(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    with open(p) as f:
        return json.load(f)


def render_text(url, timeout=70):
    """JS-rendered page text via headless Chromium (GET only, no login/forms). '' on failure."""
    import subprocess
    try:
        r = subprocess.run(["node", os.path.join(os.path.dirname(os.path.abspath(__file__)), "render.js"), url],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return ""
