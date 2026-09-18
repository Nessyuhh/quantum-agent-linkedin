"""Bot Telegram : envoi des brouillons, boutons de validation, capture terrain."""
import json, urllib.request, urllib.error, urllib.parse
from . import config

def _call(method: str, payload: dict):
    if not config.TELEGRAM_TOKEN:
        print(f"[telegram desactive] {method} {str(payload)[:120]}")
        return {}
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"[telegram] erreur {e.code} : {e.read().decode()[:300]}")
        return {}

def send(text: str, buttons=None, chat_id=None):
    payload = {"chat_id": chat_id or config.TELEGRAM_CHAT, "text": text,
               "parse_mode": "HTML", "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    return _call("sendMessage", payload)

def alert(text: str):
    send(f"⚠️ <b>Agent LinkedIn</b>\n{text}")

def get_updates(offset: int):
    return _call("getUpdates", {"offset": offset, "timeout": 0,
                                "allowed_updates": ["message", "callback_query"]})

def answer_callback(cb_id: str, text: str):
    return _call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})

def draft_buttons(item_id: str):
    return [[{"text": "✓ Publier", "callback_data": f"ok:{item_id}"},
             {"text": "✕ Rejeter", "callback_data": f"no:{item_id}"}],
            [{"text": "↻ Reecrire", "callback_data": f"rw:{item_id}"}]]
