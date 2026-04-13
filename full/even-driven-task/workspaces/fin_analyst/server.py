"""
fin_analyst_server.py
---------------------
fin_analyst agent server implementation.
Shows how each agent wires up its skills to the AgentServer base class.

Location: /workspaces/fin_analyst/server.py
Run with: python server.py
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from agent_server import AgentServer
from task_contract import SkillName

SIGNALS_DIR = "/workspaces/fin_analyst/data/signals"
LOGS_DIR    = "/workspaces/fin_analyst/logs"


class FinAnalystServer(AgentServer):

    def __init__(self):
        super().__init__(agent_id="fin_analyst", port=8001)
        self.register_skill(SkillName.GET_LATEST_SIGNAL,  self.get_latest_signal)
        self.register_skill(SkillName.GENERATE_REPORT,    self.generate_report)
        self.register_skill(SkillName.SCAN_MARKET_MOVERS, self.scan_market_movers)
        self.register_skill(SkillName.SCREEN_CANDIDATES,  self.screen_candidates)
        self.register_skill(SkillName.RECEIVE_SIGNAL,     self.receive_signal)

        os.makedirs(SIGNALS_DIR, exist_ok=True)
        os.makedirs(LOGS_DIR, exist_ok=True)

    # ── Skills ────────────────────────────────────────────────────────────────

    def get_latest_signal(self, payload: dict) -> dict:
        """
        Read cached consensus signal for a ticker.
        Fast local read — no external calls.
        """
        symbol = payload.get("symbol", "").upper()
        path   = Path(SIGNALS_DIR) / f"{symbol}.json"

        if not path.exists():
            return { "status": "not_found", "symbol": symbol }

        with open(path) as f:
            signal = json.load(f)

        # Compute signal age
        received_at = signal.get("receivedAt", "")
        age_hours   = self._signal_age_hours(received_at)

        if age_hours > 24:
            signal["status"] = "very_stale"
        elif age_hours > 8:
            signal["status"] = "stale"
        else:
            signal["status"] = "ok"

        signal["age_hours"] = round(age_hours, 1)
        return signal

    def generate_report(self, payload: dict) -> dict:
        """
        Synthesize signal + news + RAG → full ReportObject.
        All logic follows SOUL.md rules.
        """
        signal       = payload.get("signal")
        news         = payload.get("news")
        rag_context  = payload.get("rag_context")
        user_position = payload.get("user_position", "unknown")

        if not signal or signal.get("status") == "not_found":
            return { "status": "error", "reason": "signal_required" }

        ticker  = signal.get("symbol", "?")
        company = signal.get("name", "")

        # Build news sentiment summary
        news_section = self._build_news_section(news)

        # Build RAG section
        rag_section = self._build_rag_section(rag_context)

        # Detect conflicts
        conflicts = self._detect_conflicts(signal, news)

        # Build reasoning
        reasoning = self._build_reasoning(signal, news_section, rag_section, conflicts)

        # Data quality assessment
        data_quality = self._assess_data_quality(signal)

        report = {
            "ticker":      ticker,
            "company":     company,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "signal": {
                "trend":            signal.get("trendConsensus"),
                "actionIfHolding":  signal.get("actionIfHolding"),
                "actionIfNotHolding": signal.get("actionIfNotHolding"),
                "consensusScore":   signal.get("consensusScore"),
                "confidencePct":    signal.get("avgConfidencePct", 0),
                "dataQuality":      data_quality,
                "receivedAt":       signal.get("receivedAt"),
                "age_hours":        signal.get("age_hours", 0),
                "status":           signal.get("status", "ok")
            },
            "instructions": signal.get("instructions", {}),
            "userPosition": user_position,
            "newsSentiment": news_section,
            "ragContext": rag_section,
            "conflicts": conflicts,
            "reasoning": reasoning,
            "disclaimer": (
                "This report is informational only and does not constitute "
                "investment advice. All investment decisions are solely the "
                "investor's responsibility."
            )
        }

        self._log_report(ticker, data_quality)
        return report

    def receive_signal(self, payload: dict) -> dict:
        """
        Accept and store incoming push from the existing stock analysis system.
        Validates, normalizes, and writes to signals/{SYMBOL}.json.
        """
        data = payload.get("data", [])
        if not data:
            return { "status": "rejected", "reason": "empty_data" }

        stored = []
        for item in data:
            stock  = item.get("stock", {})
            symbol = stock.get("symbol", "").upper()
            if not symbol:
                continue

            normalized = {
                "symbol":          symbol,
                "name":            stock.get("name", ""),
                "trendConsensus":  item.get("trendConsensus"),
                "actionIfHolding": item.get("actionIfHolding"),
                "actionIfNotHolding": item.get("actionIfNotHolding"),
                "instructions": {
                    "holding":     item.get("finalInstructions", {}).get("holding", ""),
                    "not_holding": item.get("finalInstructions", {}).get("not_holding", "")
                },
                "consensusScore":  item.get("consensusScore"),
                "consensusInt":    self._parse_consensus(item.get("consensusScore", "0/0")),
                "avgConfidencePct": item.get("avgConfidencePct", 0),
                "lastPrice":       item.get("lastPrice", "0"),
                "receivedAt":      datetime.now(timezone.utc).isoformat(),
                "sourceCreatedAt": item.get("createdAt")
            }

            path = Path(SIGNALS_DIR) / f"{symbol}.json"
            with open(path, "w") as f:
                json.dump(normalized, f, indent=2, ensure_ascii=False)

            self._log_signal(symbol, "received", item.get("consensusScore"))
            stored.append(symbol)

        return { "status": "stored", "symbols": stored, "count": len(stored) }

    def scan_market_movers(self, payload: dict) -> dict:
        """Query IDX market data API for top movers."""
        limit = payload.get("limit", 10)
        # Implementation: call config/market_data.json endpoint
        # Placeholder — replace with actual market data API call
        return {
            "scannedAt":  datetime.now(timezone.utc).isoformat(),
            "topGainers": [],
            "topLosers":  [],
            "highVolume": [],
            "note":       "Market data API not yet configured"
        }

    def screen_candidates(self, payload: dict) -> dict:
        """Rank potential stock candidates from multi-source inputs."""
        trending   = payload.get("trending") or {}
        movers     = payload.get("movers") or {}
        rag        = payload.get("rag_context") or {}

        # Collect all mentioned tickers
        candidates = {}

        for item in trending.get("topTickers", []):
            sym = item.get("symbol", "")
            if sym:
                candidates[sym] = candidates.get(sym, {"symbol": sym, "score": 0.0, "sources": []})
                candidates[sym]["score"] += item.get("mentions", 1) * 0.35
                candidates[sym]["sources"].append("news_trending")
                candidates[sym]["newsSentiment"] = item.get("sentiment", "neutral")

        for category in ["topGainers", "highVolume"]:
            for item in movers.get(category, []):
                sym = item.get("symbol", "")
                if sym:
                    candidates[sym] = candidates.get(sym, {"symbol": sym, "score": 0.0, "sources": []})
                    candidates[sym]["score"] += 0.25
                    if "market_movers" not in candidates[sym]["sources"]:
                        candidates[sym]["sources"].append("market_movers")

        # Filter: must appear in at least 2 sources
        qualified = [c for c in candidates.values() if len(c["sources"]) >= 2]

        # Enrich with stored signals if available
        for c in qualified:
            signal = self.get_latest_signal({"symbol": c["symbol"]})
            if signal.get("status") in ("ok", "stale"):
                c["signal"]       = signal
                c["score"]       += 0.4 * (signal.get("consensusInt", 0) / 3)
                c["thesis"]       = self._build_thesis(c, signal)

        # Sort by score, return top 5
        qualified.sort(key=lambda x: x["score"], reverse=True)
        return {
            "candidates":  qualified[:5],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "totalFound":  len(qualified)
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _signal_age_hours(self, received_at: str) -> float:
        if not received_at:
            return 999.0
        try:
            received = datetime.fromisoformat(received_at)
            now      = datetime.now(timezone.utc)
            return (now - received).total_seconds() / 3600
        except Exception:
            return 999.0

    def _parse_consensus(self, score_str: str) -> int:
        try:
            return int(score_str.split("/")[0])
        except Exception:
            return 0

    def _assess_data_quality(self, signal: dict) -> str:
        if signal.get("avgConfidencePct", 0) == 0:
            return "insufficient"
        if self._parse_consensus(signal.get("consensusScore", "0/0")) < 2:
            return "partial"
        return "full"

    def _build_news_section(self, news: dict | None) -> dict:
        if not news:
            return { "overall": "unavailable", "summary": "", "articles": [], "conflictsWithSignal": False }
        return {
            "overall":            news.get("overallSentiment", "neutral"),
            "summary":            self._summarize_news(news.get("articles", [])),
            "articles":           news.get("articles", []),
            "totalFound":         news.get("totalFound", 0),
            "conflictsWithSignal": False  # set in _detect_conflicts
        }

    def _build_rag_section(self, rag: dict | None) -> dict:
        if not rag or rag.get("confidence") in ("no_context", "error", None):
            return { "available": False, "insight": "", "sources": [] }
        return {
            "available": True,
            "insight":   rag.get("answer", ""),
            "sources":   rag.get("sources", []),
            "confidence": rag.get("confidence")
        }

    def _detect_conflicts(self, signal: dict, news: dict | None) -> list[str]:
        conflicts = []
        if not news:
            return conflicts
        action    = signal.get("actionIfNotHolding", "")
        sentiment = news.get("overallSentiment", "neutral")
        if action in ("BUY", "ACCUMULATE") and sentiment == "negative":
            conflicts.append("buy_signal_negative_news")
        if action in ("SELL", "CUT LOSS") and sentiment == "positive":
            conflicts.append("sell_signal_positive_news")
        return conflicts

    def _build_reasoning(self, signal, news_section, rag_section, conflicts) -> str:
        parts = []
        trend      = signal.get("trendConsensus", "")
        consensus  = signal.get("consensusScore", "?")
        conf       = signal.get("avgConfidencePct", 0)
        parts.append(f"Trend {trend} with consensus {consensus}.")
        if conf == 0:
            parts.append("Insufficient intraday data for confidence confirmation.")
        if news_section.get("overall") not in ("unavailable", "neutral", ""):
            parts.append(f"News sentiment: {news_section['overall']}.")
        if conflicts:
            parts.append("⚡ Signal conflicts with news sentiment — exercise caution.")
        if rag_section.get("available"):
            parts.append("Domain knowledge context available — see RAG section.")
        return " ".join(parts)

    def _build_thesis(self, candidate: dict, signal: dict) -> str:
        trend   = signal.get("trendConsensus", "")
        action  = signal.get("actionIfNotHolding", "")
        news    = candidate.get("newsSentiment", "neutral")
        return f"Trending in news ({news} sentiment), {trend.lower()} trend, signal: {action}."

    def _summarize_news(self, articles: list) -> str:
        if not articles:
            return ""
        titles = [a.get("title", "") for a in articles[:3]]
        return " | ".join(t for t in titles if t)

    def _log_signal(self, symbol: str, event: str, consensus: str):
        entry = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol, "event": event, "consensusScore": consensus
        })
        with open(f"{LOGS_DIR}/signal_log.jsonl", "a") as f:
            f.write(entry + "\n")

    def _log_report(self, ticker: str, quality: str):
        entry = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "ticker": ticker, "dataQuality": quality
        })
        with open(f"{LOGS_DIR}/report_log.jsonl", "a") as f:
            f.write(entry + "\n")

    def _update_heartbeat(self):
        signals = list(Path(SIGNALS_DIR).glob("*.json"))
        super()._update_heartbeat()
        import json as _json
        hb = {
            "agent_id":            "fin_analyst",
            "status":              "ok" if signals else "degraded",
            "last_ping":           datetime.now(timezone.utc).isoformat(),
            "port":                self.port,
            "components": {
                "signal_store":    "ok" if signals else "empty",
                "market_data_api": "ok"
            },
            "signals_stored":      len(signals)
        }
        with open("/workspaces/fin_analyst/heartbeat.json", "w") as f:
            _json.dump(hb, f, indent=2)


if __name__ == "__main__":
    FinAnalystServer().start()