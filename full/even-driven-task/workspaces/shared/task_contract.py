"""
task_contract.py
----------------
Shared data contracts for inter-agent communication.
Every agent imports from here — single source of truth for schemas.

Location: /workspaces/shared/task_contract.py
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import json
import random
import string


# ── Enums ─────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    SUCCESS    = "success"
    FAILED     = "failed"
    TIMEOUT    = "timeout"


class AgentID(str, Enum):
    ORCHESTRATOR = "orchestrator"
    FIN_ANALYST  = "fin_analyst"
    WEB_SCRAPER  = "web_scraper"
    ML_PROCESSOR = "ml_processor"


class SkillName(str, Enum):
    # fin_analyst
    GET_LATEST_SIGNAL  = "get_latest_signal"
    GENERATE_REPORT    = "generate_report"
    SCAN_MARKET_MOVERS = "scan_market_movers"
    SCREEN_CANDIDATES  = "screen_candidates"
    RECEIVE_SIGNAL     = "receive_signal"

    # web_scraper
    SCRAPE_NEWS        = "scrape_news"
    SCRAPE_TRENDING    = "scrape_trending"
    SCRAPE_SECTOR      = "scrape_sector"

    # ml_processor
    RAG_QUERY          = "rag_query"
    VIDEO_ANALYSIS     = "video_content_analysis"


# ── Task ID ───────────────────────────────────────────────────────────────────

def make_task_id(skill: SkillName, suffix: str = "") -> str:
    """
    Generate a unique, readable task ID.
    Format: YYYYMMDD_HHMMSS_<skill>_<rand4>
    Example: 20260413_143022_rag_query_a3f1
    """
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    name = skill.value.replace("_", "")[:12]
    parts = [ts, name, rand]
    if suffix:
        parts.append(suffix[:8])
    return "_".join(parts)


# ── Task ──────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """
    Written by orchestrator to /workspaces/shared/tasks/<task_id>.json
    before calling agent.notify().
    """
    task_id    : str
    from_agent : AgentID
    to_agent   : AgentID
    skill      : SkillName
    payload    : dict
    created_at : str   = field(default_factory=lambda: _now())
    timeout_s  : int   = 30
    callback_url: str  = ""    # orchestrator's callback endpoint

    def to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def from_file(cls, path: str) -> "Task":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    """
    Written by agent worker to /workspaces/shared/results/<task_id>.json
    before calling orchestrator callback.
    """
    task_id      : str
    status       : TaskStatus
    result       : Any        = None
    error        : str        = None
    started_at   : str        = field(default_factory=lambda: _now())
    completed_at : str        = field(default_factory=lambda: _now())
    duration_s   : float      = 0.0

    def to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def from_file(cls, path: str) -> "TaskResult":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


# ── Notification ──────────────────────────────────────────────────────────────

@dataclass
class TaskNotification:
    """
    Sent by orchestrator to agent worker via direct call (HTTP or function).
    Minimal payload — agent reads full task from file.
    """
    task_id   : str
    task_file : str    # absolute path to task JSON file
    skill     : str    # for quick routing without reading the file
    from_agent: str


@dataclass
class TaskCallback:
    """
    Sent by agent worker to orchestrator when task completes.
    Minimal payload — orchestrator reads full result from file.
    """
    task_id     : str
    status      : str  # "success" | "failed" | "timeout"
    result_file : str  # absolute path to result JSON file
    from_agent  : str
    duration_s  : float


# ── Paths ─────────────────────────────────────────────────────────────────────

SHARED_ROOT   = "/workspaces/shared"
TASKS_DIR     = f"{SHARED_ROOT}/tasks"
RESULTS_DIR   = f"{SHARED_ROOT}/results"

def task_path(task_id: str) -> str:
    return f"{TASKS_DIR}/{task_id}.json"

def result_path(task_id: str) -> str:
    return f"{RESULTS_DIR}/{task_id}.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()