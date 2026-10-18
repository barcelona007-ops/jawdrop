"""
radar_datos.py — Datos reales del Radar único, tipo «Semana» (5-8 noches), país × mes (el usuario, 14-10-2026).

Por cada mes pedido lee Ryanair y Wizz (semana.py) y Kiwi (las demás aerolíneas, solo países con vuelo directo), se queda con la pareja ida+vuelta más barata de cada país y la
guarda con su fecha de lectura en datos/radar_semana.json (un mes nuevo sustituye al anterior del mismo mes).
Después reconstruye movil/cuadricula.json con esos precios REALES; los países/meses sin lectura salen vacíos («—»),
no se inventa nada. Kiwi añade Vueling, Turkish, easyJet… (precio estimado de la aerolínea, «≈» si es orientativo); solo vuelos directos.
El color solo depende de las horas de vuelo (semaforo.py), igual para escapada, semana o larga.

Uso:
  .venv\\Scripts\\python.exe radar_datos.py --mes 2027-09 [--mes 2027-10 ...]   # lee y guarda esos meses
  .venv\\Scripts\\python.exe radar_datos.py --meses 12                          # solo los meses que tocan (frescura.py), máx. 3 por pasada
  .venv\\Scripts\\python.exe radar_datos.py --meses 12 --todo                   # los 12, sin mirar la frescura
  .venv\\Scripts\\python.exe radar_datos.py --construir                         # solo reescribe cuadricula.json
"""
import json
import sys
from datetime import date
from pathlib import Path

import cuadricula_demo
import frescura
import ganga
import kiwi
import marcha
import radar_larga
import semana
import semaforo

VERSION = "0.14"
CARPETA = Path(__file__).resolve().parent
ALMACEN = CARPETA / "datos" / "radar_semana.json"          # última lectura de cada país y mes; SÍ va a git (la lectura diaria corre en GitHub Actions)
HISTORIAL = CARPETA / "datos" / "radar_historial.json"   # SÍ va a git: es la memoria de precios para detectar gangas
MAX_LECTURAS = 80                                          # por país y mes (unas 1,5 años a una por semana)
DIRECTOS = CARPETA / "datos" / "kiwi_directos.json"        # país -> {directo, f}: a qué países hay vuelo directo desde BCN (según Kiwi)
MAX_DESCUBRIR_POR_PASADA = 40                              # países a comprobar por pasada (una consulta cada uno)
REVISAR_SIN_DIRECTO_DIAS, REVISAR_CON_DIRECTO_DIAS = 45, 90
MAX_MESES_POR_PASADA = 3                                   # para repartir el trabajo entre días
NOCHES = (5, 8)
# Países sin aeropuerto (el usuario, 17-10-2026): se cuenta el vuelo al aeropuerto comercial más cercano del país vecino; el traslado hasta el país NO se suma
# (ya se cuadrará). código: (país vecino, aeropuertos que valen, cómo se llega desde el aeropuerto).
VIA_VECINO = {
    "LI": ("CH", {"ZRH"}, "tren y bus a Liechtenstein"), "MC": ("FR", {"NCE"}, "tren a Mónaco"), "SM": ("IT", {"RMI", "BLQ", "FRL"}, "bus a San Marino"),
    "VA": ("IT", {"FCO", "CIA"}, "metro o tren al Vaticano"), "AD": ("FR", {"TLS", "PGF"}, "bus a Andorra"),
}


def cargar():
    try:
        return json.loads(ALMACEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cargar_historial():
    try:
        return json.loads(HISTORIAL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def anotar_historial(historial, mes, res, hoy):
    """Añade la lectura de hoy de cada país a su historial (una por día; repetir el día la sustituye)."""
    h = historial.setdefault("semana", {}).setdefault(mes, {})
    for pais, r in res.items():
        lista = [x for x in h.get(pais, []) if x[0] != hoy]
        lista.append([hoy, r["p"]])
        h[pais] = lista[-MAX_LECTURAS:]
    HISTORIAL.parent.mkdir(exist_ok=True)
    HISTORIAL.write_text(json.dumps(historial, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def paises_con_directo(avisar=print):
    """Países a los que Kiwi ve vuelo directo desde BCN. Comprueba, por pasada, los que no se conocen o toca revisar
    (los más cercanos primero); el resto sale de datos/kiwi_directos.json. Una consulta por país comprobado."""
    try:
        memo = json.loads(DIRECTOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        memo = {}
    hoy = date.today()
    todos = sorted(((semaforo.km_aire(lat, lon), cod) for cod, lat, lon in cuadricula_demo.paises_del_mapa() if cod != "ES"))
    def toca(cod):
        r = memo.get(cod)
        if not r:
            return True
        edad = (hoy - date.fromisoformat(r["f"])).days
        return edad >= (REVISAR_CON_DIRECTO_DIAS if r["directo"] else REVISAR_SIN_DIRECTO_DIAS)
    pendientes = [cod for _, cod in todos if toca(cod)][:MAX_DESCUBRIR_POR_PASADA]
    for i, cod in enumerate(pendientes, 1):
        try:
            memo[cod] = {"directo": kiwi.tiene_directo("BCN", cod), "f": hoy.isoformat()}
        except kiwi.KiwiBloqueado as e:
            avisar(f"  Kiwi {cod}: {str(e)[:80]} (se salta)")
    if pendientes:
        DIRECTOS.parent.mkdir(exist_ok=True)
        DIRECTOS.write_text(json.dumps(memo, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
        avisar(f"  Kiwi: {len(pendientes)} países comprobados; con directo: {sum(r['directo'] for r in memo.values())} de {len(memo)} conocidos.")
    return sorted(c for c, r in memo.items() if r["directo"])


def leer_mes(mes, almacen, avisar=print):
    """Lee Ryanair y Wizz para el mes y guarda la mejor pareja de cada país. Devuelve nº de países con precio."""
    filas = semana.semana_paises(None, mes, NOCHES[0], NOCHES[1], avisar=lambda t: avisar(f"  {mes} {t}"))
    kiwi_paises = paises_con_directo(avisar)
    for i, pais in enumerate(kiwi_paises, 1):   # Kiwi: las demás aerolíneas (Vueling, Turkish, easyJet…); gana la pareja más barata
        avisar(f"  {mes} Kiwi {i}/{len(kiwi_paises)} {pais}")
        try:
            p = kiwi.semana_pais("BCN", pais, mes, NOCHES[0], NOCHES[1])
        except kiwi.KiwiBloqueado as e:
            avisar(f"  Kiwi {pais}: {str(e)[:80]} (se salta)")
            continue
        if p:
            filas.setdefault(pais, []).append(p)
    for cod, (vecino, aps, como) in VIA_VECINO.items():   # la mejor pareja que aterriza en un aeropuerto válido del vecino
        buenas = [x for x in filas.get(vecino, []) if x.get("destino") in aps]
        if buenas:
            m = min(buenas, key=lambda x: x["total"])
            filas[cod] = [dict(m, ciudad=f"{m['ciudad']} (luego {como})")]
    hoy = date.today().isoformat()
    res = {}
    for pais, lista in filas.items():
        if lista:
            m = min(lista, key=lambda x: x["total"])
            res[pais] = {"p": round(m["total"]), "f": hoy, "aerolinea": m["aerolinea"], "ciudad": m["ciudad"],
                         "destino": m["destino"], "ida": m["ida"], "vuelta": m["vuelta"], "noches": m["noches"]}
            if m.get("orientativo"):
                res[pais]["e"] = True
            if m.get("tramos"):   # detalle de cada vuelo para la ficha (hora, nº de vuelo, enlace); las lecturas antiguas no lo tienen
                res[pais]["t"] = {k: semana.tramo_corto(v) for k, v in m["tramos"].items()}
    anotar_historial(cargar_historial(), mes, res, hoy)
    almacen[mes] = res
    ALMACEN.parent.mkdir(exist_ok=True)
    ALMACEN.write_text(json.dumps(almacen, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(res)


def construir(almacen):
    """Escribe movil/cuadricula.json con las lecturas reales (huecos = sin dato)."""
    hoy = date.today()
    historial = cargar_historial().get("semana", {})
    meses = []
    y, m = hoy.year, hoy.month
    for _ in range(12):
        meses.append({"id": f"{y}-{m:02d}", "nombre": cuadricula_demo.NOMBRES[m], "anio": y})
        m += 1
        if m == 13:
            y, m = y + 1, 1
    filas = []
    con_dato = gangas = 0
    for cod, lat, lon in cuadricula_demo.paises_del_mapa():
        km = semaforo.km_aire(lat, lon)
        celdas = []
        for mes in meses:
            r = (almacen.get(mes["id"]) or {}).get(cod)
            if r:
                con_dato += 1
                previas = [(f, p) for f, p in historial.get(mes["id"], {}).get(cod, []) if f != r["f"]]
                g = ganga.evaluar(r["p"], previas)
                celda = {"p": r["p"], "c": semaforo.color(r["p"], km), "f": r["f"], "e": bool(r.get("e")),
                         "v": f"{r['ciudad']} · {r['aerolinea']} · {r['ida']} → {r['vuelta']} ({r['noches']} noches)"}
                celda.update(ci=r["ciudad"], ap=r["destino"], a=r["aerolinea"], i=r["ida"], r=r["vuelta"], n=r["noches"])   # para la ficha
                if r.get("t"):
                    celda["t"] = r["t"]
                if g["estado"] == "ganga":
                    celda.update(g=1, sem=celda["c"], c="ganga", mediana=g["mediana"], pct=g["pct"])
                    gangas += 1
                elif g["estado"] == "normal":
                    celda.update(mediana=g["mediana"], pct=g["pct"])
                celdas.append(celda)
            else:
                celdas.append({"p": None, "c": "", "f": None, "e": False})
        filas.append({"cod": cod, "km": round(km), "h": round(semaforo.horas(km), 1), "tipo": semaforo.tipo(km),
                      "celdas": celdas})
    # Países de viaje largo con escalas (Tailandia): su fila sale de radar_larga (Kiwi, hasta 2 escalas, 25-35 noches), precio cerrado ida + vuelta.
    larga = radar_larga.cargar()
    for zid, z in radar_larga.ZONAS.items():
        fila = next((f for f in filas if f["cod"] == z.get("cuadricula")), None)
        if not fila:
            continue
        for i, mes in enumerate(meses):
            r = (larga.get(zid) or {}).get(mes["id"])
            if not r or not r.get("combos"):
                continue
            c = r["combos"][0]
            previa = fila["celdas"][i].get("p")
            if previa is not None and previa <= c["total"] and not z.get("sustituye"):
                continue   # el directo ya es más barato (países con vuelo directo desde BCN)
            fila["celdas"][i] = {"p": c["total"], "c": semaforo.color(c["total"], fila["km"], z.get("topes")), "f": r["f"], "e": True,
                                 "v": f"{c['ida']['ciudad']} → {c['vuelta']['desde_ciudad']} · {' + '.join(c['ida']['aerolineas'])} · {c['noches']} noches" + (f" · luego {c['hub']['ap']} → Bangkok" if c.get("hub") else "") + (" · vía Madrid (tren + vuelo)" if c.get("madrid") else ""),
                                 "esc": {"noches": c["noches"], "ida": c["ida"], "vuelta": c["vuelta"], "hub": c.get("hub"), "madrid": c.get("madrid"), "origen": c.get("origen", "BCN")}}
            con_dato += 1
        fila["esc"] = True
    # Celdas rescatadas (18-10-2026): se perdió parte de radar_larga.json; estas celdas salen de la cuadrícula publicada antes de perderla.
    # Solo rellenan huecos: cualquier lectura real nueva manda sobre ellas.
    try:
        rescate = json.loads((Path(__file__).resolve().parent / "datos" / "cuadricula_rescatada.json").read_text(encoding="utf-8"))["celdas"]
    except (OSError, ValueError, KeyError):
        rescate = {}
    for f in filas:
        for i, mes in enumerate(meses):
            c = (rescate.get(f["cod"]) or {}).get(mes["id"])
            if c and f["celdas"][i].get("p") is None:
                f["celdas"][i] = c
                con_dato += 1
    for f in filas:
        if f["cod"] in radar_larga.AVISOS:   # peligro / sin ruta (el usuario, 17-10-2026)
            t, m = radar_larga.AVISOS[f["cod"]]
            f["aviso"] = {"t": t, "m": m}
    filas.sort(key=lambda f: f["cod"])
    salida = {"version": VERSION, "ejemplo": False, "viaje": "semana", "noches": list(NOCHES),
              "visitados": cuadricula_demo.visitados(), "generado": hoy.isoformat(), "leyenda": semaforo.leyenda(),
              "meses": meses, "paises": filas}
    tmp = cuadricula_demo.SALIDA.with_suffix(".tmp")   # escribe y renombra: si falla (disco lleno) queda la cuadrícula anterior
    tmp.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    tmp.replace(cuadricula_demo.SALIDA)
    print(f"{len(filas)} países × {len(meses)} meses: {con_dato} casillas con precio real, {gangas} gangas → {cuadricula_demo.SALIDA}")


def main(argv):
    meses = [argv[i + 1] for i, a in enumerate(argv) if a == "--mes"]
    if "--meses" in argv:
        n = int(argv[argv.index("--meses") + 1])
        y, m = date.today().year, date.today().month
        for _ in range(n):
            meses.append(f"{y}-{m:02d}")
            m += 1
            if m == 13:
                y, m = y + 1, 1
    almacen = cargar()
    if "--meses" in argv and "--todo" not in argv:
        # solo los meses cuya lectura ya no vale según su antelación, los más atrasados primero, con tope por pasada
        def ultima(mes):
            fechas = [r["f"] for r in (almacen.get(mes) or {}).values()]
            return max(fechas) if fechas else None
        due = [mm for mm in meses if frescura.toca(mm, ultima(mm))]
        due.sort(key=lambda mm: ultima(mm) or "")
        print(f"Meses que tocan leer: {len(due)} de {len(meses)}; esta pasada: {min(len(due), MAX_MESES_POR_PASADA)}.")
        meses = due[:MAX_MESES_POR_PASADA]
    fallos = []
    for i, mes in enumerate(meses):
        print(f"{mes}: leyendo Ryanair y Wizz…")
        marcha.avisar("semana", i, len(meses), mes)
        try:
            print(f"{mes}: {leer_mes(mes, almacen)} países con precio.")
        except Exception as e:   # una fuente cerrada o caída: ese mes no se toca (ni precios ni historial) y se sigue con el resto
            fallos.append(mes)
            print(f"{mes}: NO se ha leído ({type(e).__name__}: {str(e)[:120]}). Se conserva la lectura anterior.")
    if meses:
        marcha.avisar("semana", len(meses), len(meses), "", fin=True)
    if meses or "--construir" in argv:
        construir(almacen)
    else:
        print(__doc__)
    if fallos:
        print(f"Meses con fallo: {', '.join(fallos)}")
        return 1 if len(fallos) == len(meses) else 0   # fallo total = el trabajo falla (y GitHub avisa); parcial = se guarda lo leído
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
