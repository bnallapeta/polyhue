#!/usr/bin/env python3
"""Dev server for the audience page.

Endpoints:
    GET  /                serves index.html (and other static files)
    POST /color           {seed} → picks a language by hashing seed,
                          calls the matching get_color_* tool upstream,
                          returns the color JSON.
    GET  /events          server-sent events stream for stage broadcasts.
    POST /broadcast       {event: "flash", ...} fans out to all /events
                          subscribers. Stage uses this.
    POST /mcp             raw MCP passthrough to the upstream Spin server.

/broadcast, /trigger-denial and /mcp are admin endpoints: they require the
token in an X-Admin-Token header. Set ADMIN_TOKEN to choose it, otherwise a
random one is generated at startup and printed below. The audience page itself
(/, /color, /events) stays open — phones need no token.

Note: when fronted by Tailscale Funnel the proxy makes every public request
look like it came from 127.0.0.1, so there is deliberately no localhost
exemption here.

Run:
    python3 serve.py            # listens on 0.0.0.0:8080
    PORT=9000 python3 serve.py  # custom port
    ADMIN_TOKEN=hunter2 python3 serve.py
"""

import json
import hashlib
import os
import queue
import secrets
import sys
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
MCP_UPSTREAM = os.environ.get("MCP_UPSTREAM", "http://127.0.0.1:3000/mcp")
PORT = int(os.environ.get("PORT", "8080"))
LANGUAGES = ("rs", "py", "ts")

# Endpoints that can drive the stage. Never left unauthenticated: if no token is
# supplied we invent one rather than falling open, so a forgotten env var can't
# hand the red-flash beat to the room.
ADMIN_PATHS = ("/broadcast", "/trigger-denial", "/mcp")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN") or secrets.token_urlsafe(16)
ADMIN_TOKEN_GENERATED = "ADMIN_TOKEN" not in os.environ

# Thread-safe set of subscriber queues for SSE.
_subscribers_lock = threading.Lock()
_subscribers: "set[queue.Queue[str]]" = set()


def pick_language(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return LANGUAGES[digest[0] % len(LANGUAGES)]


def call_upstream_tool_raw(name: str, arguments: dict) -> dict:
    """Call a tool upstream, returning the full result envelope (including isError)."""
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }).encode("utf-8")
    req = urllib.request.Request(
        MCP_UPSTREAM,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8").strip()
    if text.startswith("data:"):
        text = text[len("data:"):].strip()
    payload = json.loads(text)
    if "error" in payload:
        raise RuntimeError(payload["error"].get("message", "upstream error"))
    return payload["result"]


def call_upstream_tool(name: str, arguments: dict) -> dict:
    """Call a tool upstream and return the parsed inner JSON content."""
    result = call_upstream_tool_raw(name, arguments)
    inner = result["content"][0]["text"]
    return json.loads(inner)


def broadcast(message: dict) -> int:
    line = "data: " + json.dumps(message) + "\n\n"
    with _subscribers_lock:
        targets = list(_subscribers)
    for q in targets:
        try:
            q.put_nowait(line)
        except queue.Full:
            pass
    return len(targets)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    # ----- routing -----

    def do_GET(self):
        if self.path == "/events" or self.path.startswith("/events?"):
            self._serve_events()
            return
        super().do_GET()

    def _admin_ok(self) -> bool:
        """Constant-time check of the X-Admin-Token header."""
        return secrets.compare_digest(
            self.headers.get("X-Admin-Token", ""), ADMIN_TOKEN
        )

    def do_POST(self):
        if self.path in ADMIN_PATHS and not self._admin_ok():
            self._write_json(403, {"error": "admin token required"})
            return
        if self.path == "/color":
            self._serve_color()
        elif self.path == "/mcp":
            self._proxy_mcp()
        elif self.path == "/broadcast":
            self._serve_broadcast()
        elif self.path == "/trigger-denial":
            self._serve_trigger_denial()
        else:
            self.send_error(404)

    # ----- handlers -----

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError:
            return {}

    def _write_json(self, status: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_color(self):
        body = self._read_json()
        seed = str(body.get("seed", ""))
        lang = pick_language(seed) if seed else pick_language(self.address_string())
        try:
            color = call_upstream_tool(f"get_color_{lang}", {"seed": seed})
        except Exception as e:
            self._write_json(502, {"error": str(e)})
            return
        color["routed_to"] = lang
        self._write_json(200, color)

    def _proxy_mcp(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        req = urllib.request.Request(
            MCP_UPSTREAM,
            data=body,
            method="POST",
            headers={
                "Content-Type": self.headers.get("Content-Type", "application/json"),
                "Accept": self.headers.get("Accept", "application/json, text/event-stream"),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.URLError as e:
            self.send_error(502, f"upstream error: {e}")

    def _serve_broadcast(self):
        body = self._read_json()
        if "event" not in body:
            body["event"] = "flash"
        count = broadcast(body)
        self._write_json(200, {"delivered_to": count})

    def _serve_trigger_denial(self):
        """Call the Regorus-gated peek_attendees tool. If it's denied — which it
        always is, by policy — broadcast a flash to every connected phone."""
        try:
            result = call_upstream_tool_raw("peek_attendees", {})
        except Exception as e:
            self._write_json(502, {"error": str(e)})
            return

        is_denied = result.get("isError") is True
        inner_text = result.get("content", [{}])[0].get("text", "")
        try:
            inner = json.loads(inner_text)
        except json.JSONDecodeError:
            inner = {"raw": inner_text}

        delivered = 0
        if is_denied:
            delivered = broadcast({
                "event": "flash",
                "reason": inner.get("reason", "policy denial"),
            })

        self._write_json(200, {
            "tool": "peek_attendees",
            "denied": is_denied,
            "policy_reason": inner.get("reason"),
            "broadcast_delivered_to": delivered,
        })

    def _serve_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q: "queue.Queue[str]" = queue.Queue(maxsize=64)
        with _subscribers_lock:
            _subscribers.add(q)

        # Initial hello so EventSource considers us open.
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=20)
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Heartbeat — keeps the connection alive past proxy timeouts.
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with _subscribers_lock:
                _subscribers.discard(q)

    def log_message(self, fmt, *args):
        # Less chatty; skip the noisy event-stream pings.
        if self.path in ("/events",):
            return
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    print(f"audience page:  http://localhost:{PORT}/", file=sys.stderr)
    print(f"proxying /mcp → {MCP_UPSTREAM}", file=sys.stderr)
    if ADMIN_TOKEN_GENERATED:
        print(f"admin token (generated): {ADMIN_TOKEN}", file=sys.stderr)
        print("  set ADMIN_TOKEN=... to pin it across restarts", file=sys.stderr)
    else:
        print("admin token: from ADMIN_TOKEN env var", file=sys.stderr)
    print(f"broadcast a flash:    curl -X POST http://localhost:{PORT}/broadcast -H 'X-Admin-Token: {ADMIN_TOKEN}' -d '{{\"event\":\"flash\"}}'", file=sys.stderr)
    print(f"trigger Regorus deny: curl -X POST http://localhost:{PORT}/trigger-denial -H 'X-Admin-Token: {ADMIN_TOKEN}'", file=sys.stderr)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
