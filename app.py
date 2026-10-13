"""Offline Listing Writer - local server.

Serves the web page and forwards requests to Ollama running on this computer.
Uses only the Python standard library, so there is nothing to pip install.

Run:  python app.py      (then open http://localhost:8000)
"""
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("MODEL", "gemma3:4b")
PORT = int(os.environ.get("PORT", "8000"))
HERE = Path(__file__).parent

LANGUAGES = {"fr": "French", "en": "English"}
TONES = {
    "friendly": "warm, friendly and conversational, like a trusted local seller",
    "professional": "clear, polite and professional",
}
PLATFORMS = {
    "whatsapp": "a WhatsApp message or status (short lines, a few emojis, no hashtags)",
    "facebook": "a Facebook Marketplace post (short title line, then details)",
    "instagram": "an Instagram caption (catchy first line, emojis, 5 relevant hashtags at the end)",
}


def build_prompt(d):
    language = LANGUAGES.get(d.get("language"), "French")
    tone = TONES.get(d.get("tone"), TONES["friendly"])
    platform = PLATFORMS.get(d.get("platform"), PLATFORMS["whatsapp"])
    lines = [
        f"Product: {d.get('product', '').strip()}",
        f"Condition: {d.get('condition', '').strip() or 'not specified'}",
        f"Price: {d.get('price', '').strip() or 'not specified'}",
        f"Details: {d.get('details', '').strip() or 'none'}",
        f"Seller contact/location: {d.get('contact', '').strip() or 'not specified'}",
    ]
    return (
        "You write sales listings for small sellers in Cameroon.\n"
        f"Write the listing in {language}, in a {tone} tone, formatted as {platform}.\n"
        "Rules: use ONLY the facts below. Do not invent features, brands, "
        "warranties or discounts. Keep the price exactly as given. "
        "Output only the listing text, with no explanations.\n\n"
        + "\n".join(lines)
    )


def call_ollama(path, payload=None, timeout=300):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        OLLAMA_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj))

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html")
        elif self.path == "/api/models":
            try:
                tags = call_ollama("/api/tags", timeout=5)
                names = [m["name"] for m in tags.get("models", [])]
                self._json(200, {"models": names, "default": DEFAULT_MODEL})
            except Exception:
                self._json(200, {"models": [], "default": DEFAULT_MODEL})
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/api/generate":
            return self._json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "Invalid request."})

        if not str(data.get("product", "")).strip():
            return self._json(400, {"error": "Enter the product name first."})

        model = data.get("model") or DEFAULT_MODEL
        try:
            result = call_ollama(
                "/api/generate",
                {
                    "model": model,
                    "prompt": build_prompt(data),
                    "stream": False,
                    "options": {"temperature": 0.7},
                },
            )
            self._json(200, {"text": result.get("response", "").strip()})
        except urllib.error.HTTPError as e:
            if e.code == 404:
                msg = f"Model '{model}' is not installed. Run: ollama pull {model}"
            else:
                msg = f"Ollama returned an error ({e.code})."
            self._json(502, {"error": msg})
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            self._json(
                503,
                {"error": "Cannot reach Ollama. Open the Ollama app, then try again."},
            )

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Offline Listing Writer running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
