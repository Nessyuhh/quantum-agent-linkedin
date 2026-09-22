"""Publie la premiere publication validee de la file. Echoue bruyamment."""
import sys, time, traceback
from pathlib import Path
from lib import config, store, telegram, render, linkedin


# Ce que le profil dit en repartageant, quand la publication n'a pas fourni
# d'accroche de rechange. Court, factuel, sans emphase.
PHRASE_DE_RELAIS = "Ce qu'on voit sur le terrain, en ce moment."


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

    cible = config.cible()
    config.require("LINKEDIN_ORG_ACCESS_TOKEN" if cible == "page"
                   else "LINKEDIN_ACCESS_TOKEN")
    relais = (cible == "page" and config.RELAIS_PROFIL
              and bool(config.LINKEDIN_TOKEN))

    if config.DRY_RUN:
        # Repetition generale : on va jusqu'au bout de ce qui peut casser
        # (jetons, identites LinkedIn, rendu du visuel) sans rien publier.
        print(f"[repetition] {cible} : jeton accepte, auteur "
              f"{linkedin.author_urn(cible)}")
        if relais:
            print("[repetition] relais profil : auteur "
                  f"{linkedin.author_urn('profil')}")
        print(f"[repetition] pret a publier {item['id']}, visuel {png}")
        telegram.send("\ud83e\uddea <b>R\u00e9p\u00e9tition g\u00e9n\u00e9rale</b>\n"
                      f"Publication sur : {cible}"
                      + (", puis relais depuis ton profil." if relais else ".")
                      + "\nJetons accept\u00e9s, visuel fabriqu\u00e9.\n"
                      f"La publication <code>{item['id']}</code> partirait sans erreur.")
        return 0

    try:
        owner = linkedin.author_urn(cible)
        cle = linkedin.jeton(cible)
        image_urn = linkedin.upload_image(png.read_bytes(), owner, cle)
        post_id = linkedin.create_post(item["texte"], image_urn,
                                       item.get("alt"), owner, cle)
    except Exception as exc:
        telegram.alert(f"Publication LinkedIn en echec sur \u00ab {cible} \u00bb.\n"
                       f"<code>{str(exc)[:500]}</code>\n"
                       "Si c'est une 401, le jeton a expire : relance "
                       "scripts/auth_linkedin.py.")
        traceback.print_exc()
        raise
    print(f"Publie sur {cible} : {item['id']} -> {post_id}")

    # ------------------------------------------------------------ le relais
    # Le profil repartage le post de la page. Tout l'engagement declenche par
    # ce repartage s'inscrit au compte de la page : c'est la seule maniere de
    # faire profiter une page qui debute d'un reseau personnel deja constitue.
    relais_urn = ""
    if relais and str(post_id).startswith("urn:li:"):
        if config.RELAIS_DELAI_MIN:
            time.sleep(config.RELAIS_DELAI_MIN * 60)
        mot = (item.get("hooks") or [""])[0].strip() or PHRASE_DE_RELAIS
        try:
            relais_urn = linkedin.reshare(post_id, mot)
            print(f"Relaye depuis le profil : {relais_urn}")
        except Exception as exc:
            # Le relais est un bonus : son echec ne doit pas annuler une
            # publication deja en ligne.
            telegram.alert("Publication faite sur la page, mais le relais "
                           f"depuis ton profil a \u00e9chou\u00e9 :\n"
                           f"<code>{str(exc)[:400]}</code>\n"
                           "Tu peux repartager le post \u00e0 la main.")
            traceback.print_exc()

    item["status"] = "published"
    item["published_at"] = store.now()
    item["post_urn"] = post_id
    item["post_urns"] = {cible: post_id, "relais_profil": relais_urn}
    store.save(data)

    restants = len([i for i in data["items"] if i["status"] == "approved"])
    lien = (f"https://www.linkedin.com/feed/update/{post_id}/"
            if str(post_id).startswith("urn:li:") else "")
    ou = "la page Quantum Consulting" if cible == "page" else "ton profil"
    telegram.send(f"\u2705 <b>Publi\u00e9e</b> sur {ou} \u00b7 {item['pilier']} \u00b7 "
                  f"<code>{item['id']}</code>\n{item['texte'][:300]}\u2026\n\n"
                  + (f"{lien}\n\n" if lien else "")
                  + ("\u21aa\ufe0f Relay\u00e9e depuis ton profil.\n\n" if relais_urn else "")
                  + f"<i>{restants} publication(s) encore en file. "
                    f"Dans quelques jours, /stats pour saisir ses chiffres.</i>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
