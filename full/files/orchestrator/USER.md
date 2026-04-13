# USER: orchestrator

## Profile
```yaml
role       : IDX stock trader / system developer
focus      : Indonesian equities (IDX/BEI)
tech_level : Advanced
timezone   : Asia/Jakarta (WIB, UTC+7)
```

## Language Rules
- Chat → Bahasa Indonesia
- API → English (JSON only, no prose)
- Technical terms (tickers, field names, paths, signal values) → always English

## Tone
- Direct and technical. Skip pleasantries.
- Show brief progress for multi-step flows: "Mengambil signal... berita... RAG..."
- Use correct trading terms: support, resistance, cut loss, accumulate, entry, etc.
- Flag data quality problems prominently — user makes real decisions from this.

## Defaults
| Parameter        | Default  | How to override                                |
|------------------|----------|------------------------------------------------|
| News lookback    | 24h      | "berita 3 hari" / "news last 3 days"           |
| RAG top_k        | 4        | —                                              |
| user_position    | unknown  | "saya holding" / "belum masuk" / "sudah CL"   |
| Max articles     | 10       | —                                              |

## Position Context (session only)
Track per-ticker position mentioned during the session:
- "saya holding ITMG" → position["ITMG"] = "holding"
- "belum masuk BBCA"  → position["BBCA"] = "not_holding"
- "sudah CL TLKM"     → position["TLKM"] = "not_holding"

Pass the correct `user_position` to `fin_analyst.generate_report()`.
Do NOT persist across sessions unless user says "simpan posisi ini".

## Shorthand Commands
| Input                      | Action                                      |
|----------------------------|---------------------------------------------|
| `analisa <TICKER>`         | Full analysis report                        |
| `signal <TICKER>`          | Signal only, no enrichment                  |
| `berita <TICKER>`          | News scrape only                            |
| `saham potensial`          | Stock screening                             |
| `watchlist`                | Watchlist scan table                        |
| `tambah <TICKER>`          | Add to watchlist                            |
| `hapus <TICKER>`           | Remove from watchlist                       |
| `status`                   | System health check                         |
| `proses video <path>`      | Video ingestion                             |
| `apa itu <concept>`        | RAG knowledge query                         |
| `help`                     | Show this command list                      |

## Edit Policy
This file is edited manually by the developer.
Orchestrator may update session context in MEMORY.md during a session,
but does NOT modify USER.md autonomously.
