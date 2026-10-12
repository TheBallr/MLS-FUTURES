"""Shared helpers for scripts: HTTP session, ET/UTC conversion, logging in one line."""
from __future__ import annotations
import datetime as dt, os, sys
from zoneinfo import ZoneInfo
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(UA)
    return s


def get(url, params=None, timeout=40, headers=None, retries=3, json=True):
    """GET with retries; returns parsed JSON (or text) or None after printing one line."""
    s = session()
    if headers:
        s.headers.update(headers)
    last = None
    for i in range(retries):
        try:
            r = s.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json() if json else r.text
            last = f"{r.status_code}"
            if r.status_code in (401, 403, 404):
                break
        except requests.RequestException as e:
            last = str(e)[:120]
        dt_sleep = 2 * (i + 1)
        import time; time.sleep(dt_sleep)
    print(f"fetch: {url.split('?')[0]} failed ({last})", file=sys.stderr)
    return None


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def utc_iso(d: dt.datetime) -> str:
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: str) -> dt.datetime:
    s = str(s).replace("Z", "+00:00")
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC)


def et_date(d: dt.datetime) -> str:
    return d.astimezone(ET).strftime("%Y-%m-%d")


def et_str(d: dt.datetime) -> str:
    return d.astimezone(ET).strftime("%a %b %d %I:%M %p ET").replace(" 0", " ")


def today_et() -> dt.date:
    return dt.datetime.now(ET).date()
