"""Recupere le TELEGRAM_CHAT_ID depuis ton propre bot, et teste la boucle.

    python3 scripts/get_chat_id.py

Le jeton est demande sans affichage a l'ecran : il ne passe ni dans une URL, ni
dans l'historique du navigateur, ni dans l'historique du shell. Il n'est pas
enregistre sur le disque non plus.

Prealable : avoir envoye au moins un message a son bot depuis Telegram.
"""
import getpass, json, os, sys, urllib.error, urllib.request


def appel(jeton: str, methode: str, payload=None):
    url = f"https://api.telegram.org/bot{jeton}/{methode}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data,
                                 method="POST" if data else "GET")
    if data:
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        corps = e.read().decode()[:300]
        if e.code == 401:
            raise SystemExit("Jeton refuse par Telegram (401). Verifie que tu as "
                             "colle le jeton complet donne par BotFather.")
        raise SystemExit(f"Telegram a repondu {e.code} : {corps}")


def main() -> int:
    jeton = os.environ.get("TELEGRAM_BOT_TOKEN") or getpass.getpass(
        "Colle le jeton du bot (rien ne s'affiche, c'est normal) : ").strip()
    if not jeton:
        raise SystemExit("Aucun jeton saisi.")

    moi = appel(jeton, "getMe").get("result", {})
    print(f"\nBot reconnu : @{moi.get('username', '?')}")

    maj = appel(jeton, "getUpdates").get("result", [])
    chats = {}
    for u in maj:
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id"):
            nom = " ".join(filter(None, [chat.get("first_name"),
                                         chat.get("last_name"),
                                         chat.get("title")])) or chat.get("type")
            chats[chat["id"]] = nom

    if not chats:
        print("\nAucun message recu par le bot pour l'instant.")
        print("Envoie-lui n'importe quoi depuis Telegram, puis relance ce script.")
        print("Attention : si tu as deja consulte getUpdates ailleurs, Telegram a")
        print("peut-etre purge la file. Dans ce cas, renvoie simplement un message.")
        return 1

    print("\n" + "=" * 62)
    for cid, nom in chats.items():
        print(f"TELEGRAM_CHAT_ID = {cid}    ({nom})")
    print("=" * 62)

    cible = list(chats)[0]
    appel(jeton, "sendMessage", {
        "chat_id": cible,
        "text": "✅ Agent LinkedIn Quantum Consulting : le canal fonctionne. "
                "C'est ici que les brouillons arriveront."})
    print("\nMessage de test envoye. Si tu le vois dans Telegram, la boucle est bonne.")
    print("Colle le nombre ci-dessus dans le secret TELEGRAM_CHAT_ID sur GitHub.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
