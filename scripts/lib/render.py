"""Rendu d'un gabarit HTML en PNG 1200x1200 avec Chromium (Playwright)."""
import html as _html, re
from pathlib import Path
from . import config

GABARITS = {"A": "gabarit-a.html", "B": "gabarit-b.html", "C": "gabarit-c.html"}


def esc(value: str) -> str:
    return _html.escape(str(value), quote=False)


def steps_html(steps, dashed_first=False) -> str:
    """steps : [{'nom': 'Mail recu', 'temps': 'J+0'}, ...] -> boites + liens."""
    parts = []
    for i, s in enumerate(steps):
        if i:
            parts.append('<div class="link"></div>')
        parts.append(
            f'<div class="box"><span class="n">{esc(s["nom"])}</span>'
            f'<span class="t">{esc(s["temps"])}</span></div>')
    return "".join(parts)


def fill(gabarit: str, values: dict) -> str:
    src = (config.TEMPLATES / GABARITS[gabarit]).read_text(encoding="utf-8")
    css = (config.TEMPLATES / "_base.css").read_text(encoding="utf-8")
    fitjs = (config.TEMPLATES / "_fit.js").read_text(encoding="utf-8")
    src = src.replace('<link rel="stylesheet" href="_base.css">',
                      f"<style>{css}</style>")
    src = src.replace('<script src="_fit.js"></script>', f"<script>{fitjs}</script>")
    for key, val in values.items():
        src = src.replace("{{" + key + "}}", str(val))
    src = re.sub(r"\{\{[A-Z_]+\}\}", "", src)
    return src


def to_png(html_str: str, out_path: Path) -> Path:
    from playwright.sync_api import sync_playwright
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".html")
    tmp.write_text(html_str, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 1200},
                                device_scale_factor=1)
        page.goto(tmp.as_uri())
        try:
            page.wait_for_function("document.fonts.ready.then(() => true)", timeout=15000)
            page.wait_for_function("window.__fitDone === true", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(800)
        page.screenshot(path=str(out_path), clip={"x": 0, "y": 0,
                                                  "width": 1200, "height": 1200})
        browser.close()
    return out_path


def build(gabarit: str, visual: dict, out_path: Path) -> Path:
    values = dict(visual)
    if gabarit == "B":
        values["BEFORE_STEPS"] = steps_html(visual.get("before_steps", []))
        values["AFTER_STEPS"] = steps_html(visual.get("after_steps", []))
        values.pop("before_steps", None)
        values.pop("after_steps", None)
    return to_png(fill(gabarit, values), out_path)
