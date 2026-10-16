"""
semana.py — Prueba del tipo de viaje «Semana» del Radar único (el usuario, 14-10-2026).

Para uno o varios países y un mes, la mejor pareja ida+vuelta de 5-8 noches desde BCN (mismo aeropuerto) con
Ryanair y Wizz Air, y su color del semáforo (el de siempre: solo cuentan las horas de vuelo). Gratis, sin SerpApi, todo por la caché.
Sin Vueling ni Kiwi todavía (no dan pareja ida+vuelta con fechas: se sumarían dos solo-ida).

Uso:  .venv\\Scripts\\python.exe semana.py IT PT --mes 2027-09 [--noches 5-8] [--sin-wizz]
"""
import sys
from datetime import date, timedelta

import cache
import ryanair
import semaforo
import wizz

VERSION = "0.3"
ORIGEN = "BCN"


def _rango_mes(mes):
    primero = date.fromisoformat(mes + "-01")
    ultimo = date(primero.year + primero.month // 12, primero.month % 12 + 1, 1) - timedelta(days=1)
    return max(primero, date.today()), ultimo


def ryanair_pareja(destino, mes, n_min, n_max):
    """Mejor ida+vuelta de n_min-n_max noches de Ryanair a un aeropuerto (ida dentro del mes)."""
    desde, ultimo = _rango_mes(mes)
    p = dict(ryanair.COMUNES, departureAirportIataCode=ORIGEN, arrivalAirportIataCode=destino,
             outboundDepartureDateFrom=desde.isoformat(), outboundDepartureDateTo=ultimo.isoformat(),
             inboundDepartureDateFrom=desde.isoformat(),
             inboundDepartureDateTo=(ultimo + timedelta(days=n_max)).isoformat(),
             durationFrom=n_min, durationTo=n_max)
    fares = ryanair._pedir(ryanair.URL_IDA_VUELTA, p, True).get("fares", [])
    if not fares:
        return None
    m = min(fares, key=lambda f: f["summary"]["price"]["value"])
    o, v = m["outbound"], m["inbound"]
    return {"aerolinea": "Ryanair", "ida": o["departureDate"][:10], "vuelta": v["departureDate"][:10],
            "total": float(m["summary"]["price"]["value"]), "noches": m["summary"].get("tripDurationDays")}


def semana_paises(paises, mes, n_min=5, n_max=8, con_wizz=True, avisar=None):
    """{país: [filas de más barata a más cara]}; cada fila = aeropuerto con su mejor pareja y color.
    `paises` = lista de códigos, o None para todos los de la red de Ryanair y Wizz (sin España)."""
    aeropuertos = ryanair.aeropuertos()
    desde, ultimo = _rango_mes(mes)
    p = dict(ryanair.COMUNES, departureAirportIataCode=ORIGEN, outboundDepartureDateFrom=desde.isoformat(),
             outboundDepartureDateTo=ultimo.isoformat())
    destinos = {}   # aeropuerto -> (ciudad, país, nombre)
    for f in ryanair._pedir(ryanair.URL_SOLO_IDA, p, True).get("fares", []):
        t = ryanair._tramo(f["outbound"], "ida")
        if t["pais"] != "ES" and (paises is None or t["pais"] in paises):
            destinos[t["destino"]] = (t["ciudad"], t["pais"], t["pais_nombre"])
    filas = {pais: [] for pais in (paises or sorted({d[1] for d in destinos.values()}))}
    for i, (d, (ciudad, pais, nombre)) in enumerate(sorted(destinos.items()), 1):
        if avisar:
            avisar(f"Ryanair {i}/{len(destinos)} {d}")
        par = ryanair_pareja(d, mes, n_min, n_max)
        if par:
            filas[pais].append(dict(par, destino=d, ciudad=ciudad, pais_nombre=nombre))
    if con_wizz:
        aero_w, red_w = wizz.red(ORIGEN)
        solo = [d for d in red_w if aero_w.get(d, {}).get("pais") not in ("ES", None)
                and (paises is None or aero_w[d]["pais"] in paises)]   # solo los países pedidos
        for r in (wizz.radar(ORIGEN, mes, solo, n_min, n_max) if solo else []):
            if r["pais"] != "ES" and r["pareja"]:
                filas.setdefault(r["pais"], [])
                filas[r["pais"]].append(dict(r["pareja"], destino=r["destino"], ciudad=r["ciudad"],
                                             pais_nombre=r["pais_nombre"]))
    for pais, lista in filas.items():
        for f in lista:
            a = aeropuertos.get(f["destino"])
            km = semaforo.km_aire(a["lat"], a["lon"]) if a and a.get("lat") is not None else None
            f["km"] = km
            f["color"] = semaforo.color(f["total"], km)
        lista.sort(key=lambda f: f["total"])
    return filas


def main(argv):
    mes = argv[argv.index("--mes") + 1] if "--mes" in argv else None
    noches = argv[argv.index("--noches") + 1] if "--noches" in argv else "5-8"
    if not mes:
        print(__doc__)
        return 1
    a, _, b = noches.partition("-")
    paises = [x.upper() for x in argv if len(x) == 2 and x.isalpha()]
    filas = semana_paises(paises, mes, int(a), int(b or a), "--sin-wizz" not in argv)
    for pais, lista in filas.items():
        print(f"\n{pais}  ({mes}, {noches} noches)")
        if not lista:
            print("  sin pareja ida+vuelta en esas fechas")
        for f in lista[:6]:
            h = semaforo.horas(f["km"])
            print(f"  {f['total']:>6.0f} € {f['color']:<6} {f['ciudad']:<18}{f['destino']} {f['aerolinea']:<9}"
                  f" {f['ida']} -> {f['vuelta']} ({f['noches']} n)  ~{h:.1f} h" if h else
                  f"  {f['total']:>6.0f} € {f['color']:<6} {f['ciudad']:<18}{f['destino']} {f['aerolinea']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
