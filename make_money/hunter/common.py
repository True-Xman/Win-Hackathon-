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
