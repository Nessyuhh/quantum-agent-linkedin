"""Recupere un jeton LinkedIn de 60 jours. A lancer sur ta machine, pas dans Actions.

    python3 scripts/auth_linkedin.py

Le Client ID est propose par defaut. Le Client Secret est demande sans affichage :
il ne passe ni dans l'historique du shell, ni dans un fichier, ni nulle part ailleurs.

L'URL de redirection declaree dans l'application LinkedIn :
    http://localhost:8723/callback
"""
import getpass, json, os, secrets, sys, threading, time, urllib.parse, urllib.request, webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8723
CLIENT_ID_DEFAUT = "78n37pj2698jrb"   # le Client ID n'est pas un secret
REDIRECT = f"http://localhost:{PORT}/callback"
SCOPES = "openid profile w_member_social"
META = Path(__file__).resolve().parents[1] / "content" / "token_meta.json"

recu = {}

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    print("\n" + "!" * 70)
    print("  truststore n'est pas installe.")
    print("  Ton Mac intercepte le TLS (antivirus ou VPN), donc Python va")
    print("  refuser le certificat de LinkedIn. Lance d'abord :")
    print("\n      pip3 install truststore\n")
    print("  puis relance ce script.")
    print("!" * 70 + "\n")
    raise SystemExit(1)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            # Chrome demande /favicon.ico en arrivant : on ne s'en occupe pas.
            self.send_response(204)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        recu.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "<body style='font-family:system-ui;background:#0D0720;color:#E2E8F0;"
            "display:flex;align-items:center;justify-content:center;height:100vh'>"
            "<h2>Autorisation enregistree. Tu peux fermer cet onglet "
            "et revenir au Terminal.</h2></body>".encode())

    def log_message(self, *a):
        pass


def copier(valeur: str) -> bool:
    """Met la valeur dans le presse-papier du Mac. Rien n'est ecrit sur le disque."""
    try:
        import subprocess
        subprocess.run(["pbcopy"], input=valeur.encode(), check=True)
        return True
    except Exception:
        return False


def main() -> int:
    cid = (os.environ.get("LINKEDIN_CLIENT_ID")
           or input(f"Client ID [{CLIENT_ID_DEFAUT}] : ").strip()
           or CLIENT_ID_DEFAUT)
    secret = (os.environ.get("LINKEDIN_CLIENT_SECRET")
              or getpass.getpass("Colle le Client Secret "
                                 "(rien ne s'affiche, c'est normal) : ").strip())
    if not secret:
        print("Aucun Client Secret saisi.")
        return 1

    state = secrets.token_urlsafe(16)
    auth = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT,
        "state": state, "scope": SCOPES})

    try:
        server = HTTPServer(("localhost", PORT), Handler)
    except OSError as exc:
        print(f"Impossible d'ecouter sur le port {PORT} : {exc}")
        print("Un ancien lancement du script tourne peut-etre encore. Ferme-le, "
              "ou attends une minute, puis relance.")
        return 1
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("\nUn onglet LinkedIn va s'ouvrir : clique sur Autoriser.")
    print("Si rien ne s'ouvre, ouvre cette adresse a la main :\n" + auth + "\n")
    webbrowser.open(auth)

    print("En attente de ton autorisation dans le navigateur...")
    attente = 0
    while "code" not in recu and "error" not in recu:
        time.sleep(0.2)
        attente += 0.2
        if attente > 300:
            print("Delai depasse. Relance le script.")
            return 1
    server.shutdown()
    if "error" in recu:
        print("LinkedIn a refuse :", recu.get("error"),
              recu.get("error_description", ""))
        return 1
    if recu.get("state") != state:
        print("State invalide, on arrete.")
        return 1

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": recu["code"],
        "client_id": cid, "client_secret": secret, "redirect_uri": REDIRECT}).encode()
    req = urllib.request.Request("https://www.linkedin.com/oauth/v2/accessToken",
                                 data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=60) as r:
        token = json.loads(r.read().decode())

    me = urllib.request.Request("https://api.linkedin.com/v2/userinfo")
    me.add_header("Authorization", "Bearer " + token["access_token"])
    with urllib.request.urlopen(me, timeout=60) as r:
        info = json.loads(r.read().decode())

    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps({"issued_at": datetime.now(timezone.utc).isoformat(
        timespec="seconds"), "expires_in": token.get("expires_in")}, indent=2) + "\n")

    urn = "urn:li:person:" + info["sub"]
    jours = round(token.get("expires_in", 0) / 86400)
    prenom = info.get("given_name") or info.get("name") or "toi"

    print("\n" + "=" * 70)
    print(f"  Autorisation accordee par {prenom}. Jeton valide {jours} jours.")
    print("=" * 70)

    if copier(token["access_token"]):
        print("\n[1/2] Le JETON est dans ton presse-papier.")
        print("      Colle-le dans le secret GitHub  LINKEDIN_ACCESS_TOKEN")
        print("      puis clique Add secret.")
        input("\n      Appuie sur Entree quand c'est fait... ")
    else:
        print("\n[1/2] LINKEDIN_ACCESS_TOKEN, a copier :\n")
        print(token["access_token"])
        input("\n      Appuie sur Entree quand c'est colle sur GitHub... ")

    if copier(urn):
        print("\n[2/2] L'IDENTIFIANT est dans ton presse-papier.")
        print("      Colle-le dans le secret GitHub  LINKEDIN_PERSON_URN")
        print(f"      (sa valeur est {urn}, ce n'est pas un secret)")
    else:
        print(f"\n[2/2] LINKEDIN_PERSON_URN = {urn}")

    print("\n" + "=" * 70)
    print("  Termine. Les deux secrets posent l'agent sur ton profil.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
