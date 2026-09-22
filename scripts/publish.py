"""Publie la premiere publication validee de la file. Echoue bruyamment."""
import sys, traceback
from pathlib import Path
from lib import config, store, telegram, render, linkedin


def main() -> int:
    data = store.load()
    pret = [i for i in data["items"] if i["status"] == "approved"]
    pret.sort(key=lambda i: i["created_at"])

    if not pret:
        telegram.alert("File vide au creneau de publication. Rien n'a ete publie.\n"
                       "Envoie-moi une note de terrain pour relancer la machine.")
        return 0

    item = pret[0]
    png = config.OUT / f"{item['id']}.png"

    try:
        render.build(item["gabarit"], item["visual"], png, item.get("theme"))
    except Exception as exc:
        telegram.alert(f"Rendu du visuel impossible ({item['id']}) : {exc}")
        raise

    config.require("LINKEDIN_ACCESS_TOKEN")

    if config.DRY_RUN:
        # Repetition generale : on va jusqu'au bout de ce qui peut casser
        # (jeton, identite LinkedIn, rendu du visuel) sans rien publier.
        owner = linkedin.author_urn()
        print(f"[repetition] jeton accepte, auteur {owner}")
        print(f"[repetition] pret a publier {item['id']}, visuel {png}")
        telegram.send(f"\ud83e\uddea <b>R\u00e9p\u00e9tition g\u00e9n\u00e9rale</b>\n"
                      f"Jeton accept\u00e9, auteur reconnu, visuel fabriqu\u00e9.\n"
                      f"La publication <code>{item['id']}</code> partirait sans erreur.")
        return 0

    try:
        owner = linkedin.author_urn()
        image_urn = linkedin.upload_image(png.read_bytes(), owner)
        post_id = linkedin.create_post(item["texte"], image_urn, item.get("alt"))
    except Exception as exc:
        telegram.alert("Publication LinkedIn en echec.\n"
                       f"<code>{str(exc)[:500]}</code>\n"
                       "Si c'est une 401, le jeton a expire : relance scripts/auth_linkedin.py.")
        traceback.print_exc()
        raise

    item["status"] = "published"
    item["published_at"] = store.now()
    item["post_urn"] = post_id
    store.save(data)

    restants = len([i for i in data["items"] if i["status"] == "approved"])
    lien = (f"https://www.linkedin.com/feed/update/{post_id}/"
            if str(post_id).startswith("urn:li:") else "")
    telegram.send(f"✅ <b>Publiée</b> · {item['pilier']} · "
                  f"<code>{item['id']}</code>\n{item['texte'][:300]}…\n\n"
                  + (f"{lien}\n\n" if lien else "")
                  + f"<i>{restants} publication(s) encore en file. "
                    f"Dans quelques jours, /stats pour saisir ses chiffres.</i>")
    print(f"Publie : {item['id']} -> {post_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
