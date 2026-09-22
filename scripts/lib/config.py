"""Configuration centrale. Tout vient de l'environnement, rien n'est en dur."""
import os
from pathlib import Path

from . import net  # branche Python sur le trousseau macOS si truststore est la

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "brand"
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
OUT = ROOT / "out"
QUEUE = CONTENT / "queue.json"

# Redaction. LLM_PROVIDER : "gemini", "claude", ou vide pour choisir selon la
# cle presente. Les deux MODEL vides = l'agent prend le plus recent disponible.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.environ.get("GOOGLE_MODEL", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "")

LINKEDIN_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN", "")
LINKEDIN_ORG_URN = os.environ.get("LINKEDIN_ORG_URN", "")   # page entreprise, phase 4
LINKEDIN_VERSION = os.environ.get("LINKEDIN_VERSION", "202608")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

POSTS_PER_RUN = int(os.environ.get("POSTS_PER_RUN", "1"))
# Stock de publications validees a maintenir en file. Au-dela, la redaction
# quotidienne se met en veille : inutile d'accumuler des brouillons que
# Younes devra trier pour rien.
STOCK_CIBLE = int(os.environ.get("STOCK_CIBLE", "4"))

# Validation humaine systematique. Rien ne part sans un clic de Younes.
# Mettre AUTO_PUBLISH=1 un jour ouvrirait la publication automatique des
# piliers surs, mais ce n'est pas le mode choisi.
AUTO_PUBLISH = os.environ.get("AUTO_PUBLISH", "") == "1"
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"

def brand(name: str) -> str:
    p = BRAND / f"{name}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""

def require(*names):
    """Verifie qu'une variable est bien disponible, sous son nom de secret
    GitHub OU sous son nom interne.

    Le 22 septembre, la publication a echoue sur \u00ab Variables manquantes :
    LINKEDIN_ACCESS_TOKEN \u00bb alors que le secret etait bien en place : ce
    module l'expose sous le nom LINKEDIN_TOKEN, et l'ancienne version ne
    regardait que ses propres variables. Elle aurait echoue a tous les coups.
    On regarde desormais les deux, et on previent dans Telegram plutot que de
    mourir en silence dans un journal que personne ne lit.
    """
    manquantes = [n for n in names
                  if not globals().get(n) and not os.environ.get(n)]
    if not manquantes:
        return
    message = "Variables manquantes : " + ", ".join(manquantes)
    try:
        from . import telegram
        telegram.alert("\u26a0\ufe0f <b>Publication impossible</b>\n" + message
                       + "\n\nVerifie les secrets du depot GitHub.")
    except Exception:
        pass
    raise SystemExit(message)
