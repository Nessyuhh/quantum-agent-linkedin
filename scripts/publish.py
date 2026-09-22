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

    cibles = config.cibles()
    for cible in cibles:
        config.require("LINKEDIN_ORG_ACCESS_TOKEN" if cible == "page"
                       else "LINKEDIN_ACCESS_TOKEN")

    if config.DRY_RUN:
        # Repetition generale : on va jusqu'au bout de ce qui peut casser
        # (jeton, identite LinkedIn, rendu du visuel) sans rien publier.
        for cible in cibles:
            print(f"[repetition] {cible} : jeton accepte, auteur "
                  f"{linkedin.author_urn(cible)}")
        print(f"[repetition] pret a publier {item['id']}, visuel {png}")
        telegram.send("\ud83e\uddea <b>R\u00e9p\u00e9tition g\u00e9n\u00e9rale</b>\n"
                      f"Cible(s) : {', '.join(cibles)}.\n"
                      "Jeton accept\u00e9, auteur reconnu, visuel fabriqu\u00e9.\n"
                      f"La publication <code>{item['id']}</code> partirait sans erreur.")
        return 0

    liens, urns = [], {}
    for cible in cibles:
        try:
            owner = linkedin.author_urn(cible)
            cle = linkedin.jeton(cible)
            image_urn = linkedin.upload_image(png.read_bytes(), owner, cle)
            post_id = linkedin.create_post(item["texte"], image_urn,
                                           item.get("alt"), owner, cle)
        except Exception as exc:
            telegram.alert(f"Publication LinkedIn en echec sur la cible "
                           f"\u00ab {cible} \u00bb.\n"
                           f"<code>{str(exc)[:500]}</code>\n"
                           "Si c'est une 401, le jeton a expire : relance "
                           "scripts/auth_linkedin.py.")
            traceback.print_exc()
            raise
        urns[cible] = post_id
        if str(post_id).startswith("urn:li:"):
            liens.append(f"https://www.linkedin.com/feed/update/{post_id}/")
        print(f"Publie sur {cible} : {item['id']} -> {post_id}")

    item["status"] = "published"
    item["published_at"] = store.now()
    item["post_urn"] = urns.get("page") or urns.get("profil")
    item["post_urns"] = urns
    store.save(data)

    restants = len([i for i in data["items"] if i["status"] == "approved"])
    ou = "la page" if cibles == ["page"] else (
        "ton profil" if cibles == ["profil"] else "la page et ton profil")
    telegram.send(f"\u2705 <b>Publi\u00e9e</b> sur {ou} \u00b7 {item['pilier']} \u00b7 "
                  f"<code>{item['id']}</code>\n{item['texte'][:300]}\u2026\n\n"
                  + ("\n".join(liens) + "\n\n" if liens else "")
                  + f"<i>{restants} publication(s) encore en file. "
                    f"Dans quelques jours, /stats pour saisir ses chiffres.</i>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
