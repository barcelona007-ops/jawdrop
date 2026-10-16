"""
liteapi.py — Hoteles por LiteAPI (Nuitee) para Jawdrop (EXPERIMENTAL).

Una llamada a /hotels/rates trae TODA una ciudad con sus habitaciones y precios. El endpoint de tarifas
no tiene cupo mensual (es gratis dentro de las condiciones de uso), así que no gasta las búsquedas de
SerpApi. Va por la caché (6 h) y con pausa entre llamadas. La clave sale de .env (LITEAPI_KEY).

Uso de prueba:  .venv\\Scripts\\python.exe liteapi.py "Turin" IT 2026-11-29 2026-12-01
"""
import re
import sys
import time
from urllib.parse import urlencode

import requests

import cache
import config
import hoteles

VERSION = "0.7"
URL = "https://api.liteapi.travel/v3.0/hotels/rates"
HORAS_CACHE = 6
PAUSA = 1.5            # el límite de sandbox es de 5 peticiones por segundo; vamos muy por debajo
_ultima = 0.0


def _post(cuerpo, usar_cache=True):
    global _ultima

    def real():
        global _ultima
        espera = PAUSA - (time.time() - _ultima)
        if espera > 0:
            time.sleep(espera)
        for intento in range(5):             # 429 = demasiado rápido: esperar el doble cada vez
            _ultima = time.time()
            r = requests.post(URL, json=cuerpo, timeout=90,
                              headers={"X-API-Key": config.liteapi_key(), "accept": "application/json",
                                       "content-type": "application/json"})
            if r.status_code != 429:
                break
            time.sleep(3 * 2 ** intento)
        if r.status_code == 429:
            raise RuntimeError("LiteAPI: demasiadas peticiones (429); espera unos minutos")
        if r.status_code in (401, 403):
            raise RuntimeError("LiteAPI rechaza la clave (revisa LITEAPI_KEY en el .env)")
        if r.status_code == 404:
            return {"data": [], "hotels": []}      # sin disponibilidad
        r.raise_for_status()
        return r.json()

    return cache.con_cache(["liteapi", "rates", cuerpo], HORAS_CACHE, real, usar_cache)


def cuerpo(ciudad, pais, entrada, salida, limite=200):
    return {"cityName": ciudad, "countryCode": pais, "checkin": entrada, "checkout": salida,
            "currency": "EUR", "guestNationality": "ES", "occupancies": [{"adults": 1}],
            "limit": limite, "maxRatesPerHotel": 12, "timeout": 12}


def leer(datos):
    """Respuesta -> (sandbox, [{nombre, nota, opiniones, estrellas, zona, habitaciones:[{nombre, precio,
    personas, cancelable}]}]). No consulta nada. El precio es el TOTAL de la estancia."""
    fichas = {h.get("id"): h for h in datos.get("hotels", [])}
    salida = []
    for d in datos.get("data", []):
        ficha = fichas.get(d.get("hotelId"), {})
        habs = []
        for rt in d.get("roomTypes", []):
            for r in rt.get("rates", []):
                total = ((r.get("retailRate") or {}).get("total") or [{}])[0].get("amount")
                if total is None:
                    continue
                politica = (r.get("cancellationPolicies") or {}).get("refundableTag")
                habs.append({"nombre": hoteles._arreglado(r.get("name") or rt.get("name")),
                             "precio_total": float(total), "personas": r.get("maxOccupancy"),
                             "cancelable": politica == "RFN", "desayuno": r.get("boardName")})
        salida.append({"id": d.get("hotelId"), "nombre": ficha.get("name") or d.get("hotelId"),
                       "nota": ficha.get("rating"), "opiniones": ficha.get("review_count"),
                       "estrellas": ficha.get("stars"), "zona": ficha.get("address"),
                       "lat": ficha.get("latitude"), "lon": ficha.get("longitude"),
                       "foto": ficha.get("main_photo"), "habitaciones": habs})
    return bool(datos.get("sandbox")), salida


def buscar(ciudad, pais, entrada, salida, usar_cache=True):
    return leer(_post(cuerpo(ciudad, pais, entrada, salida), usar_cache))


class _SinCache(Exception):
    pass


def _no_pedir():
    raise _SinCache()


def desde_cache(ciudad, pais, entrada, salida):
    """Alojamientos ya guardados (de cualquier antigüedad) o None si no se ha consultado. No llama a la API."""
    try:
        datos = cache.con_cache(["liteapi", "rates", cuerpo(ciudad, pais, entrada, salida)], 10 ** 6,
                                _no_pedir, True)
    except _SinCache:
        return None
    return leer(datos)[1]


NOTA_MINIMA = 7.0     # LiteAPI da la nota sobre 10 (lo que pidió el usuario: 7 o más)
NOMBRES = {"Turín": "Turin", "Venecia": "Venice", "Milán": "Milan", "Bérgamo": "Bergamo", "Roma": "Rome",
           "Londres": "London", "Lisboa": "Lisbon", "Oporto": "Porto", "Cracovia": "Krakow",
           "Varsovia": "Warsaw", "Breslavia": "Wroclaw", "Praga": "Prague", "Viena": "Vienna",
           "Génova": "Genoa", "Nápoles": "Naples", "Bolonia": "Bologna", "Niza": "Nice", "Bruselas": "Brussels",
           "Basilea": "Basel", "Chisináu": "Chisinau", "Dánzig": "Gdansk", "Sofía": "Sofia", "París": "Paris", "París-Orly": "Paris", "Málaga": "Malaga",
           "Múnich": "Munich", "Colonia": "Cologne", "Copenhague": "Copenhagen", "Belgrado": "Belgrade",
           "Edimburgo": "Edinburgh", "Ámsterdam": "Amsterdam", "Hamburgo": "Hamburg", "Berlín": "Berlin",
           "Bucarest": "Bucharest", "Tánger": "Tangier", "Atenas": "Athens", "Florencia": "Florence"}
PAISES = {"Suiza": "CH", "Moldavia": "MD", "República Checa": "CZ", "España": "ES", "Italia": "IT", "Marruecos": "MA", "Portugal": "PT", "Reino Unido": "GB", "Francia": "FR",
          "Alemania": "DE", "Polonia": "PL", "Hungría": "HU", "Rumanía": "RO", "Croacia": "HR", "Bélgica": "BE",
          "Países Bajos": "NL", "Grecia": "GR", "Irlanda": "IE", "Austria": "AT", "Chequia": "CZ",
          "Bulgaria": "BG", "Albania": "AL", "Malta": "MT", "Eslovaquia": "SK", "Dinamarca": "DK",
          "Suecia": "SE", "Noruega": "NO", "Finlandia": "FI", "Lituania": "LT", "Letonia": "LV",
          "Estonia": "EE", "Turquía": "TR", "Egipto": "EG", "Serbia": "RS", "Eslovenia": "SI"}


def destino(texto):
    """'Turín (TRN), Italia' -> ('Turin', 'IT') o None si no se conoce el país."""
    m = re.match(r"\s*([^(,]+?)\s*(?:\(\w{3}\))?\s*,\s*(.+?)\s*$", texto)
    if not m:
        return None
    ciudad, pais = m.group(1), PAISES.get(m.group(2))
    ciudad = re.sub(r"\s+(Otopeni|Chopin|Orly|Stansted|Gatwick|Luton|Fiumicino|Ciampino).*$", "", ciudad)
    return (NOMBRES.get(ciudad, ciudad), pais) if pais else None


def enlace_booking(nombre, ciudad, entrada, salida):
    """Búsqueda en Booking por el nombre del hotel (ver booking.hotel: hay que pulsar «Buscar»)."""
    import booking
    return booking.hotel(nombre, ciudad, entrada, salida)


def enlace_mapa(nombre, ciudad):
    return "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{nombre}, {ciudad}"})


FACTOR_PRECIO = 1.0   # Calibrado con la lista real de Booking del usuario (Palermo, 1→2-nov, baño privado, nota ≥ 7,
                      # su nivel Genius, impuestos incluidos): 43, 43, 44, 44, 44, 45 €. La criba sobre LiteAPI da
                      # 42, 44, 46 (mediana 44) → factor ≈ 1. (Con 1,2 salían 56 €: sobraba. El 1,13-1,2 de Google/
                      # LiteAPI es precio PÚBLICO; el del usuario lleva el descuento Genius, ~15-20 %.) Una ciudad: pocos datos.
MIN_OPINIONES = 50    # como el usuario: casi nadie ha valorado lo que tiene menos
MAX_KM = 3.0          # distancia al centro (mediana de las coordenadas de la ciudad)


def _km(a, b):
    import math
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def estimar(ciudad, pais, entrada, salida, usar_cache=True, texto=None):
    """Hoteles que el usuario miraría (criba parecida a la de Booking) y un precio orientativo por noche.

    Criba: habitación sin litera ni baño compartido (por el nombre), nota ≥ 7/10 (la de LiteAPI se parece
    a la de Booking), ≥ 50 opiniones y ≤ 3 km del centro. Se enseñan los 3 más baratos; el estimado es la
    MEDIANA de esos 3 (no el mínimo, que suele ser un extremo) por FACTOR_PRECIO. Una llamada, gratis.
    """
    import statistics
    from datetime import datetime
    noches = (datetime.strptime(salida, "%Y-%m-%d") - datetime.strptime(entrada, "%Y-%m-%d")).days
    _, lista = buscar(ciudad, pais, entrada, salida, usar_cache)
    pts = [(float(h["lat"]), float(h["lon"])) for h in lista if h.get("lat") and h.get("lon")]
    centro = (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts)) if pts else None
    cand = []
    for h in lista:
        if h["nota"] is None or float(h["nota"]) < NOTA_MINIMA:
            continue
        if int(h.get("opiniones") or 0) < MIN_OPINIONES:
            continue
        km = None
        if centro and h.get("lat") and h.get("lon"):
            km = _km(centro, (float(h["lat"]), float(h["lon"])))
            if km > MAX_KM:
                continue
        val = [x for x in h["habitaciones"] if hoteles.clasificar(x["nombre"], x["personas"])]
        if not val:
            continue
        m = min(val, key=lambda x: x["precio_total"])
        cand.append({"nombre": h["nombre"], "nota": float(h["nota"]), "opiniones": int(h["opiniones"]),
                     "km": round(km, 1) if km is not None else None, "hab": m["nombre"],
                     "cancelable": m["cancelable"], "desayuno": m["desayuno"],
                     "porNocheLite": round(m["precio_total"] / noches, 2),
                     "porNoche": round(m["precio_total"] / noches * FACTOR_PRECIO, 2),
                     "booking": enlace_booking(h["nombre"], texto or ciudad, entrada, salida)})
    cand.sort(key=lambda c: c["porNoche"])
    if not cand:
        return None
    top = cand[:3]
    por_noche = statistics.median(c["porNoche"] for c in top)
    return {"porNoche": round(por_noche, 2), "total": round(por_noche * noches, 2), "noches": noches,
            "candidatos": len(cand), "sugerencias": top}


def propuestas(lista, noches, n=3):
    """Los n alojamientos más baratos con habitación válida y nota ≥ 7. Precio = total de la estancia."""
    out = []
    for h in lista:
        if h["nota"] is None or h["nota"] < NOTA_MINIMA:
            continue
        val = [x for x in h["habitaciones"] if hoteles.clasificar(x["nombre"], x["personas"])]
        if val:
            m = min(val, key=lambda x: x["precio_total"])
            out.append({"nombre": h["nombre"], "nota": h["nota"], "estrellas": h["estrellas"],
                        "zona": h.get("zona"), "lat": h.get("lat"), "lon": h.get("lon"),
                        "habitacion": m["nombre"], "total": m["precio_total"], "noches": noches,
                        "por_noche": m["precio_total"] / noches, "cancelable": m["cancelable"],
                        "confianza": hoteles.clasificar(m["nombre"], m["personas"])})
    out.sort(key=lambda p: p["total"])
    return out[:n]


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    sys.stdout.reconfigure(encoding="utf-8")
    crudo = _post(cuerpo(*sys.argv[1:5]))
    sandbox, lista = leer(crudo)
    print(f"sandbox: {sandbox} · claves de la respuesta: {list(crudo)} · alojamientos con tarifa: {len(lista)}")
    for h in lista[:25]:
        habs = sorted(h["habitaciones"], key=lambda x: x["precio_total"])
        mejor = next((x for x in habs if hoteles.clasificar(x["nombre"], x["personas"])), None)
        print(f"- {h['nombre']} · nota {h['nota']} ({h['opiniones']} op.) · {h['estrellas']}★ · "
              f"{len(habs)} tarifas")
        for x in habs[:3]:
            marca = "✓" if hoteles.clasificar(x["nombre"], x["personas"]) else "✗"
            print(f"     {marca} {x['precio_total']:>7.2f} €  {x['nombre']}  ({x['personas']} pers.)")
