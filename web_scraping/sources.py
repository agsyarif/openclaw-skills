"""
sources.py
----------
Load konfigurasi sumber berita dari JSON config file.
User cukup edit sources_config.json — tidak perlu ubah kode.

Location: /workspaces/web_scraper/skills/web_scraping/sources.py
"""

import json
from pathlib import Path

CONFIG_PATH          = Path(__file__).parent / "config" / "sources_config.json"
FALLBACK_CONFIG_PATH = Path("/workspaces/web_scraper/config/sources_config.json")


def load_sources() -> list[dict]:
    """
    Load daftar sumber dari JSON config.
    Hanya return sumber yang enabled=true, sorted by priority.
    """
    config  = _load_config()
    sources = config.get("sources", [])
    active  = [s for s in sources if s.get("enabled", True)]
    active.sort(key=lambda x: x.get("priority", 99))

    if not active:
        print("⚠️  Tidak ada sumber aktif di sources_config.json")

    return active


def load_defaults() -> dict:
    """Load default settings dari config."""
    config = _load_config()
    return config.get("defaults", {
        "max_articles_per_source": 10,
        "cache_ttl_minutes":       30,
        "request_timeout_s":       12,
        "min_title_length":        15,
        "max_summary_chars":       300,
    })


def _load_config() -> dict:
    for path in [CONFIG_PATH, FALLBACK_CONFIG_PATH]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Error loading {path}: {e}")
    print(f"⚠️  Config tidak ditemukan. Buat file:\n   {FALLBACK_CONFIG_PATH}")
    return {"sources": [], "defaults": {}}


# ── Sector Keywords ────────────────────────────────────────────────────────────

SECTOR_KEYWORDS = {
    "banking":       ["bank", "perbankan", "kredit", "BI rate", "suku bunga", "OJK", "BBCA", "BBRI", "BMRI", "BBNI"],
    "coal_mining":   ["batubara", "coal", "tambang", "ITMG", "ADRO", "PTBA", "harga batubara"],
    "telco":         ["telekomunikasi", "telco", "seluler", "5G", "TLKM", "EXCL", "ISAT"],
    "consumer":      ["consumer goods", "FMCG", "ritel", "ICBP", "INDF", "UNVR", "MYOR"],
    "automotive":    ["otomotif", "mobil", "kendaraan", "EV", "ASII", "SMSM"],
    "mining_metals": ["nikel", "emas", "tembaga", "ANTM", "INCO", "MDKA"],
    "property":      ["properti", "real estate", "perumahan", "KPR", "BSDE", "SMRA", "CTRA"],
    "energy":        ["energi", "minyak", "gas", "BBM", "PGAS", "MEDC", "AKRA"],
}

# ── Known IDX Tickers ─────────────────────────────────────────────────────────

KNOWN_TICKERS = {
    "BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "BTPS", "BNII", "MEGA",
    "ITMG", "ADRO", "PTBA", "BUMI", "HRUM", "TOBA",
    "TLKM", "EXCL", "ISAT", "FREN",
    "ICBP", "INDF", "UNVR", "MYOR", "CPIN", "JPFA",
    "ASII", "SMSM", "AUTO", "INDS",
    "ANTM", "INCO", "MDKA", "TINS",
    "BSDE", "SMRA", "CTRA", "PWON", "LPKR",
    "PGAS", "MEDC", "AKRA", "ELSA",
    "GOTO", "BUKA", "EMTK", "SCMA", "MTEL",
}
