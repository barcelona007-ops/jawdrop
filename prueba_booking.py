"""prueba_booking.py 0.1 — PROTOTIPO (17-10-2026): lee las 12 primeras tarjetas de Booking con tus filtros (Playwright + Chrome a la vista, IP de casa).
Funciona desde el PC; desde GitHub Actions Booking devuelve HTTP 202 (comprobación) y no da resultados. Base del botón Hotel de Flash."""
import asyncio, json, sys
sys.path.insert(0, r"C:\escapadas_flash")
import booking
from playwright.async_api import async_playwright

CASOS = [("Turín, Italia", "2026-10-18", "2026-10-20"),
         ("Turín, Italia", "2026-10-25", "2026-10-27"),
         ("Palermo, Italia", "2026-11-01", "2026-11-02")]
OUT = "resultados"

JS = """() => [...document.querySelectorAll('[data-testid="property-card"]')].slice(0,12).map(c => ({
  nombre: c.querySelector('[data-testid="title"]')?.innerText,
  precio: c.querySelector('[data-testid="price-and-discounted-price"]')?.innerText,
  nota: c.querySelector('[data-testid="review-score"]')?.innerText,
  dist: c.querySelector('[data-testid="distance"]')?.innerText,
  hab: c.querySelector('[data-testid="recommended-units"]')?.innerText?.slice(0,120)}))"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=False)
        pg = await (await b.new_context(locale="es-ES", viewport={"width":1280,"height":900})).new_page()
        res = {}
        for ciudad, e, s in CASOS:
            url = booking.busqueda(ciudad, e, s)
            await pg.goto(url, wait_until="domcontentloaded")
            await pg.wait_for_timeout(6000)
            for t in ("Rechazar", "Reject"):
                try:
                    await pg.get_by_role("button", name=t).click(timeout=1500); break
                except Exception: pass
            await pg.wait_for_timeout(3000)
            txt = (await pg.inner_text("body"))[:400].replace("\n", " | ")
            cards = await pg.evaluate(JS)
            res[f"{ciudad} {e}->{s}"] = {"titulo": await pg.title(), "url": pg.url, "inicio": txt, "tarjetas": cards}
            await pg.screenshot(path=f"{OUT}/booking_{e}.png")
            print(ciudad, e, "tarjetas:", len(cards), "|", await pg.title(), flush=True)
            if not cards:
                print("SIN TARJETAS, paro:", txt); break
            await pg.wait_for_timeout(25000)
        json.dump(res, open(f"{OUT}/booking_res.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        await b.close()
asyncio.run(main())
