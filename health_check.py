from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import time

START_TIME = time.time()


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps(
                {
                    "status": "ok",
                    "uptime_seconds": round(time.time() - START_TIME, 3),
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def run(host="0.0.0.0", port=8080):
    server = HTTPServer((host, port), HealthCheckHandler)
    print(f"Health check listening on http://{host}:{port}/health")
    server.serve_forever()


if __name__ == "__main__":
    run()
