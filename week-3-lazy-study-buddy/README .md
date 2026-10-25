# Lazy Study Buddy

Paste your study notes and get a short summary plus quiz questions, written by an open-weight AI model (Gemma through Ollama) that runs entirely on your own computer. No internet, no subscription, and your notes never leave the machine.

Built for the Hacktoberfest 2026 DEV Challenge (Week 3: Slow and Steady).

## Requirements
- [Ollama](https://ollama.com) installed
- Python 3.8+ (no extra packages needed)
- Gemma 3 4B: `ollama pull gemma3:4b`

## Run
```
python app.py
```
Open http://localhost:8000 in your browser, click **Try sample notes**, then **Make my study pack**.

To use a different model: `MODEL=gemma3:1b python app.py` (Windows PowerShell: `$env:MODEL="gemma3:1b"; python app.py`).

## How it works
A small model on a small laptop cannot read long notes in one go, so the app reads them in pieces:

1. The notes are split into chunks of about 1,800 characters.
2. Each chunk is summarised into a few bullet points.
3. If there were several chunks, the points are merged into one short summary.
4. A quiz is written from the summary, in a fixed `Q1:` / `A1:` format that the app parses, so questions show up as tap-to-reveal cards.

Only the first 9,000 characters of notes are used.

## Limits
- It repeats what is in your notes, so a quiz can only be as good as the notes and the small model.
- Check answers against your course material before relying on them.

Built with the help of an AI assistant (Claude), then tested and published by me. Uses Google's Gemma model under Gemma's own license terms.
