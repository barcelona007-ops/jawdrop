"""
microestados_ahora.py 0.2 — Lee ya el precio de los microestados (Mónaco, Liechtenstein, San Marino, Vaticano) los 12 meses (20-10-2026).

Pregunta a Kiwi por el aeropuerto concreto de cada uno (Niza, Zúrich, Rímini/Bolonia/Forlì, Roma) y lo guarda en datos/radar_semana.json
como si el aeropuerto estuviera dentro del país (igual que radar_datos.leer_mes). Solo AÑADE o mejora: no borra nada, y una lectura
que ya hay más barata se queda. Para la Raspberry (la que puede leer); el candado es el mismo de la fusión horaria. ~100 consultas gratis.
Uso: .venv/bin/python microestados_ahora.py [--seco]   (--seco: lee y enseña, sin guardar)
"""
import fcntl
import json
import sqlite3
import subprocess
import sys
import time
from datetime import date

import kiwi
import radar_datos as rd

VERSION = "0.2"


def meses():
    y, m = date.today().year, date.today().month
    for _ in range(12):
        yield f"{y}-{m:02d}"
        m += 1
        if m == 13:
            y, m = y + 1, 1


def leer():
    nuevas = {}
    for mes in meses():
        for cod, (_, aps, como) in rd.VIA_VECINO.items():
            for intento in range(8):   # la caché (SQLite) la comparte el lector principal: si está ocupada, esperar y repetir
                try:
                    p = kiwi.semana_pais("BCN", cod, mes, rd.NOCHES[0], rd.NOCHES[1], destinos=sorted(aps))
                    break
                except sqlite3.OperationalError:
                    time.sleep(20)
                except kiwi.KiwiBloqueado as e:
                    print(f"{mes} {cod}: Kiwi {str(e)[:80]} (se salta)", flush=True)
                    p = None
                    break
            else:
                print(f"{mes} {cod}: caché ocupada (se salta)", flush=True)
                continue
            if not p:
                print(f"{mes} {cod}: sin vuelos", flush=True)
                continue
            r = {"p": round(p["total"]), "f": date.today().isoformat(), "aerolinea": p["aerolinea"], "ciudad": f"{p['ciudad']} (luego {como})",
                 "destino": p["destino"], "ida": p["ida"], "vuelta": p["vuelta"], "noches": p["noches"]}
            if p.get("orientativo"):
                r["e"] = True
            if p.get("tramos"):
                r["t"] = {k: rd.semana.tramo_corto(v) for k, v in p["tramos"].items()}
            nuevas[(mes, cod)] = r
            print(f"{mes} {cod}: {r['p']} € {r['aerolinea']} {r['destino']}", flush=True)
    return nuevas


def guardar(nuevas):
    """Con el candado de la fusión: relee, añade/mejora, comprueba que no se pierde nada y renombra un archivo aparte."""
    with open("/tmp/escapadas-fusion.lock", "w") as cand:
        fcntl.flock(cand, fcntl.LOCK_EX)
        almacen = rd.cargar()
        antes = {(m, c) for m, v in almacen.items() for c in v}
        puestas = 0
        for (mes, cod), r in nuevas.items():
            ya = (almacen.get(mes) or {}).get(cod)
            if ya is None or r["p"] <= ya.get("p", 10**9):
                almacen.setdefault(mes, {})[cod] = r
                puestas += 1
        if antes - {(m, c) for m, v in almacen.items() for c in v}:
            sys.exit("Se perdería algo: no se guarda nada.")
        tmp = rd.ALMACEN.with_suffix(".tmp")
        tmp.write_text(json.dumps(almacen, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(rd.ALMACEN)
    return puestas


def main(argv):
    nuevas = leer()
    if "--seco" in argv:
        print(f"{len(nuevas)} lecturas (seco: no se guarda).")
        return 0
    print(f"Guardadas {guardar(nuevas)} de {len(nuevas)}.", flush=True)
    for args in (["radar_datos.py", "--construir"], ["radar_larga.py", "--construir"]):
        subprocess.run([sys.executable, *args], cwd=rd.CARPETA, check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
