"""
example_flows.py
----------------
Concrete usage examples for each orchestrator workflow.
Shows how task delegation looks in practice.

Location: /workspaces/orchestrator/example_flows.py
"""

from orchestrator_client import delegate, delegate_parallel, delegate_async
from task_contract import AgentID, SkillName, TaskStatus


# ─────────────────────────────────────────────────────────────────────────────
# FLOW 1: Stock Analysis — synchronous parallel
# Triggered by: "analisa ITMG" / "analisa BBCA saya lagi holding"
# ─────────────────────────────────────────────────────────────────────────────

def flow_stock_analysis(ticker: str, user_position: str = "unknown") -> dict:
    """
    Full stock analysis: signal + news + RAG → report.
    Parallel enrichment, sequential report generation.
    """

    # Step 1: Get latest signal (fast, local read on fin_analyst side)
    signal_result = delegate(
        to      = AgentID.FIN_ANALYST,
        skill   = SkillName.GET_LATEST_SIGNAL,
        payload = { "symbol": ticker },
        timeout_s = 5
    )

    if signal_result.status == TaskStatus.FAILED:
        return { "status": "error", "reason": f"Signal unavailable for {ticker}: {signal_result.error}" }

    signal = signal_result.result

    # Step 2: Parallel enrichment — news + RAG simultaneously
    # Determine sector from fin_analyst MEMORY.md sector map
    sector = signal.get("sector", "")
    rag_query = f"{ticker} {sector} IDX stock analysis outlook".strip()

    enrichment = delegate_parallel([
        {
            "to":      AgentID.WEB_SCRAPER,
            "skill":   SkillName.SCRAPE_NEWS,
            "payload": { "symbol": ticker, "hours": 24, "max_articles": 10 }
        },
        {
            "to":      AgentID.ML_PROCESSOR,
            "skill":   SkillName.RAG_QUERY,
            "payload": { "query": rag_query, "top_k": 4 }
        }
    ], timeout_s=20)

    news = enrichment.get(SkillName.SCRAPE_NEWS.value)
    rag  = enrichment.get(SkillName.RAG_QUERY.value)

    # Step 3: Generate report
    report_result = delegate(
        to    = AgentID.FIN_ANALYST,
        skill = SkillName.GENERATE_REPORT,
        payload = {
            "signal":        signal,
            "news":          news.result if news and news.status == TaskStatus.SUCCESS else None,
            "rag_context":   rag.result  if rag  and rag.status  == TaskStatus.SUCCESS else None,
            "user_position": user_position
        },
        timeout_s = 15
    )

    return report_result.result if report_result.status == TaskStatus.SUCCESS else {
        "status": "error", "reason": report_result.error
    }


# ─────────────────────────────────────────────────────────────────────────────
# FLOW 2: Stock Screening — synchronous parallel
# Triggered by: "saham potensial" / "carikan saham bagus"
# ─────────────────────────────────────────────────────────────────────────────

def flow_stock_screening() -> dict:
    """
    Find potential IDX stocks from trending news + market movers + RAG context.
    """

    # Parallel: trending news + market movers + RAG domain context
    data = delegate_parallel([
        {
            "to":      AgentID.WEB_SCRAPER,
            "skill":   SkillName.SCRAPE_TRENDING,
            "payload": { "market": "IDX", "hours": 48 }
        },
        {
            "to":      AgentID.FIN_ANALYST,
            "skill":   SkillName.SCAN_MARKET_MOVERS,
            "payload": { "limit": 10 }
        },
        {
            "to":      AgentID.ML_PROCESSOR,
            "skill":   SkillName.RAG_QUERY,
            "payload": { "query": "IDX high momentum sectors potential stocks", "top_k": 4 }
        }
    ], timeout_s=25)

    trending = data.get(SkillName.SCRAPE_TRENDING.value)
    movers   = data.get(SkillName.SCAN_MARKET_MOVERS.value)
    rag      = data.get(SkillName.RAG_QUERY.value)

    # fin_analyst synthesizes candidates
    screen_result = delegate(
        to    = AgentID.FIN_ANALYST,
        skill = SkillName.SCREEN_CANDIDATES,
        payload = {
            "trending":    trending.result if trending and trending.status == TaskStatus.SUCCESS else None,
            "movers":      movers.result   if movers   and movers.status   == TaskStatus.SUCCESS else None,
            "rag_context": rag.result      if rag      and rag.status      == TaskStatus.SUCCESS else None,
        },
        timeout_s = 20
    )

    return screen_result.result if screen_result.status == TaskStatus.SUCCESS else {
        "status": "error", "reason": screen_result.error
    }


# ─────────────────────────────────────────────────────────────────────────────
# FLOW 3: Video Ingestion — asynchronous fire-and-forget
# Triggered by: "proses video lecture_01.mp4"
# ─────────────────────────────────────────────────────────────────────────────

def flow_video_ingestion(video_path: str, notify_user_fn: callable) -> str:
    """
    Start video ingestion in background. Return task_id immediately.
    Call notify_user_fn(result) when done.

    notify_user_fn should send a message to the user (e.g. via chat callback).
    """

    def on_complete(result):
        if result.status == TaskStatus.SUCCESS:
            r = result.result
            notify_user_fn(
                f"✅ Video selesai diproses.\n"
                f"   Video ID  : {r.get('video_id')}\n"
                f"   Chunks    : {r.get('chunks_indexed')}\n"
                f"   Training  : {r.get('training_records')} records\n"
                f"   Durasi    : {result.duration_s:.0f}s"
            )
        else:
            notify_user_fn(
                f"❌ Video processing failed: {result.error}"
            )

    task_id = delegate_async(
        to          = AgentID.ML_PROCESSOR,
        skill       = SkillName.VIDEO_ANALYSIS,
        payload     = { "video_path": video_path, "language": "id", "model_size": "medium" },
        on_complete = on_complete,
        timeout_s   = 3600   # 1 hour max
    )

    return task_id


# ─────────────────────────────────────────────────────────────────────────────
# FLOW 4: News Only — synchronous single agent
# Triggered by: "berita TLKM"
# ─────────────────────────────────────────────────────────────────────────────

def flow_news_only(ticker: str, hours: int = 24) -> dict:
    result = delegate(
        to      = AgentID.WEB_SCRAPER,
        skill   = SkillName.SCRAPE_NEWS,
        payload = { "symbol": ticker, "hours": hours, "max_articles": 10 },
        timeout_s = 20
    )
    return result.result if result.status == TaskStatus.SUCCESS else {
        "status": "error", "reason": result.error
    }


# ─────────────────────────────────────────────────────────────────────────────
# FLOW 5: Knowledge Query — synchronous single agent
# Triggered by: "apa itu MACD" / "jelaskan support resistance"
# ─────────────────────────────────────────────────────────────────────────────

def flow_knowledge_query(question: str) -> dict:
    result = delegate(
        to      = AgentID.ML_PROCESSOR,
        skill   = SkillName.RAG_QUERY,
        payload = { "query": question, "top_k": 4 },
        timeout_s = 15
    )
    return result.result if result.status == TaskStatus.SUCCESS else {
        "status": "error", "reason": result.error
    }


# ─────────────────────────────────────────────────────────────────────────────
# FLOW 6: Watchlist Scan — sequential per ticker
# Triggered by: "watchlist" / "cek semua"
# ─────────────────────────────────────────────────────────────────────────────

def flow_watchlist_scan(tickers: list[str]) -> list[dict]:
    """
    Fetch latest signal for each ticker sequentially.
    Returns list of signal summaries for table rendering.
    """
    results = []
    for ticker in tickers:
        result = delegate(
            to      = AgentID.FIN_ANALYST,
            skill   = SkillName.GET_LATEST_SIGNAL,
            payload = { "symbol": ticker },
            timeout_s = 5
        )
        if result.status == TaskStatus.SUCCESS:
            results.append(result.result)
        else:
            results.append({
                "symbol": ticker,
                "status": "unavailable",
                "error":  result.error
            })
    return results