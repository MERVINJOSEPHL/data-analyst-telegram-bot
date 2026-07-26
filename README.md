# Data-Analyst Telegram Bot

This project implements a Telegram bot that receives plain-text data-analysis questions, asks an LLM to solve them, and replies with a single JSON object in the form:

{"answer": <answer>, "log_url": "https://your-host/run.jsonl"}

## Local run

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Set environment variables via `.env` or the shell.
