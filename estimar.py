r"""
estimar.py 0.2 — Cuánto costará (en consultas y en minutos) una búsqueda por país, SIN hacer ninguna consulta.

Mira la caché (`cache.py`) y cuenta solo las consultas que de verdad saldrían a internet, con la pausa
de cada pieza (Kiwi, Ryanair, Wizz). Es la base de la confirmación del «buscador a medida»: «≈ 140
consultas, ~12 min, ¿sigo?». No gasta SerpApi ni molesta a ninguna aerolínea; como mucho lee la lista de
aeropuertos (Ryanair) y la red de Wizz, que están en caché 24-72 h.

Uso:
  .venv\Scripts\python.exe estimar.py Turquia --mes 2027-04 [--dias 4] [--salida domingo]
"""
import argparse
import sys
from datetime import timedelta

import cache
import kiwi
import pais
import ryanair
import wizz

VERSION = "0.2"
EXTRA_S = 2        # segundos que tarda cada consulta real, además de la pausa
UMBRAL_MIN = 5     # a partir de aquí conviene pedir confirmación


def _min_texto(segundos):
    m = segundos / 60
    return "menos de 1 min" if m < 1 else f"~{m:.0f} min"


def estimar_pais(texto, meses=None, desde=None, hasta=None, salida="domingo", dias="4",
                 con_kiwi=True, con_ryanair=True, con_wizz=True, vuelta=None, solo="", sin=""):
    """Devuelve {"pais", "fechas", "fuentes": {nombre: {"total", "nuevas", "segundos"}}, "nuevas", "segundos",
    "minutos", "pide_confirmacion", "texto"}. Lanza ValueError si el país, las fechas o los días no valen."""
    codigo = pais.codigo_pais(texto)
    if not codigo:
        raise ValueError(f"No reconozco el país «{texto}».")
    dmin, dmax = pais._dias(dias)
    fechas = pais.fechas_de(salida, meses, desde, hasta)
    if not fechas:
        raise ValueError("No hay ninguna fecha de salida en ese periodo (¿ya pasó?).")
    vuelta = (vuelta or "").strip().lower()
    fechas_vuelta = pais.fechas_vuelta_de(fechas, dmin, dmax, None if vuelta in ("", "todos", "cualquiera") else vuelta)
    con_kiwi, con_ryanair, con_wizz = pais.filtro_fuentes(pais._norm_lista(solo), pais._norm_lista(sin),
                                                           con_kiwi, con_ryanair, con_wizz)
    origen = pais.ORIGEN
    fuentes = {}

    def cuenta(nombre, claves, pausa):
        """claves = [(partes, horas)]; cuenta las que no están en la caché."""
        nuevas = sum(1 for partes, horas in claves if cache.leer(partes, horas) is None)
        fuentes[nombre] = {"total": len(claves), "nuevas": nuevas, "segundos": nuevas * (pausa + EXTRA_S)}

    if con_kiwi:
        lote = [f"Country:{codigo}"]
        k = []
        for f in fechas:
            d = f.isoformat()
            k.append((["kiwi", "rango1", [f"Airport:{origen}"], lote, d, d, 50], kiwi.HORAS_CACHE))
        for f in fechas_vuelta:
            d = f.isoformat()
            k.append((["kiwi", "rango1", lote, [f"Airport:{origen}"], d, d, 50], kiwi.HORAS_CACHE))
        cuenta("Kiwi", k, kiwi.PAUSA)

    coords = {}
    if con_ryanair or con_wizz:
        try:
            coords = ryanair.aeropuertos()
        except Exception:
            coords = {}
    if con_ryanair:
        k = []
        for f in fechas:
            p = dict(ryanair.COMUNES, departureAirportIataCode=origen, outboundDepartureDateFrom=f.isoformat(),
                     outboundDepartureDateTo=f.isoformat(), outboundDepartureTimeFrom="00:00",
                     outboundDepartureTimeTo="23:59")
            k.append((["ryanair", ryanair.URL_SOLO_IDA, p], ryanair.HORAS_CACHE))
        # Aeropuertos del país con ruta: exacto si las idas ya están en caché; si no, cota superior.
        aps, exacto = set(), True
        for partes, horas in k:
            datos = cache.leer(partes, horas)
            if datos is None:
                exacto = False
                continue
            for fa in datos.get("fares", []):
                iata = fa["outbound"]["arrivalAirport"]["iataCode"]
                if coords.get(iata, {}).get("pais") == codigo:
                    aps.add(iata)
        if not exacto:
            aps |= {a for a, v in coords.items() if v.get("pais") == codigo}
        for ap in sorted(aps):
            for f in fechas_vuelta:
                d = f.isoformat()
                p = dict(ryanair.COMUNES, departureAirportIataCode=ap, arrivalAirportIataCode=origen,
                         outboundDepartureDateFrom=d, outboundDepartureDateTo=d,
                         outboundDepartureTimeFrom="00:00", outboundDepartureTimeTo="23:59")
                k.append((["ryanair", ryanair.URL_SOLO_IDA, p], ryanair.HORAS_CACHE))
        cuenta("Ryanair", k, ryanair.PAUSA)
        fuentes["Ryanair"]["cota"] = not exacto

    if con_wizz:
        try:
            aeropuertos, red = wizz.red(origen)
            rutas = [d for d in red if aeropuertos.get(d, {}).get("pais") == codigo]
        except Exception:
            rutas = []
        por_mes = {}
        for f in fechas:
            por_mes.setdefault((f.year, f.month), []).append(f)
        k = []
        for d in rutas:
            for fs in por_mes.values():
                a, b = min(fs), max(fs)
                cuerpo = {
                    "flightList": [
                        {"departureStation": origen, "arrivalStation": d,
                         "from": a.isoformat(), "to": b.isoformat()},
                        {"departureStation": d, "arrivalStation": origen,
                         "from": (a + timedelta(days=dmin - 1)).isoformat(),
                         "to": (b + timedelta(days=dmax - 1)).isoformat()},
                    ],
                    "priceType": "regular", "adultCount": 1, "childCount": 0, "infantCount": 0,
                }
                k.append((["wizz", "timetableV2", cuerpo], wizz.HORAS_CACHE))
        cuenta("Wizz", k, wizz.PAUSA)

    nuevas = sum(v["nuevas"] for v in fuentes.values())
    segundos = sum(v["segundos"] for v in fuentes.values())
    detalle = " · ".join(f"{n}: {v['nuevas']} de {v['total']}" + (" (como mucho)" if v.get("cota") else "")
                         for n, v in fuentes.items())
    if nuevas == 0:
        texto = "Todo está ya en la caché: sale en segundos y sin consultar a nadie."
    else:
        texto = f"≈ {nuevas} consultas nuevas, {_min_texto(segundos)} ({detalle})"
    return {"pais": codigo, "fechas": len(fechas), "fuentes": fuentes, "nuevas": nuevas, "segundos": segundos,
            "minutos": round(segundos / 60, 1), "pide_confirmacion": segundos / 60 >= UMBRAL_MIN, "texto": texto}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Cuánto costará una búsqueda por país, sin hacerla")
    ap.add_argument("pais")
    ap.add_argument("--mes")
    ap.add_argument("--desde")
    ap.add_argument("--hasta")
    ap.add_argument("--salida", default="domingo")
    ap.add_argument("--dias", default="4")
    ap.add_argument("--vuelta", default="")
    ap.add_argument("--solo", default="")
    ap.add_argument("--sin", default="")
    ap.add_argument("--sin-kiwi", action="store_true")
    ap.add_argument("--sin-ryanair", action="store_true")
    ap.add_argument("--sin-wizz", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = estimar_pais(a.pais, a.mes, a.desde, a.hasta, a.salida, a.dias,
                         not a.sin_kiwi, not a.sin_ryanair, not a.sin_wizz,
                         a.vuelta, a.solo, a.sin)
    except ValueError as e:
        sys.exit(str(e))
    print(f"estimar.py {VERSION}: {r['pais']}, {r['fechas']} fechas de ida.")
    print(r["texto"])
    if r["pide_confirmacion"]:
        print(f"Pasa de {UMBRAL_MIN} min: el buscador pedirá confirmación.")


if __name__ == "__main__":
    main()
