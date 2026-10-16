"""
comprobar.py 1.0 — Comprueba UN vuelo suelto en Google Flights (SerpApi). Cuesta 1 búsqueda de las 250/mes.

Es lo único que queda para SerpApi: confirmar a mano el precio real de un vuelo que ya has elegido (por
ejemplo uno de Turkish, Pegasus o Eurowings, donde Kiwi y la aerolínea a veces no coinciden).
Todo lo demás (Ryanair, Wizz, Vueling, Kiwi, radar, países) es gratis y no pasa por aquí.

Uso:  .venv\\Scripts\\python.exe comprobar.py BCN IST 2026-11-28 [--aerolinea TK] [--gastar]
  - Sin --gastar NO busca nada: solo dice cuántas búsquedas te quedan.
  - Con --gastar hace 1 búsqueda (si ya estaba en la caché de 12 h, no gasta).
  - --aerolinea es el código de dos letras (VY, TK, PC, EW, U2...); sin él salen todas las aerolíneas.
"""
import argparse
import sys

import vueling

VERSION = "1.0"


def main():
    ap = argparse.ArgumentParser(description="Comprueba un vuelo suelto en Google Flights (1 búsqueda de SerpApi)")
    ap.add_argument("desde", help="aeropuerto de salida, p. ej. BCN")
    ap.add_argument("hasta", help="aeropuerto de llegada, p. ej. IST")
    ap.add_argument("dia", help="fecha AAAA-MM-DD")
    ap.add_argument("--aerolinea", default="", help="código de aerolínea (VY, TK, PC...); vacío = todas")
    ap.add_argument("--gastar", action="store_true", help="confirma que quieres gastar 1 búsqueda")
    a = ap.parse_args()

    try:
        usadas, total, quedan = vueling.cuota()
        print(f"SerpApi: {usadas} usadas de {total} este mes; quedan {quedan}.")
    except Exception as e:
        sys.exit(f"No se pudo consultar la cuota de SerpApi ({str(e)[:80]}). No se busca nada.")
    if not a.gastar:
        print("No se ha buscado nada. Añade --gastar para gastar 1 búsqueda.")
        return

    vueling.TOPE = 1
    p = vueling._parametros([a.desde.upper()], [a.hasta.upper()], a.dia, a.aerolinea.upper() or None)
    if not a.aerolinea:
        p.pop("include_airlines", None)
    try:
        datos = vueling._buscar(p, True)
    except vueling.SinPresupuesto as e:
        sys.exit(f"Sin presupuesto: {e}")
    nombre = a.aerolinea.upper() or "todas"
    vuelos = vueling._tramos(datos, {}, "ida", nombre)
    print(f"Búsquedas gastadas ahora: {vueling.gastadas()} (0 = estaba en la caché).")
    if not vuelos:
        print("Google no devuelve vuelos directos con esos datos.")
    for t in sorted(vuelos, key=lambda x: x["salida"]):
        print(f"  {t['vuelo'] or '?':8} {t['desde']}→{t['hasta']}  {t['salida'][11:]}→{t['llegada'][11:]}  {t['precio']:.0f} €")


if __name__ == "__main__":
    main()
