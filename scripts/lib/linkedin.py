"""Client LinkedIn : identite, upload d'image, publication.

Deux comptes, deux jetons. Le profil parle avec « Share on LinkedIn »
(w_member_social), la page avec la Community Management API
(w_organization_social), sur une application LinkedIn distincte car ce produit
ne tolere aucun autre produit a cote de lui. Chaque fonction recoit donc le
jeton de la cible visee, et rien n'est publie sous une identite par defaut.
"""
import json, time, urllib.request, urllib.error
from . import config

REST = "https://api.linkedin.com/rest"


def jeton(cible: str = "profil") -> str:
    """Chaque cible a son jeton. Aucun repli silencieux : publier sur le profil
    alors qu'on visait la page serait une surprise, pas un service."""
    if cible == "page":
        if not config.LINKEDIN_ORG_TOKEN:
            raise RuntimeError(
                "Jeton de la page manquant : le secret LINKEDIN_ORG_ACCESS_TOKEN "
                "n'est pas renseigne. La publication sur la page exige une "
                "application dediee au produit Community Management API.")
        return config.LINKEDIN_ORG_TOKEN
    return config.LINKEDIN_TOKEN


def _headers(extra=None, token=None):
    h = {
        "Authorization": f"Bearer {token or config.LINKEDIN_TOKEN}",
        "LinkedIn-Version": config.LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if extra:
        h.update(extra)
    return h


def _request(url, data=None, method="GET", headers=None, raw=False):
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or _headers()).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read()
            return (body, dict(r.headers)) if raw else (
                json.loads(body.decode()) if body else {}, dict(r.headers))
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:600]
        raise RuntimeError(f"LinkedIn {e.code} sur {url}\n{detail}") from None


def userinfo() -> dict:
    """Valide le jeton et renvoie l'identite. 'sub' est l'identifiant membre."""
    data, _ = _request("https://api.linkedin.com/v2/userinfo",
                       headers={"Authorization": f"Bearer {config.LINKEDIN_TOKEN}"})
    return data


def author_urn(cible: str = "profil") -> str:
    if cible == "page":
        if not config.LINKEDIN_ORG_URN:
            raise RuntimeError(
                "Identite de la page manquante : renseigne le secret "
                "LINKEDIN_ORG_URN, de la forme urn:li:organization:123456.")
        return config.LINKEDIN_ORG_URN
    if config.LINKEDIN_PERSON_URN:
        return config.LINKEDIN_PERSON_URN
    return f"urn:li:person:{userinfo()['sub']}"


def upload_image(png_bytes: bytes, owner: str, token: str = None) -> str:
    """initializeUpload, puis PUT du binaire. Renvoie l'urn de l'image.

    L'image appartient a celui qui publiera : une image televersee par le
    profil ne peut pas illustrer un post de la page.
    """
    token = token or config.LINKEDIN_TOKEN
    payload = json.dumps({"initializeUploadRequest": {"owner": owner}}).encode()
    data, _ = _request(f"{REST}/images?action=initializeUpload", payload, "POST",
                       _headers({"Content-Type": "application/json"}, token))
    value = data["value"]
    _request(value["uploadUrl"], png_bytes, "PUT",
             {"Authorization": f"Bearer {token}",
              "Content-Type": "application/octet-stream"}, raw=True)
    # L'upload n'est pas synchrone : on laisse LinkedIn finir le traitement.
    time.sleep(6)
    return value["image"]


def create_post(commentary: str, image_urn: str = None, alt_text: str = None,
                owner: str = None, token: str = None) -> str:
    owner = owner or author_urn()
    token = token or config.LINKEDIN_TOKEN
    body = {
        "author": owner,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                         "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if image_urn:
        media = {"id": image_urn}
        if alt_text:
            media["altText"] = alt_text[:350]
        body["content"] = {"media": media}
    _, headers = _request(f"{REST}/posts", json.dumps(body).encode(), "POST",
                          _headers({"Content-Type": "application/json"}, token))
    return headers.get("x-restli-id") or headers.get("X-RestLi-Id", "")
