"""
agent_server.py
---------------
Base HTTP server for all OpenClaw agent workers.
Each agent runs this to expose:
  POST /notify   ← orchestrator sends task notification here
  POST /callback ← (orchestrator only) receives task completion here
  GET  /health   ← heartbeat check

Location: /workspaces/shared/agent_server.py
Every agent imports and extends AgentServer.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable

from task_contract import (
    Task, TaskResult, TaskStatus,
    TaskNotification, TaskCallback,
    task_path, result_path
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
)


class AgentServer:
    """
    Base class for all OpenClaw agent workers.

    Usage in each agent:
        from agent_server import AgentServer
        from task_contract import SkillName

        class FinAnalyst(AgentServer):
            def __init__(self):
                super().__init__(agent_id="fin_analyst", port=8001)
                self.register_skill(SkillName.GET_LATEST_SIGNAL, self.get_latest_signal)
                self.register_skill(SkillName.GENERATE_REPORT,   self.generate_report)

            def get_latest_signal(self, payload: dict) -> dict:
                # ... implementation ...
                return { "signal": ... }

        if __name__ == "__main__":
            FinAnalyst().start()
    """

    def __init__(self, agent_id: str, port: int):
        self.agent_id  = agent_id
        self.port      = port
        self.skills    : dict[str, Callable] = {}
        self.log       = logging.getLogger(agent_id)
        self._start_time = time.time()

        # Ensure shared directories exist
        import os
        from task_contract import TASKS_DIR, RESULTS_DIR
        os.makedirs(TASKS_DIR, exist_ok=True)
        os.makedirs(RESULTS_DIR, exist_ok=True)

    def register_skill(self, skill: "SkillName", handler: Callable):
        """Register a skill handler function."""
        self.skills[skill.value] = handler
        self.log.info(f"Skill registered: {skill.value}")

    # ── HTTP Handler ──────────────────────────────────────────────────────────

    def _make_handler(self):
        agent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # suppress default HTTP access log

            def _read_body(self) -> dict:
                length = int(self.headers.get("Content-Length", 0))
                raw    = self.rfile.read(length)
                return json.loads(raw) if raw else {}

            def _respond(self, status: int, body: dict):
                payload = json.dumps(body, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(payload))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                if self.path == "/health":
                    self._respond(200, {
                        "agent_id":  agent.agent_id,
                        "status":    "ok",
                        "uptime_s":  round(time.time() - agent._start_time, 1),
                        "skills":    list(agent.skills.keys()),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                else:
                    self._respond(404, {"error": "not_found"})

            def do_POST(self):
                body = self._read_body()

                if self.path == "/notify":
                    # Orchestrator is notifying us of a new task
                    threading.Thread(
                        target=agent._handle_notification,
                        args=(body,),
                        daemon=True
                    ).start()
                    self._respond(202, {"status": "accepted", "task_id": body.get("task_id")})

                elif self.path == "/callback":
                    # An agent worker is reporting task completion (orchestrator only)
                    threading.Thread(
                        target=agent._handle_callback,
                        args=(body,),
                        daemon=True
                    ).start()
                    self._respond(202, {"status": "accepted"})

                else:
                    self._respond(404, {"error": "unknown_endpoint"})

        return Handler

    # ── Notification Handler ──────────────────────────────────────────────────

    def _handle_notification(self, raw: dict):
        """
        Called in background thread when orchestrator sends a task notification.
        1. Read task file
        2. Route to registered skill handler
        3. Write result file
        4. Call orchestrator callback
        """
        task_id   = raw.get("task_id")
        task_file = raw.get("task_file")
        skill     = raw.get("skill")

        self.log.info(f"Task received: {task_id} | skill: {skill}")
        t_start = time.time()

        # Read task file
        try:
            task = Task.from_file(task_file)
        except Exception as e:
            self.log.error(f"Cannot read task file {task_file}: {e}")
            return

        # Validate skill is registered
        handler = self.skills.get(task.skill)
        if not handler:
            self._write_result_and_callback(task, TaskStatus.FAILED,
                error=f"Skill '{task.skill}' not registered on {self.agent_id}",
                duration=time.time() - t_start)
            return

        # Execute skill
        try:
            result = handler(task.payload)
            self._write_result_and_callback(task, TaskStatus.SUCCESS,
                result=result, duration=time.time() - t_start)
        except Exception as e:
            self.log.exception(f"Skill execution failed: {task_id}")
            self._write_result_and_callback(task, TaskStatus.FAILED,
                error=str(e), duration=time.time() - t_start)

    def _write_result_and_callback(
        self,
        task: Task,
        status: TaskStatus,
        result=None,
        error: str = None,
        duration: float = 0.0
    ):
        """Write result file, then notify orchestrator via callback."""
        import os
        now = datetime.now(timezone.utc).isoformat()

        task_result = TaskResult(
            task_id      = task.task_id,
            status       = status,
            result       = result,
            error        = error,
            completed_at = now,
            duration_s   = round(duration, 2)
        )

        # Write result file
        rpath = result_path(task.task_id)
        try:
            task_result.to_file(rpath)
            self.log.info(f"Result written: {rpath} | status: {status}")
        except Exception as e:
            self.log.error(f"Cannot write result file: {e}")
            return

        # Update heartbeat
        self._update_heartbeat()

        # Notify orchestrator callback
        if task.callback_url:
            self._send_callback(task, status, rpath, duration)

    def _send_callback(self, task: Task, status: TaskStatus, result_file: str, duration: float):
        """HTTP POST to orchestrator's /callback endpoint."""
        import urllib.request, urllib.error

        payload = json.dumps({
            "task_id":     task.task_id,
            "status":      status.value,
            "result_file": result_file,
            "from_agent":  self.agent_id,
            "duration_s":  round(duration, 2)
        }).encode()

        try:
            req = urllib.request.Request(
                task.callback_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
            self.log.info(f"Callback sent: {task.task_id} → {task.callback_url}")
        except Exception as e:
            self.log.warning(f"Callback failed for {task.task_id}: {e}")
            # Non-fatal — result file is still written, orchestrator can read it

    # ── Callback Handler (orchestrator only, override in OrchestratorServer) ──

    def _handle_callback(self, raw: dict):
        """
        Override in orchestrator to handle agent completion callbacks.
        Default: log only.
        """
        self.log.info(
            f"Callback received: task={raw.get('task_id')} "
            f"status={raw.get('status')} from={raw.get('from_agent')}"
        )

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _update_heartbeat(self):
        """Write heartbeat.json. Override in each agent for custom fields."""
        import os
        hb_path = f"/workspaces/{self.agent_id}/heartbeat.json"
        os.makedirs(os.path.dirname(hb_path), exist_ok=True)
        with open(hb_path, "w") as f:
            json.dump({
                "agent_id":  self.agent_id,
                "status":    "ok",
                "last_ping": datetime.now(timezone.utc).isoformat(),
                "port":      self.port
            }, f, indent=2)

    # ── Start ─────────────────────────────────────────────────────────────────

    def start(self):
        """Start the HTTP server. Blocks until interrupted."""
        server = HTTPServer(("0.0.0.0", self.port), self._make_handler())
        self._update_heartbeat()
        self.log.info(f"Agent '{self.agent_id}' listening on port {self.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            self.log.info("Shutting down.")
            server.shutdown()