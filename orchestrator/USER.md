# USER: orchestrator

## User Profile
```yaml
role       : Stock trader / system developer
focus      : Indonesian equities (IDX/BEI)
language   : Bahasa Indonesia (chat) | English (API)
tech_level : Advanced — understands agent architecture, API schemas, trading concepts
timezone   : Asia/Jakarta (WIB, UTC+7)
```

---

## Interaction Preferences

### Language
- Chat responses → Bahasa Indonesia
- API responses → English (JSON, no natural language)
- Technical terms (ticker symbols, field names, file paths) → always English

### Tone (Chat)
- Direct and technical — no filler, no over-explanation
- Show step progress for multi-agent flows
- Use trading terminology correctly (support, resistance, cut loss, accumulate, etc.)
- Flag data quality issues prominently — user relies on this for real decisions

### Output Format
- Full report for single ticker: use format template in SOUL.md
- Watchlist overview: use compact table format in TOOLS.md
- Raw JSON: only when user explicitly requests it or in API mode

---

## Default Parameters
| Parameter             | Default  | Override                                    |
|-----------------------|----------|---------------------------------------------|
| News lookback         | 24 hours | User can say "berita 3 hari terakhir"       |
| Max articles          | 10       | —                                           |
| RAG top_k             | 4        | —                                           |
| user_position         | unknown  | User says "saya holding" or "belum masuk"   |
| contextId (stock API) | 10       | Set in fin_analyst config — do not override |

---

## Position Context
When the user mentions their current position, carry it for the session:
- "Saya holding ITMG" → set `user_position = "holding"` for ITMG
- "Belum masuk BBCA" → set `user_position = "not_holding"` for BBCA
- "Sudah cut loss TLKM" → set `user_position = "not_holding"` for TLKM

Pass `user_position` to `fin_analyst.generate_report()` so instructions
are tailored correctly to the user's actual situation.

Do NOT persist position data across sessions unless user says "simpan posisi ini".

---

## Watchlist
- Stored at: `/workspaces/orchestrator/data/watchlist.json`
- User can manage via: "tambah [TICKER] ke watchlist", "hapus [TICKER]", "cek watchlist"
- On "cek watchlist" → run watchlist scan (TOOLS.md)

---

## Shorthand Commands (Chat mode)
| User says                         | Action                                              |
|-----------------------------------|-----------------------------------------------------|
| "analisa [TICKER]"                | Full analysis report for that ticker                |
| "signal [TICKER]"                 | Fetch signal only, brief output (no enrichment)     |
| "berita [TICKER]"                 | News scrape only for that ticker                    |
| "watchlist" / "cek watchlist"     | Watchlist scan — brief signal table                 |
| "tambah [TICKER]"                 | Add ticker to watchlist                             |
| "hapus [TICKER]"                  | Remove ticker from watchlist                        |
| "status"                          | System health check (all agents + stock API)        |
| "proses video [path]"             | Delegate to ml_processor video_content_analysis     |
| "apa itu [concept]"               | RAG query to ml_processor knowledge base            |
| "help"                            | Show available commands                             |

---

## Update Instructions
This file is edited manually by the user/developer.
The orchestrator reads it on startup and warm start.
The orchestrator does NOT modify this file autonomously
unless the user says "simpan preferensi ini" or "update USER.md".
