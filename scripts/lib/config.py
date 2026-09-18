"""Configuration centrale. Tout vient de l'environnement, rien n'est en dur."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "brand"
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
OUT = ROOT / "out"
QUEUE = CONTENT / "queue.json"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "")  # vide = resolution auto

LINKEDIN_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN", "")
LINKEDIN_ORG_URN = os.environ.get("LINKEDIN_ORG_URN", "")   # page entreprise, phase 4
LINKEDIN_VERSION = os.environ.get("LINKEDIN_VERSION", "202608")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

POSTS_PER_RUN = int(os.environ.get("POSTS_PER_RUN", "3"))
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"

def brand(name: str) -> str:
    p = BRAND / f"{name}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""

def require(*names):
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise SystemExit("Variables manquantes : " + ", ".join(missing))
