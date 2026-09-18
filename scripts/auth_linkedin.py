"""Recupere un jeton LinkedIn de 60 jours. A lancer sur ta machine, pas dans Actions.

    export LINKEDIN_CLIENT_ID=...
    export LINKEDIN_CLIENT_SECRET=...
    python3 scripts/auth_linkedin.py

L'URL de redirection a declarer dans l'application LinkedIn :
    http://localhost:8723/callback
"""
import json, os, secrets, sys, threading, urllib.parse, urllib.request, webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8723
REDIRECT = f"http://localhost:{PORT}/callback"
SCOPES = "openid profile w_member_social"
META = Path(__file__).resolve().parents[1] / "content" / "token_meta.json"

recu = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        recu.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>C'est bon, tu peux fermer cet onglet.</h2>".encode())

    def log_message(self, *a):
        pass


def main() -> int:
    cid = os.environ.get("LINKEDIN_CLIENT_ID")
    secret = os.environ.get("LINKEDIN_CLIENT_SECRET")
    if not cid or not secret:
        print("Definis LINKEDIN_CLIENT_ID et LINKEDIN_CLIENT_SECRET.")
        return 1

    state = secrets.token_urlsafe(16)
    auth = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT,
        "state": state, "scope": SCOPES})

    server = HTTPServer(("localhost", PORT), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    print("Ouverture du navigateur. Si rien ne s'ouvre, colle cette URL :\n" + auth)
    webbrowser.open(auth)

    while "code" not in recu and "error" not in recu:
        pass
    if "error" in recu:
        print("Refus LinkedIn :", recu)
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

    print("\n" + "=" * 70)
    print("LINKEDIN_ACCESS_TOKEN =\n" + token["access_token"])
    print("\nLINKEDIN_PERSON_URN =\nurn:li:person:" + info["sub"])
    print(f"\nValide {round(token.get('expires_in', 0)/86400)} jours.")
    print("Colle ces deux valeurs dans les secrets GitHub du depot.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
