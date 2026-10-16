"""
ryanair.py — Pieza de Ryanair para Jawdrop.

Usa los buscadores públicos de precios de la web de Ryanair (farfnd), que devuelven la tarifa básica
(sin maleta ni asiento) del vuelo más barato que cumple un horario.
  - Idas: una sola consulta "BCN → cualquier destino" con la franja de hora del domingo.
  - Vueltas: una consulta por día (lunes / martes) que da la vuelta más barata desde CADA aeropuerto
    de Ryanair con ruta a BCN (sirve también para volver desde otro aeropuerto). Si la del martes llega
    tarde, una consulta más por aeropuerto para buscar una más temprana.
  - Aeropuertos (país y coordenadas): una consulta, caché 3 días.
Todo pasa por la caché (24 horas) y con 3 s de pausa entre consultas reales.
"""
import time
from datetime import date, datetime, timedelta

import requests

import aeropuertos as aeropuertos_tabla
import cache

VERSION = "3.4"
HORAS_CACHE = 24
PAUSA = 3
URL_IDA_VUELTA = "https://www.ryanair.com/api/farfnd/v4/roundTripFares"
URL_SOLO_IDA = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"
CABECERAS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/141.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
}
COMUNES = {"currency": "EUR", "market": "es-es", "adultPaxCount": 1}

_ultima = 0.0


def _get(url, params=None):
    """Consulta real a Ryanair, respetando la pausa."""
    global _ultima
    espera = PAUSA - (time.time() - _ultima)
    if espera > 0:
        time.sleep(espera)
    r = requests.get(url, params=params, headers=CABECERAS, timeout=30)
    _ultima = time.time()
    if r.status_code != 200:
        raise RuntimeError(f"Ryanair respondió {r.status_code}: {r.text[:200]}")
    return r.json()


def _pedir(url, params, usar_cache):
    return cache.con_cache(["ryanair", url, params], HORAS_CACHE, lambda: _get(url, params), usar_cache)


def _tramo(t, sentido):
    """Pasa un tramo de Ryanair al formato común. `sentido` = 'ida' o 'vuelta'."""
    otro = t["arrivalAirport"] if sentido == "ida" else t["departureAirport"]
    desde, hasta = t["departureAirport"]["iataCode"], t["arrivalAirport"]["iataCode"]
    return {
        "aerolinea": "Ryanair",
        "desde": desde, "hasta": hasta,
        "destino": otro["iataCode"],
        "ciudad": otro.get("city", {}).get("name", "") or otro.get("name", ""),
        "pais": otro.get("city", {}).get("countryCode", "").upper(),
        "pais_nombre": otro.get("countryName", ""),
        "salida": t["departureDate"][:16],
        "llegada": t["arrivalDate"][:16],
        "llegada_aprox": False,
        "vuelo": t.get("flightNumber", ""),
        "precio": float(t["price"]["value"]),
        "precio_minimo": False,
        "enlace": enlace(desde, hasta, t["departureDate"][:10]),
    }


def enlace(desde, hasta, dia):
    return ("https://www.ryanair.com/es/es/trip/flights/select?adults=1&teens=0&children=0&infants=0"
            f"&dateOut={dia}&isConnectedFlight=false&isReturn=false&discount=0"
            f"&originIata={desde}&destinationIata={hasta}")


def idas(origen, domingo, hora_desde, hora_hasta, usar_cache=True):
    """Ida más barata a cada destino el domingo dentro de la franja. Una consulta."""
    p = dict(COMUNES, departureAirportIataCode=origen,
             outboundDepartureDateFrom=domingo, outboundDepartureDateTo=domingo,
             outboundDepartureTimeFrom=hora_desde, outboundDepartureTimeTo=hora_hasta)
    return [_tramo(f["outbound"], "ida") for f in _pedir(URL_SOLO_IDA, p, usar_cache).get("fares", [])]


def vueltas(origen, domingo, dia, hora_desde, hora_hasta, usar_cache=True):
    """Vuelta más barata a `origen` desde CADA aeropuerto de Ryanair con ruta directa, en `dia` y franja.

    Truco: se pide un ida+vuelta con la ida en cualquier día de la semana anterior (cualquier hora);
    Ryanair devuelve, por destino, la vuelta más barata que cumple la franja. Una consulta.
    Devuelve {aeropuerto: tramo}.
    """
    d = date.fromisoformat(domingo)
    desde = max(date.today(), d - timedelta(days=6)).isoformat()
    p = dict(COMUNES, departureAirportIataCode=origen,
             outboundDepartureDateFrom=desde, outboundDepartureDateTo=domingo,
             inboundDepartureDateFrom=dia, inboundDepartureDateTo=dia,
             inboundDepartureTimeFrom=hora_desde, inboundDepartureTimeTo=hora_hasta)
    res = {}
    for f in _pedir(URL_IDA_VUELTA, p, usar_cache).get("fares", []):
        v = _tramo(f["inbound"], "vuelta")
        res[v["destino"]] = v
    return res


def aeropuertos(usar_cache=True):
    """Aeropuertos activos de Ryanair con país, coordenadas y zona horaria. Caché 3 días.
    Devuelve {iata: {ciudad, pais, pais_nombre, lat, lon}}."""
    datos = cache.con_cache(
        ["ryanair", "aeropuertos"], 72,
        lambda: _get("https://www.ryanair.com/api/views/locate/5/airports/es/active"), usar_cache)
    res = {}
    for a in datos:
        if not a.get("coordinates"):
            continue
        ciudad, pais, pais_nombre = aeropuertos_tabla.corregir(
            a["code"], a.get("city", {}).get("name") or a.get("name", a["code"]),
            a.get("country", {}).get("code", "").upper(), a.get("country", {}).get("name", ""))
        res[a["code"]] = {"ciudad": ciudad, "pais": pais, "pais_nombre": pais_nombre,
                          "lat": a["coordinates"]["latitude"], "lon": a["coordinates"]["longitude"]}
    return res


def nombres_en(usar_cache=True):
    """Nombres en inglés (ciudad y aeropuerto) para los enlaces de traslados. Caché 3 días.
    Devuelve {iata: (ciudad, aeropuerto)}."""
    datos = cache.con_cache(
        ["ryanair", "aeropuertos_en"], 72,
        lambda: _get("https://www.ryanair.com/api/views/locate/5/airports/en/active"), usar_cache)
    return {a["code"]: (a.get("city", {}).get("name") or a.get("name", a["code"]), a.get("name", a["code"]))
            for a in datos}


def vuelta_desde(destino, origen, dia, hora_desde, hora_hasta, usar_cache=True):
    """Vuelta más barata destino → origen en `dia` dentro de la franja (o None). Una consulta."""
    p = dict(COMUNES, departureAirportIataCode=destino, arrivalAirportIataCode=origen,
             outboundDepartureDateFrom=dia, outboundDepartureDateTo=dia,
             outboundDepartureTimeFrom=hora_desde, outboundDepartureTimeTo=hora_hasta)
    fares = _pedir(URL_SOLO_IDA, p, usar_cache).get("fares", [])
    return _tramo(fares[0]["outbound"], "vuelta") if fares else None


def ajustar_llegada(vuelta, origen, tope, usar_cache=True, intentos=3):
    """Si la vuelta llega después de `tope` (AAAA-MM-DDTHH:MM), busca otra que salga antes."""
    while vuelta and vuelta["llegada"] > tope and intentos > 0:
        antes = (datetime.fromisoformat(vuelta["salida"]) - timedelta(minutes=1)).strftime("%H:%M")
        vuelta = vuelta_desde(vuelta["destino"], origen, vuelta["salida"][:10], "00:00", antes, usar_cache)
        intentos -= 1
    return vuelta if vuelta and vuelta["llegada"] <= tope else None


def radar(origen, mes, dias_min=6, dias_max=8, usar_cache=True, avisar=None):
    """Radar de un mes (AAAA-MM) para viajes largos. Por destino:
      - la ida más barata del mes (una consulta para todos los destinos), y
      - la mejor pareja ida+vuelta de `dias_min`-`dias_max` días con la ida en ese mes (una consulta por
        destino; la vuelta puede caer en el mes siguiente), con fechas y precio total exactos.
    Devuelve {destino: {destino, ciudad, pais, pais_nombre, ida: (fecha, precio), pareja: None | dict}}."""
    primero = date.fromisoformat(mes + "-01")
    ultimo = date(primero.year + primero.month // 12, primero.month % 12 + 1, 1) - timedelta(days=1)
    desde = max(primero, date.today()).isoformat()
    hasta = ultimo.isoformat()
    p = dict(COMUNES, departureAirportIataCode=origen, outboundDepartureDateFrom=desde,
             outboundDepartureDateTo=hasta)
    res = {}
    for f in _pedir(URL_SOLO_IDA, p, usar_cache).get("fares", []):
        t = _tramo(f["outbound"], "ida")
        res[t["destino"]] = {"destino": t["destino"], "ciudad": t["ciudad"], "pais": t["pais"],
                             "pais_nombre": t["pais_nombre"], "ida": (t["salida"][:10], t["precio"]),
                             "pareja": None, "enlace": t["enlace"]}
    fin_vuelta = (ultimo + timedelta(days=dias_max)).isoformat()
    for i, destino in enumerate(sorted(res), 1):
        if avisar:
            avisar(i, len(res), destino)
        p = dict(COMUNES, departureAirportIataCode=origen, arrivalAirportIataCode=destino,
                 outboundDepartureDateFrom=desde, outboundDepartureDateTo=hasta,
                 inboundDepartureDateFrom=desde, inboundDepartureDateTo=fin_vuelta,
                 durationFrom=dias_min, durationTo=dias_max)
        try:
            fares = _pedir(URL_IDA_VUELTA, p, usar_cache).get("fares", [])
        except RuntimeError:
            continue
        if fares:
            m = min(fares, key=lambda f: f["summary"]["price"]["value"])
            o, v = m["outbound"], m["inbound"]
            res[destino]["pareja"] = {
                "aerolinea": "Ryanair", "ida": o["departureDate"][:10], "vuelta": v["departureDate"][:10],
                "precio_ida": float(o["price"]["value"]), "precio_vuelta": float(v["price"]["value"]),
                "total": float(m["summary"]["price"]["value"]),
                "noches": m["summary"].get("tripDurationDays")}
    return res
