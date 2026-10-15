"""Recupere le jeton de la PAGE Quantum Consulting. A lancer sur ta machine.

    python3 scripts/auth_page.py

Ce script est le jumeau de auth_linkedin.py, mais pour l'autre application :
celle de la page. Les deux ne peuvent pas cohabiter sur une meme application,
parce que w_member_social (le profil) et w_organization_social (la page) ne
vivent pas sous la meme autorisation.

A lancer le jour ou LinkedIn accorde Community Management API. Avant cet
accord, l'ecran d'autorisation refusera le scope : c'est attendu, ce n'est pas
une panne du script.

L'URL de redirection est deja declaree dans l'application :
    http://localhost:8723/callback
"""
import getpass, json, os, secrets, sys, threading, time, urllib.parse, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8723
# Le Client ID de l'application "Quantum Consulting Pages". Ce n'est pas un
# secret : il circule en clair dans chaque URL d'autorisation.
CLIENT_ID_DEFAUT = "780e3ehr7w8ufm"
REDIRECT = f"http://localhost:{PORT}/callback"
# Le seul scope indispensable pour publier au nom de la page. Si l'onglet Auth
# en affiche d'autres une fois l'accord donne, on peut les ajouter ici, separes
# par des espaces. Demander un scope non accorde fait echouer l'autorisation.
SCOPES = os.environ.get("LINKEDIN_ORG_SCOPES", "w_organization_social")

recu = {}

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    print("\n" + "!" * 70)
    print("  truststore n'est pas installe.")
    print("  Lance d'abord :  pip3 install truststore")
    print("!" * 70 + "\n")
    raise SystemExit(1)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(204)
            self.end_headers()
            return
        recu.update({k: v[0]
                     for k, v in urllib.parse.parse_qs(parsed.query).items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "<body style='font-family:system-ui;background:#0D0720;color:#E2E8F0;"
            "display:flex;align-items:center;justify-content:center;height:100vh'>"
            "<h2>Autorisation enregistree. Reviens au Terminal.</h2></body>"
            .encode())

    def log_message(self, *a):
        pass


def copier(valeur: str) -> bool:
    """Met la valeur dans le presse-papier. Rien n'est ecrit sur le disque."""
    try:
        import subprocess
        subprocess.run(["pbcopy"], input=valeur.encode(), check=True)
        return True
    except Exception:
        return False


def main() -> int:
    cid = (os.environ.get("LINKEDIN_ORG_CLIENT_ID")
           or input(f"Client ID [{CLIENT_ID_DEFAUT}] : ").strip()
           or CLIENT_ID_DEFAUT)
    secret = (os.environ.get("LINKEDIN_ORG_CLIENT_SECRET")
              or getpass.getpass("Colle le Client Secret de l'app Pages "
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
        print("Un ancien lancement tourne peut-etre encore. Ferme-le et relance.")
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
        print("Si le message parle de scope non autorise, c'est que "
              "Community Management API n'est pas encore accorde.")
        return 1
    if recu.get("state") != state:
        print("State invalide, on arrete.")
        return 1

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": recu["code"],
        "client_id": cid, "client_secret": secret,
        "redirect_uri": REDIRECT}).encode()
    req = urllib.request.Request("https://www.linkedin.com/oauth/v2/accessToken",
                                 data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=60) as r:
        token = json.loads(r.read().decode())

    jours = round(token.get("expires_in", 0) / 86400)
    print("\n" + "=" * 70)
    print(f"  Jeton de la page obtenu. Valide {jours} jours.")
    print("=" * 70)

    if copier(token["access_token"]):
        print("\nLe JETON est dans ton presse-papier.")
    else:
        print("\nJeton a copier :\n")
        print(token["access_token"])
    print("Colle-le dans le secret GitHub  LINKEDIN_ORG_ACCESS_TOKEN")
    print("puis clique Add secret.")
    print("\nAu creneau suivant, le pont s'eteint tout seul et l'agent publie "
          "directement sur la page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
