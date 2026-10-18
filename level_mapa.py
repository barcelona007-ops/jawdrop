"""
level_mapa.py — Pasa un volcado de precios de Level (LL) a datos/level_precios.json, con historial (el usuario, 17-10-2026).

Por qué no se lee solo, como Iberojet: la web de Level (flylevel.com) tiene un antibot (Akamai) que devuelve «403 Access Denied» al Chrome de Playwright.
No se esquiva. Una persona, o el navegador de la app de Claude, SÍ puede: abre flylevel.com, pega `level_lectura.js` en la consola y copia el resultado
a datos/level_volcado.txt. La web enseña el mismo calendario (/nwe/flights/api/calendar, «solo ida»): el precio de un día es la tarifa Economy Light
(sin equipaje) de ida suelta, con tasas (BCN-JFK 9-ene-2027 = 354,99 € = 355 € del calendario).

Formato del volcado: línea «#leido AAAA-MM-DDTHH:MM», y por cada ruta una línea «BCN-JFK» seguida de «AAMMDD=precio,AAMMDD=precio,…».
Uso:  .venv/Scripts/python.exe level_mapa.py [volcado]      (por defecto datos/level_volcado.txt; se puede repetir: el historial solo apunta cambios)
Siguiente paso: contraste_comision.py --sigla LL
"""
import json
import sys
from pathlib import Path

VERSION = "0.2"
CARPETA = Path(__file__).resolve().parent / "datos"
ALMACEN = CARPETA / "level_precios.json"


def main(volcado):
    guardado = json.loads(ALMACEN.read_text(encoding="utf-8")) if ALMACEN.exists() else {"vuelos": {}}
    leido, ruta, nuevos, cambios = "", "", 0, 0
    for linea in Path(volcado).read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("#leido"):
            leido = linea.split()[1]
        elif "=" not in linea:
            ruta = linea
        elif linea:
            o, d = ruta.split("-")
            for par in linea.split(","):
                f, precio = par.split("=")
                fecha, precio = f"20{f[:2]}-{f[2:4]}-{f[4:]}", float(precio)
                clave = f"{o}-{d} {fecha}"
                ant = guardado["vuelos"].get(clave)
                hist = (ant or {}).get("historial") or []
                if not hist or hist[-1][1] != precio:
                    hist.append([leido, precio])   # historial: solo cuando el precio cambia
                    cambios += bool(ant)
                nuevos += not ant
                guardado["vuelos"][clave] = {"origen": o, "destino": d, "fecha": fecha, "precio": precio, "tarifa": "LIGHT", "leido": leido, "historial": hist}
    ALMACEN.write_text(json.dumps(guardado, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(guardado['vuelos'])} vuelos en {ALMACEN.name} ({nuevos} nuevos, {cambios} con precio cambiado)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CARPETA / "level_volcado.txt")
