"""
kiwi.py — Pieza de Kiwi.com para Jawdrop.

Kiwi junta casi todas las aerolíneas (Turkish, Pegasus, AJet, SunExpress, Icelandair, Vueling...) y
permite pedir «cualquier aeropuerto de un país». Se usa para encontrar vuelos que Ryanair y Wizz no dan.
Consulta pública de su buscador (sin clave), tal como la usa un programa abierto de código libre.
  - Solo ida, solo directos, 1 adulto, tarifa de Kiwi en euros (sin maletas).
  - Una consulta = un DÍA con su franja de horas. Con rangos largos Kiwi se queda antes con los más
    baratos y luego aplica el filtro de horas, y salen 0 resultados: por eso un día por consulta.
  - Caché de 24 horas y pausa de 5 s entre consultas reales. Si Kiwi responde con error, se avisa y el
    programa sigue sin Kiwi (`KiwiBloqueado`); no se insiste ni se disfraza nada.
Limitaciones:
  - Kiwi suma una comisión sobre el precio de la aerolínea. Como el usuario reserva SIEMPRE en la aerolínea,
    `precio` es el precio estimado de la aerolínea (precio de Kiwi menos su comisión) y `precio_kiwi` guarda
    lo que dice Kiwi. Comisión medida el 12-10-2026 contra el precio real (ver COMISION):
      · Vueling: Kiwi = 2,26 + 1,071 × precio de Vueling (37 vuelos, error al revertir ±3 €, típico 0,5 €).
      · Ryanair (+~13 %, a veces +33 %) y Wizz (+1 a 3 €): no se usan de Kiwi, se leen directo.
      · easyJet (+14 €, ≈ +60 %), Turkish (+1 a 3 €), Pegasus (+6 a 8 €), AJet (+9 €), Eurowings (+3 €)
        y Transavia (+8 a 9 €): medidas con 1-3 vuelos de un día cada una (PROVISIONAL, ±3-4 €).
      · Resto (SunExpress, Icelandair, Volotea...): sin medir. Se enseña el precio de Kiwi tal cual y
        marcado «precio de Kiwi»: en la aerolínea será igual o algo menor.
    Para medir otra aerolínea, comparar su precio real con el de Kiwi (mismo vuelo, mismo día) y añadir su
    fila a COMISION: el resto del programa no cambia.
  - No trae el número de vuelo.
Los tramos salen en el mismo formato común que ryanair.py y wizz.py.
"""
import time
from datetime import date, datetime, timedelta

import requests

import aeropuertos as aeropuertos_tabla
import cache
import vueling

VERSION = "1.5"
HORAS_CACHE = 24
LOTE = 20   # aeropuertos de origen por consulta de vueltas (con más, Kiwi llega al tope de 50 y se pierden)
PAUSA = 5
URL = "https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchOneWayItinerariesQuery"
CABECERAS = {"User-Agent": "FlightFinder/0.1.0"}

CONSULTA = """query SearchOneWayItinerariesQuery($search: SearchOnewayInput,$filter: ItinerariesFilterInput,$options: ItinerariesOptionsInput){
onewayItineraries(search:$search,filter:$filter,options:$options){__typename
... on AppError{error: message}
... on Itineraries{itineraries{__typename ... on ItineraryOneWay{id priceEur{amount}
sector{duration sectorSegments{segment{source{station{code name gps{lat lng} city{name country{code name}}} localTime} destination{station{code name gps{lat lng} city{name country{code name}}} localTime} carrier{code name}}}}}}}}}"""

# Igual que CONSULTA pero con la hora UTC de cada tramo y los datos de la escala (para calcular cuánto dura): lo usa `escalas()`.
CONSULTA_ESC = """query SearchOneWayItinerariesQuery($search: SearchOnewayInput,$filter: ItinerariesFilterInput,$options: ItinerariesOptionsInput){
onewayItineraries(search:$search,filter:$filter,options:$options){__typename
... on AppError{error: message}
... on Itineraries{itineraries{__typename ... on ItineraryOneWay{id priceEur{amount} provider{name} duration
sector{duration sectorSegments{layover{isBaggageRecheck isWalkingDistance} segment{source{utcTime localTime station{code name city{name country{code name}}}} destination{utcTime localTime station{code name city{name country{code name}}}} carrier{code name}}}}}}}}}"""

# Comisión de Kiwi por aerolínea: precio_kiwi = fijo + pendiente × precio_aerolinea; `margen` = error (±€).
# Medida con vuelos reales (precio de la web de la aerolínea frente a Kiwi, mismo vuelo y día).
COMISION = {
    "VY": {"fijo": 2.26, "pendiente": 1.071, "margen": 3, "medido": "37 vuelos, 12-10-2026"},
    # Medidas el 12-10-2026 con precios de Google Flights (SerpApi), BCN, nov-2026 a ene-2027, 22 búsquedas.
    # «fijo» = euros que suma Kiwi; Transavia suma un 12 %. Vuelos medidos por aerolínea entre paréntesis.
    "U2": {"fijo": 14.5, "pendiente": 1.0, "margen": 2, "medido": "10 vuelos, 7 rutas: +14 a +15 € siempre"},
    "TK": {"fijo": 1.5, "pendiente": 1.0, "margen": 3, "medido": "3 vuelos BCN-IST (+1 a +3 €); el 28-nov Google daba 337 y Kiwi 175-256"},
    "PC": {"fijo": 7.0, "pendiente": 1.0, "margen": 4, "medido": "5 vuelos (+4 a +8 €; un día Kiwi 21 € por encima)"},
    "VF": {"fijo": 9.0, "pendiente": 1.0, "margen": 4, "medido": "3 vuelos BCN-ESB (+7 a +11 €)"},
    # Wizz (W6 Hungría, W4 Malta): medido el 13-10-2026 con 33 vuelos de dos domingos frente a lo que da Wizz:
    # Kiwi - Wizz de -3 a +9 €, casi siempre de 0 a 3 €. Solo lo usa verificar_wizz.py (Wizz se lee directo).
    "W6": {"fijo": 1.5, "pendiente": 1.0, "margen": 3, "medido": "33 vuelos, 13-10-2026: 0 a +3 € casi siempre"},
    "W4": {"fijo": 1.5, "pendiente": 1.0, "margen": 3, "medido": "33 vuelos, 13-10-2026: 0 a +3 € casi siempre"},
    "EW": {"fijo": 3.0, "pendiente": 1.0, "margen": 4, "medido": "3 vuelos (+3 €; el 7-dic Google 105 y Kiwi 61)"},
    "HV": {"fijo": 0.0, "pendiente": 1.12, "margen": 3, "medido": "3 vuelos BCN-AMS (+12 %)"},
    "XQ": {"fijo": 0.0, "pendiente": 1.0, "margen": 4, "medido": "1 vuelo BCN-ADB (140 = 140)"},
    "V7": {"fijo": 3.0, "pendiente": 1.0, "margen": 4, "medido": "1 vuelo BCN-NTE (29→32)"},
}

# Aerolíneas que ya se leen directamente (más exactas): Ryanair (FR, RK, AL Malta Air, RR Buzz) y Wizz
YA_LEIDAS = ("FR", "RK", "AL", "RR", "W6", "W4", "W9", "5W")
DIAS_SEMANA = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

_ultima = 0.0
_avisos = []   # avisos de la última consulta (los recoge quien llama)


class KiwiBloqueado(Exception):
    """Kiwi no ha respondido bien (cierre, límite o cambio). Se sigue sin Kiwi."""


def _consulta(origenes, destinos, dia, h_desde, h_hasta, limite, dia_fin=None, paradas=0, texto=CONSULTA):
    """Una consulta real a Kiwi, respetando la pausa. Devuelve la lista de itinerarios (JSON de Kiwi).
    Con `dia_fin` pide un RANGO de días (de `dia` a `dia_fin`) y no filtra por horas ni por día de la
    semana: es la consulta del radar (los más baratos del rango)."""
    global _ultima
    espera = PAUSA - (time.time() - _ultima)
    if espera > 0:
        time.sleep(espera)
    d = date.fromisoformat(dia)
    variables = {
        "search": {
            "itinerary": {"source": {"ids": origenes}, "destination": {"ids": destinos},
                          "outboundDepartureDate": {"start": f"{dia}T00:00:00", "end": f"{dia_fin or dia}T23:59:59"}},
            "passengers": {"adults": 1, "children": 0, "infants": 0, "adultsHoldBags": 0,
                           "adultsHandBags": 0, "childrenHoldBags": [], "childrenHandBags": []},
            "cabinClass": {"cabinClass": "ECONOMY", "applyMixedClasses": False}},
        "filter": {"transportTypes": ["FLIGHT"], "contentProviders": ["KIWI", "FRESH", "KAYAK"],
                   "limit": limite, "maxStopsCount": paradas,
                   **({} if dia_fin else {
                       "outbound": {"departureHours": {"start": int(h_desde[:2]), "end": int(h_hasta[:2])},
                                    "days": [DIAS_SEMANA[d.weekday()]]}})},
        "options": {"sortBy": "PRICE", "currency": "eur", "locale": "es", "partner": "skypicker",
                    "affilID": "skypicker", "storeSearch": False},
    }
    try:
        r = requests.post(URL, json={"query": texto, "variables": variables}, headers=CABECERAS, timeout=90)
    except requests.RequestException as e:
        raise KiwiBloqueado(str(e)) from e
    finally:
        _ultima = time.time()
    if r.status_code != 200:
        raise KiwiBloqueado(f"Kiwi respondió {r.status_code}: {r.text[:200]}")
    try:
        res = r.json()["data"]["onewayItineraries"]
    except (ValueError, KeyError, TypeError) as e:
        raise KiwiBloqueado(f"respuesta de Kiwi no entendida: {r.text[:200]}") from e
    if res.get("__typename") != "Itineraries":
        raise KiwiBloqueado(f"Kiwi devolvió un error: {res.get('error')}")
    return res["itineraries"]


def _tramo(it):
    """Pasa un itinerario directo de Kiwi al formato común (o None si no es un vuelo suelto)."""
    segs = it.get("sector", {}).get("sectorSegments", [])
    if len(segs) != 1:
        return None
    s = segs[0]["segment"]
    o, d = s["source"], s["destination"]
    desde, hasta = o["station"]["code"], d["station"]["code"]
    precio_kiwi = float(it["priceEur"]["amount"])
    codigo = s["carrier"]["code"]
    precio, extra = precio_kiwi, {"precio_orientativo": True}
    com = COMISION.get(codigo)
    if com:
        # precio de la aerolínea = (Kiwi - fijo) / pendiente, redondeado al euro como lo da la aerolínea
        precio = float(max(round((precio_kiwi - com["fijo"]) / com["pendiente"]), 0))
        extra = {"precio_estimado": True, "margen": com["margen"]}
    return {
        "aerolinea": s["carrier"]["name"],
        "sigla": s["carrier"]["code"],
        "desde": desde, "hasta": hasta,
        "salida": o["localTime"][:16], "llegada": d["localTime"][:16],
        "llegada_aprox": False,
        "vuelo": "",
        "precio": precio,
        "precio_minimo": False,
        "precio_kiwi": precio_kiwi,
        **extra,
        "fuente": "kiwi",
        "_origen": o["station"], "_destino": d["station"],
    }


def _formato(t, sentido):
    """Rellena destino / ciudad / país según `sentido` ('ida': el otro extremo es la llegada)."""
    est = t.pop("_destino") if sentido == "ida" else t.pop("_origen")
    t.pop("_origen", None)
    t.pop("_destino", None)
    ciudad = est.get("city") or {}
    pais = ciudad.get("country") or {}
    nom, cod, nom_pais = aeropuertos_tabla.corregir(
        est["code"], ciudad.get("name") or est.get("name", est["code"]), (pais.get("code") or "").upper(),
        pais.get("name", ""))
    t.update({"destino": est["code"], "ciudad": nom, "pais": cod, "pais_nombre": nom_pais,
              "enlace": enlace(t["desde"], t["hasta"], t["salida"][:10], t["sigla"])})
    gps = est.get("gps") or {}
    if gps.get("lat") is not None:
        t["coords"] = {"ciudad": t["ciudad"], "pais": t["pais"], "pais_nombre": t["pais_nombre"],
                       "lat": gps["lat"], "lon": gps["lng"]}
    return t


# Web de la aerolínea para los vuelos de Kiwi (se reserva en la aerolínea). Solo Vueling y easyJet admiten
# enlace al día; el resto lleva a su portada (hay que poner la ruta a mano). Sin sigla conocida: Kiwi.
PORTADAS = {
    "TK": "https://www.turkishairlines.com/es-es/",
    "PC": "https://www.flypgs.com/es",
    "VF": "https://www.ajet.com/es",
    "EW": "https://www.eurowings.com/es.html",
    "HV": "https://www.transavia.com/es-ES/home/",
    "XQ": "https://www.sunexpress.com/es-es/",
    "V7": "https://www.volotea.com/es/",
}


def enlace(desde, hasta, dia, sigla=""):
    """Enlace a la web de la aerolínea del vuelo (no a Kiwi); Kiwi solo si no conocemos la aerolínea."""
    if sigla == "VY":
        return vueling.enlace(desde, hasta, dia)
    if sigla == "U2":
        return (f"https://www.easyjet.com/es/buy/flights?isOneWay=on&dep={desde}&dest={hasta}&dd={dia}"
                "&apax=1&cpax=0&ipax=0&pid=www.easyjet.com")
    if sigla in PORTADAS:
        return PORTADAS[sigla]
    return f"https://www.kiwi.com/es/search/results/{desde}/{hasta}/{dia}/no-return?stopNumber=0"


def _pedir(origenes, destinos, dia, h_desde, h_hasta, limite, usar_cache):
    return cache.con_cache(
        ["kiwi", "consulta1", origenes, destinos, dia, h_desde, h_hasta, limite], HORAS_CACHE,
        lambda: _consulta(origenes, destinos, dia, h_desde, h_hasta, limite), usar_cache)


def rango(origenes, destinos, desde, hasta, excluir=YA_LEIDAS, limite=50, usar_cache=True):
    """Radar: vuelos directos de `origenes` a `destinos` (ids de Kiwi: 'Airport:BCN', 'Country:TR') con
    salida entre `desde` y `hasta` (AAAA-MM-DD), sin filtro de horas. Los más baratos del rango (hasta
    `limite`), uno por aeropuerto, aerolínea y día. El sentido se deduce: si el origen es un solo
    aeropuerto, el «otro extremo» es el destino (ida); si no, el origen (vuelta)."""
    origenes, destinos = list(origenes), list(destinos)
    sentido = "ida" if len(origenes) == 1 and origenes[0].startswith("Airport:") else "vuelta"
    its = cache.con_cache(["kiwi", "rango1", origenes, destinos, desde, hasta, limite], HORAS_CACHE,
                          lambda: _consulta(origenes, destinos, desde, "00:00", "23:59", limite, hasta),
                          usar_cache)
    if len(its) >= limite:
        _avisos.append(f"Kiwi: {origenes[:2]}→{destinos[:2]} {desde}..{hasta} llegó al tope de {limite}.")
    return _unicos(its, sentido, excluir)


def radar_mes(origen, paises, mes, excluir=YA_LEIDAS, avisar=None, usar_cache=True):
    """Radar de un mes (AAAA-MM): para cada país de `paises` (['TR', 'IS'...]), los vuelos directos más
    baratos desde `origen` en el mes, sin Ryanair ni Wizz. Una consulta por país (~5 s). Sigue si un país
    falla. Devuelve (tramos, avisos)."""
    primero = date.fromisoformat(mes + "-01")
    ultimo = date(primero.year + primero.month // 12, primero.month % 12 + 1, 1)
    desde = max(primero, date.today()).isoformat()
    hasta = (ultimo - date.resolution).isoformat()
    tramos, avisos = [], []
    for i, pais in enumerate(paises, 1):
        if avisar:
            avisar(i, len(paises), pais)
        try:
            tramos += rango([f"Airport:{origen}"], [f"Country:{pais}"], desde, hasta, excluir,
                            usar_cache=usar_cache)
        except KiwiBloqueado as e:
            avisos.append(f"Kiwi {pais}: {str(e)[:70]}")
    return tramos, avisos


def tiene_directo(origen, pais, dias=360, usar_cache=True):
    """¿Hay algún vuelo directo de `origen` a ese país (cualquier aerolínea, Ryanair y Wizz incluidas) en el próximo año?
    Una consulta. Sirve para no preguntar mes a mes por países a los que no se vuela sin escalas."""
    hoy = date.today()
    its = rango([f"Airport:{origen}"], [f"Country:{pais}"], hoy.isoformat(), (hoy + timedelta(days=dias)).isoformat(),
                excluir=(), limite=10, usar_cache=usar_cache)
    return bool(its)


def semana_pais(origen, pais, mes, n_min=5, n_max=8, usar_cache=True):
    """Mejor ida+vuelta de `n_min`-`n_max` noches a un país con aerolíneas que NO son Ryanair ni Wizz (esas se leen directo),
    con la ida dentro del mes (AAAA-MM), mismo aeropuerto de ida y de vuelta (pueden ser aerolíneas distintas: dos billetes).
    Dos consultas (~10 s). Devuelve None o {aerolinea, ida, vuelta, total, noches, destino, ciudad, orientativo}.
    `orientativo` = algún tramo es precio de Kiwi sin comisión conocida (en la aerolínea será igual o algo menor)."""
    primero = date.fromisoformat(mes + "-01")
    ultimo = date(primero.year + primero.month // 12, primero.month % 12 + 1, 1) - timedelta(days=1)
    desde = max(primero, date.today())
    idas = rango([f"Airport:{origen}"], [f"Country:{pais}"], desde.isoformat(), ultimo.isoformat(), usar_cache=usar_cache)
    if not idas:
        return None
    vueltas = rango([f"Country:{pais}"], [f"Airport:{origen}"], (desde + timedelta(days=n_min)).isoformat(),
                    (ultimo + timedelta(days=n_max)).isoformat(), usar_cache=usar_cache)
    por_dia = {}
    for v in vueltas:
        k = (v["destino"], v["salida"][:10])
        if k not in por_dia or v["precio"] < por_dia[k]["precio"]:
            por_dia[k] = v
    mejor = None
    for i in idas:
        dia = date.fromisoformat(i["salida"][:10])
        for n in range(n_min, n_max + 1):
            v = por_dia.get((i["destino"], (dia + timedelta(days=n)).isoformat()))
            if v and (mejor is None or i["precio"] + v["precio"] < mejor["total"]):
                mejor = {"aerolinea": i["aerolinea"] if i["aerolinea"] == v["aerolinea"] else f'{i["aerolinea"]} + {v["aerolinea"]}',
                         "ida": i["salida"][:10], "vuelta": v["salida"][:10], "total": i["precio"] + v["precio"], "noches": n,
                         "destino": i["destino"], "ciudad": i["ciudad"], "pais": pais,
                         "orientativo": bool(i.get("precio_orientativo") or v.get("precio_orientativo"))}
    return mejor


def escalas(origenes, destinos, desde, hasta, paradas=1, limite=50, usar_cache=True):
    """Itinerarios de SOLO IDA con hasta `paradas` escalas (1 por defecto), con salida entre `desde` y `hasta` (AAAA-MM-DD),
    de cualquier aerolínea (Ryanair y Wizz incluidas: aquí no hay directo que leer aparte). Los `limite` más baratos del rango.
    Cada uno: precio_kiwi, aerolineas, tramos (aeropuerto, ciudad, país, hora local y UTC), escalas (aeropuerto, país, horas, llegada y
    salida locales, cambia_equipaje), horas totales y proveedor. Precio = el de Kiwi (orientativo: no se le descuenta comisión).
    Todo pasa por la caché y la pausa de siempre; una consulta."""
    its = cache.con_cache(["kiwi", "escalas1", origenes, destinos, desde, hasta, paradas, limite], HORAS_CACHE,
                          lambda: _consulta(origenes, destinos, desde, "00:00", "23:59", limite, hasta, paradas, CONSULTA_ESC), usar_cache)
    res = []
    for it in its:
        segs = [s["segment"] for s in it["sector"]["sectorSegments"]]
        lays = [s.get("layover") or {} for s in it["sector"]["sectorSegments"]]
        t = lambda e: datetime.fromisoformat(e["utcTime"].replace("Z", "+00:00"))
        tramos = [{"desde": s["source"]["station"]["code"], "hasta": s["destination"]["station"]["code"],
                   "ciudad_desde": (s["source"]["station"].get("city") or {}).get("name", ""),
                   "ciudad_hasta": (s["destination"]["station"].get("city") or {}).get("name", ""),
                   "pais_hasta": ((s["destination"]["station"].get("city") or {}).get("country") or {}).get("code", ""),
                   "sale_local": s["source"]["localTime"][:16], "llega_local": s["destination"]["localTime"][:16],
                   "aerolinea": s["carrier"]["name"], "sigla": s["carrier"]["code"]} for s in segs]
        esc = []
        for i in range(1, len(segs)):
            esc.append({"aeropuerto": tramos[i]["desde"], "ciudad": tramos[i - 1]["ciudad_hasta"], "pais": tramos[i - 1]["pais_hasta"],
                        "horas": round((t(segs[i]["source"]) - t(segs[i - 1]["destination"])).total_seconds() / 3600, 1),
                        "llega_local": tramos[i - 1]["llega_local"], "sale_local": tramos[i]["sale_local"],
                        "cambia_equipaje": bool(lays[i].get("isBaggageRecheck"))})
        res.append({"precio_kiwi": float(it["priceEur"]["amount"]), "aerolineas": sorted({x["aerolinea"] for x in tramos}),
                    "tramos": tramos, "escalas": esc, "horas_total": round(it["duration"] / 3600, 1),
                    "proveedor": (it.get("provider") or {}).get("name", ""), "destino": tramos[-1]["hasta"],
                    "ciudad": tramos[-1]["ciudad_hasta"], "pais": tramos[-1]["pais_hasta"], "salida": tramos[0]["sale_local"][:10]})
    return sorted(res, key=lambda x: x["precio_kiwi"])


def idas(origen, destinos, dia, h_desde, h_hasta, excluir=YA_LEIDAS, limite=50, usar_cache=True):
    """Idas directas origen → `destinos` (['Country:TR', 'Airport:IST'...]; vacío = a cualquier sitio) en
    `dia` dentro de la franja. Más barata de cada aeropuerto de destino y aerolínea. `excluir` = códigos
    de aerolínea que ya se leen directamente (Ryanair, Wizz). Una consulta."""
    its = _pedir([f"Airport:{origen}"], list(destinos), dia, h_desde, h_hasta, limite, usar_cache)
    if len(its) >= limite:
        _avisos.append(f"Kiwi: {origen} {dia} llegó al tope de {limite} resultados; puede faltar alguno.")
    return _unicos(its, "ida", excluir)


def vueltas(origenes, destino, dia, h_desde, h_hasta, excluir=YA_LEIDAS, limite=50, usar_cache=True):
    """Vueltas directas desde `origenes` (['Country:TR', 'Airport:IST'...]) a `destino` (aeropuerto,
    p. ej. 'BCN') en `dia` dentro de la franja. Una consulta."""
    its = []
    origenes = list(origenes)
    for i in range(0, len(origenes), LOTE):
        parte = _pedir(origenes[i:i + LOTE], [f"Airport:{destino}"], dia, h_desde, h_hasta, limite, usar_cache)
        if len(parte) >= limite:
            _avisos.append(f"Kiwi: vueltas a {destino} {dia} llegaron al tope de {limite}; puede faltar alguna.")
        its += parte
    return _unicos(its, "vuelta", excluir)


def _unicos(its, sentido, excluir):
    """Tramos en formato común; deja el más barato por aeropuerto y aerolínea y salta `excluir`."""
    mejores = {}
    for it in its:
        t = _tramo(it)
        if not t:
            continue
        cod = it["sector"]["sectorSegments"][0]["segment"]["carrier"]["code"]
        if cod in excluir:
            continue
        t = _formato(t, sentido)
        k = (t["destino"], t["aerolinea"], t["salida"])
        if k not in mejores or t["precio"] < mejores[k]["precio"]:
            mejores[k] = t
    return sorted(mejores.values(), key=lambda t: t["precio"])


if __name__ == "__main__":
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(description="Prueba de Kiwi (solo ida, directos)")
    ap.add_argument("sentido", choices=("ida", "vuelta"))
    ap.add_argument("lugar", help="ida: destino (TR, IST...); vuelta: origen (TR, IST...)")
    ap.add_argument("dia", help="AAAA-MM-DD")
    ap.add_argument("--desde", default="06:00")
    ap.add_argument("--hasta", default="10:00")
    ap.add_argument("--origen", default="BCN")
    ap.add_argument("--todas", action="store_true", help="incluir Ryanair y Wizz")
    a = ap.parse_args()
    ids = [f"Country:{a.lugar.upper()}" if len(a.lugar) == 2 else f"Airport:{a.lugar.upper()}"]
    excl = () if a.todas else YA_LEIDAS
    try:
        if a.sentido == "ida":
            res = idas(a.origen, ids, a.dia, a.desde, a.hasta, excl)
        else:
            res = vueltas(ids, a.origen, a.dia, a.desde, a.hasta, excl)
    except KiwiBloqueado as e:
        print("Kiwi no responde:", e)
        sys.exit(1)
    print(f"kiwi.py {VERSION}: {len(res)} vuelos")
    for t in res:
        print(f'{t["precio"]:>6.0f} € ({"estim. aerolínea, Kiwi " + format(t["precio_kiwi"], ".0f") if t.get("precio_estimado") else "Kiwi"}) | {t["desde"]} {t["salida"][11:]} → {t["hasta"]} '
              f'{t["llegada"][11:]} | {t["aerolinea"]} | {t["ciudad"]} ({t["pais"]} {t["pais_nombre"]})')
    if "--json" in sys.argv:
        print(json.dumps(res[:2], ensure_ascii=False, indent=1))
