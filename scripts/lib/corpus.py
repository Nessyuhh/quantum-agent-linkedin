"""Le corpus se construit tout seul : chaque publication que Younes valide
explicitement devient un exemple de reference pour les suivantes.

Deux garde-fous. On ne retient QUE les textes valides a la main, jamais ceux
partis en automatique : le clic de validation est le signal, pas la publication.
Et on plafonne le nombre d'exemples, parce qu'un modele qui s'imite trop
longtemps finit par deriver. Des exemples ecrits de la main de Younes restent
superieurs a n'importe quelle recolte automatique.
"""
from . import config

MAX_EXEMPLES = 12
MARQUEUR = "<!-- RECOLTE AUTOMATIQUE -->"


def ajouter(texte: str) -> bool:
    chemin = config.BRAND / "corpus.md"
    if not texte or not texte.strip():
        return False
    actuel = chemin.read_text(encoding="utf-8") if chemin.exists() else ""
    if texte.strip()[:120] in actuel:
        return False

    tete, _, queue = actuel.partition(MARQUEUR)
    exemples = [b.strip() for b in queue.split("\n---\n") if b.strip()]
    exemples.append(texte.strip())
    exemples = exemples[-MAX_EXEMPLES:]

    if not tete.strip():
        tete = actuel
    chemin.write_text(
        tete.rstrip() + f"\n\n{MARQUEUR}\n\n" + "\n\n---\n\n".join(exemples) + "\n",
        encoding="utf-8")
    return True
