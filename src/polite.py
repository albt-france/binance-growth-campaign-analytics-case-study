"""Polite HTTP helper used by every collector of this project.

Rules (see data/README.md):
- official APIs and public files only, never a workaround of any block;
- at most one request per second towards binance.com (we apply it to every host);
- neutral User-Agent, no personal data, no account, no cookie;
- raw responses cached in data/raw/ (never published).
"""
import time
from pathlib import Path

import requests

USER_AGENT = "binance-case-study/1.0"
MIN_DELAY_S = 1.0
_last = 0.0


def _wait():
    """Sleep so that two requests are always at least MIN_DELAY_S apart."""
    global _last
    wait = MIN_DELAY_S - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()


def get(url: str, timeout: int = 300, stream: bool = False):
    """GET with the polite delay; returns the response or None on a network error."""
    _wait()
    try:
        return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=stream)
    except requests.RequestException as e:
        print("[error]", url, e)
        return None


def cached(url: str, path: Path) -> Path | None:
    """Download url to path once (streamed to disk); later runs reuse the cached file."""
    if path.exists() and path.stat().st_size > 0:
        return path
    r = get(url, stream=True)
    if r is None or r.status_code != 200:
        print("[skip]", url, getattr(r, "status_code", None))
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    tmp.replace(path)
    return path


class RateLimited(Exception):
    """The server said "too many requests" twice: stop and resume later from the cache."""


def cached_json(url: str, path: Path, min_delay: float | None = None):
    """Fetch a JSON document once and cache it; returns the parsed JSON (or None).
    On HTTP 429 we wait what the server asks (Retry-After, default 120 s), try once more, then stop."""
    import json
    global MIN_DELAY_S
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8"))
    old = MIN_DELAY_S
    MIN_DELAY_S = min_delay or MIN_DELAY_S
    r = get(url, timeout=60)
    if r is not None and r.status_code == 429:
        wait = int(r.headers.get("Retry-After", "120") or 120)
        print(f"[polite] 429 - waiting {wait}s as asked by the server", flush=True)
        time.sleep(wait)
        r = get(url, timeout=60)
        if r is not None and r.status_code == 429:
            MIN_DELAY_S = old
            raise RateLimited(url)
    MIN_DELAY_S = old
    if r is None or r.status_code != 200:
        print("[skip]", url, getattr(r, "status_code", None))
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r.text, encoding="utf-8")
    return r.json()
