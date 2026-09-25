"""Passe hebdomadaire : choisit des angles, redige, critique, remplit la file.

Double passe volontaire. La passe de critique est ce qui separe un texte passable
d'un texte publiable, et elle ne coute que quelques centimes de plus.
"""
import json, sys
from lib import config, store, llm, telegram, render

# Chaque pilier dispose de deux mises en page possibles. On prend celle qui n'a
# pas servi le plus recemment : cinq gabarits et deux ambiances donnent assez de
# combinaisons pour qu'un lecteur regulier ne voie pas deux fois la meme image.
# Le gabarit B (le meme processus avant et apres, en deux voies) est retire de
# la rotation le 25 septembre : Younes le juge bon pour une annonce unique, pas
# pour une mise en page qui revient. Le fichier templates/gabarit-b.html reste
# en place pour que les anciennes publications continuent de se regenerer, mais
# plus aucun pilier ne le propose.
GABARITS_PAR_PILIER = {
    "chiffre": ["A", "E"],
    "pedagogie": ["D", "C"],
    "coulisses": ["D", "A"],
    "position": ["C", "D"],
    "preuve": ["E", "A"],
}
VALIDATION_OBLIGATOIRE = {"position"}
ROTATION = ["chiffre", "pedagogie", "coulisses", "position"]

SCHEMA_VISUEL = {
    "A": '"visual": {"EYEBROW": "la LEGENDE de la mesure : ce qui a ete chronometre et dans '
         'quel contexte anonymise, en capitales, une a deux lignes separees par <br>. '
         'Jamais un libelle interne ni une etiquette de classement", '
         '"NUMBER": "le chiffre seul, 1 a 4 caracteres", '
         '"UNIT": "l\'unite en capitales avec un point final", '
         '"REVEAL": "une a deux lignes, <b>...</b> autour du chiffre secondaire, <br> pour le retour a la ligne"}',
    "B": '"visual": {"TITLE": "titre condense, 2 lignes avec <br>, point final", '
         '"BEFORE_TOTAL": "ex 11 jours", "before_steps": [{"nom": "Mail recu", "temps": "J+0"}], '
         '"AFTER_TOTAL": "ex 4 heures", "after_steps": [{"nom": "Mail recu", "temps": "H+0"}], '
         '"NOTE": "deux lignes courtes en capitales separees par \\n"}  '
         '(before_steps : 4 a 6 etapes, after_steps : 1 a 2)',
    "C": '"visual": {"PHRASE": "la phrase, 2 a 3 lignes separees par <br>, point final, '
         'le segment a mettre en valeur entoure de <span class=\\"grad-text\\">...</span>"}',
    "D": '"visual": {"TITLE": "titre court en une ligne, point final", '
         '"STEP1_T": "le premier temps, une phrase de 6 a 10 mots, sans point final", '
         '"STEP1_D": "ce que ca donne concretement, une phrase de 12 a 18 mots", '
         '"STEP2_T": "...", "STEP2_D": "...", "STEP3_T": "...", "STEP3_D": "...", '
         '"TOTAL": "le bilan en capitales, 3 a 6 mots, ex UNE DEMI-JOURNEE SUR PLACE"}',
    "E": '"visual": {"TITLE": "ce qu\'on mesure, une a deux lignes avec <br>, point final", '
         '"LEFT_LABEL": "AUJOURD\'HUI", "LEFT_NUMBER": "le chiffre seul, 1 a 4 caracteres", '
         '"LEFT_UNIT": "l\'unite et sa precision, 5 a 10 mots", '
         '"RIGHT_LABEL": "APRES", "RIGHT_NUMBER": "le chiffre seul, 1 a 4 caracteres", '
         '"RIGHT_UNIT": "l\'unite et sa precision, 5 a 10 mots", '
         '"NOTE": "une phrase qui explique l\'ecart, 12 a 20 mots, point final"}',
}


def systeme_redaction() -> str:
    return (
        "Tu rédiges les publications LinkedIn de Quantum Consulting, cabinet français "
        "qui fait gagner du temps aux dirigeants de TPE et PME en automatisant leurs "
        "tâches répétitives.\n\n"
        "CINQ RÈGLES ABSOLUES, avant toutes les autres :\n"
        "1. Tu écris en français CORRECTEMENT ACCENTUÉ. Tous les accents, toutes les "
        "cédilles, y compris sur les capitales. Un texte non accentué est rejeté.\n"
        "2. Tu écris pour un dirigeant qui ne connaît RIEN à l'intelligence "
        "artificielle et n'a aucune envie d'apprendre le vocabulaire. Aucun terme "
        "technique. Tu décris ce que la chose fait, en français ordinaire. Le test : "
        "un dirigeant de 55 ans qui n'a jamais ouvert ChatGPT doit comprendre chaque "
        "phrase du premier coup.\n"
        "3. Tu n'INVENTES aucun cas, aucun client, aucun personnage. Pas de "
        "\u00ab un dirigeant dans la Loire \u00bb, pas de \u00ab le dirigeant de la PME de douze "
        "personnes a remarqu\u00e9 que\u2026 \u00bb. Quantum Consulting n'a pas encore "
        "d'histoires de clients \u00e0 raconter, donc tu n'en racontes pas. Tu t'adresses "
        "au lecteur directement : vous, votre \u00e9quipe, votre fichier de suivi.\n"
        "4. Ta PREMI\u00c8RE LIGNE est une question pr\u00e9cise qu'un dirigeant peut se poser "
        "le lundi matin sur sa propre entreprise. Le reste du texte y r\u00e9pond. Tu ne "
        "commences JAMAIS par citer une \u00e9tude, un article ou un classement, jamais par "
        "une mise en sc\u00e8ne, jamais par une grande d\u00e9claration sur l'IA.\n"
        "5. Les nombres s'\u00e9crivent en chiffres : 2026, 12 personnes, 2 heures. Jamais "
        "en toutes lettres.\n\n"
        f"## POSITIONNEMENT\n{config.brand('positionnement')}\n\n"
        f"## VOIX\n{config.brand('voix')}\n\n"
        f"## EXEMPLES DE REFERENCE (imite ce rythme, jamais le contenu)\n{config.brand('corpus')}\n"
    )


def systeme_critique() -> str:
    return (
        "Tu es le relecteur impitoyable de Quantum Consulting. Tu ne felicites jamais. "
        "Tu appliques la liste noire a la lettre et tu reecris le texte pour le rendre "
        "publiable. Si le texte est irrecuperable, tu le dis.\n\n"
        "TROIS FAUTES QUE TU CORRIGES SYSTEMATIQUEMENT, meme si le reste est bon :\n"
        "1. Un cas invente, un client imaginaire, un personnage fabrique : tu le "
        "remplaces par une adresse directe au lecteur (vous, votre equipe).\n"
        "2. Une ouverture qui cite une etude, un article, un classement, ou qui met "
        "une scene en place : tu la remplaces par une question precise que le "
        "dirigeant se pose sur sa propre entreprise.\n"
        "3. Un nombre ecrit en toutes lettres : tu le remets en chiffres.\n\n"
        f"## VOIX\n{config.brand('voix')}\n\n"
        f"## LISTE NOIRE\n{config.brand('interdits')}\n"
    )


CONSIGNE_VEILLE = (
    "Cet angle vient d'un flux d'actualite. Il te sert de point de depart pour "
    "choisir le sujet, et de rien d'autre : l'actualite n'apparait PAS dans le "
    "texte. Ni citee, ni resumee, ni evoquee en ouverture. Tu en tires le probleme "
    "d'organisation qu'elle revele, et tu ecris sur ce probleme comme s'il n'y "
    "avait jamais eu d'article. Si elle ne change rien pour un dirigeant de PME, "
    "tu l'ecris franchement, c'est une bien meilleure publication qu'un "
    "enthousiasme de commande.\n\n")


def rediger(angle: str, pilier: str, gabarit: str, deja_traites, source="veille") -> dict:
    prompt = (
        (CONSIGNE_VEILLE if source == "veille" else "")
        + f"Angle a traiter : {angle}\n"
        f"Pilier : {pilier}\n"
        f"Gabarit visuel impose : {gabarit}\n\n"
        f"## PREUVES CHIFFREES AUTORISEES\n{config.brand('preuves')}\n"
        "Tu ne peux citer AUCUN chiffre de resultat qui ne figure pas ci-dessus.\n\n"
        f"## SUJETS DEJA TRAITES RECEMMENT, a ne pas repeter\n"
        + ("\n".join(f"- {s}" for s in deja_traites) or "- aucun") + "\n\n"
        "Produis un objet JSON avec ces cles :\n"
        '{"texte": "la publication complete, 120 a 220 mots, sauts de ligne reels",\n'
        ' "hooks": ["variante d\'accroche 1", "variante d\'accroche 2"],\n'
        ' "alt": "description du visuel pour les lecteurs d\'ecran, une phrase",\n'
        f' {SCHEMA_VISUEL[gabarit]}\n'
        '}\n'
        "Le visuel doit reprendre le chiffre ou l'idee centrale du texte, pas le repeter mot pour mot. "
        "Le visuel est PUBLIC : aucun libelle interne, aucune reference de dossier, "
        "aucun nom de pilier, aucune etiquette de classement n'y figure."
    )
    return llm.ask_json(systeme_redaction(), prompt, max_tokens=2500)


def critiquer(brouillon: dict, pilier: str, gabarit: str) -> dict:
    prompt = (
        "Voici un brouillon de publication et son visuel.\n\n"
        f"TEXTE :\n{brouillon.get('texte','')}\n\n"
        f"VISUEL :\n{json.dumps(brouillon.get('visual', {}), ensure_ascii=False, indent=1)}\n\n"
        "1. Liste chaque violation de la liste noire, precisement.\n"
        "2. Applique les deux tests finaux.\n"
        "3. Reecris le texte pour corriger tout ce que tu as releve, en gardant le fond "
        "et la longueur. Si rien n'est a corriger, renvoie le texte tel quel.\n"
        "4. Corrige le visuel si une de ses valeurs viole la charte.\n\n"
        "Reponds en JSON :\n"
        '{"problemes": ["..."], "verdict": "publiable" ou "a_jeter",\n'
        ' "risque_humain": true si le texte pourrait vexer un client ou un lecteur, sinon false,\n'
        ' "cite_un_client": true si un client est identifiable, sinon false,\n'
        ' "texte": "le texte reecrit",\n'
        f' {SCHEMA_VISUEL[gabarit]}\n'
        '}'
    )
    return llm.ask_json(systeme_critique(), prompt, max_tokens=2500)


DELAI_PEREMPTION_JOURS = 3


def perimer_les_brouillons_oublies(data) -> None:
    """Un brouillon sans reponse au bout de trois jours sort de la file.

    Sans cela, trois brouillons oublies bloquent la redaction indefiniment :
    c'est exactement ce qui s'est produit du 19 au 22 septembre. Un brouillon
    qu'on n'a pas voulu trancher en trois jours est un brouillon qu'on ne
    veut pas, et la machine doit pouvoir continuer sans lui.
    """
    from datetime import datetime, timedelta, timezone
    limite = datetime.now(timezone.utc) - timedelta(days=DELAI_PEREMPTION_JOURS)
    perimes = []
    for item in data["items"]:
        if item.get("status") != "pending":
            continue
        try:
            cree = datetime.fromisoformat(item.get("created_at", ""))
        except ValueError:
            continue
        if cree < limite:
            item["status"] = "expired"
            perimes.append(item)
    if perimes:
        telegram.alert(
            f"\u23f3 {len(perimes)} brouillon(s) sans r\u00e9ponse depuis "
            f"{DELAI_PEREMPTION_JOURS} jours sortent de la file.\n"
            "La r\u00e9daction reprend son cours. Rien n'est publi\u00e9 sans ton clic.")
        store.save(data)


def choisir_gabarit(data, pilier: str) -> str:
    """Parmi les mises en page du pilier, celle qui a le moins servi recemment."""
    choix = GABARITS_PAR_PILIER.get(pilier) or ["D"]
    recents = [i.get("gabarit") for i in data["items"][-4:]]
    for g in choix:
        if g not in recents:
            return g
    return choix[0]


def preuves_disponibles() -> bool:
    """Le pilier chiffre exige une preuve reellement mesuree. Tant que
    preuves.md ne contient aucune ligne de donnee, on ne le propose pas :
    mieux vaut ne rien dire que citer un chiffre invente."""
    for ligne in config.brand("preuves").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith(("#", "<!--", "`", "Format", "Exemple")):
            if ligne.count("|") >= 3:
                return True
    return False


def choisir_pilier(data, idee) -> str:
    ouverts = [p for p in ROTATION
               if p != "chiffre" or preuves_disponibles()]
    if idee.get("pilier") in ouverts:
        return idee["pilier"]
    if idee.get("source") == "veille":
        ouverts = [p for p in ouverts if p in ("pedagogie", "position")]
    recents = [i.get("pilier") for i in data["items"][-6:]]
    for p in ouverts:
        if p not in recents:
            return p
    return ouverts[0] if ouverts else "pedagogie"


def main() -> int:
    if not (config.GOOGLE_API_KEY or config.ANTHROPIC_API_KEY):
        raise SystemExit("Aucune cle de redaction : definis GOOGLE_API_KEY "
                         "ou ANTHROPIC_API_KEY.")
    print("Redaction avec", llm.modele_actif())
    print("Mode :", "publication automatique" if config.AUTO_PUBLISH
          else "validation humaine systematique")
    data = store.load()

    # Deux horloges independantes : celle-ci alimente la file, celle de
    # publish.py la vide aux creneaux choisis. Quand la file est deja pleine,
    # on ne redige pas : le stock commande, pas le calendrier.
    perimer_les_brouillons_oublies(data)
    valides = [i for i in data["items"] if i.get("status") == "approved"]
    attente = [i for i in data["items"] if i.get("status") == "pending"]
    if len(valides) >= config.STOCK_CIBLE:
        print(f"{len(valides)} publication(s) validee(s) en reserve, "
              f"cible {config.STOCK_CIBLE} : rien a rediger aujourd'hui.")
        return 0
    if len(attente) >= 3:
        print(f"{len(attente)} brouillon(s) attendent deja une decision : "
              "on n'en ajoute pas un de plus.")
        return 0

    besoin = config.POSTS_PER_RUN
    idees = store.pending_ideas(data, besoin)

    if len(idees) < besoin:
        telegram.alert(
            f"Banque d'angles maigre : {len(idees)} idee(s) pour {besoin} publications.\n"
            "La veille a peut-etre echoue. Une note de terrain de ta part vaut "
            "de toute facon mieux qu'un angle de veille.")
        for _ in range(besoin - len(idees)):
            idees.append({"id": store.new_id("auto-"), "source": "defaut",
                          "text": "Explique un mecanisme d'automatisation utile a un "
                                  "dirigeant de PME, avec un exemple concret de terrain.",
                          "pilier": "pedagogie", "created_at": store.now(), "used": False,
                          "_volatile": True})

    deja = store.recent_subjects(data)
    crees = 0

    for idee in idees:
        pilier = choisir_pilier(data, idee)
        gabarit = choisir_gabarit(data, pilier)
        theme = render.theme_pour(gabarit, len(data["items"]))
        try:
            brouillon = rediger(idee["text"], pilier, gabarit, deja,
                                idee.get("source", "veille"))
            revu = critiquer(brouillon, pilier, gabarit)
        except Exception as exc:
            telegram.alert(f"Echec de generation sur un angle : {exc}")
            continue

        if revu.get("verdict") == "a_jeter":
            telegram.alert("Un brouillon a ete jete par la passe de critique.\n"
                           + "\n".join(f"· {p}" for p in revu.get("problemes", [])[:4]))
            continue

        # Validation humaine systematique : aucun brouillon ne part sans un
        # clic. AUTO_PUBLISH=1 rouvrirait le mode mixte, ce n'est pas le choix.
        auto = config.AUTO_PUBLISH and (
            pilier not in VALIDATION_OBLIGATOIRE
            and not revu.get("risque_humain")
            and not revu.get("cite_un_client"))

        item = {
            "id": store.new_id(),
            "pilier": pilier,
            "gabarit": gabarit,
            "theme": theme,
            "angle": idee["text"][:200],
            "source": idee.get("source", "veille"),
            "texte": revu.get("texte") or brouillon.get("texte", ""),
            "hooks": brouillon.get("hooks", []),
            "alt": brouillon.get("alt", ""),
            "visual": revu.get("visual") or brouillon.get("visual", {}),
            "problemes_releves": revu.get("problemes", []),
            "status": "approved" if auto else "pending",
            "auto": auto,
            "created_at": store.now(),
            "published_at": None,
            "post_urn": None,
        }
        data["items"].append(item)
        deja.append(item["angle"])
        crees += 1

        if not idee.get("_volatile"):
            for i in data["ideas"]:
                if i["id"] == idee["id"]:
                    i["used"] = True

        # Le visuel est rendu maintenant, pas a la publication : Younes doit
        # voir l'image et le texte avant de decider.
        try:
            png = render.build(item["gabarit"], item["visual"],
                               config.OUT / f"{item['id']}.png",
                               item.get("theme"))
            telegram.send_photo(
                png, f"<b>Brouillon</b> \u00b7 {pilier} \u00b7 gabarit {gabarit}\n"
                     f"<i>Au clic, le bouton tourne quelques secondes puis "
                     f"s'arr\u00eate sans rien dire : c'est normal. Les boutons "
                     f"sont relev\u00e9s toutes les 20 minutes, et ils seront "
                     f"alors remplac\u00e9s par ta d\u00e9cision.</i>")
        except Exception as exc:
            telegram.alert(f"Visuel non rendu ({item['id']}) : {exc}\n"
                           "Le texte suit quand meme, mais verifie avant de valider.")

        corps = item["texte"]
        if item["hooks"]:
            corps += "\n\n<i>Accroches alternatives :</i>\n" + "\n".join(
                f"\u00b7 {h}" for h in item["hooks"][:2])
        telegram.send(corps, buttons=telegram.draft_buttons(item["id"]))

    store.save(data)
    print(f"{crees} publication(s) ajoutee(s) a la file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
