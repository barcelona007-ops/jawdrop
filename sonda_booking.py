import asyncio, json, sys
sys.path.insert(0, r"C:\escapadas_flash")
import booking
from playwright.async_api import async_playwright
OUT = r"C:\escapadas_flash\resultados\booking_red.json"
async def main():
    vistas = []
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=False)
        pg = await (await b.new_context(locale="es-ES", viewport={"width":1280,"height":900})).new_page()
        async def alv(r):
            try:
                ct = r.headers.get("content-type", "")
                if r.request.resource_type in ("xhr", "fetch") or "json" in ct:
                    t = await r.text()
                    vistas.append({"url": r.url[:300], "metodo": r.request.method, "estado": r.status, "tipo": ct[:40], "tam": len(t),
                                   "post": (r.request.post_data or "")[:1500], "cuerpo": t[:3000]})
            except Exception: pass
        pg.on("response", alv)
        await pg.goto(booking.busqueda("Turín, Italia", "2026-10-25", "2026-10-27"), wait_until="domcontentloaded")
        await pg.wait_for_timeout(7000)
        for t in ("Rechazar", "Reject"):
            try: await pg.get_by_role("button", name=t).click(timeout=1500); break
            except Exception: pass
        await pg.wait_for_timeout(5000)
        print("titulo:", await pg.title(), "| tarjetas:", await pg.locator('[data-testid="property-card"]').count())
        open("C:/escapadas_flash/resultados/booking_pagina.html", "w", encoding="utf-8").write(await pg.content())
        await b.close()
    json.dump(vistas, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for v in vistas: print(v["metodo"], v["estado"], v["tam"], v["url"][:140])
asyncio.run(main())
