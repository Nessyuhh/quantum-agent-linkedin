"""Client Claude API. Deux passes : redaction puis critique."""
import json, re, urllib.request, urllib.error
from . import config

API = "https://api.anthropic.com/v1"
HEADERS_BASE = {"anthropic-version": "2023-06-01", "content-type": "application/json"}

_model_cache = None

def _req(path: str, payload=None, method="GET"):
    url = f"{API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in HEADERS_BASE.items():
        req.add_header(k, v)
    req.add_header("x-api-key", config.ANTHROPIC_API_KEY)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Claude API {e.code} : {e.read().decode()[:600]}") from None

def resolve_model() -> str:
    """Le nom des modeles bouge. On prend celui de l'env, sinon le plus recent
    que l'API expose, en evitant les modeles les plus legers."""
    global _model_cache
    if config.ANTHROPIC_MODEL:
        return config.ANTHROPIC_MODEL
    if _model_cache:
        return _model_cache
    try:
        models = _req("/models?limit=50").get("data", [])
        ids = [m["id"] for m in models]
        preferred = [i for i in ids if "haiku" not in i] or ids
        _model_cache = preferred[0]
    except Exception:
        _model_cache = "claude-sonnet-4-5"
    return _model_cache

def ask(system: str, prompt: str, max_tokens: int = 2000) -> str:
    payload = {
        "model": resolve_model(),
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    out = _req("/messages", payload, method="POST")
    return "".join(b.get("text", "") for b in out.get("content", []))

def ask_json(system: str, prompt: str, max_tokens: int = 2000) -> dict:
    raw = ask(system, prompt + "\n\nReponds UNIQUEMENT avec un objet JSON valide, "
                       "sans texte autour et sans bloc de code.", max_tokens)
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Reponse non JSON : {raw[:300]}")
    return json.loads(raw[start:end + 1])
