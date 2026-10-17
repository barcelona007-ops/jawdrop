"""
radar_larga.py — Radar «Larga»: viajes largos con escala y open-jaw por zonas (el usuario, 15-10-2026). Piloto: sudeste asiático.

Para cada zona (grupo de países) y mes de ida: las mejores combinaciones ida + vuelta (25-35 noches, hasta 2 escalas, billetes sueltos permitidos,
llegar a un aeropuerto y volver desde otro de la zona = open-jaw) con el PRECIO CERRADO de los dos vuelos desde y hasta BCN. Como en Flash: ida y vuelta
son dos tarjetas con su enlace. El vuelo interno entre los dos aeropuertos NO se suma (es parte del viaje); solo se enseña aparte como referencia.
Precios de Kiwi (solo ida, orientativos). Guarda con fecha en datos/radar_larga.json y escribe movil/larga.json (lo que lee la app).

Uso:  .venv\\Scripts\\python.exe radar_larga.py --mes 2027-02 [--mes 2027-03]   |   --meses 12 [--zona vn] [--max 30] (solo los que tocan, máx. 6 por pasada salvo --max)   |   --construir
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import escalas
import frescura
import kiwi
import marcha
import trenes

VERSION = "0.15"
CARPETA = Path(__file__).resolve().parent
ALMACEN = CARPETA / "datos" / "radar_larga.json"
SALIDA = CARPETA / "movil" / "larga.json"
MAX_MESES_POR_PASADA = 30   # ~75 s cada uno: ~40 min por pasada diaria (en jawdrop los minutos no cuentan). Primera carga grande: --max 120
TOP = 6   # combinaciones que se guardan por zona y mes (la más barata de cada pareja de aeropuertos)
NOMBRES_MES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

ZONAS = {
    "sudeste": {"nombre": "Sudeste asiático", "paises": ["TH", "MY", "SG", "VN", "ID", "PH", "KH"], "paradas": 2, "noches": (25, 35)},
    # Tailandia sola: alimenta su fila de la cuadrícula del Radar (radar_datos.py), no la pestaña «Larga» (16-10-2026). Se busca por país (Country:TH).
    "tailandia": {"nombre": "Tailandia", "paises": ["TH"], "paradas": 2, "noches": (25, 35), "cuadricula": "TH",
                  # Opción «hub + low cost»: llegar a KUL o SIN (mismo aeropuerto de ida y vuelta) y seguir a BKK en un vuelo suelto, que SÍ se suma al precio.
                  "hub_paises": ["MY", "SG"], "hubs": ["KUL", "SIN"], "final": "BKK"},
}

# Países lejanos con escalas para la cuadrícula: dar de alta uno = una línea aquí (código: (nombre, escalas, topes verde/ámbar o None = los del semáforo largo)).
# Mismas 25-35 noches que Tailandia. Micronesia (FM) probada el 16-10-2026 con 3 escalas y por aeropuertos: Kiwi no devuelve nada (si algún día
# sale, añadir "FM": ("Micronesia", 3, None)). Orden = prioridad de lectura.
PAISES_LARGOS = {
    "VN": ("Vietnam", 2, None), "MY": ("Malasia", 2, None), "SG": ("Singapur", 2, None), "PH": ("Filipinas", 2, None),
    "ID": ("Indonesia", 2, None), "KH": ("Camboya", 2, None),
    "JP": ("Japón", 2, None), "KR": ("Corea del Sur", 2, None), "IN": ("India", 2, None), "LK": ("Sri Lanka", 2, None),
    # Sin directo desde BCN pero sí desde MAD (comprobado con Kiwi el 16-10-2026): casi seguro saldrán con origen Madrid (la ficha lo avisa).
    "ZA": ("Sudáfrica", 2, None), "ET": ("Etiopía", 2, None), "TZ": ("Tanzania", 2, None), "NG": ("Nigeria", 2, None), "MU": ("Mauricio", 2, None),
    "PA": ("Panamá", 2, None), "CR": ("Costa Rica", 2, None), "DO": ("Rep. Dominicana", 2, None), "GT": ("Guatemala", 2, None),
    "EC": ("Ecuador", 2, None), "BO": ("Bolivia", 2, None), "PY": ("Paraguay", 2, None), "UY": ("Uruguay", 2, None),
    "VE": ("Venezuela", 2, None), "PR": ("Puerto Rico", 2, None), "LB": ("Líbano", 2, None),
}
# Lejanos CON directo desde BCN (16-10-2026, idea Colombia): el directo suele ser el más caro; se compara con escalas y con origen MAD en las
# 15-21 noches (el usuario: a Colombia y similares una semana no vale con escalas; con hasta 2 escalas entra también el directo). Su lectura SUSTITUYE al directo de 5-8 noches
# de la cuadrícula (aunque sea más cara: son otro tipo de viaje). Orden = prioridad de lectura.
PAISES_CON_DIRECTO = {
    "CO": "Colombia", "MX": "México", "PE": "Perú", "CL": "Chile", "AR": "Argentina", "BR": "Brasil",
    "HN": "Honduras", "SV": "El Salvador", "CN": "China", "HK": "Hong Kong",
}
# A 6-8,5 h de BCN (Nueva York ~8 h, Toronto/Montreal, Dubái, Doha) sí valen 4-8 noches (el usuario, 17-10): directo, o UNA escala corta, desde BCN o vía Madrid
# (tren + vuelo; en Nueva York será un caso raro). Solo sustituyen al directo de la cuadrícula si salen más baratas. Escalas de 2-4 h aceptadas, sin tope.
PAISES_MEDIOS = {"US": "Estados Unidos", "CA": "Canadá", "AE": "Emiratos Árabes", "QA": "Catar"}
for _cod, (_nombre, _paradas, _topes) in PAISES_LARGOS.items():
    ZONAS[_cod.lower()] = {"nombre": _nombre, "paises": [_cod], "paradas": _paradas, "noches": (25, 35), "cuadricula": _cod,
                           **({"topes": _topes} if _topes else {})}
# Países por desbloquear desde Madrid (16-10-2026, lista del usuario): duración propia por zona. Cáucaso/Asia central 5-9 noches, África occidental 4-8,
# África oriental 10-15, Caribe 15-28 (el usuario: 15 como mínimo, no descartar 3-4 semanas). Una escala (Kiwi con 2 escalas tarda más y no cambia el orden).
PAISES_PENDIENTES = {
    **{c: (n, 1, (5, 9)) for c, n in {"UZ": "Uzbekistán", "AZ": "Azerbaiyán", "KZ": "Kazajistán", "KG": "Kirguistán", "TJ": "Tayikistán"}.items()},
    **{c: (n, 1, (4, 8)) for c, n in {"SN": "Senegal", "CV": "Cabo Verde", "GM": "Gambia", "MR": "Mauritania", "CI": "Costa de Marfil", "GH": "Ghana",
                                      "BJ": "Benín", "TG": "Togo"}.items()},
    **{c: (n, 1, (10, 15)) for c, n in {"KE": "Kenia", "RW": "Ruanda", "UG": "Uganda", "DJ": "Yibuti", "SC": "Seychelles"}.items()},
    **{c: (n, 1, (15, 28)) for c, n in {"CU": "Cuba", "BS": "Bahamas", "JM": "Jamaica", "BB": "Barbados", "TT": "Trinidad y Tobago", "AG": "Antigua y Barbuda",
                                        "KN": "San Cristóbal y Nieves", "LC": "Santa Lucía"}.items()},
}
for _cod, (_nombre, _paradas, _noches) in PAISES_PENDIENTES.items():
    ZONAS[_cod.lower()] = {"nombre": _nombre, "paises": [_cod], "paradas": _paradas, "noches": _noches, "cuadricula": _cod}
for _cod, _nombre in PAISES_CON_DIRECTO.items():
    ZONAS[_cod.lower()] = {"nombre": _nombre, "paises": [_cod], "paradas": 2, "noches": (15, 21), "cuadricula": _cod, "sustituye": True, "margen": 0.20, "madrid_directo": False}
for _cod, _nombre in PAISES_MEDIOS.items():
    ZONAS[_cod.lower()] = {"nombre": _nombre, "paises": [_cod], "paradas": 1, "noches": (4, 8), "cuadricula": _cod, "margen": 0.20}


# Madrid como segundo origen (16-10-2026): tren Barcelona-Madrid + vuelo desde/hasta Madrid. Desde 17-10-2026 el tren es REAL (trenes.py: horarios GTFS de Renfe y Ouigo + precio de Ouigo; sin precio de Renfe/Iryo).
MADRID = True
ANTELACION_H = 6.0       # ida: el tren debe llegar a Madrid al menos tantas horas antes del vuelo (el usuario, 17-10-2026, por la situación ferroviaria)
NOCHE_MADRID = 60        # € ESTIMADOS de una noche en Madrid cuando ningún tren del mismo día llega con esa antelación (se va el día antes y se suma al total)
MARGEN_MIN = 2.0         # vuelta: menos horas de colchón que esto = aviso rojo


def _h(hhmm):
    return int(hhmm[:2]) + int(hhmm[3:5]) / 60


def _tramo_tren(fecha, sentido, hora_vuelo):
    """Mejor tren para llegar al vuelo (ida: llegada a Madrid ≥ ANTELACION_H antes del vuelo; si ese día no hay ninguno, el del día anterior + NOCHE_MADRID)
    o salir tras él (vuelta: salida ≥ llegada del vuelo + 1 h)."""
    r = _tren_dia(fecha, sentido, hora_vuelo)
    if sentido == "BCN-MAD" and r["aviso"]:
        antes = _tren_dia((date.fromisoformat(fecha) - timedelta(days=1)).isoformat(), sentido, hora_vuelo + 24)
        if antes["elegida"] and not antes["aviso"]:
            antes["noche"] = NOCHE_MADRID
            antes["_avisos"] = r["_avisos"] + antes["_avisos"]
            return antes
    return r


def _tren_dia(fecha, sentido, hora_vuelo):
    """Mejor tren de ese día (una opción por operador).
    Una opción por operador (con margen y la más barata; sin precio, la que deja más colchón). `elegida` = la más barata con precio real."""
    todos, avisos = trenes.opciones(fecha, sentido)
    for t in todos:
        t["colchon"] = round((hora_vuelo - _h(t["llega"])) if sentido == "BCN-MAD" else (_h(t["sale"]) - (hora_vuelo + 1.0)), 1)
    minimo = ANTELACION_H if sentido == "BCN-MAD" else MARGEN_MIN   # ida: antelación exigida; vuelta: colchón deseado
    validos = [t for t in todos if t["colchon"] >= (ANTELACION_H if sentido == "BCN-MAD" else 0)]
    buenos = [t for t in validos if t["colchon"] >= minimo] or validos
    mejor = {}
    for t in sorted(buenos, key=lambda t: (t["precio"] is None, t["precio"] or 0, -t["colchon"])):
        mejor.setdefault(t["op"], t)
    ops = sorted(mejor.values(), key=lambda t: (t["precio"] is None, t["precio"] or 0))
    elegida = next((t for t in ops if t["precio"] is not None), None)
    ref = elegida or (ops[0] if ops else None)   # el aviso rojo mira el tren elegido; sin precio, el de más colchón disponible
    return {"fecha": fecha, "opciones": ops, "elegida": elegida, "_avisos": avisos,
            "colchon": ref["colchon"] if ref else None, "aviso": (not ref) or ref["colchon"] < minimo}


def _con_tren(c):
    """Combinación con origen/destino MAD: suma el tren REAL (horarios GTFS + precio Ouigo; Renfe/Iryo sin precio, con aviso) y calcula el colchón
    en ida (tren → vuelo) y vuelta (vuelo → tren). Si no hay precio real, no se suma nada y `tren_sin_precio` lo dice (nunca un precio de relleno)."""
    llega = c["vuelta"]["llega"]                                     # "MM-DD HH:MM"
    f_vuelta = date.fromisoformat(c["vuelta"]["fecha"])
    f_llega = date(f_vuelta.year + (llega[:2] < c["vuelta"]["fecha"][5:7]), int(llega[:2]), int(llega[3:5]))
    ida = _tramo_tren(c["ida"]["fecha"], "BCN-MAD", _h(c["ida"]["sale"]))
    vuelta = _tramo_tren(f_llega.isoformat(), "MAD-BCN", _h(llega[-5:]))
    avisos = {(a["operador"], a["motivo"]): a for x in (ida, vuelta) for a in x.pop("_avisos")}   # sin repetir entre ida y vuelta
    precios = [x["elegida"]["precio"] for x in (ida, vuelta) if x["elegida"]]
    c["total"] += sum(precios) + ida.get("noche", 0)
    c["madrid"] = {"ida": ida, "vuelta": vuelta, "avisos": list(avisos.values()), "tren": round(sum(precios)), "noche": ida.get("noche", 0), "tren_sin_precio": len(precios) < 2,
                   "colchon_ida": ida["colchon"], "colchon_vuelta": vuelta["colchon"], "aviso_ida": ida["aviso"], "aviso_vuelta": vuelta["aviso"]}
    return c


def enlace(desde, hasta, dia):
    """Búsqueda de solo ida en Google Flights para ese día (sirve para ver el precio real y reservar; el viaje lleva varias aerolíneas)."""
    return f"https://www.google.com/travel/flights?q=Flights%20to%20{hasta}%20from%20{desde}%20on%20{dia}%20oneway"


def _tramo(it, sentido):
    t = it["tramos"]
    return {"desde": t[0]["desde"], "hasta": t[-1]["hasta"], "ciudad": it["ciudad"],
            "fecha": it["salida"], "sale": t[0]["sale_local"][11:16], "llega": t[-1]["llega_local"][5:16].replace("T", " "),
            "precio": round(it["precio_kiwi"]), "horas": it["horas_total"], "aerolineas": it["aerolineas"],
            "sueltos": len(it["aerolineas"]) > 1,
            "escalas": [{"ap": e["aeropuerto"], "ciudad": escalas.HUBS.get(e["aeropuerto"], e["ciudad"]), "pais": e["pais"], "horas": e["horas"],
                         "tipo": e["tipo"], "nuevo": e["pais_nuevo"]} for e in it["escalas"]],
            "vuelos": [[x["desde"], x["hasta"], x["sale_local"][:16].replace("T", " "), x["llega_local"][:16].replace("T", " "), x["aerolinea"]] for x in t],   # cada vuelo suelto: para tirar del hilo en la aerolínea
            "enlace": enlace(t[0]["desde"], t[-1]["hasta"], it["salida"])}


def _tramo_hub(desde, hasta, d1, d2):
    """Vuelo directo más barato desde→hasta entre las fechas d1 y d2 (inclusive), o None."""
    try:
        vs = kiwi.rango([f"Airport:{desde}"], [f"Airport:{hasta}"], d1.isoformat(), d2.isoformat(), excluir=(), limite=10)
    except kiwi.KiwiBloqueado:
        return None
    if not vs:
        return None
    v = min(vs, key=lambda x: x["precio"])
    return {"desde": desde, "hasta": hasta, "precio": round(v["precio"]), "aerolinea": v["aerolinea"], "fecha": v["salida"][:10]}


def _con_hub(z, mes, avisar):
    """Llegar a un hub (KUL, SIN) y seguir al destino final (BKK) en un vuelo aparte: la ida y la vuelta de BCN al hub + los dos saltos, todo sumado."""
    out = _leer(z["hub_paises"], z, mes, avisar, solo=lambda c: c["mismo_aeropuerto"] and c["ida"]["destino"] in z["hubs"])
    res = []
    for c in out:
        h, fin = c["aps"][0], z["final"]
        di, dv = date.fromisoformat(c["ida"]["fecha"]), date.fromisoformat(c["vuelta"]["fecha"])
        avisar(f"  {mes} hub {h} → {fin}")
        a = _tramo_hub(h, fin, di + timedelta(days=1), di + timedelta(days=3))
        b = _tramo_hub(fin, h, dv - timedelta(days=3), dv - timedelta(days=1))
        if not a or not b:
            continue
        c["total"] += a["precio"] + b["precio"]
        c["hub"] = {"ap": h, "ida": a, "vuelta": b}
        c["interno"] = None
        res.append(c)
    return res


def _priorizar(out, margen, madrid_directo=True):
    """Reglas del usuario para destinos medios (17-10-2026). Sencilla = salida de BCN con UNA aerolínea (directo o escala planificada). Madrid solo vale con vuelo
    DIRECTO desde Madrid (el total ya lleva el tren; en los lejanos basta UNA aerolínea). Madrid y los billetes sueltos (otra aerolínea, p. ej. Vueling a un hub europeo + transatlántico) solo
    ganan a la mejor sencilla si cuestan `margen` (20 %) menos o más barato; si no, manda la sencilla. El resto sigue ordenado por precio."""
    def sencilla(c):
        return c.get("origen") != "MAD" and not c["ida"]["sueltos"] and not c["vuelta"]["sueltos"]
    def madrid_ok(c):
        if madrid_directo:
            return not c["ida"]["escalas"] and not c["vuelta"]["escalas"]
        return not c["ida"]["sueltos"] and not c["vuelta"]["sueltos"]
    out = [c for c in out if c.get("origen") != "MAD" or madrid_ok(c)]
    base = [c for c in out if sencilla(c)]
    if not base:
        return out
    mejor = next((c for c in out if not sencilla(c) and c["total"] <= base[0]["total"] * (1 - margen)), base[0])
    return [mejor] + [c for c in out if c is not mejor]


def leer(zona_id, mes, avisar=print):
    z = ZONAS[zona_id]
    out = _leer(z["paises"], z, mes, avisar)
    if MADRID and z.get("madrid", True):
        try:
            out += [_con_tren(c) for c in _leer(z["paises"], z, mes, avisar, origen="MAD")]
        except kiwi.KiwiBloqueado:
            avisar(f"  {mes} Madrid: Kiwi bloqueado, se salta")
        for c in out:
            c["total"] = round(c["total"])
        out.sort(key=lambda x: x["total"])
    if z.get("hubs"):
        out += _con_hub(z, mes, avisar)
        out.sort(key=lambda x: x["total"])
    if z.get("margen"):
        out = _priorizar(out, z["margen"], z.get("madrid_directo", True))
    return out


def _leer(paises, z, mes, avisar, solo=None, origen="BCN"):
    combos, idas, vueltas = escalas.openjaw(paises, mes, z["noches"], z["paradas"], origen)
    if solo:
        combos = [c for c in combos if solo(c)]
    ciudad_de = {}
    for it in idas:
        ciudad_de[it["destino"]] = it["ciudad"]
    for it in vueltas:
        ciudad_de.setdefault(it["tramos"][0]["desde"], it["tramos"][0].get("ciudad_desde") or it["tramos"][0]["desde"])
    out = []
    for c in escalas.con_tramo_interno(combos, max_pares=TOP, avisar=lambda t: avisar(f"  {mes} {t}")):
        i, v = c["ida"], c["vuelta"]
        a, b = i["destino"], v["tramos"][0]["desde"]
        ida, vuelta = _tramo(i, "ida"), _tramo(v, "vuelta")
        ida["ciudad"] = ciudad_de.get(a, a)
        vuelta["ciudad"] = ciudad_de.get(b, b)
        vuelta["desde_ciudad"] = vuelta["ciudad"]   # en la vuelta, «ciudad» = de dónde sales
        vuelta["ciudad"] = "Madrid" if origen == "MAD" else "Barcelona"
        it = c["interno"]
        out.append({"total": round(c["total"]), "origen": origen, "noches": c["noches"], "mismo": a == b, "aps": [a, b], "ida": ida, "vuelta": vuelta,
                    "interno": ({"desde": a, "hasta": b, "precio": round(it["precio"]), "aerolinea": it["aerolinea"], "fecha": it["fecha"]}
                                if it and not it.get("mismo") else None)})
    out.sort(key=lambda x: x["total"])
    return out


def cargar():
    try:
        return json.loads(ALMACEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guardar(almacen):
    ALMACEN.parent.mkdir(exist_ok=True)
    ALMACEN.write_text(json.dumps(almacen, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def construir(almacen):
    zonas = []
    for zid, z in ZONAS.items():
        if z.get("cuadricula"):
            continue   # esas zonas solo se ven en la cuadrícula
        meses = []
        for mes, r in sorted((almacen.get(zid) or {}).items()):
            if r.get("combos"):
                meses.append({"id": mes, "nombre": NOMBRES_MES[int(mes[5:])], "anio": int(mes[:4]), "f": r["f"], "combos": r["combos"]})
        if meses:
            zonas.append({"id": zid, "nombre": z["nombre"], "paises": z["paises"], "noches": list(z["noches"]), "meses": meses})
    SALIDA.write_text(json.dumps({"version": VERSION, "generado": date.today().isoformat(), "zonas": zonas}, ensure_ascii=False,
                                 separators=(",", ":")), encoding="utf-8")
    print(f"{sum(len(z['meses']) for z in zonas)} zona-meses → {SALIDA}")


def main(argv):
    almacen = cargar()
    meses = [argv[i + 1] for i, a in enumerate(argv) if a == "--mes"]
    if "--meses" in argv:
        n = int(argv[argv.index("--meses") + 1])
        y, m = date.today().year, date.today().month
        todos = []
        for _ in range(n):
            todos.append(f"{y}-{m:02d}")
            m += 1
            if m == 13:
                y, m = y + 1, 1
        def ultima(zid, mm):
            return (almacen.get(zid) or {}).get(mm, {}).get("f")
        solo = [argv[i + 1] for i, a in enumerate(argv) if a == "--zona"]
        tope = int(argv[argv.index("--max") + 1]) if "--max" in argv else MAX_MESES_POR_PASADA
        due = sorted(((ultima(zid, mm) or "", zid, mm) for zid in ZONAS if not solo or zid in solo
                      for mm in todos if frescura.toca(mm, ultima(zid, mm))))
        print(f"Zona-meses que tocan: {len(due)}; esta pasada: {min(len(due), tope)}.")
        pares = [(zid, mm) for _, zid, mm in due[:tope]]
    else:
        pares = [(zid, mm) for zid in ZONAS for mm in meses]
    fallos = 0
    for i, (zid, mm) in enumerate(pares):
        print(f"{zid} {mm}: leyendo Kiwi…")
        marcha.avisar("larga", i, len(pares), f"{zid} {mm}")
        try:
            almacen.setdefault(zid, {})[mm] = {"f": date.today().isoformat(), "combos": leer(zid, mm)}
            guardar(almacen)
            print(f"{zid} {mm}: {len(almacen[zid][mm]['combos'])} combinaciones; la más barata {almacen[zid][mm]['combos'][0]['total']} €"
                  if almacen[zid][mm]["combos"] else f"{zid} {mm}: sin combinaciones.")
        except Exception as e:
            fallos += 1
            print(f"{zid} {mm}: NO se ha leído ({type(e).__name__}: {str(e)[:120]}). Se conserva la lectura anterior.")
    if pares:
        marcha.avisar("larga", len(pares), len(pares), "", fin=True)
    if pares or "--construir" in argv:
        construir(almacen)
    else:
        print(__doc__)
    return 1 if pares and fallos == len(pares) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
