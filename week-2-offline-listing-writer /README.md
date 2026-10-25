# Offline Listing Writer

Write product listings for WhatsApp, Facebook Marketplace and Instagram in French or English, using an open-weight AI model that runs entirely on your own computer. No internet, no subscription, and your prices and customer details never leave the machine.
 ![English listing](screenshots/english-listing.png)
   ![French listing](screenshots/french-listing.png)

Built for the Hacktoberfest 2026 DEV Challenge (Week 2: Side Hustle).

## Requirements
- [Ollama](https://ollama.com) installed
- Python 3.8+ (no extra packages needed)
- A small open-weight model, for example Gemma 4B

## Setup (needs internet once)
```
ollama pull gemma3:4b
```

## Run
```
python app.py
```
Open http://localhost:8000 in your browser.

To use a different model: `MODEL=gemma3:1b python app.py` (on Windows PowerShell: `$env:MODEL="gemma3:1b"; python app.py`).

## How it works
`app.py` is a tiny local server. It serves the page and sends your product details to Ollama at `localhost:11434`, then returns the generated listing. Saved listings are kept in your browser on this computer.

## Offline note
Writing and copying listings works with no connection. Posting to WhatsApp, Facebook or Instagram still needs internet, so write several listings offline and post them when you connect.
