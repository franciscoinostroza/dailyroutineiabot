import asyncio
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from bot.config import settings

_http_server: HTTPServer | None = None
_thread: threading.Thread | None = None


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            try:
                from bot.tools.rutina import MENSAJES_DIA
                agenda_entries = sum(len(v) for v in MENSAJES_DIA.values())
                agenda_days = len(MENSAJES_DIA)
            except Exception:
                agenda_entries = 0
                agenda_days = 0
            status = {
                "status": "ok",
                "agenda_entries": agenda_entries,
                "agenda_days": agenda_days,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"dailyroutineiabot running\n")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logging.debug(f"HealthCheck: {args[0]}")


def start_health_server(port: int = 8080):
    global _http_server, _thread
    _http_server = HTTPServer(("0.0.0.0", port), HealthHandler)
    _thread = threading.Thread(target=_http_server.serve_forever, daemon=True)
    _thread.start()
    logging.info(f"Health check server en puerto {port}")


def stop_health_server():
    global _http_server
    if _http_server:
        _http_server.shutdown()
        logging.info("Health check server detenido.")
