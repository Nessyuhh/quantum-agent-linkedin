"""Revue mensuelle : ce qui a porté, ce qui a raté, et quoi écrire ensuite.

Trois temps :

1. On relit les signaux (décisions Telegram + chiffres saisis à la main).
2. On demande au modèle une lecture de ces chiffres, avec interdiction
   formelle d'inventer une tendance sur trois publications.
3. On dépose trois angles dans la banque d'idées, en priorité sur la veille :
   la redaction suivante part donc de ce qui a fonctionné, pas de l'actualité
   du jour.

Le rapport est écrit dans content/revues/AAAA-MM.md et versionné : au bout de
six mois, la progression se lit d'un coup d'oeil.
"""
import json, sys
from datetime import datetime, timezone

from lib import analyse, config, llm, store, telegram

SYSTEME = (
    "Tu es le directeur éditorial de Quantum Consulting, cabinet de conseil en "
    "organisation, automatisation et intégration de l'IA pour des TPE et PME.\n\n"
    "Tu analyses les performances d'un compte LinkedIn qui débute. Trois règles :\n"
    "1. Tu écris en français correctement accentué.\n"
    "2. Tu ne surinterprètes jamais. En dessous de six publications mesurées, "
    "tu parles d'indice et tu le dis explicitement.\n"
    "3. Tu parles en décisions concrètes : quoi écrire, quoi arrêter, quoi "
    "tester. Aucun conseil générique du genre « publier régulièrement » ou "
    "« créer de la valeur ».\n\n"
    "Le lectorat visé : des dirigeants de TPE et PME qui ne connaissent rien à "
    "l'intelligence artificielle. Un angle est bon s'il parle d'un problème "
    "d'organisation qu'ils vivent le lundi matin, pas d'une technologie."
)


def contexte(data) -> str:
    s = analyse.synthese(data)
    lignes = [
        "## Volumes",
        json.dumps(s["volumes"], ensure_ascii=False),
        "",
        "## Fiabilité des données",
        json.dumps(s["fiabilite"], ensure_ascii=False),
        "",
        "## Décisions de Younes par dimension",
        "(taux_retenu = part validée, taux_modifie = part qu'il a fallu réécrire)",
        json.dumps(s["decisions"], ensure_ascii=False, indent=1),
        "",
        "## Engagement relevé",
        json.dumps(s["engagement"], ensure_ascii=False, indent=1),
        "",
        "## Publications en tête et en queue",
        json.dumps(s["classement"], ensure_ascii=False, indent=1),
        "",
        "## Consignes de correction données par Younes",
        json.dumps(s["consignes"], ensure_ascii=False, indent=1),
        "",
        "## Piliers éditoriaux en vigueur",
        config.brand("piliers")[:1800],
    ]
    return "\n".join(lignes)


def demander(data) -> dict:
    return llm.ask_json(
        SYSTEME,
        contexte(data) + """

Réponds en JSON strict :
{
  "lecture": "3 à 6 phrases : ce que ces chiffres disent, et ce qu'ils ne disent pas encore.",
  "ce_qui_porte": ["constat court appuyé sur un chiffre du relevé", "..."],
  "ce_qui_rate": ["constat court appuyé sur un chiffre du relevé", "..."],
  "regles_a_ajouter": ["règle de rédaction déduite des corrections demandées, formulée comme une consigne", "..."],
  "a_tester": ["une expérience précise pour le mois prochain, avec le résultat attendu", "..."],
  "angles": [
    {"texte": "sujet de publication formulé comme un problème concret vécu par un dirigeant", "pilier": "pedagogie|position|chiffre|preuve", "pourquoi": "ce que le relevé laisse penser de ce sujet"},
    {"texte": "...", "pilier": "...", "pourquoi": "..."},
    {"texte": "...", "pilier": "...", "pourquoi": "..."}
  ]
}""",
        max_tokens=2600)


def rapport(data, avis: dict) -> str:
    s = analyse.synthese(data)
    mois = datetime.now(timezone.utc).strftime("%Y-%m")
    b = [f"# Revue éditoriale · {mois}", "",
         f"Publications dans la file : {s['volumes']['total']} · "
         f"publiées : {s['volumes']['publiees']} · "
         f"chiffrées à la main : {s['volumes']['mesurees']} · "
         f"angles en réserve : {s['volumes']['angles_en_reserve']}", "",
         f"Fiabilité : décisions, {s['fiabilite']['decisions']} ; "
         f"engagement, {s['fiabilite']['engagement']}.", "",
         "## Lecture", "", avis.get("lecture", "—"), ""]
    for titre, cle in (("Ce qui porte", "ce_qui_porte"),
                       ("Ce qui rate", "ce_qui_rate"),
                       ("Règles de rédaction à ajouter", "regles_a_ajouter"),
                       ("À tester le mois prochain", "a_tester")):
        b += [f"## {titre}", ""]
        b += [f"- {x}" for x in (avis.get(cle) or ["—"])] + [""]
    b += ["## Angles déposés dans la banque d'idées", ""]
    for a in avis.get("angles", []):
        b.append(f"- **{a.get('texte','')}** · pilier {a.get('pilier','?')} — "
                 f"{a.get('pourquoi','')}")
    b += ["", "## Relevé brut", "", "```json",
          json.dumps(s, ensure_ascii=False, indent=1), "```", ""]
    return "\n".join(b)


def digest(avis: dict, s: dict) -> str:
    def liste(cle, titre):
        vals = avis.get(cle) or []
        if not vals:
            return ""
        return f"\n<b>{titre}</b>\n" + "\n".join(f"· {v}" for v in vals[:3]) + "\n"

    return ("<b>Revue éditoriale du mois</b>\n\n"
            + avis.get("lecture", "")
            + "\n"
            + liste("ce_qui_porte", "Ce qui porte")
            + liste("ce_qui_rate", "Ce qui rate")
            + liste("a_tester", "À tester")
            + "\n<b>Trois angles déposés pour la prochaine rédaction</b>\n"
            + "\n".join(f"· {a.get('texte','')}"
                        for a in avis.get("angles", [])[:3])
            + f"\n\n<i>{s['fiabilite']['engagement']}</i>")


def main() -> int:
    data = store.load()
    s = analyse.synthese(data)

    if s["volumes"]["decidees"] == 0 and s["volumes"]["mesurees"] == 0:
        telegram.send("<b>Revue éditoriale</b>\n\nRien à analyser ce mois : "
                      "aucune publication décidée. La revue reviendra le mois "
                      "prochain.")
        print("Rien a analyser.")
        return 0

    avis = demander(data)

    dossier = config.CONTENT / "revues"
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / (datetime.now(timezone.utc).strftime("%Y-%m") + ".md")
    chemin.write_text(rapport(data, avis), encoding="utf-8")
    print("Rapport ecrit :", chemin)

    # Les angles de la revue passent devant la veille : ils viennent de ce qui
    # a deja fonctionne, l'actualite du jour ne vaut pas mieux.
    for a in avis.get("angles", [])[:3]:
        if not a.get("texte"):
            continue
        data["ideas"].append({
            "id": store.new_id("revue-"), "source": "revue",
            "text": a["texte"], "pilier": a.get("pilier") or "pedagogie",
            "pourquoi": a.get("pourquoi", ""), "used": False,
            "created_at": store.now()})
    store.save(data)

    telegram.send(digest(avis, s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
