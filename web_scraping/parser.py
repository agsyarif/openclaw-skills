"""
parser.py
---------
HTML parsing untuk ekstrak artikel dari berbagai sumber berita Indonesia.
Menggunakan regex sebagai fallback jika BeautifulSoup tidak tersedia.

Location: /workspaces/web_scraper/skills/web_scraping/parser.py
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from sources import KNOWN_TICKERS

# ── Sentiment Lexicon ──────────────────────────────────────────────────────────

POSITIVE = {
    # Performa keuangan
    "laba", "untung", "profit", "keuntungan", "pendapatan naik",
    "pertumbuhan", "tumbuh", "meningkat", "rekor", "tertinggi",
    # Aksi korporasi positif
    "dividen", "buyback", "akuisisi", "ekspansi", "merger",
    "kontrak baru", "kemitraan", "investasi masuk",
    # Sentiment pasar
    "bullish", "upgrade", "overweight", "outperform", "buy",
    "naik", "menguat", "reli", "rebound", "bangkit",
    # Makro positif
    "inflasi terkendali", "ekonomi tumbuh", "surplus",
}

NEGATIVE = {
    # Performa keuangan buruk
    "rugi", "kerugian", "loss", "penurunan laba", "pendapatan turun",
    "merugi", "defisit", "anjlok", "terpuruk",
    # Masalah korporasi
    "gagal bayar", "default", "pailit", "bangkrut", "delisting",
    "investigasi", "sanksi", "denda", "sengketa", "masalah",
    # Sentiment pasar negatif
    "bearish", "downgrade", "underweight", "underperform", "sell",
    "turun", "melemah", "jatuh", "koreksi", "tekanan",
    # Makro negatif
    "inflasi tinggi", "resesi", "krisis", "defisit neraca",
    "PHK", "pemutusan hubungan kerja",
}


def classify_sentiment(text: str) -> tuple[str, float]:
    """
    Klasifikasi sentimen teks berdasarkan lexicon.
    Returns: (label, score) — label: positive/negative/neutral, score: 0.0-1.0
    """
    text_lo  = text.lower()
    pos_hits = sum(1 for w in POSITIVE if w in text_lo)
    neg_hits = sum(1 for w in NEGATIVE if w in text_lo)

    if pos_hits == 0 and neg_hits == 0:
        return "neutral", 0.5

    total = pos_hits + neg_hits
    if pos_hits > neg_hits:
        score = 0.5 + min(pos_hits / (total * 2), 0.49)
        return "positive", round(score, 2)
    elif neg_hits > pos_hits:
        score = 0.5 + min(neg_hits / (total * 2), 0.49)
        return "negative", round(score, 2)
    else:
        return "mixed", 0.5


def aggregate_sentiment(sentiments: list[str]) -> str:
    """Agregasi sentiment dari beberapa artikel."""
    if not sentiments:
        return "unavailable"
    counts = {s: sentiments.count(s) for s in set(sentiments)}
    pos = counts.get("positive", 0)
    neg = counts.get("negative", 0)
    neu = counts.get("neutral", 0)
    if pos > neg and pos > neu:
        return "positive"
    if neg > pos and neg > neu:
        return "negative"
    if pos > 0 and neg > 0:
        return "mixed"
    return "neutral"


def extract_tickers(text: str) -> list[str]:
    """Cari ticker IDX yang disebutkan dalam teks."""
    found = set()
    # Match 4-letter uppercase words
    candidates = re.findall(r'\b[A-Z]{4}\b', text)
    for c in candidates:
        if c in KNOWN_TICKERS:
            found.add(c)
    return list(found)


def clean_text(text: str, max_chars: int = 300) -> str:
    """Bersihkan HTML dan batasi panjang teks."""
    # Hapus HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Hapus entities
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    # Normalisasi whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(' ', 1)[0] + "..."
    return text


def parse_date(date_str: str) -> Optional[str]:
    """
    Parse berbagai format tanggal Indonesia ke ISO8601.
    Returns None jika tidak bisa diparse.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Format: "dd Mon yyyy" atau "dd Month yyyy"
    bulan_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "jun": 6,
        "jul": 7, "agu": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12,
        "januari": 1, "februari": 2, "maret": 3, "april": 4,
        "juni": 6, "juli": 7, "agustus": 8, "september": 9,
        "oktober": 10, "november": 11, "desember": 12,
    }

    # Try regex patterns
    patterns = [
        r'(\d{1,2})\s+(\w+)\s+(\d{4})',           # "15 Januari 2025"
        r'(\d{4})-(\d{2})-(\d{2})',                 # "2025-01-15"
        r'(\d{2})/(\d{2})/(\d{4})',                 # "15/01/2025"
        r'(\d{1,2})\s+(\w{3})\s+(\d{4})',          # "15 Jan 2025"
    ]

    for pattern in patterns:
        m = re.search(pattern, date_str, re.IGNORECASE)
        if m:
            try:
                groups = m.groups()
                if "-" in pattern or "/" in pattern:
                    if len(groups[0]) == 4:  # yyyy-mm-dd
                        y, mo, d = int(groups[0]), int(groups[1]), int(groups[2])
                    else:
                        d, mo, y = int(groups[0]), int(groups[1]), int(groups[2])
                else:
                    d   = int(groups[0])
                    mo  = bulan_map.get(groups[1].lower(), 0)
                    y   = int(groups[2])
                    if not mo:
                        continue
                dt = datetime(y, mo, d, tzinfo=timezone(timedelta(hours=7)))  # WIB
                return dt.isoformat()
            except (ValueError, IndexError):
                continue

    return None


def parse_articles_html(html: str, source: dict, query: str) -> list[dict]:
    """
    Parse artikel dari HTML menggunakan pendekatan multi-strategy:
    1. BeautifulSoup jika tersedia
    2. Regex fallback jika tidak tersedia

    Args:
        html:   HTML content
        source: source config dari sources.py
        query:  search query (untuk filter relevance)

    Returns:
        list of article dicts
    """
    try:
        from bs4 import BeautifulSoup
        return _parse_with_bs4(html, source, query)
    except ImportError:
        return _parse_with_regex(html, source, query)


def _parse_with_bs4(html: str, source: dict, query: str) -> list[dict]:
    """Parse menggunakan BeautifulSoup."""
    from bs4 import BeautifulSoup

    soup      = BeautifulSoup(html, "html.parser")
    selectors = source.get("selectors", {})
    articles  = []
    base_url  = source["base_url"]

    # Coba ambil article containers
    containers = []
    for sel in selectors.get("article_list", "").split(", "):
        found = soup.select(sel.strip())
        if found:
            containers = found
            break

    # Fallback: cari semua tag article atau li dengan link
    if not containers:
        containers = soup.find_all(["article", "li"], limit=20)

    for container in containers[:15]:
        # Title
        title = ""
        for sel in selectors.get("title", "h2, h3, a").split(", "):
            el = container.select_one(sel.strip())
            if el and el.get_text(strip=True):
                title = clean_text(el.get_text(strip=True), max_chars=200)
                break

        if not title or len(title) < 10:
            continue

        # Filter relevance
        if query.upper() not in title.upper() and query.lower() not in title.lower():
            continue

        # Link
        url = ""
        link_el = container.find("a", href=True)
        if link_el:
            href = link_el["href"]
            url  = href if href.startswith("http") else base_url + href

        # Summary
        summary = ""
        for sel in selectors.get("summary", "p").split(", "):
            el = container.select_one(sel.strip())
            if el and el.get_text(strip=True):
                summary = clean_text(el.get_text(strip=True), max_chars=300)
                break
        if not summary:
            summary = title

        # Date
        published_at = None
        for sel in selectors.get("date", "time").split(", "):
            el = container.select_one(sel.strip())
            if el:
                date_str = el.get("datetime") or el.get_text(strip=True)
                published_at = parse_date(date_str)
                if published_at:
                    break

        if not published_at:
            published_at = datetime.now(timezone.utc).isoformat()

        sentiment, score = classify_sentiment(title + " " + summary)
        tickers = extract_tickers(title + " " + summary)

        articles.append({
            "title":            title,
            "summary":          summary,
            "url":              url,
            "source":           source["name"],
            "publishedAt":      published_at,
            "sentiment":        sentiment,
            "sentimentScore":   score,
            "tickersMentioned": tickers,
        })

    return articles


def _parse_with_regex(html: str, source: dict, query: str) -> list[dict]:
    """Fallback parser menggunakan regex jika BeautifulSoup tidak ada."""
    articles = []
    base_url = source["base_url"]

    # Cari pola: link + judul yang relevan
    link_title_pattern = re.compile(
        r'href=["\']([^"\']{10,300})["\'][^>]*>\s*([^<]{15,250})',
        re.IGNORECASE
    )

    seen_titles = set()
    for m in link_title_pattern.finditer(html):
        href  = m.group(1).strip()
        title = clean_text(m.group(2), max_chars=200)

        if len(title) < 15 or title in seen_titles:
            continue

        # Filter: harus relevan dengan query
        if query.upper() not in title.upper() and query.lower() not in title.lower():
            continue

        seen_titles.add(title)
        url = href if href.startswith("http") else base_url + href

        sentiment, score = classify_sentiment(title)
        tickers = extract_tickers(title)

        articles.append({
            "title":            title,
            "summary":          title,
            "url":              url,
            "source":           source["name"],
            "publishedAt":      datetime.now(timezone.utc).isoformat(),
            "sentiment":        sentiment,
            "sentimentScore":   score,
            "tickersMentioned": tickers,
        })

        if len(articles) >= 5:
            break

    return articles


def deduplicate(articles: list[dict]) -> list[dict]:
    """
    Hapus artikel duplikat berdasarkan Jaccard similarity judul.
    Threshold: > 0.75 = duplikat. Prioritaskan artikel dengan timestamp lebih awal.
    """
    seen  = []
    dedup = []

    for article in sorted(articles, key=lambda x: x.get("publishedAt", "")):
        title_tokens = set(article.get("title", "").lower().split())

        is_dup = False
        for seen_tokens in seen:
            if not seen_tokens:
                continue
            intersection = title_tokens & seen_tokens
            union        = title_tokens | seen_tokens
            if union and len(intersection) / len(union) >= 0.75:
                is_dup = True
                break

        if not is_dup:
            dedup.append(article)
            seen.append(title_tokens)

    return dedup
