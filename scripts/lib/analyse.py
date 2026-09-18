"""Lecture des signaux : ce que Younes valide, et ce que l'audience fait.

Deux sources, aucune API payante :

1. Les décisions prises dans Telegram. Validé, modifié, refusé : c'est le
   signal le plus honnête sur la justesse du ton, et il est disponible dès
   la première semaine.
2. Les chiffres relevés à la main une fois par mois (/stats dans Telegram).
   LinkedIn ne donne les statistiques d'un profil personnel qu'à une
   application dédiée ; une minute de saisie par mois remplace ce détour.

Ce module ne calcule que des rapports simples et dit toujours sur combien de
publications il s'appuie. Un taux sur trois publications n'est pas un
enseignement, c'est une anecdote, et la synthèse le précise.
"""
from collections import defaultdict

DECISIONS = ("approved", "published", "rejected", "pending")
SEUIL_FIABLE = 6          # en dessous, on parle d'indice, pas de tendance


def publiees(items):
    return [i for i in items if i.get("status") == "published"]


def decidees(items):
    """Les publications sur lesquelles Younes s'est prononcé."""
    return [i for i in items
            if i.get("status") in ("approved", "published", "rejected")]


def mesurees(items):
    return [i for i in items if (i.get("mesures") or {}).get("vues")]


def _bucket(items, cle):
    groupes = defaultdict(list)
    for it in items:
        groupes[it.get(cle) or "inconnu"].append(it)
    return groupes


def par_dimension(items, cle):
    """Décisions réparties selon une dimension : pilier, gabarit, source."""
    out = {}
    for nom, lot in _bucket(decidees(items), cle).items():
        retenues = [i for i in lot if i.get("status") in ("approved", "published")]
        modifiees = [i for i in lot if i.get("editions")]
        out[nom] = {
            "total": len(lot),
            "retenues": len(retenues),
            "refusees": len(lot) - len(retenues),
            "modifiees": len(modifiees),
            "taux_retenu": round(len(retenues) / len(lot), 2) if lot else 0.0,
            "taux_modifie": round(len(modifiees) / len(lot), 2) if lot else 0.0,
        }
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["total"]))


def engagement(items, cle=None):
    """Vues, réactions, commentaires. Le taux rapporte les deux au nombre de vues."""
    lot = mesurees(items)
    if cle:
        return {nom: engagement(sous)
                for nom, sous in _bucket(lot, cle).items()}
    vues = sum(i["mesures"]["vues"] for i in lot)
    reac = sum(i["mesures"].get("reactions", 0) for i in lot)
    comm = sum(i["mesures"].get("commentaires", 0) for i in lot)
    return {
        "publications": len(lot),
        "vues": vues,
        "reactions": reac,
        "commentaires": comm,
        "vues_moyennes": round(vues / len(lot)) if lot else 0,
        "taux": round((reac + comm) / vues, 4) if vues else 0.0,
    }


def classement(items, limite=3):
    """Les publications qui ont porté, et celles qui sont tombées à plat."""
    lot = sorted(mesurees(items),
                 key=lambda i: (i["mesures"].get("reactions", 0)
                                + i["mesures"].get("commentaires", 0))
                 / max(i["mesures"]["vues"], 1),
                 reverse=True)
    resume = lambda i: {
        "id": i["id"], "pilier": i.get("pilier"), "gabarit": i.get("gabarit"),
        "source": i.get("source"), "angle": (i.get("angle") or "")[:120],
        "extrait": (i.get("texte") or "").split("\n")[0][:140],
        "vues": i["mesures"]["vues"],
        "reactions": i["mesures"].get("reactions", 0),
        "commentaires": i["mesures"].get("commentaires", 0),
    }
    return {"tete": [resume(i) for i in lot[:limite]],
            "queue": [resume(i) for i in lot[-limite:][::-1]] if len(lot) > limite else []}


def consignes_de_modification(items, limite=15):
    """Ce que Younes a demandé de changer : le signal qualitatif le plus riche.

    Une consigne qui revient trois fois n'est pas une correction, c'est une
    règle éditoriale manquante dans brand/voix.md.
    """
    out = []
    for it in items:
        for c in it.get("editions", []):
            out.append({"id": it["id"], "pilier": it.get("pilier"),
                        "gabarit": it.get("gabarit"), "consigne": c})
    return out[-limite:]


def angles_restants(data):
    return len([i for i in data.get("ideas", []) if not i.get("used")])


def fiabilite(n) -> str:
    if n == 0:
        return "aucune donnée"
    if n < SEUIL_FIABLE:
        return f"indice sur {n} publication(s), pas encore une tendance"
    return f"tendance sur {n} publications"


def synthese(data) -> dict:
    items = data.get("items", [])
    return {
        "volumes": {
            "total": len(items),
            "publiees": len(publiees(items)),
            "decidees": len(decidees(items)),
            "mesurees": len(mesurees(items)),
            "angles_en_reserve": angles_restants(data),
        },
        "decisions": {
            "pilier": par_dimension(items, "pilier"),
            "gabarit": par_dimension(items, "gabarit"),
            "source": par_dimension(items, "source"),
        },
        "engagement": {
            "global": engagement(items),
            "pilier": engagement(items, "pilier"),
            "gabarit": engagement(items, "gabarit"),
            "source": engagement(items, "source"),
        },
        "classement": classement(items),
        "consignes": consignes_de_modification(items),
        "fiabilite": {
            "decisions": fiabilite(len(decidees(items))),
            "engagement": fiabilite(len(mesurees(items))),
        },
    }
