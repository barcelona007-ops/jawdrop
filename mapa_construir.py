r"""
mapa_construir.py — Genera `movil/mapa.json`, el mapamundi del pasaporte (Jawdrop).

Se ejecuta UNA vez (o si se quiere rehacer el mapa); la app ya incluye el resultado. Necesita
`pip install pycountry`, solo para esto, y el archivo `countries-50m.json` (npm: `world-atlas`).
Fuente de los contornos: Natural Earth (dominio público). Cada país queda como un trazo SVG con su código
de 2 letras. Los contornos se simplifican con Douglas-Peucker POR TRAMO de frontera (los tramos que comparten
dos países se simplifican una sola vez, así las fronteras siguen encajando sin huecos) y se escriben en
coordenadas relativas con 2 decimales para que pesen poco sin perder las curvas de la costa.

Uso: .venv\Scripts\python.exe mapa_construir.py ruta\a\countries-50m.json
"""
import json
import sys
from pathlib import Path

VERSION = "0.3"
SALIDA = Path(__file__).resolve().parent / "movil" / "mapa.json"
EXTRA = {"Kosovo": "XK"}          # sin número ISO en los datos
OMITIR = {"Antarctica", "Fr. S. Antarctic Lands", "Siachen Glacier", "Indian Ocean Ter.", "Somaliland", "N. Cyprus"}
TOLERANCIA = 0.02                 # grados (~4 km): lo que Douglas-Peucker puede apartarse de la costa real
DECIMALES = 2                      # grados con 2 decimales (~1 km): sin rejilla, las curvas quedan naturales
MIN_ANILLO = 0.004                 # grados²: islotes más pequeños se omiten (salvo el mayor de cada país)


def decodificar(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcos = []
    for a in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in a:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcos.append(pts)
    return arcos


def anillo(arcos, indices):
    pts = []
    for i in indices:
        a = arcos[i] if i >= 0 else arcos[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts


def dp(pts, tol):
    """Douglas-Peucker iterativo: se queda con los puntos que se apartan más de `tol` de la recta."""
    n = len(pts)
    if n < 3:
        return pts
    keep = [False] * n
    keep[0] = keep[-1] = True
    pila = [(0, n - 1)]
    while pila:
        i, j = pila.pop()
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        mx, k = -1.0, -1
        for m in range(i + 1, j):
            x, y = pts[m]
            if l2 == 0:
                d = ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
            else:
                t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / l2))
                d = ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** 0.5
            if d > mx:
                mx, k = d, m
        if mx > tol and k > 0:
            keep[k] = True
            pila.append((i, k))
            pila.append((k, j))
    return [p for p, c in zip(pts, keep) if c]


def simplificar(arcos):
    """Cada tramo se simplifica una vez; los pequeños (islas, micropaíses) con tolerancia proporcional a su tamaño."""
    out = []
    for a in arcos:
        xs = [p[0] for p in a]
        ys = [p[1] for p in a]
        ext = max(max(xs) - min(xs), max(ys) - min(ys)) if a else 0
        out.append(dp(a, min(TOLERANCIA, ext / 25)))
    return out


def area(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def num(v):
    t = ("%." + str(DECIMALES) + "f") % v
    t = t.rstrip("0").rstrip(".") if "." in t else t
    return "0" if t in ("-0", "") else t


def trazo(pts):
    """Ruta SVG en coordenadas relativas (l), calculadas desde los valores YA redondeados para que no se acumule error."""
    q = 10 ** DECIMALES
    r = []
    for lon, lat in pts:
        p = (round(lon * q), round(-lat * q))
        if not r or p != r[-1]:
            r.append(p)
    if len(r) < 4:
        return ""
    trozos, actual = [], [r[0]]
    for p in r[1:]:                        # un salto de más de 180° es el meridiano ±180: se corta ahí
        if abs(p[0] - actual[-1][0]) > 180 * q:
            trozos.append(actual)
            actual = []
        actual.append(p)
    trozos.append(actual)
    d = ""
    for t in trozos:
        if len(t) < 3:
            continue
        d += "M%s %s" % (num(t[0][0] / q), num(t[0][1] / q))
        cmd = ""
        for (x0, y0), (x1, y1) in zip(t, t[1:]):
            s = ""
            for v in ((x1 - x0) / q, (y1 - y0) / q):
                n = num(v)
                s += n if (not s or n.startswith("-")) else " " + n
            d += ("l" + s) if not cmd else (s if s.startswith("-") else " " + s)
            cmd = "l"
        d += "z"
    return d


def main():
    import pycountry
    topo = json.load(open(sys.argv[1], encoding="utf-8"))
    arcos = simplificar(decodificar(topo))
    mapa = {}
    for g in topo["objects"]["countries"]["geometries"]:
        nombre = g["properties"]["name"]
        if nombre in OMITIR:
            continue
        if nombre in EXTRA:
            cod = EXTRA[nombre]
        else:
            p = pycountry.countries.get(numeric=str(g["id"]).zfill(3))
            if not p:
                print("sin código:", nombre)
                continue
            cod = p.alpha_2
        polis = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        anillos = [anillo(arcos, r) for poli in polis for r in poli[:1]]   # solo contornos exteriores
        mayor = max(anillos, key=area, default=[])
        d = "".join(trazo(a) for a in anillos if a is mayor or area(a) >= MIN_ANILLO)
        if d:
            mapa[cod] = mapa.get(cod, "") + d
    SALIDA.write_text(json.dumps({"version": VERSION, "viewBox": "-180 -85 360 145", "paises": mapa},
                                 separators=(",", ":")), encoding="utf-8")
    print(f"{len(mapa)} países, {SALIDA.stat().st_size // 1024} KB -> {SALIDA}")


if __name__ == "__main__":
    main()
