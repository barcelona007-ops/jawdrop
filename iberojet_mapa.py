"""
iberojet_mapa.py — Lee los precios por trayecto de Iberojet (E9) para los próximos 12 meses (el usuario, 17-10-2026) y los guarda en datos/iberojet_precios.json.

Abre TU Chrome (Playwright, canal «chrome») y hace lo que haría una persona: entra en el enlace de búsqueda de iberojet.com, acepta las cookies
y mira el calendario de cada ruta y mes. Cada búsqueda trae a la vez el calendario de ida y el de vuelta; solo se guarda lo que la web carga sola.
Despacio (PAUSA entre búsquedas) y se para si no llega ningún precio varias veces seguidas (bloqueo o captcha). No esquiva nada.
Para qué: medir lo que suma Kiwi sobre el precio de la web (contraste_comision.py) y, con esa fórmula, no depender de este PC. Playwright: pip install playwright.

Uso:  .venv\\Scripts\\python.exe iberojet_mapa.py [--origenes MAD,BCN] [--meses 12] [--pausa 6]
"""
import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

VERSION = "0.3"
ALMACEN = Path(__file__).resolve().parent / "datos" / "iberojet_precios.json"
BASE = "https://www.iberojet.com/es"
SEGUIDAS_VACIAS = 4   # búsquedas seguidas SIN respuesta de precios = paro (posible bloqueo)
MESES_CERRADOS = 2    # meses seguidos sin precio en una ruta = el plazo de venta aún no está abierto: se salta el resto de esa ruta


def url_busqueda(origen, destino, ida):
    return (f"{BASE}/select?showCalendar=true&origin={origen}&destination={destino}&departure={ida}T00:00:00&arrival={ida + timedelta(days=7)}T00:00:00"
            "&adults=1&children=0&infants=0&currency=EUR&promotionalCode=")


def primeros_de_mes(n):
    """Un día de ida por cada uno de los n próximos meses (el 15, o dentro de 3 días en el mes actual)."""
    hoy = date.today()
    for i in range(n):
        m = hoy.month - 1 + i
        d = date(hoy.year + m // 12, m % 12 + 1, 15)
        yield max(d, hoy + timedelta(days=3)) if i == 0 else d


async def leer_mes(pg, origen, destino, ida, pausa):
    """Una búsqueda: devuelve (filas de ida y vuelta, nº de respuestas de precios)."""
    precios, publica = [], {}

    async def alv(r):
        try:
            if "/api/fare-quotes?" in r.url:
                precios.append(json.loads(await r.text())["data"])
            elif "/api/fare-quotes/public" in r.url:
                for x in json.loads(await r.text())["data"]:
                    publica[x["date"]] = (x["origin"], x["destination"])
        except Exception:
            pass

    pg.on("response", alv)
    try:
        await pg.goto(url_busqueda(origen, destino, ida), wait_until="domcontentloaded", timeout=40000)
        for _ in range(int(20 / 1)):   # hasta 20 s por las dos respuestas de precios y la lista pública
            if len(precios) >= 2 and publica:
                break
            await asyncio.sleep(1)
    finally:
        pg.remove_listener("response", alv)
    filas = []
    for lista in precios:
        for x in lista:
            o, d = publica.get(x["departureDate"], (None, None))
            if o:
                filas.append({"origen": o, "destino": d, "fecha": x["departureDate"][:10], "hora": x["departureDate"][11:16], "vuelo": x["flightNumber"],
                              "precio": x["lowestFarePriceWithTax"], "tarifa": x["fareTypeName"]})
    await asyncio.sleep(pausa)
    return filas, len(precios)


async def main(origenes, meses, pausa):
    guardado = json.loads(ALMACEN.read_text(encoding="utf-8")) if ALMACEN.exists() else {"vuelos": {}}
    ahora = datetime.now().isoformat(timespec="minutes")
    vacias = 0
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome" if sys.platform == "win32" else None, headless=False)  # en la Raspberry (Linux) usa el Chromium de Playwright
        pg = await b.new_page(viewport={"width": 1280, "height": 1000})
        rutas = []
        pg.on("response", lambda r: None)
        # La red de rutas la da la propia web al abrir la portada (/api/flights)
        red = {}

        async def alv_red(r):
            if "/front-api/api/flights?" in r.url:
                try:
                    for o in json.loads(await r.text())["data"]:
                        red[o["airportCode"]] = [x["destinationAirportCode"] for x in o["destinations"]]
                except Exception:
                    pass

        pg.on("response", alv_red)
        await pg.goto(BASE, wait_until="domcontentloaded", timeout=40000)
        try:
            await pg.locator("#onetrust-accept-btn-handler").click(timeout=10000)
        except Exception:
            pass
        for _ in range(20):
            if red:
                break
            await asyncio.sleep(1)
        pg.remove_listener("response", alv_red)
        rutas = [(o, d) for o in origenes for d in red.get(o, [])]
        print(f"{len(rutas)} rutas × {meses} meses = {len(rutas) * meses} búsquedas", flush=True)
        for o, d in rutas:
            sin_precio = 0   # meses seguidos sin precio en esta ruta: aún no venden esas fechas (no es un bloqueo)
            for ida in primeros_de_mes(meses):
                if sin_precio >= MESES_CERRADOS:
                    break
                filas, n = await leer_mes(pg, o, d, ida, pausa)
                sin_precio = 0 if filas else sin_precio + 1
                vacias = vacias + 1 if n < 2 else 0   # bloqueo = la web ni responde con precios; un mes vacío con respuesta es normal
                for f in filas:
                    clave = f"{f['origen']}-{f['destino']} {f['fecha']} {f['hora']}"
                    ant = guardado["vuelos"].get(clave)
                    hist = (ant or {}).get("historial") or ([[ant["leido"], ant["precio"]]] if ant else [])
                    if not hist or hist[-1][1] != f["precio"]:
                        hist.append([ahora, f["precio"]])   # historial: solo se apunta cuando el precio cambia (el usuario, 17-10-2026: predecir cuándo suben)
                    guardado["vuelos"][clave] = {**f, "leido": ahora, "historial": hist}
                print(f"{o}-{d} {ida:%Y-%m}: {len(filas)} precios ({n} respuestas)", flush=True)
                if vacias >= SEGUIDAS_VACIAS:
                    print("Paro: varias búsquedas seguidas sin precios (¿bloqueo o captcha?). Mira la ventana de Chrome.")
                    ALMACEN.write_text(json.dumps(guardado, ensure_ascii=False, indent=0), encoding="utf-8")
                    await b.close()
                    return
            ALMACEN.write_text(json.dumps(guardado, ensure_ascii=False, indent=0), encoding="utf-8")   # guarda tras cada ruta
        await b.close()
    print(f"{len(guardado['vuelos'])} vuelos con precio en {ALMACEN.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--origenes", default="MAD,BCN")
    ap.add_argument("--meses", type=int, default=12)
    ap.add_argument("--pausa", type=float, default=6)
    a = ap.parse_args()
    asyncio.run(main(a.origenes.split(","), a.meses, a.pausa))
