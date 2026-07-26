import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from flask import Flask, Response, jsonify, request
from openai import OpenAI

app = Flask(__name__)

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "run.jsonl"

API_BASE = os.environ.get("OPENAI_BASE_URL", "https://aipipe.org/openai/v1")
API_KEY = os.environ.get("OPENAI_API_KEY")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")

if not API_KEY:
    API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIxZjMwMDE2NDdAZHMuc3R1ZHkuaWl0bS5hYy5pbiIsImlhdCI6MTc4NDk4NTA3OSwiaXNzIjoiaHR0cHM6Ly9haXBpcGUub3JnIiwiYXVkIjoiYWlwaXBlLWFwaSIsImV4cCI6MTc4NTU4OTg3OX0.AbADHACeaN4Dofbfv-10OUwHG9HSHz0gdP3ogZ2Lack"

client = OpenAI(base_url=API_BASE, api_key=API_KEY)


def append_log(entry: dict[str, Any]) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


@app.get("/")
def health():
    return jsonify({"status": "ok"})


@app.get("/run.jsonl")
def run_log():
    if not LOG_PATH.exists():
        return Response("", mimetype="application/jsonl")
    return Response(LOG_PATH.read_text(encoding="utf-8"), mimetype="application/jsonl")


@app.post("/telegram")
def telegram_webhook():
    payload = request.get_json(silent=True) or {}
    if not payload:
        return jsonify({"ok": False, "error": "empty payload"})

    update = payload
    message = None
    chat_id = None
    text = None
    if isinstance(update, dict):
        message = update.get("message") or update.get("edited_message")
        if message:
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text") or message.get("caption") or ""

    if not text or not chat_id:
        return jsonify({"ok": False, "error": "missing message"})

    cleaned = text.strip()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "chat_id": chat_id,
        "message": cleaned,
    }
    append_log(entry)

    try:
        answer = solve_question(cleaned)
        reply_payload = {"answer": answer["answer"], "log_url": build_log_url()}
        send_telegram_message(chat_id, json.dumps(reply_payload, ensure_ascii=False))
        entry["reply"] = reply_payload
        append_log(entry)
        return jsonify({"ok": True})
    except Exception as exc:
        error_payload = {"answer": {"error": str(exc)}, "log_url": build_log_url()}
        send_telegram_message(chat_id, json.dumps(error_payload, ensure_ascii=False))
        entry["reply"] = error_payload
        append_log(entry)
        return jsonify({"ok": False, "error": str(exc)})


def build_log_url() -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL.rstrip("/") + "/run.jsonl"
    return "https://example.com/run.jsonl"


def solve_question(question: str) -> dict[str, Any]:
    prompt = f"""You are a data-analysis assistant. The user asks a question about public data or inline data. You must answer by producing a single JSON object with keys 'answer' and 'log_url'.

Important:
- Return ONLY valid JSON. No prose or markdown.
- The 'answer' value must be shaped exactly as the user's question requests.
- If the question asks for a single value, return that value directly inside 'answer' if the question asks for a simple scalar. Otherwise use the schema asked by the question.
- For multi-turn requests, answer the last message only.
- If the question includes an inline dataset, use it directly.
- If the question references public data (MOSPI, etc.), reason from the text or from general knowledge; do not claim to have browsed the web unless you actually do.
- If you cannot determine the answer confidently, return a best-effort answer and include a short explanation inside the answer object if appropriate.

User question:
{question}
"""
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.choices[0].message.content or "{}"
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    parsed = extract_json_object(text)
    if not isinstance(parsed, dict) or "answer" not in parsed or "log_url" not in parsed:
        raise ValueError("LLM response was not a valid answer object")
    return parsed


def extract_json_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return {}
    return {}


def send_telegram_message(chat_id: int | str, text: str) -> None:
    if not BOT_TOKEN:
        print("Telegram BOT_TOKEN missing; skipping send")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)
