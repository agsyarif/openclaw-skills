"""
fetcher.py
----------
HTTP fetching layer dengan rate limiting, retry, dan error handling.
Semua request web_scraper melalui modul ini.

Location: /workspaces/web_scraper/skills/web_scraping/fetcher.py
"""

import time
import urllib.error
import urllib.request
from typing import Optional

# Throttle tracker: {domain: last_request_time}
_last_request: dict[str, float] = {}

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection":      "keep-alive",
}


def fetch(url: str, timeout: int = 12, rate_limit_s: float = 2.0) -> Optional[str]:
    """
    Fetch URL dengan rate limiting dan retry otomatis.

    Args:
        url:          URL yang akan di-fetch
        timeout:      timeout dalam detik
        rate_limit_s: minimum jeda antar request ke domain yang sama

    Returns:
        HTML string atau None jika gagal
    """
    domain = _extract_domain(url)

    # Rate limiting per domain
    if domain in _last_request:
        elapsed = time.time() - _last_request[domain]
        if elapsed < rate_limit_s:
            time.sleep(rate_limit_s - elapsed)

    _last_request[domain] = time.time()

    req = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Handle gzip encoding
            raw = resp.read()
            encoding = resp.headers.get_content_charset("utf-8")

            # Try to decompress if gzip
            content_encoding = resp.headers.get("Content-Encoding", "")
            if "gzip" in content_encoding:
                import gzip
                raw = gzip.decompress(raw)

            return raw.decode(encoding, errors="replace")

    except urllib.error.HTTPError as e:
        if e.code == 429:
            # Rate limited — wait longer and retry once
            print(f"  ⏳ Rate limited by {domain}, waiting 15s...")
            time.sleep(15)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="replace")
            except Exception:
                return None
        elif e.code in (403, 503, 429):
            print(f"  ⚠️  {domain} blocked ({e.code})")
            return None
        elif e.code == 404:
            return None
        else:
            print(f"  ⚠️  HTTP {e.code} from {domain}")
            return None

    except urllib.error.URLError as e:
        print(f"  ⚠️  Cannot reach {domain}: {e.reason}")
        return None

    except Exception as e:
        print(f"  ⚠️  Fetch error for {domain}: {type(e).__name__}")
        return None


def _extract_domain(url: str) -> str:
    """Extract domain dari URL untuk rate limiting."""
    try:
        parts = url.split("//", 1)[1].split("/")[0]
        return parts.replace("www.", "")
    except Exception:
        return url[:30]
