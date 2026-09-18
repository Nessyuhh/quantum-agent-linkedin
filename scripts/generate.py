"""Passe hebdomadaire : choisit des angles, redige, critique, remplit la file.

Double passe volontaire. La passe de critique est ce qui separe un texte passable
d'un texte publiable, et elle ne coute que quelques centimes de plus.
"""
import json, sys
from lib import config, store, llm, telegram

GABARIT_PAR_PILIER = {"chiffre": "A", "pedagogie": "B", "coulisses": "A", "position": "C"}
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
         'le segment a mettre en valeur entoure de <span class=\\"grad-text-clair\\">...</span>"}',
}


def systeme_redaction() -> str:
    return (
        "Tu rediges les publications LinkedIn de Quantum Consulting, cabinet francais "
        "d'automatisation et d'integration IA pour PME et ETI. Tu ecris EXACTEMENT dans "
        "la voix decrite ci-dessous, sans jamais t'en ecarter.\n\n"
        f"## POSITIONNEMENT\n{config.brand('positionnement')}\n\n"
        f"## VOIX\n{config.brand('voix')}\n\n"
        f"## EXEMPLES DE REFERENCE (imite ce rythme, jamais le contenu)\n{config.brand('corpus')}\n"
    )


def systeme_critique() -> str:
    return (
        "Tu es le relecteur impitoyable de Quantum Consulting. Tu ne felicites jamais. "
        "Tu appliques la liste noire a la lettre et tu reecris le texte pour le rendre "
        "publiable. Si le texte est irrecuperable, tu le dis.\n\n"
        f"## VOIX\n{config.brand('voix')}\n\n"
        f"## LISTE NOIRE\n{config.brand('interdits')}\n"
    )


CONSIGNE_VEILLE = (
    "Cet angle vient d'un flux d'actualite. Tu ne resumes PAS l'actualite et tu ne "
    "la commentes pas en general : tu expliques ce qu'elle change concretement pour "
    "un dirigeant de PME francaise, avec un exemple de processus precis. Si elle ne "
    "change rien pour lui, tu l'ecris franchement, c'est une bien meilleure "
    "publication qu'un enthousiasme de commande.\n\n")


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
    data = store.load()
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
        gabarit = GABARIT_PAR_PILIER[pilier]
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

        auto = (pilier not in VALIDATION_OBLIGATOIRE
                and not revu.get("risque_humain")
                and not revu.get("cite_un_client"))

        item = {
            "id": store.new_id(),
            "pilier": pilier,
            "gabarit": gabarit,
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

        if auto:
            telegram.send(
                f"\U0001f7e2 <b>Programme automatiquement</b> · {pilier} · gabarit {gabarit}\n\n"
                f"{item['texte'][:900]}",
                buttons=[[{"text": "✕ Annuler finalement", "callback_data": f"no:{item['id']}"}]])
        else:
            telegram.send(
                f"✍️ <b>A valider</b> · {pilier} · gabarit {gabarit}\n\n"
                f"{item['texte'][:900]}\n\n"
                f"<i>Accroches alternatives :</i>\n"
                + "\n".join(f"· {h}" for h in item["hooks"][:2]),
                buttons=telegram.draft_buttons(item["id"]))

    store.save(data)
    print(f"{crees} publication(s) ajoutee(s) a la file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
