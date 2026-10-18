r"""booking_json.py 0.1 — Lee los resultados de Booking del JSON que la propia página lleva dentro (17-10-2026). PROTOTIPO.

Chrome a la vista y desde tu IP de casa (como prueba_booking.py). Una búsqueda = una página; se quedan los `n` primeros (por defecto 5, orden por precio).
No esquiva nada: la comprobación AWS WAF la pasa el Chrome normal; si no hay resultados, se para.
Uso:  .venv\Scripts\python.exe booking_json.py "Turín, Italia" 2026-10-25 2026-10-27 [--filtros "texto nflt"] [--n 5]
"""
import argparse
import asyncio
import html
import json
import re
import sys

from playwright.async_api import async_playwright

import booking

VERSION = "0.1"


def _propiedades(o):
    if isinstance(o, dict):
        if "priceDisplayInfoIrene" in o:
            yield o
        for v in o.values():
            yield from _propiedades(v)
    elif isinstance(o, list):
        for v in o:
            yield from _propiedades(v)


def _filtro_banos(o):
    """Opciones del contador «Baños» de la página: {mínimo: nº de alojamientos}."""
    if isinstance(o, dict):
        if o.get("field") == "unit_config_grouped" and str(o.get("urlId", "")).startswith("min_bathrooms="):
            yield o["id"], o["count"]
        for v in o.values():
            yield from _filtro_banos(v)
    elif isinstance(o, list):
        for v in o:
            yield from _filtro_banos(v)


def extraer(pagina_html, n=5):
    """(alojamientos, {mín. baños: cuántos}) a partir del HTML de resultados."""
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", pagina_html, re.S):
        if "priceDisplayInfoIrene" in m.group(1):
            d = json.loads(html.unescape(m.group(1)) if m.group(1).lstrip().startswith("&") else m.group(1))
            break
    else:
        return [], {}
    res = []
    for p in _propiedades(d):
        b, pr = p["basicPropertyData"], p["priceDisplayInfoIrene"]["displayPrice"]["amountPerStay"]
        u = (p.get("matchingUnitConfigurations") or {}).get("unitConfigurations") or [{}]
        bl = (p.get("blocks") or [{}])[0]
        res.append({"id": b["id"], "nombre": p["displayName"]["text"], "precio": round(pr["amountUnformatted"], 2),
                    "nota": b["reviews"]["totalScore"], "resenas": b["reviews"]["reviewsCount"],
                    "distancia": p["location"]["mainDistance"], "lat": b["location"]["latitude"], "lon": b["location"]["longitude"],
                    "habitacion": u[0].get("name"), "banos_ficha": u[0].get("nbBathrooms"),   # 0 = la ficha no lo dice
                    "cancela_gratis_hasta": bl.get("freeCancellationUntil"), "desayuno": bool(p.get("mealPlanIncluded")),
                    "quedan": (bl.get("onlyXLeftMessage") or {}).get("translation")})
    return res[:n], dict(sorted(set(_filtro_banos(d))))


async def buscar(ciudad, entrada, salida, filtros=booking.FILTROS, n=5, pg=None):
    """Una búsqueda. Devuelve (alojamientos, contador de baños). Reutiliza `pg` si se le pasa (varias búsquedas con pausa)."""
    async def _hacer(pg):
        await pg.goto(booking.busqueda(ciudad, entrada, salida, filtros=filtros), wait_until="domcontentloaded")
        await pg.wait_for_selector('[data-testid="property-card"]', timeout=30000)
        return extraer(await pg.content(), n)
    if pg:
        return await _hacer(pg)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=False)
        try:
            return await _hacer(await (await b.new_context(locale="es-ES", viewport={"width": 1280, "height": 900})).new_page())
        finally:
            await b.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ciudad"); ap.add_argument("entrada"); ap.add_argument("salida")
    ap.add_argument("--filtros", default=booking.FILTROS); ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()
    aloj, banos = asyncio.run(buscar(a.ciudad, a.entrada, a.salida, a.filtros, a.n))
    sys.stdout.reconfigure(encoding="utf-8")
    print("Baños (mínimo: alojamientos):", banos)
    for x in aloj:
        print(f'{x["precio"]:>7.2f} € | {x["nota"]} ({x["resenas"]}) | {x["distancia"]} | {x["nombre"]} | {x["habitacion"]} | baños ficha {x["banos_ficha"]}')
