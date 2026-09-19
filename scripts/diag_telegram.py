"""Audit du canal Telegram. Ne consomme rien, ne stocke rien.

    python3 scripts/diag_telegram.py

Le jeton est demandé sans affichage. Le script interroge Telegram en lecture
seule : il n'envoie aucun offset, donc les clics en attente restent disponibles
pour l'agent ensuite. Aucune écriture sur le disque.

Ce qu'il répond :
  · quel bot répond à ce jeton (au cas où il y en aurait deux) ;
  · s'il existe un webhook qui détournerait les mises à jour ;
  · ce que Telegram garde en file, clic par clic.
"""
import getpass, json, os, sys, urllib.error, urllib.request
from datetime import datetime, timezone


def appel(jeton, methode, payload=None):
    url = f"https://api.telegram.org/bot{jeton}/{methode}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data,
                                 method="POST" if data else "GET")
    if data:
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        corps = e.read().decode()[:400]
        print(f"  !! {methode} a repondu {e.code} : {corps}")
        return {}


def horodatage(ts):
    if not ts:
        return "?"
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime(
        "%d/%m %H:%M:%S")


def main() -> int:
    jeton = os.environ.get("TELEGRAM_BOT_TOKEN") or getpass.getpass(
        "Colle le jeton du bot (rien ne s'affiche, c'est normal) : ").strip()
    if not jeton:
        raise SystemExit("Aucun jeton saisi.")

    print("\n--- 1. Identite du bot ---")
    moi = appel(jeton, "getMe").get("result", {})
    print(f"  @{moi.get('username', '?')}  (id {moi.get('id', '?')}, "
          f"nom « {moi.get('first_name', '?')} »)")

    print("\n--- 2. Webhook ---")
    hook = appel(jeton, "getWebhookInfo").get("result", {})
    print(f"  url                  : {hook.get('url') or 'aucune'}")
    print(f"  en attente de livraison : {hook.get('pending_update_count', 0)}")
    if hook.get("last_error_message"):
        print(f"  derniere erreur      : {hook['last_error_message']} "
              f"({horodatage(hook.get('last_error_date'))})")
    if hook.get("allowed_updates"):
        print(f"  types autorises      : {hook['allowed_updates']}")

    print("\n--- 3. File d'attente (lecture seule, rien n'est consomme) ---")
    res = appel(jeton, "getUpdates", {"timeout": 0,
                                      "allowed_updates": ["message",
                                                          "callback_query"]})
    maj = res.get("result", []) or []
    print(f"  {len(maj)} mise(s) a jour en file.")
    clics = 0
    for u in maj:
        uid = u.get("update_id")
        if "callback_query" in u:
            cb = u["callback_query"]
            clics += 1
            qui = (cb.get("from") or {}).get("first_name", "?")
            print(f"  [{uid}] CLIC   {horodatage((cb.get('message') or {}).get('date'))}"
                  f"  de {qui}  donnee = {cb.get('data')}")
        elif "message" in u:
            m = u["message"]
            print(f"  [{uid}] MESSAGE {horodatage(m.get('date'))}  "
                  f"« {(m.get('text') or '')[:50]} »")
        else:
            print(f"  [{uid}] autre : {list(u.keys())}")

    print("\n--- Verdict ---")
    if clics:
        print(f"  Telegram a bien {clics} clic(s) en file. Le probleme est en aval :")
        print("  c'est le releve GitHub qui ne les voit pas ou ne les traite pas.")
    elif maj:
        print("  Telegram a des messages mais aucun clic sur un bouton.")
        print("  Clique sur un bouton d'un brouillon, puis relance ce script.")
    else:
        print("  File vide. Si tu viens de cliquer, c'est qu'un autre programme")
        print("  a releve le bot avant nous : un bot ne peut etre releve que par")
        print("  un seul programme a la fois.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
