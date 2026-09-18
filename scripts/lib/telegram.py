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


def _call(method: str, payload: dict, strict: bool = False):
    """strict : une erreur devient une exception, donc un workflow rouge.

    Les envois peuvent echouer en silence sans grande consequence. La lecture
    des clics, elle, ne le peut pas : un releve muet ressemble a un releve
    vide, et on croirait que Younes n'a rien clique.
    """
    if not config.TELEGRAM_TOKEN:
        print(f"[telegram desactive] {method} {str(payload)[:120]}")
        if strict:
            raise RuntimeError("TELEGRAM_BOT_TOKEN absent : impossible de lire "
                               "les clics.")
        return {}
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{method}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 method="POST")
    req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        print(f"[telegram] erreur {e.code} sur {method} : {detail}")
        if strict:
            raise RuntimeError(f"Telegram {method} a repondu {e.code} : {detail}")
        return {}
    except Exception as exc:
        print(f"[telegram] echec reseau sur {method} : {exc}")
        if strict:
            raise
        return {}
    if strict and not out.get("ok", False):
        raise RuntimeError(f"Telegram {method} a repondu : {str(out)[:300]}")
    return out


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


def etat_polling() -> dict:
    """Un webhook actif rend getUpdates aveugle. On s'en assure a chaque releve.

    Le diagnostic est imprime : s'il existe un webhook, ou si un autre
    programme consomme les memes mises a jour, ca se voit ici et pas dans un
    releve vide qu'on prendrait pour un silence de Younes.
    """
    info = _call("getWebhookInfo", {})
    donnees = (info or {}).get("result", {}) or {}
    url = donnees.get("url") or ""
    en_attente = donnees.get("pending_update_count", 0)
    print(f"[telegram] webhook : {url or 'aucun'} · "
          f"mises a jour en attente : {en_attente}")
    if url:
        print("[telegram] webhook actif : je le retire pour pouvoir lire les clics.")
        _call("deleteWebhook", {"drop_pending_updates": False})
    return donnees


def get_updates(offset: int):
    res = _call("getUpdates", {"offset": offset, "timeout": 0,
                               "allowed_updates": ["message", "callback_query"]},
                strict=True)
    n = len(res.get("result", []) or [])
    print(f"[telegram] {n} mise(s) a jour recue(s) depuis l'offset {offset}.")
    return res


def answer_callback(cb_id: str, text: str):
    return _call("answerCallbackQuery", {"callback_query_id": cb_id,
                                         "text": text})


def draft_buttons(item_id: str):
    """Les trois seules reponses possibles a un brouillon."""
    return [[{"text": VALIDE, "callback_data": f"ok:{item_id}"}],
            [{"text": MODIFIER, "callback_data": f"mod:{item_id}"},
             {"text": REFUSE, "callback_data": f"no:{item_id}"}]]
