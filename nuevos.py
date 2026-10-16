r"""
nuevos.py — Los N países nuevos más cercanos, con ida y vuelta (Jawdrop).

Coge los países que el usuario no ha visitado (`paises_visitados.txt`), los ordena por distancia a Barcelona y,
para los N primeros, busca la mejor combinación ida+vuelta (dos billetes de solo ida, directos) con
`pais.py`: Kiwi, Ryanair y Wizz, todo gratis, por la caché y sin SerpApi. Al final enseña una tabla
comparativa y la guarda en `resultados\nuevos_<periodo>.md`.

  - Solo cuenta ida y vuelta: un precio de solo ida no se enseña como resultado.
  - Liechtenstein no tiene aeropuerto: se entra por Zúrich (se busca Zúrich ida y vuelta y se avisa del
    traslado por tierra, unas 2 h).
  - Cada país también queda guardado para el panel «Un país concreto» de la demo.

Uso:
  .venv\Scripts\python.exe nuevos.py                              (10 países, próximos 2 meses, dom → mar/mié)
  .venv\Scripts\python.exe nuevos.py --n-nuevos 5 --mes 2027-01,2027-02
  .venv\Scripts\python.exe nuevos.py --salida viernes,sabado --dias 3-4
  .venv\Scripts\python.exe nuevos.py --solo-listar                (solo los países y distancias, sin consultar)
"""
import argparse
import math
import sys
from datetime import date
from pathlib import Path

import pais
import paises

VERSION = "0.3"
CARPETA = Path(__file__).resolve().parent / "resultados"
BCN = (41.297, 2.078)

# País -> (lat, lon) del aeropuerto principal al que se entra; solo sirve para ordenar por cercanía.
# Si el usuario quiere más países, se añaden aquí.
ENTRADAS = {
    "DZ": (36.69, 3.21), "TN": (36.85, 10.23), "MT": (35.86, 14.48), "IE": (53.42, -6.27),
    "TR": (41.26, 28.74), "CY": (34.88, 33.63), "EG": (30.12, 31.41), "IS": (63.99, -22.60),
    "IL": (32.01, 34.88), "JO": (31.72, 35.99), "LB": (33.82, 35.49), "SN": (14.74, -17.49),
    "CV": (16.74, -22.95), "AZ": (40.47, 50.05), "AE": (25.25, 55.36), "QA": (25.27, 51.61),
    "SA": (21.68, 39.16), "BH": (26.27, 50.63), "OM": (23.59, 58.28), "KZ": (51.02, 71.47),
    "UZ": (41.26, 69.28), "GE": (41.67, 44.95), "LI": (47.46, 8.55),   # Liechtenstein: por Zúrich
    # Con vuelo directo desde BCN (12-10-2026): Level, Iberojet, Air Canada, Avianca, LATAM...
    "US": (40.64, -73.78), "CA": (45.47, -73.74), "MX": (19.44, -99.07), "DO": (18.57, -68.36),
    "SV": (13.44, -89.06), "HN": (14.06, -87.22), "CO": (4.70, -74.15), "PE": (-12.02, -77.11),
    "CL": (-33.39, -70.79), "AR": (-34.82, -58.54), "BR": (-23.43, -46.47), "BO": (-17.64, -63.14),
    "GM": (13.34, -16.65), "KW": (29.23, 47.97), "HK": (22.31, 113.91),
}


def _km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def candidatos(n):
    """[(código, km)] de los n países nuevos más cercanos (sin España)."""
    nuevos = [(c, _km(BCN, xy)) for c, xy in ENTRADAS.items() if paises.es_nuevo(c)]
    return sorted(nuevos, key=lambda t: t[1])[:n]


def _meses_por_defecto():
    h = date.today()
    m1 = (h.year, h.month + 1) if h.month < 12 else (h.year + 1, 1)
    m2 = (m1[0], m1[1] + 1) if m1[1] < 12 else (m1[0] + 1, 1)
    return f"{m1[0]}-{m1[1]:02d},{m2[0]}-{m2[1]:02d}"


def _fila(codigo, km, a):
    """Busca un país y devuelve un diccionario sencillo con su mejor opción (o el motivo de que no haya)."""
    nombre = pais.nombre_pais(codigo)
    fila = {"codigo": codigo, "pais": nombre, "km": round(km), "mejor": None, "nota": ""}
    buscar_en = "CH" if codigo == "LI" else codigo
    if codigo == "LI":
        fila["pais"] = "Liechtenstein (vía Zúrich)"
        fila["nota"] = "sin aeropuerto: entras por Zúrich y son unas 2 h por tierra"
    try:
        entrada, (opciones, coords, _mejores, _por_dia) = pais.ejecutar(
            buscar_en, a.mes, None, None, a.salida, a.dias, 1, a.max_fechas)
    except ValueError as e:
        fila["nota"] = str(e)
        return fila
    if codigo == "LI":   # solo Zúrich → Zúrich
        opciones = [o for o in opciones if o["entrada"] == "ZRH" and o["salida_ap"] == "ZRH"]
        if not opciones:
            return fila
        o = min(opciones, key=lambda o: o["total"])
        res = pais.resumen(o, coords)
    else:
        if not entrada["mejores"]:
            fila["nota"] = fila["nota"] or "sin ida y vuelta directos en esas fechas"
            return fila
        res = entrada["mejores"][0]
        pais.guardar(entrada)
    fila["mejor"] = res
    return fila


def _hora(iso):
    return str(iso)[11:16] if len(str(iso)) >= 16 else str(iso)


def _t(t):
    return f"{t['precio']:.0f} € {t['aerolinea']} {_hora(t['salida'])}→{_hora(t['llegada'])}{t['marca']}"


def _tabla(filas, periodo, salida, dias):
    sep = "|---|---|---|---|---|---|"
    out = [f"# Países nuevos más cercanos: ida y vuelta ({periodo}, salida {salida}, {dias} días)", "",
           "| País | Km | Ida+vuelta | Fechas | Cómo | Nota |", sep]
    for f in filas:
        m = f["mejor"]
        if m:
            fechas = (f"{pais._fecha(m['ida'])} → {pais._fecha(m['vuelta'])} · "
                      f"{pais.noches(m['ida'], m['vuelta'])}")
            como = (f"ida {_t(m['t_ida'])} / vuelta {_t(m['t_vuelta'])} "
                    f"({m['entrada']}" + ("" if m["mismo"] else f" → {m['salida']}") + ")")
            est = " (estimado)" if any(m[k]["marca"] in ("~", "≈") for k in ("t_ida", "t_vuelta")) else ""
            out.append(f"| {f['pais']} | {f['km']} | **{m['total']:.0f} €**{est} | {fechas} | {como} | "
                       f"{f['nota']} |")
        else:
            out.append(f"| {f['pais']} | {f['km']} | — | — | — | {f['nota']} |")
    out.append("")
    out.append("Precios con «~» o «≈» en las búsquedas de cada país son de Kiwi (estimados); conviene "
               "comprobarlos antes de comprar.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Los N países nuevos más cercanos, con ida y vuelta")
    ap.add_argument("--n-nuevos", type=int, default=10, help="cuántos países (10)")
    ap.add_argument("--mes", help="AAAA-MM (varios con comas); por defecto, los 2 meses siguientes")
    ap.add_argument("--salida", default="domingo", help="día(s) de salida (domingo)")
    ap.add_argument("--dias", default="3-4", help="duración contando ida y vuelta (3-4)")
    ap.add_argument("--max-fechas", type=int, default=12, help="tope de fechas de ida por país (12)")
    ap.add_argument("--solo-listar", action="store_true", help="solo enseña los países y su distancia")
    a = ap.parse_args(argv)
    a.mes = a.mes or _meses_por_defecto()

    for aviso in paises.cargar()[1]:
        print("Aviso:", aviso)
    lista = candidatos(a.n_nuevos)
    print(f"nuevos.py {VERSION}: los {len(lista)} países nuevos más cercanos")
    for c, km in lista:
        print(f"  {pais.nombre_pais(c):<24} {km:>5.0f} km")
    if a.solo_listar:
        return
    print(f"\nBuscando ida y vuelta ({a.mes}, salida {a.salida}, {a.dias} días). Gratis, con caché; "
          "la primera vez son unos 2 min por país.\n")
    filas = []
    for i, (c, km) in enumerate(lista, 1):
        print(f"[{i}/{len(lista)}] {pais.nombre_pais(c)}...", flush=True)
        try:
            filas.append(_fila(c, km, a))
        except Exception as e:   # una fuente caída no debe tirar toda la tabla
            filas.append({"codigo": c, "pais": pais.nombre_pais(c), "km": round(km), "mejor": None,
                          "nota": f"error: {e}"})
    texto = _tabla(filas, a.mes.replace(",", "+"), a.salida, a.dias)
    print("\n" + texto)
    CARPETA.mkdir(exist_ok=True)
    ruta = CARPETA / f"nuevos_{a.mes.replace(',', '+')}.md"
    ruta.write_text(texto + "\n", encoding="utf-8")
    print(f"\nGuardado en {ruta.relative_to(ruta.parent.parent)}")
    try:
        import ver_resultados
        ver_resultados.construir()
    except Exception:
        pass


if __name__ == "__main__":
    main()
