# TOOLS: web_scraper

## http_get(url, timeout=10) → response
Fetch a URL. Returns `{ status_code, html, headers }`.
On 429 → wait 10s, retry once.
On 403 / 503 → return `{ status_code, html: null }` immediately.

## parse_html(html, selectors) → extracted_fields
Extract fields from HTML using CSS selectors defined in `config/sources.json`.
Returns dict of extracted values. Missing selector → null value (never throws).

## classify_sentiment(text) → { label, score }
Classify sentiment of text (title + summary combined).
Returns `{ label: "positive|negative|neutral", score: 0.0–1.0 }`.
Rules defined in SOUL.md.

## deduplicate(articles[]) → articles[]
Remove duplicate articles by title similarity (Jaccard > 0.8 = duplicate).
Keep earliest `publishedAt`. Operates on in-memory list only.

## extract_tickers(text) → string[]
Find IDX ticker symbols (4 uppercase letters matching known IDX format)
mentioned in a text string. Returns unique list.

## log_scrape(entry)
Append to `/workspaces/web_scraper/logs/scrape_log.jsonl`.
```json
{ "ts": "ISO8601", "task": "scrape_news", "symbol": "ITMG", "found": 3, "duration_s": 2.1, "sources_ok": 3, "sources_failed": 1 }
```
