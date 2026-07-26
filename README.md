# Data-Analyst Telegram Bot

This project implements a Telegram bot that receives plain-text data-analysis questions, asks an LLM to solve them, and replies with a single JSON object in the form:

{"answer": <answer>, "log_url": "https://your-host/run.jsonl"}

## Local run

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Set environment variables via `.env` or the shell.

## Render deployment

1. Create a new Web Service on Render.
2. Connect this repository.
3. Use the existing `render.yaml` config.
4. Set the environment variables in Render for `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, and `PUBLIC_BASE_URL`.
5. Render will expose the app at your service URL, and `/run.jsonl` will be publicly reachable for the grader.
