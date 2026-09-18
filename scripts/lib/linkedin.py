"""Client LinkedIn : identite, upload d'image, publication.

Produit utilise : « Share on LinkedIn » (scope w_member_social), gratuit et
self-service. La page entreprise passe par la Community Management API, qui
demande une validation manuelle : elle est prevue en phase 4 via LINKEDIN_ORG_URN.
"""
import json, time, urllib.request, urllib.error
from . import config

REST = "https://api.linkedin.com/rest"


def _headers(extra=None):
    h = {
        "Authorization": f"Bearer {config.LINKEDIN_TOKEN}",
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


def author_urn() -> str:
    if config.LINKEDIN_ORG_URN:
        return config.LINKEDIN_ORG_URN
    if config.LINKEDIN_PERSON_URN:
        return config.LINKEDIN_PERSON_URN
    return f"urn:li:person:{userinfo()['sub']}"


def upload_image(png_bytes: bytes, owner: str) -> str:
    """initializeUpload, puis PUT du binaire. Renvoie l'urn de l'image."""
    payload = json.dumps({"initializeUploadRequest": {"owner": owner}}).encode()
    data, _ = _request(f"{REST}/images?action=initializeUpload", payload, "POST",
                       _headers({"Content-Type": "application/json"}))
    value = data["value"]
    _request(value["uploadUrl"], png_bytes, "PUT",
             {"Authorization": f"Bearer {config.LINKEDIN_TOKEN}",
              "Content-Type": "application/octet-stream"}, raw=True)
    # L'upload n'est pas synchrone : on laisse LinkedIn finir le traitement.
    time.sleep(6)
    return value["image"]


def create_post(commentary: str, image_urn: str = None, alt_text: str = None) -> str:
    owner = author_urn()
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
                          _headers({"Content-Type": "application/json"}))
    return headers.get("x-restli-id") or headers.get("X-RestLi-Id", "")
