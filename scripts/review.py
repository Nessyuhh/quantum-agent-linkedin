"""Releve les reponses Telegram : validations, rejets, reecritures, et les notes
de terrain envoyees en message libre, qui alimentent la banque d'angles."""
import sys
from lib import config, store, telegram, llm, corpus

def reecrire(item) -> str:
    systeme = ("Tu reecris une publication LinkedIn de Quantum Consulting. Meme fond, "
               "meme longueur, angle d'attaque different.\n\n"
               f"## VOIX\n{config.brand('voix')}\n\n"
               f"## LISTE NOIRE\n{config.brand('interdits')}")
    prompt = (f"Texte a reecrire :\n\n{item['texte']}\n\n"
              "Reponds en JSON : {\"texte\": \"la nouvelle version\"}")
    return llm.ask_json(systeme, prompt, max_tokens=1800).get("texte", item["texte"])


def main() -> int:
    data = store.load()
    offset = int(data["state"].get("telegram_offset", 0))
    res = telegram.get_updates(offset)
    updates = res.get("result", []) if isinstance(res, dict) else []
    touched = 0

    for upd in updates:
        offset = max(offset, int(upd.get("update_id", 0)) + 1)

        cb = upd.get("callback_query")
        if cb:
            action, _, item_id = (cb.get("data") or "").partition(":")
            item = store.find(data, item_id)
            if not item:
                telegram.answer_callback(cb["id"], "Publication introuvable")
                continue
            if action == "ok":
                item["status"] = "approved"
                # Une validation explicite est le seul signal fiable de ce qui
                # sonne juste : ce texte devient un exemple pour les suivants.
                if corpus.ajouter(item.get("texte", "")):
                    item["au_corpus"] = True
                telegram.answer_callback(cb["id"], "Valide, elle part au prochain creneau")
            elif action == "no":
                item["status"] = "rejected"
                telegram.answer_callback(cb["id"], "Rejetee")
            elif action == "rw":
                telegram.answer_callback(cb["id"], "Je reecris, deux minutes")
                try:
                    item["texte"] = reecrire(item)
                    item["status"] = "pending"
                    telegram.send(f"↻ <b>Reecrite</b>\n\n{item['texte'][:900]}",
                                  buttons=telegram.draft_buttons(item["id"]))
                except Exception as exc:
                    telegram.alert(f"Reecriture impossible : {exc}")
            touched += 1
            continue

        msg = upd.get("message") or {}
        texte = (msg.get("text") or "").strip()
        if not texte:
            continue

        if texte.startswith("/file") or texte.startswith("/queue"):
            compte = {}
            for it in data["items"]:
                compte[it["status"]] = compte.get(it["status"], 0) + 1
            libres = len([i for i in data["ideas"] if not i.get("used")])
            telegram.send("<b>Etat de la file</b>\n"
                          + "\n".join(f"· {k} : {v}" for k, v in sorted(compte.items()))
                          + f"\n· angles en reserve : {libres}")
            continue

        if texte.startswith("/"):
            telegram.send("Envoie-moi simplement une phrase sur ce que tu as fait "
                          "aujourd'hui, elle devient un angle. /file pour l'etat de la file.")
            continue

        data["ideas"].append({"id": store.new_id("idee-"), "source": "terrain",
                              "text": texte, "used": False, "created_at": store.now()})
        telegram.send("✓ Note de terrain enregistree. Elle sera travaillee "
                      "a la prochaine passe de redaction.")
        touched += 1

    data["state"]["telegram_offset"] = offset
    store.save(data)
    print(f"{touched} evenement(s) traite(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
