"""Veille quotidienne : remplit la banque d'angles a partir de flux RSS gratuits.

C'est ce qui permet a l'agent de tourner des le premier jour, sans attendre
que Younes ait alimente quoi que ce soit a la main.
"""
import re, sys, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from html import unescape
from lib import config, store

MAX_PAR_SOURCE = 4
MAX_RESERVE = 24
UA = "Mozilla/5.0 (compatible; QuantumConsultingVeille/1.0)"


def sources():
    chemin = config.CONTENT / "sources.txt"
    if not chemin.exists():
        return []
    return [l.strip() for l in chemin.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def nettoyer(texte: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", texte or ""))).strip()


def lire(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            racine = ET.fromstring(r.read())
    except Exception as exc:
        print(f"[veille] source ignoree {url} : {exc}")
        return []

    articles = []
    for item in list(racine.iter("item"))[:MAX_PAR_SOURCE]:
        titre = nettoyer((item.findtext("title") or ""))
        lien = (item.findtext("link") or "").strip()
        resume = nettoyer(item.findtext("description") or "")[:400]
        if titre:
            articles.append({"titre": titre, "url": lien, "resume": resume})
    if not articles:  # flux Atom
        ns = "{http://www.w3.org/2005/Atom}"
        for entree in list(racine.iter(f"{ns}entry"))[:MAX_PAR_SOURCE]:
            titre = nettoyer(entree.findtext(f"{ns}title") or "")
            lien_el = entree.find(f"{ns}link")
            lien = lien_el.get("href", "") if lien_el is not None else ""
            resume = nettoyer(entree.findtext(f"{ns}summary") or "")[:400]
            if titre:
                articles.append({"titre": titre, "url": lien, "resume": resume})
    return articles


def main() -> int:
    data = store.load()
    connus = {i.get("text", "")[:90] for i in data["ideas"]}
    connus |= {i.get("angle", "")[:90] for i in data["items"]}
    libres = len([i for i in data["ideas"] if not i.get("used")])
    ajoutes = 0

    for url in sources():
        if libres + ajoutes >= MAX_RESERVE:
            break
        for art in lire(url):
            resume = art["resume"]
            if resume[:40].lower() == art["titre"][:40].lower():
                resume = ""
            texte = art["titre"] + (f" | {resume}" if resume else "")
            if texte[:90] in connus:
                continue
            connus.add(texte[:90])
            data["ideas"].append({
                "id": store.new_id("veille-"), "source": "veille",
                "text": texte[:600], "url": art["url"],
                "used": False, "created_at": store.now()})
            ajoutes += 1

    store.save(data)
    print(f"{ajoutes} angle(s) de veille ajoute(s). Reserve : {libres + ajoutes}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
