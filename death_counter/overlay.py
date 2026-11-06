from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from .save_parser import CharacterSlot

OVERLAY_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Elden Ring Death Counter</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: "Segoe UI", Arial, sans-serif;
    }
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: transparent;
    }
    body {
      display: grid;
      place-items: center;
    }
    #counter {
      display: flex;
      flex-wrap: nowrap;
      align-items: center;
      gap: 0.25em;
      color: white;
      font-size: min(18vw, 18vh);
      font-weight: 800;
      line-height: 1;
      text-align: center;
      white-space: nowrap;
      text-shadow:
        -3px -3px 0 #000,
         3px -3px 0 #000,
        -3px  3px 0 #000,
         3px  3px 0 #000,
         0 0 12px #000;
    }
    #value {
      font-variant-numeric: tabular-nums;
    }
    body.waiting #counter {
      opacity: 0.65;
    }
  </style>
</head>
<body class="waiting">
  <div id="counter">
    <span id="label">Deaths:</span>
    <span id="value">--</span>
  </div>
  <script>
    const params = new URLSearchParams(window.location.search);
    const value = document.getElementById("value");
    const label = document.getElementById("label");
    label.textContent = params.get("label") ?? "Deaths:";
    if (params.get("label") === "") label.hidden = true;

    async function refresh() {
      try {
        const response = await fetch("/api/status", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const status = await response.json();
        if (status.ready) {
          value.textContent = status.deaths;
          document.body.classList.remove("waiting");
          document.title = `${status.name}: ${status.deaths} deaths`;
        } else {
          document.body.classList.add("waiting");
        }
      } catch {
        document.body.classList.add("waiting");
      }
    }

    refresh();
    setInterval(refresh, 500);
  </script>
</body>
</html>
"""


class OverlayState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: dict[str, Any] = {
            "ready": False,
            "deaths": None,
            "name": None,
            "slot": None,
            "level": None,
            "hp": None,
            "maxHp": None,
            "error": None,
            "updatedAt": None,
        }

    def update_character(self, character: CharacterSlot) -> None:
        with self._lock:
            self._payload = {
                "ready": True,
                "deaths": character.deaths,
                "name": character.name,
                "slot": character.slot,
                "level": character.level,
                "hp": character.hp,
                "maxHp": character.max_hp,
                "error": None,
                "updatedAt": datetime.now(UTC).isoformat(),
            }

    def update_error(self, error: Exception) -> None:
        with self._lock:
            self._payload["error"] = str(error)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._payload)


class _OverlayRequestHandler(BaseHTTPRequestHandler):
    state: OverlayState

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in ("/", "/overlay"):
            self._send(
                200,
                OVERLAY_HTML.encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return
        if path == "/api/status":
            payload = json.dumps(
                self.state.snapshot(), separators=(",", ":")
            ).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        self._send(404, b"Not found\n", "text/plain; charset=utf-8")

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


class OverlayServer:
    def __init__(
        self, state: OverlayState, port: int = 8765, host: str = "127.0.0.1"
    ) -> None:
        handler = type(
            "BoundOverlayRequestHandler",
            (_OverlayRequestHandler,),
            {"state": state},
        )
        self._server = ThreadingHTTPServer((host, port), handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="obs-overlay-server",
            daemon=True,
        )

    @property
    def port(self) -> int:
        return self._server.server_port

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/overlay"

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
