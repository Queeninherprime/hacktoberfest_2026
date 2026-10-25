"""Lazy Study Buddy - local server.

Paste your study notes and get a short summary plus quiz questions, written by an
open-weight model (Gemma through Ollama) running on your own computer.
Uses only the Python standard library, so there is nothing to pip install.

Run:  python app.py      (then open http://localhost:8000)
"""
import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("MODEL", "gemma3:4b")
PORT = int(os.environ.get("PORT", "8000"))
HERE = Path(__file__).parent

MAX_CHARS = 9000    # a small model on a small laptop cannot read unlimited notes
CHUNK_CHARS = 1800  # notes are read in pieces of about this size
LANGUAGES = {"en": "English", "fr": "French"}


# ---------- text helpers ----------

def split_chunks(text, size=CHUNK_CHARS):
    """Split notes into pieces at paragraph or line breaks, each at most `size` characters."""
    pieces, current = [], ""
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if not para:
            continue
        while len(para) > size:  # one very long paragraph: cut it
            if current:
                pieces.append(current)
                current = ""
            pieces.append(para[:size])
            para = para[size:]
        if len(current) + len(para) + 1 > size and current:
            pieces.append(current)
            current = para
        else:
            current = (current + "\n" + para).strip()
    if current:
        pieces.append(current)
    return pieces


def clean_bullets(text):
    """Keep only bullet lines, written as '- ...'. If the model used no bullets, keep its text."""
    text = text.replace("**", "")
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^([-*\u2022]|\d+[.)])\s+", line):
            line = re.sub(r"^([-*\u2022]|\d+[.)])\s+", "", line).strip()
            if line:
                lines.append("- " + line)
    return "\n".join(lines) if lines else text.strip()


def parse_qa(text):
    """Read 'Q1: ... / A1: ...' pairs. Tolerates French labels and markdown bold."""
    text = text.replace("**", "")
    pairs, question = [], None
    for line in text.splitlines():
        line = line.strip().lstrip("*-\u2022 ").strip()
        m = re.match(r"(?:Q|Question)\s*\d*\s*[:.)-]\s*(.+)", line, re.I)
        if m:
            question = m.group(1).strip()
            continue
        m = re.match(r"(?:A|Answer|R\u00e9ponse|Reponse)\s*\d*\s*[:.)-]\s*(.+)", line, re.I)
        if m and question:
            pairs.append({"q": question, "a": m.group(1).strip()})
            question = None
    return pairs


# ---------- prompts ----------

def summary_prompt(chunk, language):
    return (
        "You help students revise. Read the study notes below and write 3 to 5 short "
        "bullet points with the key facts.\n"
        f"Write in {language}. Use ONLY information from the notes and do not add facts. "
        "Output only the bullet points, each starting with '- '.\n\n"
        f"NOTES:\n{chunk}"
    )


def condense_prompt(points, language):
    return (
        "Below are bullet points taken from different parts of a student's notes. "
        "Merge them into 5 to 8 clear bullet points without repeating anything.\n"
        f"Write in {language}. Use ONLY these points. "
        "Output only the bullet points, each starting with '- '.\n\n"
        f"POINTS:\n{points}"
    )


def quiz_prompt(points, language, n):
    return (
        f"Write {n} quiz questions, each with a short answer, to help a student revise. "
        "Base them ONLY on the points below.\n"
        f"Write in {language}. Use exactly this format and nothing else:\n"
        "Q1: the question\nA1: the answer\nQ2: the question\nA2: the answer\n\n"
        f"POINTS:\n{points}"
    )


# ---------- model calls ----------

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


def generate(model, prompt):
    result = call_ollama(
        "/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 600},
        },
    )
    return result.get("response", "").strip()


def make_study_pack(notes, language_code, n_questions, model):
    language = LANGUAGES.get(language_code, "English")
    truncated = len(notes) > MAX_CHARS
    notes = notes[:MAX_CHARS]
    chunks = split_chunks(notes)

    # 1) read the notes piece by piece
    partial = [clean_bullets(generate(model, summary_prompt(c, language))) for c in chunks]
    points = "\n".join(partial)

    # 2) if there were several pieces, merge their points into one short summary
    if len(chunks) > 1:
        points = clean_bullets(generate(model, condense_prompt(points, language)))

    # 3) write the quiz from the summary points
    quiz_text = generate(model, quiz_prompt(points, language, n_questions))
    questions = parse_qa(quiz_text)[:n_questions]

    return {
        "summary": points,
        "questions": questions,
        "chunks": len(chunks),
        "truncated": truncated,
    }


# ---------- web server ----------

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
        if self.path != "/api/study":
            return self._json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "Invalid request."})

        notes = str(data.get("notes", "")).strip()
        if len(notes) < 40:
            return self._json(400, {"error": "Paste at least a few sentences of notes first."})
        try:
            n = max(1, min(10, int(data.get("questions", 5))))
        except (TypeError, ValueError):
            n = 5
        model = data.get("model") or DEFAULT_MODEL

        try:
            self._json(200, make_study_pack(notes, data.get("language", "en"), n, model))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                msg = f"Model '{model}' is not installed. Run: ollama pull {model}"
            else:
                msg = f"Ollama returned an error ({e.code})."
            self._json(502, {"error": msg})
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            self._json(503, {"error": "Cannot reach Ollama. Open the Ollama app, then try again."})

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Lazy Study Buddy running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
