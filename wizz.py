"""
wizz.py — Pieza de Wizz Air para Jawdrop.

Usa dos consultas internas de la web de Wizz Air, a través de la librería flywizz:
  - asset/map: la red de rutas (qué destinos hay desde BCN, con país y coordenadas). Caché 3 días.
  - search/timetableV2: por cada ruta, en UNA consulta, las idas y las vueltas de un periodo (un fin de
    semana o un mes entero), con todas las horas de salida de cada día y el precio más barato del día
    (tarifa normal, sin Discount Club). Caché 24 horas, 4 s de pausa entre consultas.
Limitaciones (por cómo responde Wizz):
  - Precio: Wizz da el precio del vuelo más barato del día. Si ese día hay varios vuelos y el que
    cumple el horario no es el más barato, el precio real es MAYOR: se marca como «mínimo» (≥).
  - Hora de llegada: Wizz no la da. Se calcula por la distancia y la diferencia horaria y se marca
    como aproximada (≈).
  - La búsqueda normal de Wizz (search/search) está bloqueada por su antibots; no se usa.
"""
import math
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flywizz.transport import WizzairTransport

import aeropuertos as aeropuertos_tabla
import cache

VERSION = "2.0"
HORAS_CACHE = 24
HORAS_CACHE_RED = 72
PAUSA = 4

# Zona horaria por país (para estimar la hora de llegada)
ZONAS = {
    "ES": "Europe/Madrid", "PT": "Europe/Lisbon", "GB": "Europe/London", "IE": "Europe/Dublin",
    "FR": "Europe/Paris", "IT": "Europe/Rome", "DE": "Europe/Berlin", "AT": "Europe/Vienna",
    "CH": "Europe/Zurich", "NL": "Europe/Amsterdam", "BE": "Europe/Brussels", "PL": "Europe/Warsaw",
    "CZ": "Europe/Prague", "SK": "Europe/Bratislava", "HU": "Europe/Budapest", "SI": "Europe/Ljubljana",
    "HR": "Europe/Zagreb", "RS": "Europe/Belgrade", "BA": "Europe/Sarajevo", "ME": "Europe/Podgorica",
    "MK": "Europe/Skopje", "AL": "Europe/Tirane", "XK": "Europe/Belgrade", "RO": "Europe/Bucharest",
    "BG": "Europe/Sofia", "GR": "Europe/Athens", "CY": "Asia/Nicosia", "MD": "Europe/Chisinau",
    "UA": "Europe/Kyiv", "LT": "Europe/Vilnius", "LV": "Europe/Riga", "EE": "Europe/Tallinn",
    "FI": "Europe/Helsinki", "SE": "Europe/Stockholm", "NO": "Europe/Oslo", "DK": "Europe/Copenhagen",
    "IS": "Atlantic/Reykjavik", "MT": "Europe/Malta", "GE": "Asia/Tbilisi", "AM": "Asia/Yerevan",
    "TR": "Europe/Istanbul", "IL": "Asia/Jerusalem", "MA": "Africa/Casablanca", "EG": "Africa/Cairo",
    "AE": "Asia/Dubai", "SA": "Asia/Riyadh", "JO": "Asia/Amman", "AZ": "Asia/Baku", "KZ": "Asia/Almaty",
    "UZ": "Asia/Tashkent", "LU": "Europe/Luxembourg",
}

_transporte = None
_ultima = 0.0


class WizzBloqueado(Exception):
    """Wizz Air ha cerrado la puerta (antibots). Se sigue sin Wizz."""


def _t():
    global _transporte
    if _transporte is None:
        _transporte = WizzairTransport()
    return _transporte


def _pausa():
    global _ultima
    espera = PAUSA - (time.time() - _ultima)
    if espera > 0:
        time.sleep(espera)
    _ultima = time.time()


def red(origen, usar_cache=True):
    """Aeropuertos de Wizz y destinos directos desde `origen`. Devuelve (aeropuertos, destinos)."""
    def real():
        _pausa()
        try:
            return _t().get_json("asset/map", {"languageCode": "es-es"})
        except Exception as e:
            raise WizzBloqueado(str(e)) from e
    datos = cache.con_cache(["wizz", "asset/map"], HORAS_CACHE_RED, real, usar_cache)
    aeropuertos = {}
    for c in datos.get("cities", []):
        if c.get("isFakeStation") or c.get("mac") == c.get("iata"):
            continue  # códigos de "todos los aeropuertos de una ciudad" (ROM, LON…)
        ciudad, pais, pais_nombre = aeropuertos_tabla.corregir(
            c["iata"], " ".join(c.get("shortName", c["iata"]).split()), c.get("countryCode", "").upper(),
            c.get("countryName", ""))
        aeropuertos[c["iata"]] = {
            "ciudad": ciudad, "pais": pais,
            "pais_nombre": pais_nombre, "lat": c.get("latitude"), "lon": c.get("longitude"),
            "nombre_en": (c.get("aliases") or [c.get("shortName", c["iata"])])[0],
        }
    destinos = []
    for c in datos.get("cities", []):
        if c["iata"] == origen:
            destinos = [x["iata"] for x in c.get("connections", [])
                        if x.get("isDirectFlight", True) and x["iata"] in aeropuertos]
    return aeropuertos, destinos


def distancia_km(a, b):
    """Distancia en línea recta entre dos aeropuertos (dicts con lat/lon)."""
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _llegada_estimada(salida, ap_desde, ap_hasta):
    """Hora local de llegada: duración ≈ 35 min + distancia a 780 km/h, con cambio de huso."""
    minutos = 35 + distancia_km(ap_desde, ap_hasta) / 780 * 60
    z1 = ZoneInfo(ZONAS.get(ap_desde["pais"], "Europe/Madrid"))
    z2 = ZoneInfo(ZONAS.get(ap_hasta["pais"], "Europe/Madrid"))
    sale = datetime.fromisoformat(salida).replace(tzinfo=z1)
    llega = (sale + timedelta(minutes=minutos)).astimezone(z2)
    return llega.strftime("%Y-%m-%dT%H:%M")


def enlace(desde, hasta, dia):
    # Búsqueda en la web de Wizz (solo ida, 1 adulto). Desde 13-10-2026 vuelve a la web de Wizz con la búsqueda hecha:
    # El usuario no quiere pasar por Google Flights. La web de Wizz es la que bloquea a los programas, no a una persona en su móvil.
    return f"https://www.wizzair.com/es-es/booking/select-flight/{desde}/{hasta}/{dia}/null/1/0/0/null"


def _tramos(dias, aeropuertos, sentido):
    """Pasa las entradas de horario de Wizz al formato común (un tramo por hora de salida)."""
    res = []
    for d in dias:
        precio = d.get("price") or {}
        if not precio.get("amount") or precio.get("currencyCode") != "EUR":
            continue  # sin precio (0 = sin plazas a la venta) o en otra moneda: no se puede comparar
        desde, hasta = d["departureStation"], d["arrivalStation"]
        otro = hasta if sentido == "ida" else desde
        ap = aeropuertos.get(otro, {})
        salidas = d.get("departureDates") or [{"date": d["departureDate"], "isCheapestOfTheDay": True}]
        for s in salidas:
            salida = s["date"][:16]
            res.append({
                "aerolinea": "Wizz Air",
                "desde": desde, "hasta": hasta,
                "destino": otro,
                "ciudad": ap.get("ciudad", otro),
                "pais": ap.get("pais", ""),
                "pais_nombre": ap.get("pais_nombre", ""),
                "salida": salida,
                "llegada": (_llegada_estimada(salida, aeropuertos[desde], aeropuertos[hasta])
                            if desde in aeropuertos and hasta in aeropuertos else None),
                "llegada_aprox": True,
                "vuelo": "",
                "precio": float(precio["amount"]),
                "precio_minimo": not s.get("isCheapestOfTheDay", False) and len(salidas) > 1,
                "enlace": enlace(desde, hasta, salida[:10]),
            })
    return res


def horarios(origen, destino, ida_desde, ida_hasta, vuelta_desde, vuelta_hasta, aeropuertos, usar_cache=True):
    """Idas y vueltas de una ruta entre esas fechas, en UNA consulta (sirve para varias semanas).
    Devuelve (idas, vueltas) con todos los días; el filtro por día y hora lo hace escapadas.py."""
    cuerpo = {
        "flightList": [
            {"departureStation": origen, "arrivalStation": destino, "from": ida_desde, "to": ida_hasta},
            {"departureStation": destino, "arrivalStation": origen, "from": vuelta_desde, "to": vuelta_hasta},
        ],
        "priceType": "regular", "adultCount": 1, "childCount": 0, "infantCount": 0,
    }

    def real():
        _pausa()
        try:
            return _t().post_json("search/timetableV2", cuerpo)
        except Exception as e:
            if "429" in str(e) or "Kasada" in str(e) or "BotGate" in type(e).__name__:
                raise WizzBloqueado(str(e)) from e
            raise
    datos = cache.con_cache(["wizz", "timetableV2", cuerpo], HORAS_CACHE, real, usar_cache)
    return (_tramos(datos.get("outboundFlights", []), aeropuertos, "ida"),
            _tramos(datos.get("returnFlights", []), aeropuertos, "vuelta"))


def radar(origen, mes, destinos=None, dias_min=6, dias_max=8, usar_cache=True, avisar=None):
    """Radar de un mes (AAAA-MM) para viajes largos. Una consulta por ruta (Wizz solo admite un mes).
    Por destino: la ida más barata del mes y la mejor pareja ida+vuelta de `dias_min`-`dias_max` días
    (ida en ese mes; la vuelta puede caer en el siguiente). Guarda la ida más barata en el histórico.
    `avisar(i, n, destino)` se llama antes de cada ruta.
    Devuelve [{origen, destino, ciudad, pais, pais_nombre, ida: (fecha, precio), pareja: None | dict}]."""
    aeropuertos, red_destinos = red(origen, usar_cache)
    destinos = list(destinos or red_destinos)
    primero = date.fromisoformat(mes + "-01")
    ultimo = date(primero.year + primero.month // 12, primero.month % 12 + 1, 1) - timedelta(days=1)
    desde = max(primero, date.today())
    fin_vuelta = ultimo + timedelta(days=dias_max)
    res = []
    for i, d in enumerate(destinos, 1):
        if avisar:
            avisar(i, len(destinos), d)
        idas, vueltas = horarios(origen, d, desde.isoformat(), ultimo.isoformat(),
                                 desde.isoformat(), fin_vuelta.isoformat(), aeropuertos, usar_cache)
        por_dia = {}
        for t in idas:
            dia = t["salida"][:10]
            if dia not in por_dia or t["precio"] < por_dia[dia]["precio"]:
                por_dia[dia] = t
        if not por_dia:
            continue
        vuelta_dia = {}
        for t in vueltas:
            dia = t["salida"][:10]
            if dia not in vuelta_dia or t["precio"] < vuelta_dia[dia]["precio"]:
                vuelta_dia[dia] = t
        mejor = min(por_dia.values(), key=lambda t: t["precio"])
        pareja = None
        for dia, ti in por_dia.items():
            for n in range(dias_min, dias_max + 1):
                dv = (date.fromisoformat(dia) + timedelta(days=n)).isoformat()
                tv = vuelta_dia.get(dv)
                if tv and (pareja is None or ti["precio"] + tv["precio"] < pareja["total"]):
                    pareja = {"aerolinea": "Wizz Air", "ida": dia, "vuelta": dv, "precio_ida": ti["precio"],
                              "precio_vuelta": tv["precio"], "total": ti["precio"] + tv["precio"], "noches": n,
                              "tramos": {"ida": ti, "vuelta": tv}}
        res.append({"origen": origen, "destino": d, "ciudad": mejor["ciudad"], "pais": mejor["pais"],
                    "pais_nombre": mejor["pais_nombre"], "salida": mejor["salida"], "precio": mejor["precio"],
                    "directo": True, "ida": (mejor["salida"][:10], mejor["precio"]), "pareja": pareja,
                    "enlace": mejor["enlace"]})
    if res:
        cache.guardar_lecturas("wizz", res, date.today().isoformat())
    return res


if __name__ == "__main__":
    import sys
    if "--radar" in sys.argv:
        i = sys.argv.index("--mes") if "--mes" in sys.argv else -1
        if i < 0 or i + 1 >= len(sys.argv):
            sys.exit("Uso: python wizz.py --radar --mes AAAA-MM [--destinos KUT,TIA]")
        mes = sys.argv[i + 1]
        dests = (sys.argv[sys.argv.index("--destinos") + 1].upper().split(",")
                 if "--destinos" in sys.argv else None)
        try:
            lect = radar("BCN", mes, dests,
                         avisar=lambda k, n, d: print(f"  [{k}/{n}] {d}...", end="\r", flush=True))
        except WizzBloqueado as e:
            sys.exit(f"Wizz no responde ahora ({e}). No se insiste.")
        print(f"Radar Wizz Air desde BCN, {mes} (solo ida, precio del día más barato; sin Discount Club):   ")
        for r in sorted(lect, key=lambda r: r['precio']):
            print(f"  {r['precio']:6.2f} €  {r['ciudad'] + ' (' + r['destino'] + ')':28s} {r['pais_nombre']:16s} "
                  f"sale {r['salida'][:10]}")
