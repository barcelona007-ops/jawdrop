"""prueba_booking_nube.py 0.1 — UNA búsqueda de Booking desde un servidor de GitHub Actions (IP de centro de datos).
Solo comprueba si Booking responde o pide verificación. No salta nada: si hay verificación, para y lo cuenta."""
import asyncio
import booking
from playwright.async_api import async_playwright

VERSION = "0.1"
JS = """() => [...document.querySelectorAll('[data-testid="property-card"]')].slice(0,5).map(c => ({
  nombre: c.querySelector('[data-testid="title"]')?.innerText,
  precio: c.querySelector('[data-testid="price-and-discounted-price"]')?.innerText}))"""


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True)
        pg = await (await b.new_context(locale="es-ES", viewport={"width": 1280, "height": 900})).new_page()
        r = await pg.goto(booking.busqueda("Palermo, Italia", "2026-11-01", "2026-11-02"), wait_until="domcontentloaded")
        await pg.wait_for_timeout(8000)
        print("HTTP", r.status if r else None, "| título:", await pg.title())
        cuerpo = (await pg.inner_text("body"))[:300].replace("\n", " | ")
        print("inicio de la página:", cuerpo)
        cards = await pg.evaluate(JS)
        print("tarjetas:", len(cards))
        for c in cards:
            print(" -", c)
        print("RESULTADO:", "FUNCIONA" if cards else "SIN RESULTADOS (verificación o bloqueo)")
        await b.close()

asyncio.run(main())
