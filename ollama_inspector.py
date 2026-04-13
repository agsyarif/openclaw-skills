"""
ollama_inspector.py
-------------------
Transparent proxy antara OpenClaw dan Ollama.
Intercept setiap request, log token count dan isi system prompt.

CARA PAKAI:
1. Jalankan script ini:
   python ollama_inspector.py

2. Di OpenClaw config, ganti Ollama URL dari:
   http://localhost:11434
   ke:
   http://localhost:11435   ← proxy port

3. Chat di OpenClaw seperti biasa
4. Lihat output di terminal ini — akan tampil isi prompt dan token count
5. Hasil juga disimpan di: /tmp/openclaw_prompts.jsonl

STOP: Ctrl+C untuk berhenti, lalu kembalikan URL ke 11434
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PROXY_PORT   = 11435          # OpenClaw → sini
OLLAMA_PORT  = 11434          # sini → Ollama
OLLAMA_URL   = f"http://localhost:{OLLAMA_PORT}"
LOG_FILE     = "/tmp/openclaw_prompts.jsonl"

request_count = 0


def estimate_tokens(text: str) -> int:
    """Rough token estimate: chars / 4."""
    return len(text) // 4


def summarize_messages(messages: list) -> dict:
    """Breakdown token count per role."""
    breakdown = {}
    total     = 0
    for msg in messages:
        role    = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )
        tokens = estimate_tokens(content)
        breakdown[role] = breakdown.get(role, 0) + tokens
        total += tokens
    return {"breakdown": breakdown, "total": total}


def print_report(endpoint: str, body: dict, duration_ms: float):
    global request_count
    request_count += 1

    model    = body.get("model", "?")
    messages = body.get("messages", [])
    prompt   = body.get("prompt", "")  # /api/generate style

    # Handle both /api/chat and /api/generate
    if messages:
        stats = summarize_messages(messages)
        sys_msg = next(
            (m.get("content", "") for m in messages if m.get("role") == "system"),
            ""
        )
    else:
        tokens = estimate_tokens(prompt)
        stats  = {"breakdown": {"prompt": tokens}, "total": tokens}
        sys_msg = prompt

    total_tokens = stats["total"]

    # ── Print to terminal ──────────────────────────────────────────────────
    sep = "━" * 60
    print(f"\n{sep}")
    print(f"#{request_count} | {endpoint} | model: {model} | {duration_ms:.0f}ms")
    print(f"{sep}")
    print(f"📊 TOKEN COUNT: {total_tokens:,}")
    print(f"   Breakdown: {stats['breakdown']}")

    # Warn if high
    if total_tokens > 8000:
        print(f"   🔴 SANGAT TINGGI — prefill ~{total_tokens//500:.0f}–{total_tokens//400:.0f}s")
    elif total_tokens > 4000:
        print(f"   🟡 TINGGI — prefill ~{total_tokens//500:.0f}–{total_tokens//400:.0f}s")
    else:
        print(f"   🟢 OK — prefill ~{total_tokens//500:.0f}–{total_tokens//400:.0f}s")

    # System prompt preview
    if sys_msg:
        preview = sys_msg[:500].replace("\n", "↵ ")
        print(f"\n📄 SYSTEM PROMPT (first 500 chars):")
        print(f"   {preview}")
        if len(sys_msg) > 500:
            print(f"   ... [{len(sys_msg):,} chars total, ~{estimate_tokens(sys_msg):,} tokens]")

    # Message count
    if messages:
        print(f"\n💬 MESSAGES: {len(messages)} total")
        for i, m in enumerate(messages):
            role    = m.get("role", "?")
            content = m.get("content", "")
            if isinstance(content, list):
                content = str(content)
            toks    = estimate_tokens(str(content))
            preview = str(content)[:80].replace("\n", "↵ ")
            print(f"   [{i}] {role:<12} {toks:>5} tokens  |  {preview}")

    print(sep)

    # ── Save to log file ───────────────────────────────────────────────────
    log_entry = {
        "ts":           datetime.now().isoformat(),
        "request_num":  request_count,
        "endpoint":     endpoint,
        "model":        model,
        "total_tokens": total_tokens,
        "breakdown":    stats["breakdown"],
        "system_prompt_chars": len(sys_msg),
        "system_prompt_preview": sys_msg[:300]
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


class ProxyHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default access log

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def do_GET(self):
        """Forward GET requests (health, tags, ps) transparently."""
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}{self.path}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read()
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.end_headers()
                self.wfile.write(body)
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Proxy error: {e}".encode())

    def do_POST(self):
        """Intercept POST — log then forward to Ollama."""
        raw_body = self._read_body()
        t_start  = time.time()

        # Parse and log
        try:
            body = json.loads(raw_body) if raw_body else {}
            print_report(self.path, body, 0)
        except Exception:
            print(f"\n[proxy] Could not parse body for {self.path}")

        # Forward to real Ollama
        try:
            req = urllib.request.Request(
                f"{OLLAMA_URL}{self.path}",
                data=raw_body,
                headers={
                    k: v for k, v in self.headers.items()
                    if k.lower() not in ("host", "content-length")
                },
                method="POST"
            )
            req.add_header("Content-Length", len(raw_body))

            with urllib.request.urlopen(req, timeout=300) as resp:
                resp_body = resp.read()
                duration  = (time.time() - t_start) * 1000

                # Update duration in terminal
                print(f"   ⏱  Response: {duration:.0f}ms")

                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.send_header("Content-Length", len(resp_body))
                self.end_headers()
                self.wfile.write(resp_body)

        except Exception as e:
            duration = (time.time() - t_start) * 1000
            print(f"   ❌ Forward error ({duration:.0f}ms): {e}")
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Proxy error: {e}".encode())


def main():
    print(f"""
╔══════════════════════════════════════════════════════╗
║          OLLAMA INSPECTOR PROXY                      ║
╠══════════════════════════════════════════════════════╣
║  Proxy  : http://localhost:{PROXY_PORT}  (set di OpenClaw)  ║
║  Ollama : http://localhost:{OLLAMA_PORT}  (real Ollama)      ║
║  Log    : {LOG_FILE}              ║
╠══════════════════════════════════════════════════════╣
║  1. Ganti Ollama URL di OpenClaw ke port {PROXY_PORT}        ║
║  2. Chat di OpenClaw seperti biasa                   ║
║  3. Lihat breakdown token di sini                    ║
║  4. Ctrl+C untuk stop, kembalikan URL ke {OLLAMA_PORT}        ║
╚══════════════════════════════════════════════════════╝
""")

    server = HTTPServer(("0.0.0.0", PROXY_PORT), ProxyHandler)
    print(f"Listening on port {PROXY_PORT}...\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n\nStopped. Log saved to: {LOG_FILE}")
        print(f"INGAT: Kembalikan OpenClaw Ollama URL ke http://localhost:{OLLAMA_PORT}")
        server.shutdown()


if __name__ == "__main__":
    main()
