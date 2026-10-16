r"""
seguimiento.py — Vigila el precio de vuelos concretos y lo apunta una vez al día (Jawdrop).

Lee `vigilados.txt` (una línea por vuelo: ORIGEN DESTINO AAAA-MM-DD HH:MM NºVUELO [viaje]), pide a Ryanair el
precio de ese día y esa hora (una consulta por vuelo, por la caché, con pausa), comprueba que el número de
vuelo coincide y añade una línea a `seguimiento_precios.csv`. Si el vuelo ya no sale o no hay precio, lo
apunta igual como «sin precio». Repetir el mismo día sustituye la lectura de ese día (no duplica).

  seguimiento.py             lee, apunta y enseña el resumen
  seguimiento.py --subir     además hace commit y push SOLO del CSV (para la tarea diaria)
  seguimiento.py --resumen   solo enseña el resumen, sin consultar nada
"""
import argparse
import csv
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import cache
import ryanair

VERSION = "0.1"
CARPETA = Path(__file__).resolve().parent
VIGILADOS = CARPETA / "vigilados.txt"
CSV_RUTA = CARPETA / "seguimiento_precios.csv"
COLUMNAS = ["fecha_lectura", "hora_lectura", "viaje", "vuelo", "origen", "destino", "dia", "hora", "precio", "estado"]
HORAS_CACHE = 6   # si se ejecuta dos veces seguidas, la segunda no vuelve a preguntar
AVISO_EUR, AVISO_PCT = 10.0, 20.0


def _num(v):
    return "".join(c for c in str(v).upper() if c.isalnum())


def leer_vigilados(ruta=VIGILADOS):
    res = []
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        t = linea.split("#", 1)[0].split()
        if not t:
            continue
        if len(t) < 5:
            raise ValueError(f"{ruta.name}, línea {n}: faltan datos (ORIGEN DESTINO AAAA-MM-DD HH:MM NºVUELO).")
        try:
            date.fromisoformat(t[2])
            datetime.strptime(t[3], "%H:%M")
        except ValueError:
            raise ValueError(f"{ruta.name}, línea {n}: fecha u hora mal escritas ({t[2]} {t[3]}).") from None
        res.append({"origen": t[0].upper(), "destino": t[1].upper(), "dia": t[2], "hora": t[3],
                    "vuelo": _num(t[4]), "viaje": t[5] if len(t) > 5 else "suelto"})
    return res


def leer_precio(v):
    """(precio o None, estado) para un vuelo vigilado."""
    p = dict(ryanair.COMUNES, departureAirportIataCode=v["origen"], arrivalAirportIataCode=v["destino"],
             outboundDepartureDateFrom=v["dia"], outboundDepartureDateTo=v["dia"],
             outboundDepartureTimeFrom=v["hora"], outboundDepartureTimeTo=v["hora"])
    try:
        datos = cache.con_cache(["seguimiento", ryanair.URL_SOLO_IDA, p, date.today().isoformat()], HORAS_CACHE,
                                lambda: ryanair._get(ryanair.URL_SOLO_IDA, p))
    except Exception as ex:
        return None, f"error: {str(ex)[:60]}"
    for f in datos.get("fares", []):
        t = ryanair._tramo(f["outbound"], "ida")
        if _num(t["vuelo"]) == v["vuelo"] and t["salida"][:10] == v["dia"]:
            return t["precio"], "ok"
    if datos.get("fares"):
        return None, "otro vuelo a esa hora (el número no coincide)"
    return None, "sin precio"


def leer_csv():
    if not CSV_RUTA.exists():
        return []
    with CSV_RUTA.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def guardar_csv(filas):
    filas.sort(key=lambda r: (r["fecha_lectura"], r["viaje"], r["dia"], r["vuelo"]))
    with CSV_RUTA.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)


def apuntar(vigilados):
    hoy, ahora = date.today().isoformat(), datetime.now().strftime("%H:%M")
    filas = leer_csv()
    nuevas = []
    for v in vigilados:
        precio, estado = leer_precio(v)
        print(f"  {v['origen']}→{v['destino']} {v['dia']} {v['hora']} {v['vuelo']}: "
              f"{'%.2f €' % precio if precio is not None else estado}")
        nuevas.append({"fecha_lectura": hoy, "hora_lectura": ahora, "viaje": v["viaje"], "vuelo": v["vuelo"],
                       "origen": v["origen"], "destino": v["destino"], "dia": v["dia"], "hora": v["hora"],
                       "precio": f"{precio:.2f}" if precio is not None else "", "estado": estado})
    clave = lambda r: (r["fecha_lectura"], r["vuelo"], r["dia"])
    claves_nuevas = {clave(r) for r in nuevas}
    guardar_csv([r for r in filas if clave(r) not in claves_nuevas] + nuevas)


def totales():
    """{viaje: {fecha_lectura: total}} solo de los días en que se leyeron todos los vuelos del viaje."""
    filas = leer_csv()
    vuelos = {}
    for r in filas:
        vuelos.setdefault(r["viaje"], set()).add((r["vuelo"], r["dia"]))
    por = {}
    for r in filas:
        d = por.setdefault(r["viaje"], {}).setdefault(r["fecha_lectura"], {})
        d[(r["vuelo"], r["dia"])] = float(r["precio"]) if r["precio"] else None
    res = {}
    for viaje, dias in por.items():
        for fecha, d in dias.items():
            if len(d) == len(vuelos[viaje]) and all(p is not None for p in d.values()):
                res.setdefault(viaje, {})[fecha] = sum(d.values())
    return res


def resumen():
    tot = totales()
    if not tot:
        print("Aún no hay lecturas completas.")
        return
    for viaje, d in sorted(tot.items()):
        fechas = sorted(d)
        ult = d[fechas[-1]]
        txt = f"{viaje}: {ult:.2f} € el {fechas[-1]}"
        if len(fechas) > 1:
            ant = d[fechas[-2]]
            dif = ult - ant
            txt += f" ({dif:+.2f} € frente al {fechas[-2]}); mín {min(d.values()):.2f} · máx {max(d.values()):.2f}"
            if abs(dif) >= AVISO_EUR or (ant and abs(dif) / ant * 100 >= AVISO_PCT):
                txt += "  ⚠ CAMBIO NOTABLE"
        print(txt)


def subir():
    def git(*a):
        return subprocess.run(["git", *a], cwd=CARPETA, capture_output=True, text=True)
    git("add", CSV_RUTA.name)
    if git("diff", "--cached", "--quiet", "--", CSV_RUTA.name).returncode == 0:
        print("Nada nuevo que subir.")
        return
    c = git("commit", "-m", f"Seguimiento de precios {date.today().isoformat()}", "--", CSV_RUTA.name)
    p = git("push")
    print("Subido." if c.returncode == 0 and p.returncode == 0 else f"No se pudo subir: {(c.stderr + p.stderr)[:200]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Seguimiento diario del precio de vuelos concretos.")
    ap.add_argument("--subir", action="store_true", help="commit y push del CSV")
    ap.add_argument("--resumen", action="store_true", help="solo enseña el resumen")
    a = ap.parse_args(argv)
    if not a.resumen:
        vig = leer_vigilados()
        if not vig:
            print("vigilados.txt está vacío.")
            return 1
        print(f"Seguimiento {VERSION}: {len(vig)} vuelos")
        apuntar(vig)
    resumen()
    if a.subir:
        subir()
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
