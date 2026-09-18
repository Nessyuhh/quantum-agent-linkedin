"""Couche de redaction, interchangeable entre Gemini et Claude.

Le choix se fait par la variable LLM_PROVIDER, ou automatiquement selon la cle
presente. Le reste de l'agent ne sait pas quel modele tourne derriere : basculer
de Gemini a Claude ne demande qu'un secret de plus et une variable.

Les noms de modeles bougent trop vite pour etre figes dans le code : les deux
fournisseurs sont interroges sur leur catalogue et on prend le plus recent
utilisable. GOOGLE_MODEL ou ANTHROPIC_MODEL permettent d'en fixer un.
"""
import json, re, urllib.request, urllib.error
from . import config

ANTHROPIC_API = "https://api.anthropic.com/v1"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"

_cache = {}


def _http(url, payload=None, headers=None, method=None, timeout=180):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 method=method or ("POST" if data else "GET"))
    req.add_header("content-type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{url.split('/')[2]} a repondu {e.code} : "
                           f"{e.read().decode()[:500]}") from None


def provider() -> str:
    choix = (config.LLM_PROVIDER or "").strip().lower()
    if choix in ("gemini", "google"):
        return "gemini"
    if choix in ("claude", "anthropic"):
        return "claude"
    if config.GOOGLE_API_KEY:
        return "gemini"
    if config.ANTHROPIC_API_KEY:
        return "claude"
    raise SystemExit("Aucune cle de redaction : definis GOOGLE_API_KEY ou "
                     "ANTHROPIC_API_KEY.")


# ---------------------------------------------------------------- Gemini

def _rang(nom: str):
    """Classe un nom de modele par numero de version, pour prendre le plus recent."""
    nombres = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)", nom)]
    return max(nombres) if nombres else 0.0


def resolve_gemini_model() -> str:
    if config.GOOGLE_MODEL:
        return config.GOOGLE_MODEL
    if "gemini" in _cache:
        return _cache["gemini"]
    modele = "gemini-2.5-flash"
    try:
        data = _http(f"{GEMINI_API}/models?pageSize=200",
                     headers={"x-goog-api-key": config.GOOGLE_API_KEY}, timeout=60)
        noms = [m["name"].split("/")[-1] for m in data.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])]
        exclus = ("lite", "embedding", "aqa", "image", "tts", "audio",
                  "vision", "exp", "preview", "learnlm")
        flash = [n for n in noms
                 if "flash" in n and not any(x in n for x in exclus)]
        if flash:
            modele = max(flash, key=_rang)
    except Exception as exc:
        print(f"[llm] catalogue Gemini illisible, repli sur {modele} : {exc}")
    _cache["gemini"] = modele
    return modele


def _ask_gemini(system: str, prompt: str, max_tokens: int, json_mode: bool) -> str:
    modele = resolve_gemini_model()
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.9},
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    out = _http(f"{GEMINI_API}/models/{modele}:generateContent", payload,
                {"x-goog-api-key": config.GOOGLE_API_KEY})
    candidats = out.get("candidates") or []
    if not candidats:
        raison = out.get("promptFeedback", {}).get("blockReason", "inconnue")
        raise RuntimeError(f"Gemini n'a rien renvoye (raison : {raison})")
    parts = candidats[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


# ---------------------------------------------------------------- Claude

def resolve_claude_model() -> str:
    if config.ANTHROPIC_MODEL:
        return config.ANTHROPIC_MODEL
    if "claude" in _cache:
        return _cache["claude"]
    modele = "claude-sonnet-4-5"
    try:
        data = _http(f"{ANTHROPIC_API}/models?limit=50",
                     headers={"x-api-key": config.ANTHROPIC_API_KEY,
                              "anthropic-version": "2023-06-01"}, timeout=60)
        ids = [m["id"] for m in data.get("data", [])]
        retenus = [i for i in ids if "haiku" not in i] or ids
        if retenus:
            modele = retenus[0]
    except Exception as exc:
        print(f"[llm] catalogue Claude illisible, repli sur {modele} : {exc}")
    _cache["claude"] = modele
    return modele


def _ask_claude(system: str, prompt: str, max_tokens: int, json_mode: bool) -> str:
    payload = {"model": resolve_claude_model(), "max_tokens": max_tokens,
               "system": system, "messages": [{"role": "user", "content": prompt}]}
    out = _http(f"{ANTHROPIC_API}/messages", payload,
                {"x-api-key": config.ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in out.get("content", []))


# ---------------------------------------------------------------- Facade

def modele_actif() -> str:
    p = provider()
    return f"{p}:{resolve_gemini_model() if p == 'gemini' else resolve_claude_model()}"


def ask(system: str, prompt: str, max_tokens: int = 2000,
        json_mode: bool = False) -> str:
    if provider() == "gemini":
        return _ask_gemini(system, prompt, max_tokens, json_mode)
    return _ask_claude(system, prompt, max_tokens, json_mode)


def ask_json(system: str, prompt: str, max_tokens: int = 2000) -> dict:
    brut = ask(system,
               prompt + "\n\nReponds UNIQUEMENT avec un objet JSON valide, sans "
                        "texte autour et sans bloc de code.",
               max_tokens, json_mode=True).strip()
    brut = re.sub(r"^```(?:json)?|```$", "", brut, flags=re.MULTILINE).strip()
    debut, fin = brut.find("{"), brut.rfind("}")
    if debut == -1 or fin == -1:
        raise ValueError(f"Reponse non JSON : {brut[:300]}")
    return json.loads(brut[debut:fin + 1])
