"""Le jeton LinkedIn expire au bout de 60 jours et il n'existe pas de jeton de
rafraichissement sans partenariat Marketing. C'est la premiere cause de mort
silencieuse de ce genre d'agent, donc on surveille."""
import json, sys
from datetime import datetime, timezone
from lib import config, telegram, linkedin

META = config.CONTENT / "token_meta.json"


def main() -> int:
    jours = None
    if META.exists():
        issued = json.loads(META.read_text())["issued_at"]
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(issued)).days
        jours = 60 - age

    try:
        info = linkedin.userinfo()
        valide = bool(info.get("sub"))
    except Exception as exc:
        telegram.alert("Le jeton LinkedIn ne repond plus.\n"
                       f"<code>{str(exc)[:300]}</code>\n"
                       "Relance <code>python3 scripts/auth_linkedin.py</code> puis mets a jour "
                       "le secret LINKEDIN_ACCESS_TOKEN sur GitHub.")
        return 1

    if valide and jours is not None and jours <= 10:
        telegram.alert(f"Le jeton LinkedIn expire dans {jours} jour(s).\n"
                       "Relance <code>python3 scripts/auth_linkedin.py</code> puis mets a jour "
                       "le secret LINKEDIN_ACCESS_TOKEN sur GitHub. Deux minutes.")
    print(f"Jeton valide. Jours restants estimes : {jours}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
