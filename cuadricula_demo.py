"""
cuadricula_demo.py 0.1 — Datos de EJEMPLO para la cuadrícula país × mes (rediseño de Países, 14-10-2026).

Escribe movil/cuadricula.json con precios INVENTADOS (ida + vuelta, 1 adulto) para TODOS los países del mapa (la app esconde los que el usuario ya ha visitado), por código, y el color con el semáforo real (semaforo.py: horas de vuelo y topes de precio).
Sirve para probar el diseño de movil/cuadricula.html. Cuando haya datos reales (radar.json / nube), el mismo
formato se rellena con ellos: cada celda lleva `p` (precio), `f` (fecha de la lectura) y `e` (True = estimado).

Uso:  python cuadricula_demo.py
"""
import json
import random
from datetime import date
from pathlib import Path

import semaforo

VERSION = "0.3"
SALIDA = Path(__file__).resolve().parent / "movil" / "cuadricula.json"

MAPA = Path(__file__).resolve().parent / "movil" / "mapa.json"
# Territorios sin vuelos comerciales o que no son países para viajar: se dejan fuera de la cuadrícula. (AD, LI, MC, SM y VA SÍ entran desde el 17-10-2026: se llega por el país vecino, ver radar_datos.VIA_VECINO)
FUERA = {"ES", "AQ", "TF", "GS", "HM", "BV", "UM", "PN", "TK", "NU", "CK", "NF", "CX", "CC",
         "SJ", "AX", "BL", "MF", "SH", "FK", "PM", "WF", "AS", "GU", "MP", "VI", "VG", "AI", "MS", "TC", "KY", "BM", "AW", "CW", "SX", "BQ",
         "AD", "PS", "EH", "IO"}   # fuera por decisión del usuario (21-10-2026): Andorra (se va en coche), Palestina y Sáhara Occidental (no se cuentan como país), Diego García (sin acceso)


def centro(ruta):
    """(lat, lon) aproximado de un país: centro de su silueta en mapa.json (x = longitud, y = −latitud)."""
    import re
    n = [float(v) for v in re.findall(r"-?\d+\.?\d*", ruta)]
    # el trazo mezcla órdenes relativos (minúscula) y absolutos: se recorre el trazo acumulando posiciones
    x = y = 0.0
    partes = []          # una silueta por cada trazo que empieza con M/m
    xs, ys = [], []
    for cmd, args in re.findall(r"([MmLlHhVvCcSsQqTtZz])([^MmLlHhVvCcSsQqTtZz]*)", ruta):
        v = [float(t) for t in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", args)]
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M" and xs:
            partes.append((xs, ys)); xs, ys = [], []
        if c == "M" or c == "L" or c == "T":
            for i in range(0, len(v) - 1, 2):
                x, y = (x + v[i], y + v[i + 1]) if rel else (v[i], v[i + 1]); xs.append(x); ys.append(y)
        elif c == "H":
            for t in v:
                x = x + t if rel else t; xs.append(x)
        elif c == "V":
            for t in v:
                y = y + t if rel else t; ys.append(y)
        elif c in "CSQ":
            k = {"C": 6, "S": 4, "Q": 4}[c]
            for i in range(0, len(v) - k + 1, k):
                x, y = (x + v[i + k - 2], y + v[i + k - 1]) if rel else (v[i + k - 2], v[i + k - 1]); xs.append(x); ys.append(y)
    partes.append((xs, ys))
    xs, ys = max((p for p in partes if p[0] and p[1]), key=lambda p: (max(p[0]) - min(p[0])) * (max(p[1]) - min(p[1])))
    return -(min(ys) + max(ys)) / 2, (min(xs) + max(xs)) / 2


# Países enormes: el centro del mapa no es donde se aterriza; se usa su aeropuerto grande más cercano a Europa
GRANDES = {"US": (40.64, -73.78), "CA": (43.68, -79.62), "RU": (55.97, 37.41), "BR": (-23.43, -46.47), "AU": (-33.94, 151.18),
           "CN": (40.08, 116.58), "IN": (28.56, 77.1), "MX": (19.44, -99.07), "AR": (-34.82, -58.54), "CL": (-33.39, -70.79),
           "KZ": (43.35, 77.04), "ID": (-6.13, 106.66), "SA": (24.96, 46.7), "EG": (30.12, 31.41), "DZ": (36.69, 3.21),
           "NO": (60.19, 11.1), "SE": (59.65, 17.92), "GL": (64.19, -51.68), "CD": (-4.39, 15.44), "NZ": (-37.01, 174.79)}


def paises_del_mapa():
    mapa = json.loads(MAPA.read_text(encoding="utf-8"))["paises"]
    return [(cod, *(GRANDES.get(cod) or centro(ruta))) for cod, ruta in mapa.items() if cod not in FUERA]


# multiplicador de temporada por mes natural (1 = ene)
TEMPORADA = {1: 0.85, 2: 0.8, 3: 0.85, 4: 1.0, 5: 0.95, 6: 1.15, 7: 1.4, 8: 1.45, 9: 1.0, 10: 0.9, 11: 0.8, 12: 1.3}
NOMBRES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def precio_base(horas):
    if horas < 4:
        return 40 + 22 * horas
    if horas < 6:
        return 130 + 55 * (horas - 4)
    return 360 + 60 * (horas - 6)


def visitados():
    try:
        import paises
        return sorted(paises.visitados())
    except Exception:
        return []


def main():
    hoy = date.today()
    meses = []
    y, m = hoy.year, hoy.month
    for _ in range(12):
        meses.append({"id": f"{y}-{m:02d}", "nombre": NOMBRES[m], "anio": y})
        m += 1
        if m == 13:
            y, m = y + 1, 1
    filas = []
    for cod, lat, lon in paises_del_mapa():
        km = semaforo.km_aire(lat, lon)
        h = semaforo.horas(km)
        rnd = random.Random(cod)
        celdas = []
        for mes in meses:
            mm = int(mes["id"][5:])
            p = round(precio_base(h) * TEMPORADA[mm] * rnd.uniform(0.75, 1.25))
            celdas.append({"p": p, "c": semaforo.color(p, km), "f": hoy.isoformat(), "e": True})
        filas.append({"cod": cod, "km": round(km), "h": round(h, 1), "tipo": semaforo.tipo(km),
                      "celdas": celdas})
    filas.sort(key=lambda f: f["cod"])
    SALIDA.write_text(json.dumps({"version": VERSION, "ejemplo": True, "visitados": visitados(), "generado": hoy.isoformat(),
                                  "leyenda": semaforo.leyenda(), "meses": meses, "paises": filas},
                                 ensure_ascii=False), encoding="utf-8")
    verdes = sum(c["c"] == "verde" for f in filas for c in f["celdas"])
    print(f"{len(filas)} países × {len(meses)} meses, {verdes} casillas verdes → {SALIDA}")


if __name__ == "__main__":
    main()
