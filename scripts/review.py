"""Releve les decisions prises dans Telegram.

Trois reponses possibles par brouillon : Valide, Modifier, Refuse.

"Modifier" ouvre un aller-retour : le bot attend ton prochain message. Une
consigne courte ("plus court, coupe la derniere phrase") est appliquee par le
modele ; un texte long est pris tel quel comme remplacement integral. Dans les
deux cas le visuel est refait pour rester coherent avec le texte, et le
brouillon revient avec ses trois boutons.

Tout autre message libre devient une note de terrain dans la banque d'angles.
"""
import json, sys
from lib import config, store, telegram, llm, render, corpus

SEUIL_REMPLACEMENT = 250   # au-dela, on considere que c'est un texte complet


def _systeme_edition() -> str:
    return ("Tu réécris une publication LinkedIn de Quantum Consulting.\n\n"
            "DEUX RÈGLES ABSOLUES : français correctement accentué, et aucun terme "
            "technique, le lecteur est un dirigeant de TPE ou PME qui ne connaît pas "
            "le sujet.\n\n"
            f"## VOIX\n{config.brand('voix')}\n\n"
            f"## LISTE NOIRE\n{config.brand('interdits')}")


def appliquer_edition(item: dict, message: str) -> dict:
    """Renvoie le texte et le visuel mis a jour."""
    import generate  # pour reutiliser le schema de visuel du gabarit
    schema = generate.SCHEMA_VISUEL[item["gabarit"]]

    if len(message) >= SEUIL_REMPLACEMENT:
        consigne = (f"Voici le texte impose par Younes, a garder tel quel :\n\n"
                    f"{message}\n\nNe le reecris pas. Produis seulement le "
                    f"visuel correspondant.")
        texte = message
    else:
        consigne = (f"Texte actuel :\n\n{item['texte']}\n\n"
                    f"Consigne de Younes : {message}\n\n"
                    f"Reecris le texte en appliquant cette consigne, puis "
                    f"produis le visuel correspondant.")
        texte = None

    out = llm.ask_json(
        _systeme_edition(),
        consigne + '\n\nReponds en JSON : {"texte": "le texte final", '
                   + schema + "}",
        max_tokens=2500)
    return {"texte": texte or out.get("texte") or item["texte"],
            "visual": out.get("visual") or item["visual"]}


def renvoyer(item: dict, entete: str) -> None:
    try:
        png = render.build(item["gabarit"], item["visual"],
                           config.OUT / f"{item['id']}.png")
        telegram.send_photo(png, entete)
    except Exception as exc:
        telegram.alert(f"Visuel non rendu ({item['id']}) : {exc}")
    telegram.send(item["texte"], buttons=telegram.draft_buttons(item["id"]))


def main() -> int:
    data = store.load()
    offset = int(data["state"].get("telegram_offset", 0))
    res = telegram.get_updates(offset)
    updates = res.get("result", []) if isinstance(res, dict) else []
    traites = 0

    for upd in updates:
        offset = max(offset, int(upd.get("update_id", 0)) + 1)

        # ------------------------------------------------ les trois boutons
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
                data["state"].pop("attente_edition", None)
                telegram.answer_callback(cb["id"],
                                         "Valide, elle part au prochain creneau")

            elif action == "no":
                item["status"] = "rejected"
                data["state"].pop("attente_edition", None)
                telegram.answer_callback(cb["id"], "Refuse, elle ne partira pas")

            elif action == "mod":
                data["state"]["attente_edition"] = item_id
                item["status"] = "pending"
                telegram.answer_callback(cb["id"], "Dis-moi quoi changer")
                telegram.send(
                    "✏️ <b>Que faut-il changer ?</b>\n\n"
                    "Envoie une consigne courte, par exemple "
                    "<i>plus court</i>, <i>coupe la derniere phrase</i>, "
                    "<i>commence par le chiffre</i>.\n\n"
                    "Ou colle directement ton propre texte : au-dela de "
                    f"{SEUIL_REMPLACEMENT} caracteres, je le prends tel quel "
                    "et je refais seulement le visuel.")
            traites += 1
            continue

        # ------------------------------------------------ messages libres
        msg = upd.get("message") or {}
        texte = (msg.get("text") or "").strip()
        if not texte:
            continue

        if texte.startswith(("/file", "/queue")):
            compte = {}
            for it in data["items"]:
                compte[it["status"]] = compte.get(it["status"], 0) + 1
            libres = len([i for i in data["ideas"] if not i.get("used")])
            telegram.send("<b>Etat de la file</b>\n"
                          + "\n".join(f"· {k} : {v}"
                                      for k, v in sorted(compte.items()))
                          + f"\n· angles en reserve : {libres}")
            continue

        if texte.startswith("/aide") or texte.startswith("/help"):
            telegram.send(
                "<b>Ce que tu peux faire ici</b>\n\n"
                "· Les trois boutons sous chaque brouillon decident de son sort.\n"
                "· Apres Modifier, ton message suivant est la consigne.\n"
                "· Une phrase sur ce que tu as fait en mission devient un "
                "angle, et passe devant la veille.\n"
                "· /file donne l'etat de la file.")
            continue

        # Un message qui suit un clic sur Modifier est une consigne d'edition.
        en_attente = data["state"].get("attente_edition")
        if en_attente:
            item = store.find(data, en_attente)
            data["state"].pop("attente_edition", None)
            if not item:
                telegram.send("Le brouillon concerne n'existe plus.")
                continue
            telegram.send("Je reprends le brouillon, deux minutes...")
            try:
                maj = appliquer_edition(item, texte)
                item["texte"] = maj["texte"]
                item["visual"] = maj["visual"]
                item.setdefault("editions", []).append(texte[:200])
                renvoyer(item, "<b>Version revue</b> · "
                               f"{item['pilier']} · gabarit {item['gabarit']}")
            except Exception as exc:
                telegram.alert(f"Edition impossible : {exc}")
            traites += 1
            continue

        if texte.startswith("/"):
            telegram.send("Commande inconnue. /aide pour la liste.")
            continue

        data["ideas"].append({"id": store.new_id("idee-"), "source": "terrain",
                              "text": texte, "used": False,
                              "created_at": store.now()})
        telegram.send("✓ Note de terrain enregistree. Elle passera avant "
                      "les angles de veille a la prochaine redaction.")
        traites += 1

    data["state"]["telegram_offset"] = offset
    store.save(data)
    print(f"{traites} evenement(s) traite(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
