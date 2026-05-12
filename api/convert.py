"""Vercel Python serverless function: convert .docx -> events JSON.

Reuses the existing convert_events.py parser unchanged. Frontend POSTs the
raw .docx bytes; we write to /tmp, hand the path to parse_document, and
return the assembled JSON.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import tempfile
import traceback

# Repo root sits one level above this file (api/convert.py); add it so we
# can import the existing convert_events module.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from convert_events import parse_document, derive_month_label, group_into_weekends  # noqa: E402

MAX_BYTES = 10 * 1024 * 1024  # 10 MB cap; real docs run ~50-200 KB.


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return self._json(400, {"error": "empty body"})
            if length > MAX_BYTES:
                return self._json(413, {"error": "file too large", "limit_bytes": MAX_BYTES})

            body = self.rfile.read(length)
            if not body.startswith(b"PK"):
                return self._json(400, {"error": "not a .docx file (missing zip signature)"})

            original_name = self.headers.get("X-Filename") or "upload.docx"

            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(body)
                tmp_path = tmp.name

            try:
                events = parse_document(tmp_path)
                # derive_month_label uses the path only as a filename fallback;
                # use the user's original filename so the fallback can spot a
                # month name like "NYC_Events_April.docx".
                month_label = derive_month_label(events, original_name)
                weekends = group_into_weekends(events)
                payload = {"month": month_label, "weekends": weekends}
                return self._json(200, payload)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except Exception as e:
            tb = traceback.format_exc()
            sys.stderr.write(tb)
            return self._json(500, {"error": str(e) or "conversion failed"})

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Filename")

    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)
