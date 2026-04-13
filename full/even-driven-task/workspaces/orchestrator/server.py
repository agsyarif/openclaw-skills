"""
server.py — orchestrator
Location: /workspaces/orchestrator/server.py
Run with: python server.py

The orchestrator is the user-facing entry point.
It exposes:
  POST /chat      ← user message (chat mode)
  POST /api       ← structured API request
  POST /callback  ← agent workers report task completion here
  GET  /health    ← system status
  GET  /status    ← detailed agent health summary
"""

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Shared modules
sys.path.insert(0, "/workspaces/shared")
from task_contract import AgentID, SkillName, TaskStatus

# Orchestrator modules
sys.path.insert(0, "/workspaces/orchestrator")
from orchestrator_client import (
    delegate, delegate_parallel, delegate_async,
    handle_callback, handle_async_callback
)
from example_flows import (
    flow_stock_analysis,
    flow_stock_screening,
    flow_video_ingestion,
    flow_news_only,
    flow_knowledge_query,
    flow_watchlist_scan
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [orchestrator] %(levelname)s %(message)s"
)
log = logging.getLogger("orchestrator")

PORT           = 8000
WATCHLIST_PATH = "/workspaces/orchestrator/data/watchlist.json"
LOGS_DIR       = "/workspaces/orchestrator/logs"
HEARTBEAT_PATH = "/workspaces/orchestrator/heartbeat.json"
AGENT_PORTS    = {
    "fin_analyst":  "http://localhost:8001",
    "web_scraper":  "http://localhost:8002",
    "ml_processor": "http://localhost:8003",
}

_request_count = 0
_start_time    = time.time()


# ── Intent Router ──────────────────────────────────────────────────────────────

def route_intent(user_input: str, session: dict) -> dict:
    """
    Resolve user intent from natural language and execute the correct flow.
    Returns a response dict { text, data }.
    """
    text    = user_input.strip()
    text_lo = text.lower()

    # ── Shorthand commands ────────────────────────────────────────────────────

    if text_lo in ("status", "cek status", "system status"):
        return handle_status()

    if text_lo in ("help", "bantuan"):
        return handle_help()

    if text_lo in ("watchlist", "cek watchlist", "lihat watchlist"):
        return handle_watchlist_scan()

    if text_lo.startswith("tambah ") and len(text) <= 12:
        ticker = text[7:].strip().upper()
        return handle_watchlist_add(ticker)

    if text_lo.startswith("hapus ") and len(text) <= 11:
        ticker = text[6:].strip().upper()
        return handle_watchlist_remove(ticker)

    # ── Video ingestion ───────────────────────────────────────────────────────

    if "proses video" in text_lo or "analisa video" in text_lo or "tambah video" in text_lo:
        path = _extract_path(text)
        if not path:
            return { "text": "Sebutkan path video-nya. Contoh: proses video /data/raw/lecture.mp4" }
        return handle_video_ingestion(path, session)

    # ── Knowledge query ───────────────────────────────────────────────────────

    if any(kw in text_lo for kw in ("apa itu", "jelaskan", "bagaimana cara", "what is", "explain")):
        return handle_knowledge_query(text)

    # ── News only ─────────────────────────────────────────────────────────────

    if any(kw in text_lo for kw in ("berita", "news")) and not any(
        kw in text_lo for kw in ("analisa", "signal", "report")
    ):
        ticker = _extract_ticker(text)
        if ticker:
            hours = _extract_hours(text)
            return handle_news_only(ticker, hours)

    # ── Signal only (fast) ────────────────────────────────────────────────────

    if text_lo.startswith("signal "):
        ticker = _extract_ticker(text)
        if ticker:
            return handle_signal_only(ticker)

    # ── Stock screening ───────────────────────────────────────────────────────

    if any(kw in text_lo for kw in (
        "saham potensial", "saham bagus", "rekomendasikan", "carikan saham",
        "screening", "stock pick", "peluang"
    )):
        return handle_stock_screening()

    # ── Full stock analysis (default for ticker mentions) ────────────────────

    ticker = _extract_ticker(text)
    if ticker:
        position = _extract_position(text, session, ticker)
        return handle_stock_analysis(ticker, position)

    # ── Fallback ──────────────────────────────────────────────────────────────

    return {
        "text": (
            "Saya tidak yakin apa yang Anda maksud. Ketik 'help' untuk daftar perintah.\n"
            "Atau sebutkan ticker saham langsung, contoh: 'analisa BBCA'"
        )
    }


# ── Flow Handlers ──────────────────────────────────────────────────────────────

def handle_stock_analysis(ticker: str, position: str) -> dict:
    log.info(f"Flow: stock_analysis | ticker={ticker} | position={position}")
    result = flow_stock_analysis(ticker, position)
    if result.get("status") == "error":
        return { "text": f"❌ {result.get('reason', 'Analysis failed')}" }
    return { "text": _format_report(result), "data": result }


def handle_signal_only(ticker: str) -> dict:
    log.info(f"Flow: signal_only | ticker={ticker}")
    result = delegate(
        to=AgentID.FIN_ANALYST,
        skill=SkillName.GET_LATEST_SIGNAL,
        payload={"symbol": ticker},
        timeout_s=5
    )
    if result.status != TaskStatus.SUCCESS:
        return { "text": f"❌ Signal tidak tersedia untuk {ticker}: {result.error}" }
    s = result.result
    if s.get("status") == "not_found":
        return { "text": f"⚠️  Tidak ada data signal untuk {ticker}. Belum ada push dari sistem analisa." }
    age_note = f" ⚠️  ({s.get('age_hours', 0):.0f} jam lalu)" if s.get("status") == "stale" else ""
    return {
        "text": (
            f"📊 {ticker} — Signal{age_note}\n"
            f"   Trend      : {s.get('trendConsensus')}\n"
            f"   Holding    : {s.get('actionIfHolding')}\n"
            f"   Not Holding: {s.get('actionIfNotHolding')}\n"
            f"   Consensus  : {s.get('consensusScore')}"
        ),
        "data": s
    }


def handle_news_only(ticker: str, hours: int = 24) -> dict:
    log.info(f"Flow: news_only | ticker={ticker} | hours={hours}")
    result = flow_news_only(ticker, hours)
    if result.get("status") == "error":
        return { "text": f"❌ {result.get('reason')}" }
    articles = result.get("articles", [])
    if not articles:
        return { "text": f"Tidak ada berita untuk {ticker} dalam {hours} jam terakhir." }
    lines = [f"📰 Berita {ticker} ({hours}h) — Sentimen: {result.get('overallSentiment', '-')}"]
    for a in articles[:5]:
        lines.append(f"\n• {a.get('title')}\n  {a.get('source')} | {a.get('sentiment')}")
    return { "text": "\n".join(lines), "data": result }


def handle_stock_screening() -> dict:
    log.info("Flow: stock_screening")
    result = flow_stock_screening()
    if result.get("status") == "error":
        return { "text": f"❌ {result.get('reason')}" }
    candidates = result.get("candidates", [])
    if not candidates:
        return { "text": "Tidak ada kandidat saham potensial yang ditemukan saat ini." }
    lines = [f"🔍 Saham Potensial IDX — {datetime.now().strftime('%d %b %Y')}\n"]
    for c in candidates:
        sig = c.get("signal", {})
        lines.append(
            f"#{c.get('symbol')} — {c.get('company', '')}\n"
            f"  Signal    : {sig.get('trendConsensus', '-')} | {sig.get('actionIfNotHolding', '-')}\n"
            f"  Consensus : {sig.get('consensusScore', '-')}\n"
            f"  Thesis    : {c.get('thesis', '-')}\n"
            f"  Sentimen  : {c.get('newsSentiment', '-')}\n"
        )
    lines.append("\n⚠️  Bukan rekomendasi investasi. Lakukan analisa mendalam sebelum keputusan.")
    return { "text": "\n".join(lines), "data": result }


def handle_knowledge_query(question: str) -> dict:
    log.info(f"Flow: knowledge_query | q={question[:60]}")
    result = flow_knowledge_query(question)
    if result.get("confidence") in ("error", "no_context"):
        return {
            "text": (
                f"Topik ini tidak tersedia di knowledge base.\n"
                f"Tambahkan video yang relevan dengan: proses video <path>"
            )
        }
    sources = result.get("sources", [])
    src_note = ""
    if sources:
        src_note = "\n\n📚 Sumber: " + ", ".join(
            f"{s.get('video_title', s.get('video_id'))} [{s.get('start', 0):.0f}s]"
            for s in sources[:3]
        )
    return { "text": result.get("answer", "") + src_note, "data": result }


def handle_video_ingestion(video_path: str, session: dict) -> dict:
    log.info(f"Flow: video_ingestion | path={video_path}")

    def notify_user(msg: str):
        # In production: push to websocket / SSE / user session
        log.info(f"[video_complete] {msg}")

    task_id = flow_video_ingestion(video_path, notify_user)
    return {
        "text": (
            f"⏳ Video sedang diproses di background.\n"
            f"   Task ID: {task_id}\n"
            f"   Estimasi: 10–30 menit tergantung durasi video.\n"
            f"   Anda akan dinotifikasi saat selesai."
        ),
        "task_id": task_id
    }


def handle_watchlist_scan() -> dict:
    tickers = _read_watchlist()
    if not tickers:
        return { "text": "Watchlist kosong. Tambahkan ticker: tambah BBCA" }
    log.info(f"Flow: watchlist_scan | tickers={tickers}")
    signals = flow_watchlist_scan(tickers)
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📋 WATCHLIST — {datetime.now().strftime('%d %b %Y %H:%M')} WIB",
        f"{'TICKER':<8} {'TREND':<15} {'HOLDING':<12} {'NOT HOLD':<12} {'CONS'}",
        "─" * 55
    ]
    for s in signals:
        sym = s.get("symbol", "?")
        if s.get("status") == "unavailable":
            lines.append(f"{sym:<8} {'[unavailable]':<15}")
            continue
        age = f" ⚠️" if s.get("status") == "stale" else ""
        lines.append(
            f"{sym:<8}{age} "
            f"{s.get('trendConsensus', '-'):<15} "
            f"{s.get('actionIfHolding', '-'):<12} "
            f"{s.get('actionIfNotHolding', '-'):<12} "
            f"{s.get('consensusScore', '-')}"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("Ketik 'analisa <TICKER>' untuk report lengkap.")
    return { "text": "\n".join(lines), "data": signals }


def handle_watchlist_add(ticker: str) -> dict:
    if not (len(ticker) == 4 and ticker.isalpha()):
        return { "text": f"❌ Format ticker tidak valid: {ticker}. IDX ticker = 4 huruf (contoh: BBCA)" }
    tickers = _read_watchlist()
    if ticker in tickers:
        return { "text": f"⚠️  {ticker} sudah ada di watchlist." }
    tickers.append(ticker)
    _write_watchlist(tickers)
    return { "text": f"✅ {ticker} ditambahkan ke watchlist. Total: {len(tickers)} ticker." }


def handle_watchlist_remove(ticker: str) -> dict:
    tickers = _read_watchlist()
    if ticker not in tickers:
        return { "text": f"⚠️  {ticker} tidak ada di watchlist." }
    tickers.remove(ticker)
    _write_watchlist(tickers)
    return { "text": f"✅ {ticker} dihapus dari watchlist. Sisa: {len(tickers)} ticker." }


def handle_status() -> dict:
    import urllib.request
    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "🖥  STATUS SISTEM", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    icons = {"UP": "🟢", "STALE": "🟡", "DOWN": "🔴"}
    for agent_id, endpoint in AGENT_PORTS.items():
        try:
            req = urllib.request.Request(f"{endpoint}/health")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data   = json.loads(resp.read())
                uptime = data.get("uptime_s", 0)
                lines.append(f"🟢 {agent_id:<14} UP   (uptime: {uptime:.0f}s)")
        except Exception:
            lines.append(f"🔴 {agent_id:<14} DOWN")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return { "text": "\n".join(lines) }


def handle_help() -> dict:
    return {
        "text": (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📖 PERINTAH TERSEDIA\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "analisa <TICKER>      Full report + signal + berita\n"
            "signal <TICKER>       Signal saja (cepat)\n"
            "berita <TICKER>       Berita terkini\n"
            "saham potensial       Screening IDX\n"
            "watchlist             Lihat semua ticker watchlist\n"
            "tambah <TICKER>       Tambah ke watchlist\n"
            "hapus <TICKER>        Hapus dari watchlist\n"
            "apa itu <konsep>      Query knowledge base\n"
            "proses video <path>   Proses video ke knowledge base\n"
            "status                Cek kesehatan semua agent\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    }


# ── Formatters ─────────────────────────────────────────────────────────────────

def _format_report(report: dict) -> str:
    sig  = report.get("signal", {})
    news = report.get("newsSentiment", {})
    rag  = report.get("ragContext", {})
    inst = report.get("instructions", {})

    # Quality / age flags
    flags = []
    if sig.get("dataQuality") == "insufficient":
        flags.append("⚠️  Tidak ada data intraday")
    if sig.get("consensusScore", "3/3").startswith("1"):
        flags.append("⚠️  Konsensus rendah (1/3)")
    if sig.get("status") == "stale":
        flags.append(f"⚠️  Signal {sig.get('age_hours', '?'):.0f} jam lalu")
    if sig.get("status") == "very_stale":
        flags.append(f"⛔ Signal lebih dari 24 jam — tunggu update")
    flags_str = "   " + " | ".join(flags) + "\n" if flags else ""

    # Conflict
    conflicts = report.get("conflicts", [])
    conflict_str = "   ⚡ Signal berkonflik dengan sentimen berita\n" if conflicts else ""

    # RAG section
    rag_str = ""
    if rag.get("available"):
        rag_str = f"\n🧠 DOMAIN CONTEXT\n   {rag.get('insight', '')[:300]}\n"

    return (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 {report.get('ticker')} — {report.get('company')}\n"
        f"⏱  Signal: {sig.get('receivedAt', '-')[:16].replace('T', ' ')} UTC"
        f"   |   Report: {datetime.now().strftime('%Y-%m-%d %H:%M')} WIB\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 SIGNAL\n"
        f"   Trend      : {sig.get('trend')}\n"
        f"   Holding    : {sig.get('actionIfHolding')}\n"
        f"   Not Holding: {sig.get('actionIfNotHolding')}\n"
        f"   Consensus  : {sig.get('consensusScore')}   Confidence: {sig.get('confidencePct')}%\n"
        f"{flags_str}"
        f"\n📋 INSTRUKSI\n"
        f"   Jika holding     : {inst.get('holding', '-')}\n"
        f"   Jika belum masuk : {inst.get('not_holding', '-')}\n"
        f"\n📰 BERITA ({news.get('totalFound', 0)} artikel, 24h)\n"
        f"   Sentimen: {news.get('overall', 'unavailable')}\n"
        f"   {news.get('summary', '[Tidak ada berita]')}\n"
        f"{conflict_str}"
        f"{rag_str}"
        f"\n💡 SINTESIS\n   {report.get('reasoning', '-')}\n"
        f"\n⚠️  {report.get('disclaimer', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


# ── HTTP Server ────────────────────────────────────────────────────────────────

class OrchestratorHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default access log

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw    = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {
                "agent_id":  "orchestrator",
                "status":    "ok",
                "uptime_s":  round(time.time() - _start_time, 1),
                "requests":  _request_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        elif self.path == "/status":
            result = handle_status()
            self._respond(200, {"status": result["text"]})
        else:
            self._respond(404, {"error": "not_found"})

    def do_POST(self):
        global _request_count
        body = self._read_body()

        if self.path == "/chat":
            # Chat mode — natural language input
            user_input = body.get("message", "")
            session    = body.get("session", {})
            if not user_input:
                self._respond(400, {"error": "message required"})
                return
            _request_count += 1
            result = route_intent(user_input, session)
            self._respond(200, { "response": result.get("text"), "data": result.get("data") })
            _log_interaction("chat", user_input, result)

        elif self.path == "/api":
            # API mode — structured JSON input
            intent  = body.get("intent")
            payload = body.get("payload", {})
            if not intent:
                self._respond(400, {"error": "intent required"})
                return
            _request_count += 1
            result = _handle_api_intent(intent, payload)
            self._respond(200, result)

        elif self.path == "/callback":
            # Agent worker reporting task completion
            threading.Thread(
                target=handle_callback,
                args=(body,),
                daemon=True
            ).start()
            self._respond(202, {"status": "accepted"})

        else:
            self._respond(404, {"error": "unknown_endpoint"})


def _handle_api_intent(intent: str, payload: dict) -> dict:
    """Handle structured API requests."""
    handlers = {
        "stock_analysis":  lambda: flow_stock_analysis(
            payload.get("ticker"), payload.get("user_position", "unknown")),
        "stock_screening": lambda: flow_stock_screening(),
        "news":            lambda: flow_news_only(payload.get("ticker"), payload.get("hours", 24)),
        "knowledge_query": lambda: flow_knowledge_query(payload.get("query", "")),
        "signal":          lambda: delegate(
            AgentID.FIN_ANALYST, SkillName.GET_LATEST_SIGNAL,
            {"symbol": payload.get("ticker")}, timeout_s=5).result,
    }
    handler = handlers.get(intent)
    if not handler:
        return { "status": "error", "reason": f"Unknown intent: {intent}" }
    try:
        return { "status": "success", "result": handler() }
    except Exception as e:
        return { "status": "error", "reason": str(e) }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_ticker(text: str) -> str | None:
    """Find 4-letter uppercase IDX ticker in text."""
    import re
    words = text.upper().split()
    for word in words:
        clean = re.sub(r'[^A-Z]', '', word)
        if len(clean) == 4 and clean.isalpha():
            return clean
    return None

def _extract_position(text: str, session: dict, ticker: str) -> str:
    text_lo = text.lower()
    if any(k in text_lo for k in ("holding", "punya", "sudah beli", "saya masuk")):
        session.setdefault("positions", {})[ticker] = "holding"
        return "holding"
    if any(k in text_lo for k in ("belum masuk", "belum beli", "not holding")):
        session.setdefault("positions", {})[ticker] = "not_holding"
        return "not_holding"
    return session.get("positions", {}).get(ticker, "unknown")

def _extract_hours(text: str) -> int:
    import re
    m = re.search(r'(\d+)\s*(hari|jam|day|hour)', text.lower())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return n * 24 if "hari" in unit or "day" in unit else n
    return 24

def _extract_path(text: str) -> str | None:
    import re
    m = re.search(r'(/[\w./\-_]+\.\w+)', text)
    return m.group(1) if m else None

def _read_watchlist() -> list:
    try:
        with open(WATCHLIST_PATH) as f:
            return json.load(f).get("tickers", [])
    except Exception:
        return []

def _write_watchlist(tickers: list):
    os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
    with open(WATCHLIST_PATH, "w") as f:
        json.dump({"tickers": tickers, "updatedAt": datetime.now(timezone.utc).isoformat()}, f, indent=2)

def _log_interaction(mode: str, user_input: str, result: dict):
    os.makedirs(LOGS_DIR, exist_ok=True)
    entry = json.dumps({
        "ts":    datetime.now(timezone.utc).isoformat(),
        "mode":  mode,
        "input": user_input[:100],
        "has_data": "data" in result
    })
    with open(f"{LOGS_DIR}/interaction_log.jsonl", "a") as f:
        f.write(entry + "\n")

def _update_heartbeat():
    os.makedirs(os.path.dirname(HEARTBEAT_PATH), exist_ok=True)
    with open(HEARTBEAT_PATH, "w") as f:
        json.dump({
            "agent_id":  "orchestrator",
            "status":    "ok",
            "last_ping": datetime.now(timezone.utc).isoformat(),
            "port":      PORT,
            "requests_served": _request_count
        }, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs("/workspaces/orchestrator/data", exist_ok=True)

    # Heartbeat updater thread
    def heartbeat_loop():
        while True:
            _update_heartbeat()
            time.sleep(30)
    threading.Thread(target=heartbeat_loop, daemon=True).start()

    server = HTTPServer(("0.0.0.0", PORT), OrchestratorHandler)
    log.info(f"Orchestrator listening on port {PORT}")
    log.info(f"  Chat API : POST http://localhost:{PORT}/chat")
    log.info(f"  JSON API : POST http://localhost:{PORT}/api")
    log.info(f"  Health   : GET  http://localhost:{PORT}/health")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")
        server.shutdown()