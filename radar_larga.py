"""
radar_larga.py — Radar «Larga»: viajes largos con escala y open-jaw por zonas (el usuario, 15-10-2026). Piloto: sudeste asiático.

Para cada zona (grupo de países) y mes de ida: las mejores combinaciones ida + vuelta (25-35 noches, hasta 2 escalas, billetes sueltos permitidos,
llegar a un aeropuerto y volver desde otro de la zona = open-jaw) con el PRECIO CERRADO de los dos vuelos desde y hasta BCN. Como en Flash: ida y vuelta
son dos tarjetas con su enlace. El vuelo interno entre los dos aeropuertos NO se suma (es parte del viaje); solo se enseña aparte como referencia.
Precios de Kiwi (solo ida, orientativos). Guarda con fecha en datos/radar_larga.json y escribe movil/larga.json (lo que lee la app).

Uso:  .venv\\Scripts\\python.exe radar_larga.py --mes 2027-02 [--mes 2027-03]   |   --meses 12 [--zona vn] [--max 30] (solo los que tocan, máx. 6 por pasada salvo --max)   |   --construir
"""
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import aeropuertos
import escalas
import frescura
import kiwi
import marcha
import trenes

VERSION = "0.26"
CARPETA = Path(__file__).resolve().parent
ALMACEN = CARPETA / "datos" / "radar_larga.json"
SALIDA = CARPETA / "movil" / "larga.json"
PRESUPUESTO_ACTIONS = 180 * 60   # segundos de lectura por pasada en jawdrop (la semana ya gasta ~30 min y el trabajo tiene tope de 340)
MAX_MESES_POR_PASADA = 60   # ~75 s cada uno: ~40 min por pasada diaria (en jawdrop los minutos no cuentan). Primera carga grande: --max 120
EN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"   # jawdrop: lee desde el mes MÁS LEJANO y con tope 400 y presupuesto de 180 min (con pausa 1 s de kiwi.py una casilla tarda ~10-90 s; un trabajo no puede pasar de 5,6 h o perdería lo leído); el PC lee desde el más cercano, así no se pisan
REFRESCO_CADA = 5   # lecturas entre reconstrucciones de movil/cuadricula.json (3 s cada una): la cuadrícula se va llenando mientras se lee
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
# Más países por regiones (17-10-2026, sondeo de Kiwi `sondeo_paises.py`: ven BCN/MAD con ≤2 escalas 69 de 75). Duración (el usuario, 17-10): Oriente Medio y Asia central
# 5-9, África occidental 4-8, África central/oriental 10-15, África austral 12-20, Asia sur/sudeste 15-30 (el usuario, 17-10: mínimo 15), Caribe y Guayanas 15-28, Oceanía mínimo 25 (25-35).
PAISES_REGIONES = {
    **{c: (n, 2, (5, 9)) for c, n in {"AF": "Afganistán", "BH": "Baréin", "OM": "Omán", "IQ": "Irak", "SY": "Siria", "PK": "Pakistán", "TM": "Turkmenistán",
                                      "LY": "Libia"}.items()},
    **{c: (n, 2, (4, 8)) for c, n in {"BF": "Burkina Faso", "ML": "Mali", "NE": "Níger", "GN": "Guinea", "GW": "Guinea-Bisáu", "SL": "Sierra Leona",
                                      "LR": "Liberia", "ST": "Santo Tomé y Príncipe", "TD": "Chad"}.items()},
    **{c: (n, 2, (10, 15)) for c, n in {"CM": "Camerún", "CF": "Rep. Centroafricana", "CG": "Congo", "CD": "RD Congo", "GQ": "Guinea Ecuatorial", "GA": "Gabón",
                                        "BI": "Burundi", "ER": "Eritrea", "SO": "Somalia", "SS": "Sudán del Sur", "SD": "Sudán", "KM": "Comoras"}.items()},
    **{c: (n, 2, (12, 20)) for c, n in {"AO": "Angola", "BW": "Botsuana", "ZM": "Zambia", "ZW": "Zimbabue", "MZ": "Mozambique", "NA": "Namibia", "MG": "Madagascar",
                                        "MW": "Malaui", "LS": "Lesoto", "SZ": "Esuatini"}.items()},
    **{c: (n, 2, (15, 30)) for c, n in {"BD": "Bangladés", "BT": "Bután", "BN": "Brunéi", "MV": "Maldivas", "MN": "Mongolia", "MM": "Birmania", "NP": "Nepal",
                                        "TL": "Timor Oriental", "KP": "Corea del Norte", "TW": "Taiwán", "MO": "Macao", "LA": "Laos"}.items()},
    **{c: (n, 2, (15, 28)) for c, n in {"BZ": "Belice", "NI": "Nicaragua", "HT": "Haití", "DM": "Dominica", "GD": "Granada", "VC": "San Vicente y las Granadinas",
                                        "GY": "Guyana", "SR": "Surinam"}.items()},
    **{c: (n, 2, (25, 35)) for c, n in {"AU": "Australia", "NZ": "Nueva Zelanda", "FJ": "Fiyi", "KI": "Kiribati", "MH": "Islas Marshall", "NR": "Nauru",
                                        "PW": "Palaos", "PG": "Papúa Nueva Guinea", "WS": "Samoa", "SB": "Islas Salomón", "TO": "Tonga", "VU": "Vanuatu"}.items()},
}
# Territorios que el sondeo de Kiwi sí ve (17-10-2026, `datos/sondeo_paises.json`) y que tienen casilla en el mapa. Duración: Pacífico 25-35 como Oceanía, Groenlandia
# como Oriente Medio/Asia central (5-9), islas británicas del Canal y Man (con escala en Londres/Manchester) 4-8. Palestina, Sáhara Occ., Falkland...: Kiwi no los ve.
PAISES_REGIONES.update({
    "GL": ("Groenlandia", 2, (5, 9)), "PF": ("Polinesia Francesa", 2, (25, 35)), "NC": ("Nueva Caledonia", 2, (25, 35)),
    "GG": ("Guernsey", 1, (4, 8)), "JE": ("Jersey", 1, (4, 8)), "IM": ("Isla de Man", 1, (4, 8)),
    "XK": ("Kosovo", 1, (4, 8)), "BA": ("Bosnia y Herzegovina", 1, (4, 8)),   # sin directo desde BCN (Kiwi, 15-10): se leen con escala (19-10)
})
for _cod, (_nombre, _paradas, _noches) in PAISES_REGIONES.items():
    ZONAS[_cod.lower()] = {"nombre": _nombre, "paises": [_cod], "paradas": _paradas, "noches": _noches, "cuadricula": _cod}

# Avisos que salen en la cuadrícula (el usuario, 17-10): «peligro» = hay vuelo comercial pero NO es recomendable viajar (consultar Exteriores); «sinruta» = sin vuelo útil.
_PEL = "Hay vuelo comercial, pero viajar no es recomendable. Mira las recomendaciones del Ministerio de Exteriores antes de decidir."
AVISOS = {
    **{c: ("peligro", _PEL) for c in "AF IQ SY LY SS SO SD CF ML BF NE TD HT LB".split()},
    "KP": ("peligro", "Cerrado al turismo ahora; se espera que reabra vía China (Pekín-Pionyang). El precio es solo hasta Pekín-Pionyang según Kiwi y no es recomendable ir. Mira Exteriores."),
    "BY": ("sinruta", "Sin vuelo en Kiwi. Se puede entrar por tierra desde Polonia o Lituania (frontera lenta, visado) o vía un tercer país. Por estudiar, no se lee aún."),
    "RU": ("sinruta", "Sin vuelo en Kiwi desde la UE, pero se entra vía Emiratos, China, Estambul, Belgrado o Ereván (visado). Por estudiar, no se lee aún."),
    "IR": ("sinruta", "Sin ruta: Kiwi no encuentra vuelos y viajar no es recomendable. Mira Exteriores."),
    "YE": ("sinruta", "Sin ruta: no hay vuelos comerciales útiles (guerra) y viajar no es recomendable."),
    "FM": ("sinruta", "Sin precio: Kiwi no encuentra vuelos. Se llega vía Guam u Honolulu; no se ha leído."),
}
for _cod, _nombre in PAISES_CON_DIRECTO.items():
    ZONAS[_cod.lower()] = {"nombre": _nombre, "paises": [_cod], "paradas": 2, "noches": (15, 21), "cuadricula": _cod, "sustituye": True, "margen": 0.20, "madrid_directo": False}
for _cod, _nombre in PAISES_MEDIOS.items():
    ZONAS[_cod.lower()] = {"nombre": _nombre, "paises": [_cod], "paradas": 1, "noches": (4, 8), "cuadricula": _cod, "margen": 0.20}


# Vuelta desde un país vecino (el usuario, 17-10-2026): la ida es al país de la casilla, pero la vuelta puede salir de cualquiera de su grupo (se llega a Kigali y se
# vuelve desde Entebbe). Solo grupos que se pueden unir por tierra o con un salto corto; el traslado NO se suma al precio (igual que el open-jaw del sudeste).
# Los países ya visitados (GE, AM) valen como salida. Cambiar un grupo = las lecturas de sus zonas se repiten solas (ver `vj` en main).
GRUPOS_VECINOS = [
    "KE UG RW BI TZ", "SN GM GW GN", "SL LR GN", "CI GH TG BJ", "UZ KG KZ TJ TM", "AZ GE AM", "GT BZ SV HN NI CR PA", "EC PE CO BO", "PY AR UY BR",
    "ZA BW NA ZM ZW MZ MW LS SZ", "NP BD IN", "OM BH AE QA", "GY SR", "HK MO",
]
for _g in GRUPOS_VECINOS:
    _g = _g.split()
    for _c in _g:
        if _c.lower() in ZONAS:
            ZONAS[_c.lower()]["vuelta_desde"] = [o for o in _g if o != _c]


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
            "precio": round(escalas.precio(it)), "horas": it["horas_total"], "aerolineas": it["aerolineas"],
            **({"precio_estimado": True} if "precio_web" in it else {}),
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
    out = _leer(z["paises"], z, mes, avisar, vuelta=z.get("vuelta_desde"))
    if MADRID and z.get("madrid", True):
        try:
            out += [_con_tren(c) for c in _leer(z["paises"], z, mes, avisar, origen="MAD", vuelta=z.get("vuelta_desde"))]
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


def _leer(paises, z, mes, avisar, solo=None, origen="BCN", vuelta=None):
    combos, idas, vueltas = escalas.openjaw(paises, mes, z["noches"], z["paradas"], origen, paises_vuelta=(list(paises) + vuelta) if vuelta else None)
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
    if vuelta:
        out = _solo_si_compensa(out)
    return out


TRASLADO_TIERRA = 50   # € ESTIMADOS de ir por tierra de un país al vecino cuando no hay vuelo directo entre los dos aeropuertos (autobús, taxi compartido)


def _solo_si_compensa(out):
    """Vuelta desde otro país (vecinos): solo cuenta si el ahorro supera el traslado (vuelo interno si lo hay, si no 50 € estimados);
    si no, la casilla enseñaría un precio más bajo que el real. Los combos del mismo país se quedan siempre."""
    pais = lambda ap: (aeropuertos.ficha(ap) or {}).get("pais")
    mismo_pais = [c["total"] for c in out if pais(c["aps"][0]) == pais(c["aps"][1])]
    if not mismo_pais:
        return out
    tope = min(mismo_pais)
    return [c for c in out if pais(c["aps"][0]) == pais(c["aps"][1])
            or c["total"] + (c["interno"]["precio"] if c.get("interno") else TRASLADO_TIERRA) < tope]


def _refrescar_cuadricula():
    try:
        import radar_datos   # import tardío: radar_datos importa este módulo
        radar_datos.construir(radar_datos.cargar())
    except Exception as e:   # un fallo al reconstruir nunca debe parar la lectura
        print(f"  (cuadrícula no refrescada: {type(e).__name__}: {str(e)[:80]})")


SIGLAS_CORREGIDAS = {"Level": "LL", "Iberojet Airlines": "E9"}   # nombre en Kiwi -> sigla de kiwi.COMISION


def _corregir_level(almacen):
    """Lecturas hechas antes de corregir el precio de Level e Iberojet (el usuario, 17-10-2026): en cada tramo directo de Level o Iberojet cambia el precio de Kiwi por el estimado de la web
    (kiwi.COMISION) y ajusta el total. Idempotente: el tramo corregido lleva `precio_estimado`."""
    for z in almacen.values():
        for m in z.values():
            for c in (m.get("combos") or []):
                for lado in ("ida", "vuelta"):
                    t = c.get(lado) or {}
                    sigla = SIGLAS_CORREGIDAS.get((t.get("aerolineas") or [""])[0]) if len(t.get("aerolineas") or []) == 1 else None
                    if sigla and not t.get("escalas") and not t.get("precio_estimado"):
                        nuevo = kiwi.precio_aerolinea(t["precio"], sigla, t["desde"], t["hasta"])
                        if nuevo is not None:
                            c["total"] = round(c["total"] + nuevo - t["precio"])
                            t["precio"], t["precio_estimado"] = round(nuevo), True
    return almacen


def cargar():
    try:
        return _corregir_level(json.loads(ALMACEN.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def guardar(almacen):
    ALMACEN.parent.mkdir(exist_ok=True)
    tmp = ALMACEN.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(almacen, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, ALMACEN)   # el archivo nunca queda a medias


def guardar_lectura(zid, mm, entrada):
    """Guarda UNA lectura sin pisar a otros procesos (17-10-2026: dos lectores a la vez se borraban las zonas): con un candado, relee el archivo,
    pone solo esta zona y mes, y lo escribe. Devuelve el almacén actualizado."""
    candado = ALMACEN.with_suffix(".lock")
    for _ in range(300):
        try:
            os.close(os.open(candado, os.O_CREAT | os.O_EXCL))
            break
        except FileExistsError:
            try:
                if time.time() - candado.stat().st_mtime > 60:   # candado de un proceso muerto
                    candado.unlink()
            except OSError:
                pass
            time.sleep(0.2)
    try:
        almacen = cargar()
        almacen.setdefault(zid, {})[mm] = entrada
        guardar(almacen)
        return almacen
    finally:
        try:
            candado.unlink()
        except OSError:
            pass


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
            r = (almacen.get(zid) or {}).get(mm, {})
            return r.get("f") if r.get("vj") or not ZONAS[zid].get("vuelta_desde") else None   # lectura sin «vj» de una zona con vecinos = vieja
        solo = [argv[i + 1] for i, a in enumerate(argv) if a == "--zona"]
        tope = int(argv[argv.index("--max") + 1]) if "--max" in argv else (400 if EN_ACTIONS else MAX_MESES_POR_PASADA)
        due = sorted(((ultima(zid, mm) or "", mm, zid) for zid in ZONAS if not solo or zid in solo
                      for mm in todos if frescura.toca(mm, ultima(zid, mm))))   # primero lo nunca leído, y por mes: todos los países con un mes antes de pasar al siguiente
        if EN_ACTIONS or "--desde-el-final" in argv:   # primero lo nunca leído, y dentro de eso el mes más lejano
            due.sort(key=lambda t: (t[0], -(int(t[1][:4]) * 12 + int(t[1][5:])), t[2]))
        print(f"Zona-meses que tocan: {len(due)}; esta pasada: {min(len(due), tope)}.")
        pares = [(zid, mm) for _, mm, zid in due[:tope]]
    else:
        pares = [(zid, mm) for zid in ZONAS for mm in meses]
    fallos, inicio = 0, time.time()
    for i, (zid, mm) in enumerate(pares):
        if EN_ACTIONS and time.time() - inicio > PRESUPUESTO_ACTIONS:   # que el paso de subir los datos siempre llegue a ejecutarse
            print(f"Presupuesto de {PRESUPUESTO_ACTIONS // 60} min agotado: quedan {len(pares) - i} casillas para la próxima pasada.")
            pares = pares[:i]
            break
        print(f"{zid} {mm}: leyendo Kiwi…")
        marcha.avisar("larga", i, len(pares), f"{zid} {mm}")
        try:
            almacen = guardar_lectura(zid, mm, {"f": date.today().isoformat(), "combos": leer(zid, mm), **({"vj": 1} if ZONAS[zid].get("vuelta_desde") else {})})
            if (i + 1) % REFRESCO_CADA == 0:
                _refrescar_cuadricula()
            print(f"{zid} {mm}: {len(almacen[zid][mm]['combos'])} combinaciones; la más barata {almacen[zid][mm]['combos'][0]['total']} €"
                  if almacen[zid][mm]["combos"] else f"{zid} {mm}: sin combinaciones.")
        except Exception as e:
            fallos += 1
            print(f"{zid} {mm}: NO se ha leído ({type(e).__name__}: {str(e)[:120]}). Se conserva la lectura anterior.")
    if pares:
        marcha.avisar("larga", len(pares), len(pares), "", fin=True)
    if pares or "--construir" in argv:
        construir(cargar())   # lo que haya en el archivo ahora (incluye lo de otros lectores)
    else:
        print(__doc__)
    return 1 if pares and fallos == len(pares) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
