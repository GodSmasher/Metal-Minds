import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from pacemaker.app_state import AppState


ROOT_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(ROOT_DIR, "static")
STATE = AppState()


class PacemakerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def _handle_api(self, parsed):
        query = parse_qs(parsed.query)
        metal = query.get("metal", ["copper"])[0].lower()
        horizon = query.get("horizon", ["10d"])[0]
        theme = query.get("theme", [""])[0]
        as_of_date = query.get("date", [""])[0]
        risk_appetite = query.get("risk_appetite", ["high"])[0].lower()

        try:
            if parsed.path == "/api/metals":
                payload = {"metals": STATE.get_metals()}
            elif parsed.path == "/api/dates":
                payload = {"dates": STATE.get_available_dates(metal)}
            elif parsed.path == "/api/decision":
                payload = STATE.get_decision(metal, horizon, as_of_date=as_of_date, risk_appetite=risk_appetite).to_dict()
            elif parsed.path == "/api/news-clusters":
                payload = {"items": STATE.get_news_clusters(metal, as_of_date=as_of_date)}
            elif parsed.path == "/api/analog-events":
                payload = {"items": STATE.get_analog_events(metal, theme)}
            elif parsed.path == "/api/scenarios":
                payload = {"scenarios": STATE.get_scenarios(metal, horizon, as_of_date=as_of_date, risk_appetite=risk_appetite)}
            elif parsed.path == "/api/refresh":
                STATE.refresh()
                payload = {"status": "ok"}
            else:
                self._write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return
        except KeyError:
            self._write_json({"error": f"Unknown metal: {metal}"}, status=HTTPStatus.NOT_FOUND)
            return
        self._write_json(payload)

    def _write_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), PacemakerHandler)
    print(f"pacemaker.ai demo server running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
