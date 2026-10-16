"""
vueling.py — Pieza de Vueling para Jawdrop.

Vueling ya no tiene consulta propia que podamos leer, así que se usa SerpApi (Google Flights):
  - Una búsqueda de SerpApi = 1 de las 250 gratis al mes. Las respuestas se guardan en la caché
    (12 horas): repetir la misma búsqueda no gasta.
  - Se filtra por Vueling (VY) y solo vuelos directos. Una búsqueda admite VARIOS aeropuertos a la vez,
    así que se agrupan en lotes de LOTE: la ida de un domingo = 1 búsqueda por lote de destinos, y cada
    día de vuelta = 1 búsqueda por lote de aeropuertos de salida.
  - Google da la hora de llegada real (no calculada) y el precio del vuelo concreto.
Seguridad del gasto:
  - `TOPE` fija cuántas búsquedas NUEVAS puede hacer esta ejecución (por defecto 10). Al llegar, se para.
  - `SIMULAR = True` no llama a SerpApi: solo cuenta cuántas gastaría (`gastadas()`).
  - `cuota()` / `cuenta()` preguntan a SerpApi cuántas quedan este mes y cuándo se renuevan (no gasta).
  - Los vuelos de Vueling vistos se GUARDAN por domingo con su fecha (`guardar_tramos`) y se siguen
    enseñando después, sin gastar, marcados con su antigüedad (`tramos_guardados`).
La clave sale de config.py (.env); este módulo nunca la muestra.

Desde la 2.0 hay además el RADAR GRATIS (`mejores_precios`, `radar`, `historico`): usa `bestPrices`, la
consulta pública que alimenta el calendario de precios de la web de Vueling. No gasta SerpApi.
  - Da, por destino, UN precio: el mejor vuelo directo solo de ida desde la fecha pedida (con día y hora
    de salida, sin hora de llegada). No fija un domingo concreto: sirve para ver «cuándo está barato».
  - Cada lectura se guarda con su fecha en la tabla `lecturas` de la caché (histórico).
  - Pausa de varios segundos entre consultas y caché de 12 h; si Vueling responde mal, se avisa y se sigue.
  - `enlace(desde, hasta, dia)`: enlace directo a la lista de vuelos de ese día en la web de Vueling (2.2).
  - OJO: `bestPrices` da la hora de salida en UTC (1 h menos que la local en invierno, 2 h en verano).
    Desde la 2.1 se pasa a la hora de Barcelona (Europe/Madrid) al leerla. Comprobado con 37 vuelos
    contra Kiwi (12-10-2026). Vale para salidas de España peninsular, que es lo que usamos.
"""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

import aeropuertos as aeropuertos_tabla
import cache
import config

VERSION = "2.5"
HORAS_CACHE = 12
HORAS_RED = 24 * 90
LOTE = 10          # aeropuertos por búsqueda: probado, con 12 o más Google no devuelve nada

# Punto de partida: destinos internacionales de Vueling desde BCN (de memoria; se completa y corrige
# solo, porque se guarda cada aeropuerto donde se ve un vuelo de Vueling).
RED_INICIAL = [
    "AMS", "ATH", "BER", "BRU", "CDG", "ORY", "LHR", "LGW", "FCO", "MXP", "LIN", "VCE", "NAP", "BLQ",
    "FLR", "PSA", "GOA", "TRN", "CTA", "PMO", "BRI", "ZRH", "GVA", "BSL", "VIE", "MUC", "FRA", "DUS",
    "HAM", "STR", "CGN", "LIS", "OPO", "FAO", "DUB", "EDI", "MAN", "BHX", "CPH", "ARN", "OSL", "HEL",
    "PRG", "BUD", "WAW", "KRK", "SKG", "IST", "TLV", "CMN", "RAK", "TNG", "AGA", "ALG", "ORN", "TUN",
    "NCE", "LYS", "MRS", "TLS", "BOD", "NTE", "BIQ", "SXB", "MLA", "DBV", "SPU", "ZAG", "TIA", "BEG",
    "OTP", "SOF", "RIX", "VNO", "TLL", "LUX", "BLL", "BVA", "NUE", "LEJ", "BRN", "NAP", "AMM", "CAI",
]
# Ciudad, país (código) y nombre del país de cada aeropuerto de la red. Bestprices y la búsqueda de Google
# dan solo el código: si ni Ryanair, Wizz ni Kiwi traen el nombre (p. ej. Burdeos, BOD), se usa esta tabla
# en vez de enseñar el código.
CIUDADES = {
    "AMS": ("Ámsterdam", "NL", "Países Bajos"), "ATH": ("Atenas", "GR", "Grecia"),
    "BER": ("Berlín", "DE", "Alemania"), "BRU": ("Bruselas", "BE", "Bélgica"),
    "CDG": ("París", "FR", "Francia"), "ORY": ("París", "FR", "Francia"),
    "BVA": ("París-Beauvais", "FR", "Francia"), "LHR": ("Londres", "GB", "Reino Unido"),
    "LGW": ("Londres", "GB", "Reino Unido"), "FCO": ("Roma", "IT", "Italia"),
    "MXP": ("Milán", "IT", "Italia"), "LIN": ("Milán", "IT", "Italia"), "VCE": ("Venecia", "IT", "Italia"),
    "NAP": ("Nápoles", "IT", "Italia"), "BLQ": ("Bolonia", "IT", "Italia"), "FLR": ("Florencia", "IT", "Italia"),
    "PSA": ("Pisa", "IT", "Italia"), "GOA": ("Génova", "IT", "Italia"), "TRN": ("Turín", "IT", "Italia"),
    "CTA": ("Catania", "IT", "Italia"), "PMO": ("Palermo", "IT", "Italia"), "BRI": ("Bari", "IT", "Italia"),
    "ZRH": ("Zúrich", "CH", "Suiza"), "GVA": ("Ginebra", "CH", "Suiza"), "BSL": ("Basilea", "CH", "Suiza"),
    "BRN": ("Berna", "CH", "Suiza"), "VIE": ("Viena", "AT", "Austria"), "MUC": ("Múnich", "DE", "Alemania"),
    "FRA": ("Fráncfort", "DE", "Alemania"), "DUS": ("Düsseldorf", "DE", "Alemania"),
    "HAM": ("Hamburgo", "DE", "Alemania"), "STR": ("Stuttgart", "DE", "Alemania"),
    "CGN": ("Colonia", "DE", "Alemania"), "NUE": ("Núremberg", "DE", "Alemania"),
    "LEJ": ("Leipzig", "DE", "Alemania"), "LIS": ("Lisboa", "PT", "Portugal"), "OPO": ("Oporto", "PT", "Portugal"),
    "FAO": ("Faro", "PT", "Portugal"), "DUB": ("Dublín", "IE", "Irlanda"), "EDI": ("Edimburgo", "GB", "Reino Unido"),
    "MAN": ("Mánchester", "GB", "Reino Unido"), "BHX": ("Birmingham", "GB", "Reino Unido"),
    "CPH": ("Copenhague", "DK", "Dinamarca"), "BLL": ("Billund", "DK", "Dinamarca"),
    "ARN": ("Estocolmo", "SE", "Suecia"), "OSL": ("Oslo", "NO", "Noruega"), "HEL": ("Helsinki", "FI", "Finlandia"),
    "PRG": ("Praga", "CZ", "Chequia"), "BUD": ("Budapest", "HU", "Hungría"), "WAW": ("Varsovia", "PL", "Polonia"),
    "KRK": ("Cracovia", "PL", "Polonia"), "SKG": ("Tesalónica", "GR", "Grecia"), "IST": ("Estambul", "TR", "Turquía"),
    "TLV": ("Tel Aviv", "IL", "Israel"), "CMN": ("Casablanca", "MA", "Marruecos"),
    "RAK": ("Marrakech", "MA", "Marruecos"), "TNG": ("Tánger", "MA", "Marruecos"),
    "AGA": ("Agadir", "MA", "Marruecos"), "ALG": ("Argel", "DZ", "Argelia"), "ORN": ("Orán", "DZ", "Argelia"),
    "TUN": ("Túnez", "TN", "Túnez"), "NCE": ("Niza", "FR", "Francia"), "LYS": ("Lyon", "FR", "Francia"),
    "MRS": ("Marsella", "FR", "Francia"), "TLS": ("Toulouse", "FR", "Francia"), "BOD": ("Burdeos", "FR", "Francia"),
    "NTE": ("Nantes", "FR", "Francia"), "BIQ": ("Biarritz", "FR", "Francia"), "SXB": ("Estrasburgo", "FR", "Francia"),
    "MLA": ("Malta", "MT", "Malta"), "DBV": ("Dubrovnik", "HR", "Croacia"), "SPU": ("Split", "HR", "Croacia"),
    "ZAG": ("Zagreb", "HR", "Croacia"), "TIA": ("Tirana", "AL", "Albania"), "BEG": ("Belgrado", "RS", "Serbia"),
    "OTP": ("Bucarest", "RO", "Rumanía"), "SOF": ("Sofía", "BG", "Bulgaria"), "RIX": ("Riga", "LV", "Letonia"),
    "VNO": ("Vilna", "LT", "Lituania"), "TLL": ("Tallin", "EE", "Estonia"), "LUX": ("Luxemburgo", "LU", "Luxemburgo"),
    "AMM": ("Amán", "JO", "Jordania"), "CAI": ("El Cairo", "EG", "Egipto"),
}


def ciudad(codigo):
    """(ciudad, código de país, nombre del país) de un aeropuerto de la red de Vueling; si no está en la
    tabla, (código, "", "") como antes."""
    if codigo in CIUDADES:
        ciu, pais, pais_nombre = CIUDADES[codigo]
        return ciu, pais, pais_nombre
    ciu, pais, pais_nombre = aeropuertos_tabla.corregir(codigo, codigo)
    return ciu, pais, pais_nombre


PAUSA = 3
TOPE = 10          # búsquedas nuevas permitidas en esta ejecución
LIMITE_MES = 245   # freno de la cuenta (250 reales): subido de 190 el 12-10-2026 por el usuario; el botón pide confirmación antes de gastar
SIMULAR = False

_gastadas = 0
_ultima = 0.0
_usadas_inicio = None  # búsquedas usadas del mes al empezar (se pregunta una vez; no gasta)
URL = "https://serpapi.com/search.json"
URL_CUENTA = "https://serpapi.com/account.json"


class SinPresupuesto(Exception):
    """Se ha llegado al tope de búsquedas de esta ejecución."""


class _Simulada(Exception):
    pass


def gastadas():
    """Búsquedas nuevas hechas (o, en simulación, que se habrían hecho) en esta ejecución."""
    return _gastadas


def cuenta():
    """Datos de la cuenta de SerpApi: usadas, total, quedan y fecha de renovación. No gasta búsquedas."""
    r = requests.get(URL_CUENTA, params={"api_key": config.serpapi_key()}, timeout=30)
    r.raise_for_status()
    d = r.json()
    total = d.get("searches_per_month") or d.get("plan_searches_left", 0)
    quedan = d.get("total_searches_left", d.get("plan_searches_left", 0))
    return {"usadas": max(total - quedan, 0), "total": total, "quedan": quedan,
            "renueva": d.get("plan_renewal_date")}


def cuota():
    """(usadas, total, quedan) del mes en SerpApi. No gasta búsquedas."""
    c = cuenta()
    return c["usadas"], c["total"], c["quedan"]


def utiles(c):
    """Búsquedas que se pueden gastar de verdad: las que quedan, sin pasar del freno del mes."""
    return max(0, min(c["quedan"], LIMITE_MES - c["usadas"]))


def reiniciar():
    """Pone a cero el contador de la ejecución (el servidor local hace varias en un mismo proceso)."""
    global _gastadas, _usadas_inicio
    _gastadas = 0
    _usadas_inicio = None


# ---- Vuelos de Vueling guardados, con su fecha ----------------------------------------------------

def enlace(desde, hasta, dia):
    """Búsqueda de Skyscanner de ese trayecto y día (solo ida, 1 adulto, directos). Desde 13-10-2026 ya no es la web de Vueling:
    su dirección de búsqueda (tickets.vueling.com/booking/flightSearch) manda a la portada en cuanto el navegador es de móvil
    (m.vueling.com no tiene dirección de búsqueda). Skyscanner enseña ese día con todas las aerolíneas; la de Vueling es una."""
    a, m, d = dia.split("-")
    return (f"https://www.skyscanner.es/transporte/vuelos/{desde.lower()}/{hasta.lower()}/{a[2:]}{m}{d}/"
            "?adultsv2=1&cabinclass=economy&rtn=0&preferdirects=true")


def _clave_guardado(domingo):
    return ["vueling", "guardado", domingo]


def tramos_guardados(domingo):
    """Vuelos de Vueling vistos en búsquedas anteriores para ese domingo; cada uno con `visto` (fecha)."""
    datos = cache.con_cache(_clave_guardado(domingo), HORAS_RED, lambda: [], True)
    # los guardados antes de la 2.2 llevaban el enlace genérico: se les pone el directo
    return [dict(t, enlace=enlace(t["desde"], t["hasta"], t["salida"][:10])) for t in datos]


def guardar_tramos(domingo, tramos, completo):
    """Guarda los vuelos vistos (con la hora de hoy). `completo` = la búsqueda llegó hasta el final:
    sustituye a lo guardado; si no, se mezcla (lo nuevo manda, lo viejo se conserva con su fecha)."""
    if SIMULAR:
        return
    ahora = datetime.now().isoformat(timespec="seconds")
    llave = lambda t: (t["desde"], t["hasta"], t["salida"])
    datos = {} if completo else {llave(t): t for t in tramos_guardados(domingo)}
    datos.update({llave(t): dict(t, visto=ahora) for t in tramos})
    cache.con_cache(_clave_guardado(domingo), HORAS_RED, lambda: list(datos.values()), False)


def _buscar(params, usar_cache):
    """Una búsqueda de Google Flights por SerpApi, con caché, tope y pausa."""
    global _gastadas, _ultima

    def real():
        global _gastadas, _ultima, _usadas_inicio
        if _gastadas >= TOPE:
            raise SinPresupuesto(f"tope de {TOPE} búsquedas de SerpApi alcanzado")
        if not SIMULAR:
            if _usadas_inicio is None:
                try:
                    _usadas_inicio = cuota()[0]
                except Exception as e:
                    raise SinPresupuesto(f"no se pudo comprobar la cuota de SerpApi ({str(e)[:60]})") from e
            if _usadas_inicio + _gastadas >= LIMITE_MES:
                raise SinPresupuesto(f"límite de {LIMITE_MES} búsquedas del mes alcanzado "
                                     f"({_usadas_inicio + _gastadas} usadas)")
        _gastadas += 1
        if SIMULAR:
            raise _Simulada()
        espera = PAUSA - (time.time() - _ultima)
        if espera > 0:
            time.sleep(espera)
        _ultima = time.time()
        r = requests.get(URL, params=dict(params, api_key=config.serpapi_key()), timeout=60)
        if r.status_code in (401, 403):
            raise RuntimeError("SerpApi rechaza la clave (revisa el .env)")
        if r.status_code == 429:
            raise RuntimeError("SerpApi: sin búsquedas disponibles este mes")
        r.raise_for_status()
        return r.json()

    try:
        return cache.con_cache(["serpapi", "google_flights", params], HORAS_CACHE, real, usar_cache)
    except _Simulada:
        return {}


def _parametros(desde, hasta, dia, aerolinea="VY"):
    return {
        "engine": "google_flights", "type": "2",            # 2 = solo ida
        "departure_id": ",".join(desde), "arrival_id": ",".join(hasta),
        "outbound_date": dia, "include_airlines": aerolinea, "stops": "1",   # solo directos
        "currency": "EUR", "hl": "es", "adults": "1",
    }


def _tramos(datos, aeropuertos, sentido, nombre="Vueling"):
    """Pasa los vuelos de Google al formato común (igual que ryanair.py y wizz.py)."""
    res = []
    for opcion in (datos.get("best_flights") or []) + (datos.get("other_flights") or []):
        tramos = opcion.get("flights") or []
        if len(tramos) != 1 or not opcion.get("price"):
            continue  # con escala o sin precio
        v = tramos[0]
        desde, hasta = v["departure_airport"]["id"], v["arrival_airport"]["id"]
        otro = hasta if sentido == "ida" else desde
        ap = aeropuertos.get(otro) or dict(zip(("ciudad", "pais", "pais_nombre"), ciudad(otro)))
        res.append({
            "aerolinea": nombre,
            "desde": desde, "hasta": hasta, "destino": otro,
            "ciudad": ap.get("ciudad", otro),
            "pais": ap.get("pais", ""),
            "pais_nombre": ap.get("pais_nombre", ""),
            "salida": v["departure_airport"]["time"].replace(" ", "T")[:16],
            "llegada": v["arrival_airport"]["time"].replace(" ", "T")[:16],
            "llegada_aprox": False,
            "vuelo": v.get("flight_number", ""),
            "precio": float(opcion["price"]),
            "precio_minimo": False,
            "enlace": enlace(desde, hasta, v["departure_airport"]["time"][:10]),
        })
    return res


def _lotes(codigos):
    codigos = sorted(set(codigos))
    return [codigos[i:i + LOTE] for i in range(0, len(codigos), LOTE)]


def red_conocida(usar_cache=True):
    """Aeropuertos donde se sabe (o se supone) que Vueling vuela desde/hacia BCN."""
    vista = cache.con_cache(["vueling", "red"], HORAS_RED, lambda: [], True)
    return sorted(set(RED_INICIAL) | set(vista))


def _aprender(codigos):
    """Guarda los aeropuertos donde se ha visto un vuelo de Vueling."""
    vista = set(cache.con_cache(["vueling", "red"], HORAS_RED, lambda: [], True))
    nuevos = set(codigos) - vista
    if nuevos and not SIMULAR:
        cache.con_cache(["vueling", "red"], HORAS_RED, lambda: sorted(vista | nuevos), False)


def idas(origen, destinos, dia, aeropuertos, usar_cache=True):
    """Vuelos de Vueling de `origen` a cualquiera de `destinos` ese día."""
    res = []
    for lote in _lotes(destinos):
        res += _tramos(_buscar(_parametros([origen], lote, dia), usar_cache), aeropuertos, "ida")
    _aprender(t["destino"] for t in res)
    return res


def vueltas(destino, salidas, dia, aeropuertos, usar_cache=True):
    """Vuelos de Vueling de cualquiera de `salidas` a `destino` (BCN) ese día."""
    res = []
    for lote in _lotes(salidas):
        res += _tramos(_buscar(_parametros(lote, [destino], dia), usar_cache), aeropuertos, "vuelta")
    _aprender(t["destino"] for t in res)
    return res


# ---- Radar gratis: bestPrices de Vueling ---------------------------------------------------------

URL_BEST = "https://apiw.vueling.com/api/v1/bestPrices"
LOTE_BEST = 10     # destinos por llamada (probado con 10)
PAUSA_BEST = 5
_ultima_best = 0.0


class VuelingBloqueado(Exception):
    """bestPrices no ha respondido bien. Se sigue sin el radar; no se insiste."""


def _llamar_best(origen, destinos, desde, meses):
    global _ultima_best
    espera = PAUSA_BEST - (time.time() - _ultima_best)
    if espera > 0:
        time.sleep(espera)
    _ultima_best = time.time()
    r = requests.get(URL_BEST, params={
        "originCode": origen, "destinationCodes": ",".join(destinos), "months": meses,
        "startDate": desde, "currencyCode": "EUR"}, timeout=30)
    if r.status_code != 200:
        raise VuelingBloqueado(f"bestPrices respondió {r.status_code}")
    try:
        valor = r.json()["bestPrices"]["value"]
    except Exception as e:
        raise VuelingBloqueado("bestPrices devolvió algo que no se entiende") from e
    return valor or []


def hora_local(utc):
    """'AAAA-MM-DDTHH:MM' en UTC (como la da bestPrices) -> la misma hora en Barcelona."""
    t = datetime.fromisoformat(utc[:16]).replace(tzinfo=timezone.utc)
    return t.astimezone(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%dT%H:%M")


def mejores_precios(origen, destinos, desde, meses=1, usar_cache=True):
    """Mejor vuelo directo de ida de `origen` a cada destino desde la fecha `desde` (AAAA-MM-DD).
    Devuelve [{origen, destino, salida, precio, directo}] y guarda cada lectura en el histórico."""
    destinos = sorted(set(destinos))
    res = []
    for i in range(0, len(destinos), LOTE_BEST):
        lote = destinos[i:i + LOTE_BEST]
        filas = cache.con_cache(["vueling", "bestprices", origen, lote, desde, meses], HORAS_CACHE,
                                lambda l=lote: _llamar_best(origen, l, desde, meses), usar_cache)
        for f in filas:
            res.append({"origen": f["originCode"], "destino": f["destinationCode"],
                        "salida": hora_local(f["departureDate"]),
                        "precio": f["integerPartPrice"] + f["decimalPartPrice"] / 100,
                        "directo": bool(f.get("isDirect", True))})
    if res:
        cache.guardar_lecturas("vueling", res, datetime.now().date().isoformat())
    return res


def radar(origen="BCN", destinos=None, meses_vista=6, usar_cache=True):
    """Radar de largo plazo: una lectura por destino y por mes (desde el día 1, o hoy en el mes actual).
    Devuelve las lecturas sin repetir (mismo destino y salida), de más barata a más cara."""
    from datetime import date
    hoy = date.today()
    destinos = destinos or red_conocida()
    vistas = {}
    for i in range(meses_vista):
        mes = hoy.month - 1 + i
        desde = hoy if i == 0 else date(hoy.year + mes // 12, mes % 12 + 1, 1)
        for t in mejores_precios(origen, destinos, desde.isoformat(), 1, usar_cache):
            vistas[(t["destino"], t["salida"])] = t
    return sorted(vistas.values(), key=lambda t: t["precio"])


def historico(origen="BCN"):
    """Por destino: nº de días con lectura (se toma la más barata de cada día), mínimo visto, precio
    típico (mediana) y última lectura. Con 3 o más días, `chollo` = la última está 20 % o más por
    debajo de lo típico."""
    from statistics import median
    por_dia = {}   # (destino, día visto) -> la lectura más barata de ese día
    for l in cache.lecturas("vueling", origen):
        k = (l["destino"], l["visto"])
        if k not in por_dia or l["precio"] < por_dia[k]["precio"]:
            por_dia[k] = l
    por_destino = {}
    for (destino, _), l in sorted(por_dia.items(), key=lambda kv: kv[0][1], reverse=True):
        por_destino.setdefault(destino, []).append(l)   # más reciente primero
    res = {}
    for destino, ls in por_destino.items():
        precios = [l["precio"] for l in ls]
        ultima = ls[0]
        tipico = median(precios)
        res[destino] = {"lecturas": len(ls), "minimo": min(precios), "tipico": tipico, "ultima": ultima,
                        "chollo": len(ls) >= 3 and ultima["precio"] <= tipico * 0.8}
    return res


def recuperar_de_cache(aeropuertos):
    """Una sola vez: rescata de la caché (aunque haya caducado) los vuelos de Vueling que ya se pagaron
    y los guarda por domingo con la fecha REAL en que se buscaron. No llama a SerpApi ni gasta nada.
    Devuelve {domingo: nº de vuelos}."""
    import json
    import sqlite3
    from datetime import date, timedelta
    con = sqlite3.connect(f"file:{cache.RUTA.as_posix()}?mode=ro", uri=True)
    hallados = {}   # domingo -> {(desde, hasta, salida): tramo}
    try:
        for guardado, j in con.execute("SELECT guardado, json FROM respuestas"):
            if "flight_number" not in j or "best_flights" not in j and "other_flights" not in j:
                continue
            datos = json.loads(j)
            if not isinstance(datos, dict):
                continue
            visto = datetime.fromtimestamp(guardado).isoformat(timespec="seconds")
            for sentido, extremo in (("ida", "desde"), ("vuelta", "hasta")):
                for t in _tramos(datos, aeropuertos, sentido):
                    if t[extremo] != "BCN" or not t["vuelo"].replace(" ", "").startswith("VY"):
                        continue
                    d = date.fromisoformat(t["salida"][:10])
                    domingo = (d - timedelta(days=(d.weekday() + 1) % 7)).isoformat()
                    llave = (t["desde"], t["hasta"], t["salida"])
                    previo = hallados.setdefault(domingo, {}).get(llave)
                    if not previo or previo["visto"] < visto:
                        hallados[domingo][llave] = dict(t, visto=visto)
    finally:
        con.close()
    for domingo, tramos in hallados.items():
        datos = {(t["desde"], t["hasta"], t["salida"]): t for t in tramos_guardados(domingo)}
        for llave, t in tramos.items():
            if llave not in datos or datos[llave].get("visto", "") < t["visto"]:
                datos[llave] = t
        cache.con_cache(_clave_guardado(domingo), HORAS_RED, lambda d=datos: list(d.values()), False)
    return {d: len(t) for d, t in sorted(hallados.items())}


if __name__ == "__main__":
    import sys
    if "--recuperar" in sys.argv:
        import ryanair
        for dom, n in recuperar_de_cache(ryanair.aeropuertos(True)).items():
            print(f"{dom}: {n} vuelos de Vueling recuperados de la caché")
        sys.exit()
    if "--radar" in sys.argv or "--historico" in sys.argv:
        import ryanair
        ap = ryanair.aeropuertos(True)
        nombre = lambda c: f"{ap[c]['ciudad'] if c in ap else ciudad(c)[0]} ({c})"
        if "--radar" in sys.argv:
            meses = int(sys.argv[sys.argv.index("--meses") + 1]) if "--meses" in sys.argv else 6
            dests = (sys.argv[sys.argv.index("--destinos") + 1].upper().split(",")
                     if "--destinos" in sys.argv else None)
            try:
                lecturas = radar("BCN", dests, meses)
            except VuelingBloqueado as e:
                sys.exit(f"Vueling no responde ahora ({e}). No se insiste.")
            print(f"Radar Vueling desde BCN, {meses} meses (solo ida, directo; precio de la web de Vueling):")
            for t in lecturas[:40]:
                print(f"  {t['precio']:6.2f} €  {nombre(t['destino']):30s} sale {t['salida'].replace('T', ' ')}")
        else:
            h = historico("BCN")
            print("Histórico Vueling desde BCN (mínimo visto · típico · última lectura):")
            for d, x in sorted(h.items(), key=lambda kv: kv[1]["ultima"]["precio"]):
                marca = "  ← CHOLLO" if x["chollo"] else ""
                print(f"  {nombre(d):30s} mín {x['minimo']:.0f} € · típico {x['tipico']:.0f} € · "
                      f"última {x['ultima']['precio']:.0f} € ({x['ultima']['visto']}) · {x['lecturas']} lect.{marca}")
        sys.exit()
    # Comprobación: cuántas búsquedas quedan este mes (no gasta ninguna).
    try:
        usadas, total, quedan = cuota()
        print(f"SerpApi: {usadas} usadas de {total} este mes; quedan {quedan}.")
    except Exception as e:
        print("No se pudo consultar la cuota:", str(e)[:120])
