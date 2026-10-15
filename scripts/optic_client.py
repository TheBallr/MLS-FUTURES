"""OpticOdds v3 client. The key lives only in the environment variable OPTIC_API_KEY. Never written to disk.
Every script that imports this treats the key as a bonus: no key -> client.available is False and callers print one line."""
from __future__ import annotations
import json, os, sys, time
import requests

BASE = "https://api.opticodds.com/api/v3"
HIST_RPS = 10 / 15.0  # historical endpoints: 10 requests per 15 seconds (docs); the live feed answers x-ratelimit-limit 50 per window
GEN_RPS = 2500 / 15.0


class Optic:
    def __init__(self, key: str | None = None, timeout: int = 40, verbose: bool = True):
        self.key = key or os.environ.get("OPTIC_API_KEY", "").strip()
        self.available = bool(self.key)
        self.s = requests.Session()
        if self.available:
            self.s.headers.update({"X-Api-Key": self.key, "Accept": "application/json"})
        self.timeout = timeout
        self.verbose = verbose
        self.calls = 0
        self.dark = False
        self._last_hist = 0.0

    def get(self, path: str, params: dict | list | None = None, historical: bool = False, retries: int = 3):
        """GET BASE+path. Returns parsed JSON or None (after printing one line) on any failure. Never raises on 4xx/5xx."""
        if not self.available or self.dark:
            return None
        if historical:
            wait = (1.0 / HIST_RPS) - (time.time() - self._last_hist)
            if wait > 0:
                time.sleep(wait)
        for attempt in range(retries):
            try:
                r = self.s.get(BASE + path, params=params, timeout=self.timeout)
                self.calls += 1
                if historical:
                    self._last_hist = time.time()
                    # honour the feed's own budget: when the window is spent, sleep until it resets
                    try:
                        remaining = int(r.headers.get("x-ratelimit-remaining", "1")); reset = float(r.headers.get("x-ratelimit-reset", "0"))
                        if remaining <= 1 and reset > time.time():
                            time.sleep(min(60.0, reset - time.time() + 0.5))
                    except (TypeError, ValueError):
                        pass
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (401, 403):
                    self.dark = True
                    print(f"optic: key refused ({r.status_code}) on {path}; carrying on without OpticOdds", file=sys.stderr)
                    return None
                if r.status_code == 429:
                    try:
                        reset = float(r.headers.get("x-ratelimit-reset", "0")); wait = max(2.0, min(60.0, reset - time.time() + 0.5))
                    except (TypeError, ValueError):
                        wait = 5.0 * (attempt + 1)
                    time.sleep(wait)
                    continue
                if r.status_code == 404:
                    return None
                if self.verbose:
                    print(f"optic: {r.status_code} on {path} {str(params)[:120]}: {r.text[:200]}", file=sys.stderr)
                if r.status_code >= 500:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None
            except requests.RequestException as e:
                if self.verbose and attempt == retries - 1:
                    print(f"optic: network error on {path}: {e}", file=sys.stderr)
                time.sleep(2 * (attempt + 1))
        return None

    def paged(self, path: str, params: dict, max_pages: int = 200, historical: bool = False):
        """Iterate a paginated endpoint: v3 answers page/has_more (and a cursor); older shapes total_pages. Yields each page's JSON."""
        page = 1
        while page <= max_pages:
            p = dict(params); p["page"] = page
            j = self.get(path, p, historical=historical)
            if not j or not j.get("data"):
                return
            yield j
            if "has_more" in j:
                if not j.get("has_more"):
                    return
            else:
                tp = j.get("total_pages") or 1
                if page >= tp:
                    return
            page += 1


def dump(obj, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def key_in_text(text: str) -> bool:
    """Guard used before commits: true if the live key appears in text."""
    k = os.environ.get("OPTIC_API_KEY", "")
    return bool(k) and k in text
