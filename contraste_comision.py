"""
contraste_comision.py — Mide cuánto suma Kiwi sobre el precio de la web de una aerolínea (el usuario, 17-10-2026; empezando por Iberojet, E9).

Precios de la web: datos/iberojet_precios.json (E9, los apunta iberojet_mapa.py) y datos/level_precios.json (LL, level_mapa.py: un vuelo directo por fila, con su precio de la web).
Para cada ruta y mes, pide a Kiwi los vuelos directos del rango (por la caché y con la pausa normal), empareja el de la aerolínea el mismo día y ajusta
precio_kiwi = fijo + pendiente × precio_web (mínimos cuadrados). Imprime el bloque listo para pegar en `kiwi.COMISION`. No escribe nada.

Uso:  .venv\\Scripts\\python.exe contraste_comision.py [--sigla E9] [--csv] [--origenes MAD,BCN]
  --csv: usa también datos/precios_web.csv (sigla,origen,destino,fecha,precio_web) para precios apuntados a mano.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import kiwi

CARPETA = Path(__file__).resolve().parent / "datos"
IBEROJET = CARPETA / "iberojet_precios.json"
LEVEL = CARPETA / "level_precios.json"   # level_mapa.py: precio de ida suelta, tarifa Economy Light
CSV = CARPETA / "precios_web.csv"


def ajustar(pares):
    """Mínimos cuadrados precio_kiwi = fijo + pendiente × web. Con un solo precio distinto de web, pendiente 1 y fijo = diferencia media."""
    n = len(pares)
    mx, my = sum(w for w, _ in pares) / n, sum(k for _, k in pares) / n
    sxx = sum((w - mx) ** 2 for w, _ in pares)
    if sxx < 1e-9:
        return my - mx, 1.0
    pend = sum((w - mx) * (k - my) for w, k in pares) / sxx
    return my - pend * mx, pend


def vuelos_web(sigla, usar_csv, origenes):
    """[(origen, destino, 'AAAA-MM-DD', precio_web)] desde el JSON de iberojet_mapa.py (y el CSV si se pide)."""
    out = []
    if sigla == "E9" and IBEROJET.exists():
        out += [(v["origen"], v["destino"], v["fecha"], float(v["precio"])) for v in json.loads(IBEROJET.read_text(encoding="utf-8"))["vuelos"].values()]
    if sigla == "LL" and LEVEL.exists():
        out += [(v["origen"], v["destino"], v["fecha"], float(v["precio"])) for v in json.loads(LEVEL.read_text(encoding="utf-8"))["vuelos"].values()]
    if usar_csv and CSV.exists():
        out += [(f["origen"], f["destino"], f["fecha"], float(f["precio_web"].replace(",", "."))) for f in csv.DictReader(CSV.open(encoding="utf-8")) if f["sigla"] == sigla]
    if origenes:
        out = [v for v in out if v[0] in origenes or v[1] in origenes]   # ida desde un origen o vuelta hasta él
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigla", default="E9")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--origenes", default="")
    a = ap.parse_args()
    web = vuelos_web(a.sigla, a.csv, [o for o in a.origenes.split(",") if o])
    hoy = date.today().isoformat()
    grupos = defaultdict(dict)   # (origen, destino, mes) -> {fecha: precio_web}
    for o, d, f, p in web:
        if f >= hoy:
            grupos[(o, d, f[:7])][f] = p
    pares, sin_kiwi, por_ruta = [], 0, defaultdict(list)
    for (o, d, mes), dias in sorted(grupos.items()):
        desde, hasta = min(dias), max(dias)
        try:
            its = kiwi.rango([f"Airport:{o}"], [f"Airport:{d}"], desde, hasta, excluir=())
        except kiwi.KiwiBloqueado as e:
            print(f"{o}-{d} {mes}: Kiwi falla ({str(e)[:60]})")
            continue
        k_por_dia = {t["salida"][:10]: t["precio_kiwi"] for t in its if t["sigla"] == a.sigla and t["desde"] == o and t["hasta"] == d}
        for f, w in dias.items():
            if f in k_por_dia:
                pares.append((w, k_por_dia[f]))
                por_ruta[f"{o}-{d}"].append((w, k_por_dia[f]))
            else:
                sin_kiwi += 1
        print(f"{o}-{d} {mes}: {sum(f in k_por_dia for f in dias)}/{len(dias)} con Kiwi", flush=True)
    print(f"\n{len(pares)} pares web-Kiwi ({sin_kiwi} vuelos de la web que Kiwi no trae).")
    if len(pares) < 5:
        return
    fijo, pend = ajustar(pares)
    err = [k - (fijo + pend * w) for w, k in pares]
    print(f"Con UNA fórmula para toda la aerolínea: error máx {max(abs(e) for e in err):.0f} € (si es grande, la comisión depende de la ruta).")
    print("Una recta por ruta (para pegar en `kiwi.COMISION`; margen = error que no supera el 90 % de los vuelos):")
    for ruta, v in sorted(por_ruta.items()):
        if len(v) < 8:
            continue
        f, p = ajustar(v)
        e = sorted(abs(k - (f + p * w)) for w, k in v)
        print(f'    "{a.sigla} {ruta}": {{"fijo": {f:.1f}, "pendiente": {p:.3f}, "margen": {max(round(e[int(len(e) * 0.9)]), 1)}, "medido": "{len(v)} vuelos, {hoy}"}},')


if __name__ == "__main__":
    main()
