"""
gotogate.py — Pieza de GoToGate para Jawdrop (segunda fuente de precios, empezando por Cuba que Kiwi no vende).

GoToGate (agencia que revende vuelos de muchas aerolíneas) enseña en su web ida y vuelta CON PRECIO CERRADO. Su buscador público usa una
consulta GraphQL (`/graphql/SearchOnResultPage`) que se puede pedir sin navegador: se abre la portada, se guardan sus cookies (como haría
cualquier cliente) y se repite la consulta. Sin clave, sin captcha. Medido el 19-10-2026: Madrid-La Habana 12-26 nov = 494 vuelos desde 1.197 €;
el Air Europa directo salió a 1.761 € (Skyscanner: 1.763 €).
  - Ida y vuelta (dos fechas), 1 adulto, turista. El precio es el de GoToGate (incluye sus tasas; la aerolínea directa puede variar).
  - Caché de 24 h y pausa entre consultas reales. Si responde con error o sin sesión se avisa (`GotogateBloqueado`) y el programa sigue sin
    GoToGate: no se insiste ni se disfraza nada.
Cada vuelo: precio (€), aerolíneas, tramos (ida/vuelta con aeropuerto, hora, aerolínea y número de vuelo), escalas y enlace de reserva.
"""
import time

import requests

import cache

VERSION = "0.3"
URL = "https://es.gotogate.com/graphql/SearchOnResultPage"
PORTADA = "https://es.gotogate.com/"
HORAS_CACHE = 24
PAUSA = 5.0   # segundos entre consultas reales (la prueba de tolerancia dirá si se puede bajar)
CABECERAS = {"User-Agent": "EscapadasFlash/0.2 (uso personal)", "content-type": "application/json", "X-ETG-GraphQL-Operation": "SearchOnResultPage"}

CONSULTA = """query SearchOnResultPage($routes: [Route!]!, $cabinClass: CabinClass, $direct: Boolean, $carrierCodes: [String], $adults: Int!, $childAges: [Int], $sortTypeCode: String, $filters: [Filter!]) {
  search(routes: $routes, cabinClass: $cabinClass, direct: $direct, carrierCodes: $carrierCodes, adults: $adults, childAges: $childAges, sortTypeCode: $sortTypeCode, filters: $filters) {
    flightsCount
    flights {
      id
      shareableUrl
      travelerPrices { price { price { value } } }
      bounds { segments { __typename
        ... on TripSegment { departuredAt arrivedAt duration flightNumber origin { code } destination { code } marketingCarrier { code name } }
        ... on EventSegment { duration } } }
    }
  }
}"""

_sesion = None
_ultima = 0.0


class GotogateBloqueado(Exception):
    pass


def _sesion_nueva():
    s = requests.Session()
    s.headers.update(CABECERAS)
    try:
        s.get(PORTADA, timeout=30)
    except requests.RequestException as e:
        raise GotogateBloqueado(str(e)) from e
    return s


def _consulta(origen, destino, ida, vuelta):
    """Una consulta real (respeta la pausa). Devuelve la lista de vuelos en bruto. Sesión nueva si la anterior no devuelve nada."""
    global _sesion, _ultima
    espera = PAUSA - (time.time() - _ultima)
    if espera > 0:
        time.sleep(espera)
    rutas = [{"origin": origen, "destination": destino, "departureDate": ida}]
    if vuelta:
        rutas.append({"origin": destino, "destination": origen, "departureDate": vuelta})
    cuerpo = {"operationName": "SearchOnResultPage", "query": CONSULTA,
              "variables": {"adults": 1, "cabinClass": "ECONOMY", "carrierCodes": [], "childAges": [], "direct": False, "filters": [],
                            "routes": rutas, "sortTypeCode": "CHEAP_TRIP"}}
    for intento in (1, 2):
        if _sesion is None:
            _sesion = _sesion_nueva()
        try:
            r = _sesion.post(URL, json=cuerpo, timeout=90)
        except requests.RequestException as e:
            _ultima = time.time()
            raise GotogateBloqueado(str(e)) from e
        _ultima = time.time()
        if r.status_code != 200:
            raise GotogateBloqueado(f"GoToGate respondió {r.status_code}: {r.text[:200]}")
        try:
            s = r.json()["data"]["search"]
        except (ValueError, KeyError, TypeError) as e:
            raise GotogateBloqueado(f"respuesta de GoToGate no entendida: {r.text[:200]}") from e
        if s["flightsCount"] or intento == 2:
            return s["flights"] or []
        _sesion = None   # 0 vuelos: lo normal si la sesión caducó; se abre otra y se repite UNA vez (si sigue en 0, es que no hay)


def _formatear(f):
    """tramos = por sentido, lista de vuelos; horas = duración total de cada sentido (vuelos + esperas, de GoToGate); esperas = horas de cada escala."""
    tramos, horas, esperas = [], [], []
    for b in f["bounds"]:
        segs = [s for s in b["segments"] if s["__typename"] == "TripSegment"]
        tramos.append([{"desde": s["origin"]["code"], "hasta": s["destination"]["code"], "sale": s["departuredAt"], "llega": s["arrivedAt"],
                        "aerolinea": s["marketingCarrier"]["name"], "sigla": s["marketingCarrier"]["code"], "vuelo": s["flightNumber"]} for s in segs])
        horas.append(round(sum(s["duration"] for s in b["segments"]) / 3600000, 1))
        esperas.append([round(s["duration"] / 3600000, 1) for s in b["segments"] if s["__typename"] == "EventSegment"])
    return {"precio": f["travelerPrices"][0]["price"]["price"]["value"] / 100, "tramos": tramos, "horas": horas, "esperas": esperas,
            "aerolineas": sorted({x["aerolinea"] for t in tramos for x in t}),
            "escalas_ida": len(tramos[0]) - 1, "escalas_vuelta": (len(tramos[1]) - 1) if len(tramos) > 1 else None,
            "enlace": f["shareableUrl"]}


def buscar(origen, destino, ida, vuelta=None, usar_cache=True):
    """Vuelos de ida y vuelta (o solo ida si `vuelta` es None) de ORIGEN a DESTINO (códigos IATA de aeropuerto o ciudad, fechas AAAA-MM-DD),
    ordenados del más barato al más caro. Pasa por la caché de 24 h."""
    brutos = cache.con_cache(["gotogate2", origen, destino, ida, vuelta], HORAS_CACHE, lambda: _consulta(origen, destino, ida, vuelta), usar_cache)
    return sorted((_formatear(f) for f in brutos), key=lambda x: x["precio"])


if __name__ == "__main__":
    import sys
    o, d, i, v = (sys.argv[1:5] + [None])[:4]
    for x in buscar(o, d, i, v)[:8]:
        print(f"{x['precio']:7.0f} €  ida {x['escalas_ida']} esc / vuelta {x['escalas_vuelta']} esc  {', '.join(x['aerolineas'])}")
