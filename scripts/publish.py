"""Publie la premiere publication validee de la file. Echoue bruyamment."""
import sys, time, traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from lib import config, store, telegram, render, linkedin


PARIS = ZoneInfo("Europe/Paris")


def deja_publie_aujourdhui(data: dict) -> int:
    """Combien de publications sont deja parties aujourd'hui, heure de Paris."""
    jour = datetime.now(PARIS).date()
    n = 0
    for i in data["items"]:
        horodatage = i.get("published_at")
        if not horodatage:
            continue
        try:
            quand = datetime.fromisoformat(horodatage)
        except ValueError:
            continue
        if quand.tzinfo is None:
            quand = quand.replace(tzinfo=ZoneInfo("UTC"))
        if quand.astimezone(PARIS).date() == jour:
            n += 1
    return n


def lien_page() -> str:
    """L'adresse du composeur de la page, deduite de son identifiant.

    L'identifiant d'organisation n'est pas un secret : il est dans l'adresse
    publique de la page. On le prend dans la variable quand elle est la, pour
    que ce lien reste juste si la page change un jour d'identifiant.
    """
    ident = (config.LINKEDIN_ORG_URN or "").rsplit(":", 1)[-1]
    if not ident.isdigit():
        ident = "104908740"
    return (f"https://www.linkedin.com/company/{ident}/admin/"
            "page-posts/published/")


def pont_manuel(data: dict, item: dict, png) -> int:
    """Le dernier metre, fait a la main, sans quitter la page.

    Trois envois : le visuel en piece jointe PNG (donc sans la recompression
    de sendPhoto, car ce fichier remonte ensuite sur LinkedIn), le texte seul
    pour qu'il se copie d'un geste, et les deux boutons. Le brouillon reste
    "approved" jusqu'au clic sur Publie : si Younes ne publie pas, rien n'est
    perdu et le pont se repropose demain.
    """
    jour = datetime.now(PARIS).date().isoformat()
    if data["state"].get("pont_envoye_le") == jour:
        print("[pont] deja propose aujourd'hui : ce reveil ne fait rien.")
        return 0

    try:
        render.build(item["gabarit"], item["visual"], png, item.get("theme"))
    except Exception as exc:
        telegram.alert(f"Rendu du visuel impossible ({item['id']}) : {exc}")
        raise

    telegram.send_document(
        png,
        "\U0001f9f1 <b>Publication du jour</b> · "
        f"{item['pilier']} · <code>{item['id']}</code>\n"
        "LinkedIn n'a pas encore accordé le jeton de la page. "
        "Tout est prêt : il reste le téléversement.\n"
        "<i>Le PNG ci-joint est l'original, c'est celui-là qu'il faut "
        "mettre en ligne.</i>")
    telegram.send(item["texte"],
                  buttons=telegram.pont_buttons(item["id"], lien_page()))

    data["state"]["pont_envoye_le"] = jour
    store.save(data)
    print(f"[pont] {item['id']} propose a la publication manuelle.")
    return 0


def main() -> int:
    data = store.load()

    # Garde-fou d'horloge. Deux horloges reveillent ce script : Make, qui est a
    # l'heure, et le planificateur de GitHub, qui arrive avec quatre a cinq
    # heures de retard mais qui sert de filet si la premiere tombe. Le risque
    # devient donc la double publication le meme jour. Cette garde l'interdit :
    # la premiere horloge qui arrive publie, la seconde repart sans rien faire
    # et sans bruit. Retirer cette garde, c'est reouvrir la porte a deux posts
    # le meme matin.
    if deja_publie_aujourdhui(data):
        print("[garde-fou] une publication est deja partie aujourd'hui : "
              "ce reveil ne fait rien.")
        return 0

    pret = [i for i in data["items"] if i["status"] == "approved"]
    pret.sort(key=lambda i: i["created_at"])

    if not pret:
        telegram.alert("File vide au creneau de publication. Rien n'a ete publie.\n"
                       "Envoie-moi une note de terrain pour relancer la machine.")
        return 0

    item = pret[0]
    png = config.OUT / f"{item['id']}.png"
    cible = config.cible()

    # ---------------------------------------------------- le pont provisoire
    # Garde-fou d'identite : aucun repli sur le profil, jamais. Mais une file
    # de brouillons valides qui attend un jeton que LinkedIn n'a pas encore
    # accorde, c'est une machine qui tourne a vide, et une page qui ne publie
    # pas pendant la revue. Tant que le jeton manque, l'agent fait donc tout
    # le chemin sauf le dernier metre : il fabrique le visuel, prepare le
    # texte, ouvre la page au bon endroit, et laisse Younes appuyer. La page
    # reste l'auteur, la cadence est tenue. Le jour ou le jeton arrive, ce
    # bloc ne s'execute plus : il n'y a rien a defaire.
    if cible == "page" and not config.LINKEDIN_ORG_TOKEN:
        return pont_manuel(data, item, png)

    try:
        render.build(item["gabarit"], item["visual"], png, item.get("theme"))
    except Exception as exc:
        telegram.alert(f"Rendu du visuel impossible ({item['id']}) : {exc}")
        raise

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
        telegram.send("🧪 <b>Répétition générale</b>\n"
                      f"Publication sur : {cible}"
                      + (", puis relais depuis ton profil." if relais else ".")
                      + "\nJetons acceptés, visuel fabriqué.\n"
                      f"La publication <code>{item['id']}</code> partirait sans erreur.")
        return 0

    try:
        owner = linkedin.author_urn(cible)
        cle = linkedin.jeton(cible)
        image_urn = linkedin.upload_image(png.read_bytes(), owner, cle)
        post_id = linkedin.create_post(item["texte"], image_urn,
                                       item.get("alt"), owner, cle)
    except Exception as exc:
        telegram.alert(f"Publication LinkedIn en echec sur « {cible} ».\n"
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
        # Repartage sec, sans commentaire : dans le fil des abonnes du profil,
        # le post s'affiche au nom et au logo de la page. Ajouter une phrase
        # ramenerait l'attention sur le profil, c'est exactement l'inverse du
        # but recherche.
        try:
            relais_urn = linkedin.reshare(post_id)
            print(f"Relaye depuis le profil : {relais_urn}")
        except Exception as exc:
            # Le relais est un bonus : son echec ne doit pas annuler une
            # publication deja en ligne.
            telegram.alert("Publication faite sur la page, mais le relais "
                           f"depuis ton profil a échoué :\n"
                           f"<code>{str(exc)[:400]}</code>\n"
                           "Tu peux repartager le post à la main.")
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
    telegram.send(f"✅ <b>Publiée</b> sur {ou} · {item['pilier']} · "
                  f"<code>{item['id']}</code>\n{item['texte'][:300]}…\n\n"
                  + (f"{lien}\n\n" if lien else "")
                  + ("↪️ Relayée depuis ton profil.\n\n" if relais_urn else "")
                  + f"<i>{restants} publication(s) encore en file. "
                    f"Dans quelques jours, /stats pour saisir ses chiffres.</i>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
