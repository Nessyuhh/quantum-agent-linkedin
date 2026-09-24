"""Releve les decisions prises dans Telegram.

Trois reponses possibles par brouillon : Valide, Modifier, Refuse.

"Modifier" ouvre un aller-retour : le bot attend ton prochain message. Une
consigne courte ("plus court, coupe la derniere phrase") est appliquee par le
modele ; un texte long est pris tel quel comme remplacement integral. Dans les
deux cas le visuel est refait pour rester coherent avec le texte, et le
brouillon revient avec ses trois boutons.

Tout autre message libre devient une note de terrain dans la banque d'angles.
"""
import json, re, sys
from lib import analyse, config, store, telegram, llm, render, corpus

SEUIL_REMPLACEMENT = 250   # au-dela, on considere que c'est un texte complet


def _systeme_edition() -> str:
    return ("Tu réécris une publication LinkedIn de Quantum Consulting.\n\n"
            "QUATRE RÈGLES ABSOLUES : français correctement accentué ; aucun terme "
            "technique, le lecteur est un dirigeant de TPE ou PME qui ne connaît pas "
            "le sujet ; aucun cas ni personnage inventé, on s'adresse au lecteur "
            "directement ; les nombres en chiffres, jamais en toutes lettres.\n\n"
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
                           config.OUT / f"{item['id']}.png", item.get("theme"))
        telegram.send_photo(png, entete)
    except Exception as exc:
        telegram.alert(f"Visuel non rendu ({item['id']}) : {exc}")
    telegram.send(item["texte"], buttons=telegram.draft_buttons(item["id"]))


def confirmer(chat_id, message_id, etiquette: str, message) -> None:
    """Rend la decision visible, sans dependre de la bulle expirable.

    Deux gestes : les trois boutons du brouillon deviennent une etiquette figee,
    et un message recapitule. L'un comme l'autre restent valables des heures
    apres le clic, contrairement a answerCallbackQuery.
    """
    if chat_id and message_id:
        try:
            telegram.retirer_boutons(chat_id, message_id, etiquette)
        except Exception as exc:
            print(f"[releve] etiquette non posee : {exc}")
    if message:
        telegram.send(message)


def main() -> int:
    data = store.load()
    telegram.etat_polling()
    offset = int(data["state"].get("telegram_offset", 0))
    res = telegram.get_updates(offset)
    updates = res.get("result", []) if isinstance(res, dict) else []
    traites = 0

    for upd in updates:
        offset = max(offset, int(upd.get("update_id", 0)) + 1)

        # Le bot est joignable par n'importe qui sur Telegram. Sans ce filtre,
        # un inconnu qui lui ecrit voit son texte range dans la banque d'angles,
        # et peut meme remplacer un brouillon si l'agent attend une reecriture.
        # On n'ecoute qu'un seul salon : celui de Younes.
        origine_upd = (upd.get("callback_query") or upd).get("message") or {}
        salon = str((origine_upd.get("chat") or {}).get("id") or "")
        if config.TELEGRAM_CHAT and salon and salon != str(config.TELEGRAM_CHAT):
            print(f"[releve] message ignore : salon inconnu ({salon}).")
            continue

        # ------------------------------------------------ les trois boutons
        cb = upd.get("callback_query")
        if cb:
            action, _, item_id = (cb.get("data") or "").partition(":")
            if action == "vu":          # etiquette figee, deja traitee
                telegram.answer_callback(cb["id"], "Deja decide")
                continue
            item = store.find(data, item_id)
            origine = cb.get("message") or {}
            chat_origine = (origine.get("chat") or {}).get("id")
            msg_origine = origine.get("message_id")
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
                confirmer(chat_origine, msg_origine,
                          "\u2705 Valid\u00e9e",
                          f"\u2705 <b>Valid\u00e9e</b> \u00b7 <code>{item['id']}</code>\n"
                          "Elle part au prochain cr\u00e9neau de publication.")

            elif action == "no":
                item["status"] = "rejected"
                data["state"].pop("attente_edition", None)
                telegram.answer_callback(cb["id"], "Refuse, elle ne partira pas")
                confirmer(chat_origine, msg_origine,
                          "\u274c Refus\u00e9e",
                          f"\u274c <b>Refus\u00e9e</b> \u00b7 <code>{item['id']}</code>\n"
                          "Elle ne partira pas. Dis-moi ce qui n'allait pas si tu "
                          "veux que la prochaine soit meilleure.")

            elif action == "mod":
                data["state"]["attente_edition"] = item_id
                item["status"] = "pending"
                telegram.answer_callback(cb["id"], "Dis-moi quoi changer")
                confirmer(chat_origine, msg_origine, "\u270f\ufe0f \u00c0 reprendre",
                          None)
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

        if texte.startswith("/stats"):
            attente = [i for i in data["items"]
                       if i.get("status") == "published"
                       and not (i.get("mesures") or {}).get("vues")]
            if not attente:
                telegram.send("Aucune publication en attente de chiffres. "
                              "Elles sont toutes relevées.")
                continue
            data["state"]["attente_stats"] = True
            lignes = []
            for it in attente[:12]:
                jour = (it.get("published_at") or "")[:10]
                debut = (it.get("texte") or "").split("\n")[0][:70]
                lignes.append(f"<code>{it['id']}</code> · {jour} · {it.get('pilier')}\n  {debut}")
            telegram.send(
                "<b>Relevé des chiffres</b>\n\n"
                + "\n\n".join(lignes)
                + "\n\nRéponds une ligne par publication, dans cet ordre :\n"
                  "<code>identifiant vues réactions commentaires</code>\n\n"
                  "Exemple : <code>013a26ea 1240 18 3</code>\n"
                  "Tu peux en envoyer plusieurs d'un coup, une par ligne. "
                  "Les commentaires sont facultatifs. <code>/fin</code> arrête la saisie.")
            continue

        if data["state"].get("attente_stats"):
            if texte.startswith(("/fin", "/stop")):
                data["state"].pop("attente_stats", None)
                telegram.send("Saisie terminée.")
                continue
            lus, ignores = 0, []
            for ligne in texte.splitlines():
                # « 013a26ea 1240 18 3 » comme « 013a26ea : 1 240 vues,
                # 18 reactions, 3 commentaires » : on lit l'identifiant, puis
                # les nombres dans l'ordre, et on ignore les mots.
                tete = re.match(r"^\s*([0-9a-f]{4,12})\b(.*)$", ligne)
                nombres = (re.findall(r"\d+(?:[ \u00a0\u202f]\d{3})*", tete.group(2))
                           if tete else [])
                if not tete or len(nombres) < 2:
                    if ligne.strip():
                        ignores.append(ligne.strip()[:40])
                    continue
                item = store.find(data, tete.group(1))
                if not item:
                    ignores.append(tete.group(1))
                    continue
                nombre = lambda v: int(re.sub(r"[^0-9]", "", v)) if v else 0
                item["mesures"] = {
                    "vues": nombre(nombres[0]),
                    "reactions": nombre(nombres[1]),
                    "commentaires": nombre(nombres[2]) if len(nombres) > 2 else 0,
                    "releve_le": store.now()}
                lus += 1
            if lus:
                data["state"].pop("attente_stats", None)
                s_ = analyse.synthese(data)
                g = s_["engagement"]["global"]
                telegram.send(
                    f"✓ {lus} publication(s) chiffrée(s).\n\n"
                    f"Cumul : {g['vues']} vues, {g['reactions']} réactions, "
                    f"{g['commentaires']} commentaires.\n"
                    f"Taux d'interaction : {round(g['taux'] * 100, 2)} %\n"
                    f"<i>{s_['fiabilite']['engagement']}</i>"
                    + (f"\n\nLignes non reconnues : {', '.join(ignores)}"
                       if ignores else ""))
                traites += 1
                continue
            telegram.send("Aucune ligne reconnue. Format attendu : "
                          "<code>identifiant vues réactions commentaires</code>. "
                          "<code>/fin</code> pour arrêter.")
            continue

        if texte.startswith("/aide") or texte.startswith("/help"):
            telegram.send(
                "<b>Ce que tu peux faire ici</b>\n\n"
                "· Les trois boutons sous chaque brouillon decident de son sort.\n"
                "· Apres Modifier, ton message suivant est la consigne.\n"
                "· Une phrase sur ce que tu as fait en mission devient un "
                "angle, et passe devant la veille.\n"
                "· /file donne l'état de la file.\n"
                "· /stats ouvre le relevé des chiffres LinkedIn : une minute par mois, et la revue mensuelle sait ce qui porte.")
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
