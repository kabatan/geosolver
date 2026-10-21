"""Local-only UI bridge for saving full ChatGPT answers without truncation."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUESTS = json.loads((HERE / "teacher_requests.json").read_text())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = ("<!doctype html><meta charset='utf-8'><title>Teacher import</title>"
                "<form method='post'><label>Batch <input name='batch' type='number' "
                "min='1' max='5'></label><textarea name='answer'></textarea>"
                "<button type='submit'>Save teacher answer</button></form>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        from urllib.parse import parse_qs

        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size < 200000:
            self.send_error(413)
            return
        form = parse_qs(self.rfile.read(size).decode(), keep_blank_values=True)
        try:
            batch = int(form["batch"][0])
            answer = form["answer"][0]
            assert 1 <= batch <= 5
            rows = json.loads(answer)
            assert [row["id"] for row in rows] == REQUESTS[batch - 1]["ids"]
            path = HERE / f"raw-batch{batch}.txt"
            assert not path.exists()
            path.write_text(answer)
            body = f"Saved batch {batch}: {len(rows)} answers, {len(answer)} characters.".encode()
        except Exception as error:
            self.send_error(400, repr(error))
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8877), Handler).serve_forever()
