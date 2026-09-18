"""Bot Telegram : envoi des brouillons avec leur visuel, trois boutons de
decision, et capture des notes de terrain.

Chaque brouillon part en deux messages : le visuel d'abord, puis le texte avec
les boutons. Telegram plafonne la legende d'une photo a 1024 caracteres, et une
publication depasse souvent ce seuil : en separant, rien n'est jamais tronque.
"""
import json, urllib.error, urllib.request, uuid
from pathlib import Path
from . import config

VALIDE = "✅ Valide"
MODIFIER = "✏️ Modifier"
REFUSE = "❌ Refuse"


def _call(method: str, payload: dict):
    if not config.TELEGRAM_TOKEN:
        print(f"[telegram desactive] {method} {str(payload)[:120]}")
        return {}
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 method="POST")
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


def send_photo(chemin, caption: str = "", chat_id=None):
    """Envoie le visuel du brouillon, en multipart, sans dependance externe."""
    if not config.TELEGRAM_TOKEN:
        print(f"[telegram desactive] photo {chemin}")
        return {}
    chemin = Path(chemin)
    frontiere = "----QC" + uuid.uuid4().hex
    morceaux = []

    def champ(nom, valeur):
        morceaux.append(
            f"--{frontiere}\r\nContent-Disposition: form-data; "
            f'name="{nom}"\r\n\r\n{valeur}\r\n'.encode())

    champ("chat_id", chat_id or config.TELEGRAM_CHAT)
    if caption:
        champ("caption", caption[:1000])
        champ("parse_mode", "HTML")
    morceaux.append(
        f"--{frontiere}\r\nContent-Disposition: form-data; "
        f'name="photo"; filename="{chemin.name}"\r\n'
        "Content-Type: image/png\r\n\r\n".encode())
    morceaux.append(chemin.read_bytes())
    morceaux.append(f"\r\n--{frontiere}--\r\n".encode())

    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendPhoto"
    req = urllib.request.Request(url, data=b"".join(morceaux), method="POST")
    req.add_header("content-type",
                   f"multipart/form-data; boundary={frontiere}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"[telegram] photo en echec {e.code} : {e.read().decode()[:300]}")
        return {}


def get_updates(offset: int):
    return _call("getUpdates", {"offset": offset, "timeout": 0,
                                "allowed_updates": ["message", "callback_query"]})


def answer_callback(cb_id: str, text: str):
    return _call("answerCallbackQuery", {"callback_query_id": cb_id,
                                         "text": text})


def draft_buttons(item_id: str):
    """Les trois seules reponses possibles a un brouillon."""
    return [[{"text": VALIDE, "callback_data": f"ok:{item_id}"}],
            [{"text": MODIFIER, "callback_data": f"mod:{item_id}"},
             {"text": REFUSE, "callback_data": f"no:{item_id}"}]]
