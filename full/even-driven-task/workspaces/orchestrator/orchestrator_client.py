"""
orchestrator_client.py
----------------------
The orchestrator's side of inter-agent communication.

Handles:
  1. Writing task files to shared workspace
  2. Sending push notifications to agent workers
  3. Receiving callbacks from agent workers
  4. Reading result files

Location: /workspaces/orchestrator/orchestrator_client.py
"""

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from task_contract import (
    AgentID, SkillName, Task, TaskCallback, TaskResult, TaskStatus,
    make_task_id, task_path, result_path, TASKS_DIR, RESULTS_DIR
)

log = logging.getLogger("orchestrator.client")

# ── Agent Registry ─────────────────────────────────────────────────────────────
# Each agent exposes an HTTP server. Orchestrator notifies via POST /notify.

AGENT_ENDPOINTS: dict[str, str] = {
    AgentID.FIN_ANALYST:  "http://localhost:8001",
    AgentID.WEB_SCRAPER:  "http://localhost:8002",
    AgentID.ML_PROCESSOR: "http://localhost:8003",
}

ORCHESTRATOR_CALLBACK = "http://localhost:8000/callback"

# ── Pending Callbacks ──────────────────────────────────────────────────────────
# task_id → threading.Event + result holder
# Set when orchestrator receives callback from agent.

_pending: dict[str, dict] = {}
_pending_lock = threading.Lock()


# ── Core: delegate ─────────────────────────────────────────────────────────────

def delegate(
    to: AgentID,
    skill: SkillName,
    payload: dict,
    timeout_s: int = 30
) -> TaskResult:
    """
    Full delegation flow:
      1. Write task file to shared workspace
      2. Push notification to agent
      3. Wait for callback (event-based, no polling)
      4. Read result file

    Returns TaskResult — caller handles success/failure.
    Raises TimeoutError if agent does not respond within timeout_s.
    """
    os.makedirs(TASKS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # 1. Create task
    task_id = make_task_id(skill)
    task    = Task(
        task_id      = task_id,
        from_agent   = AgentID.ORCHESTRATOR,
        to_agent     = to,
        skill        = skill,
        payload      = payload,
        timeout_s    = timeout_s,
        callback_url = ORCHESTRATOR_CALLBACK
    )

    # 2. Write task file
    tpath = task_path(task_id)
    task.to_file(tpath)
    log.info(f"Task written: {task_id} → {to.value}/{skill.value}")

    # 3. Register pending event BEFORE sending notification
    event = threading.Event()
    with _pending_lock:
        _pending[task_id] = {"event": event, "result": None}

    # 4. Send push notification to agent
    endpoint = AGENT_ENDPOINTS.get(to)
    if not endpoint:
        _cleanup_pending(task_id)
        raise ValueError(f"No endpoint registered for agent: {to}")

    _notify_agent(endpoint, task_id, tpath, skill)

    # 5. Wait for callback (event-driven, no polling)
    completed = event.wait(timeout=timeout_s)

    if not completed:
        _cleanup_pending(task_id)
        log.warning(f"Task timeout: {task_id} ({timeout_s}s)")
        raise TimeoutError(f"Agent {to.value} did not respond within {timeout_s}s")

    # 6. Read result
    with _pending_lock:
        entry = _pending.pop(task_id, {})

    rpath = result_path(task_id)
    try:
        return TaskResult.from_file(rpath)
    except Exception as e:
        log.error(f"Cannot read result file for {task_id}: {e}")
        return TaskResult(
            task_id  = task_id,
            status   = TaskStatus.FAILED,
            error    = f"Result file unreadable: {e}"
        )


def _notify_agent(endpoint: str, task_id: str, task_file: str, skill: SkillName):
    """POST /notify to the target agent. Fire and forget — agent processes async."""
    payload = json.dumps({
        "task_id":   task_id,
        "task_file": task_file,
        "skill":     skill.value,
        "from_agent": AgentID.ORCHESTRATOR.value
    }).encode()

    req = urllib.request.Request(
        f"{endpoint}/notify",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            log.info(f"Notification accepted by {endpoint}: {task_id}")
    except urllib.error.URLError as e:
        # Agent not reachable — clean up and raise
        _cleanup_pending(task_id)
        raise RuntimeError(f"Agent at {endpoint} not reachable: {e}")


def handle_callback(raw: dict):
    """
    Called by orchestrator's HTTP server when an agent POSTs to /callback.
    Unblocks the waiting delegate() call.
    """
    task_id = raw.get("task_id")
    if not task_id:
        return

    with _pending_lock:
        entry = _pending.get(task_id)

    if entry:
        entry["result"] = raw
        entry["event"].set()
        log.info(f"Callback received: {task_id} | status: {raw.get('status')}")
    else:
        # Late callback — task already timed out or was cleaned up
        log.warning(f"Late callback for unknown task: {task_id}")


def _cleanup_pending(task_id: str):
    with _pending_lock:
        _pending.pop(task_id, None)


# ── Parallel Delegation ────────────────────────────────────────────────────────

def delegate_parallel(tasks: list[dict], timeout_s: int = 30) -> dict[str, TaskResult]:
    """
    Run multiple delegations concurrently.

    tasks = [
        { "to": AgentID.WEB_SCRAPER,  "skill": SkillName.SCRAPE_NEWS, "payload": {...} },
        { "to": AgentID.ML_PROCESSOR, "skill": SkillName.RAG_QUERY,   "payload": {...} },
    ]

    Returns dict keyed by skill name → TaskResult.
    Each task has its own timeout. Partial results are returned if some fail.
    """
    results = {}

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(
                delegate,
                t["to"], t["skill"], t["payload"], timeout_s
            ): t["skill"].value
            for t in tasks
        }

        for future in as_completed(futures):
            skill_name = futures[future]
            try:
                results[skill_name] = future.result()
            except (TimeoutError, RuntimeError) as e:
                log.warning(f"Parallel task failed: {skill_name} — {e}")
                results[skill_name] = TaskResult(
                    task_id = f"failed_{skill_name}",
                    status  = TaskStatus.FAILED,
                    error   = str(e)
                )

    return results


# ── Fire-and-Forget (for long-running async tasks) ────────────────────────────

def delegate_async(
    to: AgentID,
    skill: SkillName,
    payload: dict,
    on_complete: callable = None,
    timeout_s: int = 1800
) -> str:
    """
    Fire-and-forget delegation for long-running tasks (e.g. video ingestion).

    Orchestrator writes task + notifies agent, then returns task_id immediately.
    When agent completes, it sends callback which triggers on_complete(result).

    Returns task_id for status tracking.
    """
    os.makedirs(TASKS_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    task_id = make_task_id(skill)
    task    = Task(
        task_id      = task_id,
        from_agent   = AgentID.ORCHESTRATOR,
        to_agent     = to,
        skill        = skill,
        payload      = payload,
        timeout_s    = timeout_s,
        callback_url = ORCHESTRATOR_CALLBACK
    )

    # Write task file
    task.to_file(task_path(task_id))
    log.info(f"Async task written: {task_id} → {to.value}/{skill.value}")

    # Register callback handler if provided
    if on_complete:
        event = threading.Event()
        with _pending_lock:
            _pending[task_id] = {
                "event":       event,
                "result":      None,
                "on_complete": on_complete
            }

    # Notify agent (non-blocking)
    endpoint = AGENT_ENDPOINTS.get(to)
    try:
        _notify_agent(endpoint, task_id, task_path(task_id), skill)
    except RuntimeError as e:
        log.error(f"Async notify failed: {e}")

    return task_id


def handle_async_callback(raw: dict):
    """
    Extended callback handler for async tasks.
    Calls on_complete(result) if registered.
    """
    task_id = raw.get("task_id")
    with _pending_lock:
        entry = _pending.get(task_id)

    if entry:
        # Read result
        rpath = result_path(task_id)
        try:
            result = TaskResult.from_file(rpath)
        except Exception:
            result = TaskResult(task_id=task_id, status=TaskStatus.FAILED)

        # Call completion handler
        on_complete = entry.get("on_complete")
        if on_complete:
            threading.Thread(target=on_complete, args=(result,), daemon=True).start()

        with _pending_lock:
            _pending.pop(task_id, None)