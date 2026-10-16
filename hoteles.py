"""
hoteles.py — Pieza de hoteles para Jawdrop (EXPERIMENTAL, fase 5).

Usa SerpApi (Google Hotels). Una búsqueda = 1 de las 250 gratis al mes. Reutiliza el freno de gasto de
vueling.py (tope por ejecución, límite del mes y caché), así que nunca gasta de más.

Cómo distingue «habitación de verdad» de «litera»: la lista de Google solo da el precio de la cama más
barata (en un hostel, la litera). La ficha de cada alojamiento trae las habitaciones tal como las pone
Booking.com («Cama en habitación compartida de 10 camas con baño compartido», «Habitación Doble»...).
Se descartan las literas, los dormitorios y las habitaciones con baño compartido, y se queda con la
habitación individual/doble más barata. Una ficha = 1 búsqueda.

Uso de prueba:  .venv\\Scripts\\python.exe hoteles.py "Krakow" 2026-10-18 2026-10-19 [fichas_max]
"""
import math
import re
import statistics
import sys
import unicodedata
from datetime import datetime

import vueling

VERSION = "0.4"

NOTA_MINIMA = 3.5      # sobre 5 (≈ 7 sobre 10, lo que pidió el usuario el 11-10-2026)
UMBRAL_FICHA = 30      # solo se abre la ficha si el precio de la lista es menor (es probable que sea litera)
MAX_PERSONAS = 4       # una «habitación de 6 camas» es un dormitorio aunque no lo diga

_DORMITORIO = ("cama en", "dormitorio", "compartida", "compartido", "dorm", "bed in", "shared room",
               "mixed", "capsula", "female", "femenin")
_BANO_COMPARTIDO = ("bano compartido", "banos compartidos", "shared bathroom", "bano comun")
_BANO_PRIVADO = ("bano privado", "private bathroom", "ensuite", "en suite", "bano propio")


def _arreglado(texto):
    """Arregla el «HabitaciÃ³n» que a veces traen las fichas (texto en UTF-8 leído como latin-1)."""
    texto = texto or ""
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def _limpio(texto):
    """Minúsculas y sin tildes, para comparar."""
    sin = unicodedata.normalize("NFD", _arreglado(texto).lower())
    return "".join(c for c in sin if unicodedata.category(c) != "Mn")


def clasificar(nombre, personas=None):
    """'privada' (dice baño privado), 'probable' (no dice nada malo) o None (litera/compartida)."""
    n = _limpio(nombre)
    if any(p in n for p in _BANO_COMPARTIDO):
        return None
    if any(p in n for p in _DORMITORIO):    # una litera lo es aunque el baño sea privado
        return None
    if personas and personas > MAX_PERSONAS:
        return None
    return "privada" if any(p in n for p in _BANO_PRIVADO) else "probable"


def parametros(ciudad, entrada, salida):
    return {
        "engine": "google_hotels", "q": f"hoteles {ciudad}",
        "check_in_date": entrada, "check_out_date": salida,
        "adults": "1", "currency": "EUR", "gl": "es", "hl": "es",
        "rating": "7",         # 7 = 3,5 o más sobre 5 (≈ 7 sobre 10)
    }


def leer_lista(datos):
    """Respuesta de la lista de Google Hotels -> [{nombre, precio_lista, nota, ...}]. No consulta nada."""
    salida_ = []
    for h in datos.get("properties", []):
        precio = (h.get("rate_per_night") or {}).get("extracted_lowest")
        salida_.append({
            "nombre": h.get("name"), "precio_lista": precio,
            "nota": h.get("overall_rating"), "opiniones": h.get("reviews"),
            "estrellas": h.get("extracted_hotel_class"), "token": h.get("property_token"),
            "zona": ", ".join(n.get("name", "") for n in (h.get("nearby_places") or [])[:1]),
            "coordenadas": h.get("gps_coordinates"), "enlace": h.get("link"),
        })
    return salida_


def leer_habitaciones(datos):
    """Respuesta de la ficha -> [{nombre, precio, personas, fuente}]. No consulta nada."""
    habs = []
    for fuente in datos.get("featured_prices", []):
        for r in fuente.get("rooms", []):
            precio = (r.get("rate_per_night") or {}).get("extracted_lowest")
            if precio:
                habs.append({"nombre": _arreglado(r.get("name")), "precio": precio,
                             "personas": r.get("num_guests"), "fuente": fuente.get("source")})
    return habs


def mejor_habitacion(habs):
    """La habitación válida más barata, con su grado de confianza, o None."""
    validas = []
    for h in habs:
        c = clasificar(h["nombre"], h["personas"])
        if c:
            validas.append(dict(h, confianza=c))
    return min(validas, key=lambda h: (h["precio"], h["confianza"] != "privada"), default=None)


def resolver(lista, fichas):
    """Junta la lista con las fichas ya leídas ({token: habitaciones}). No consulta nada.

    Cada elemento trae 'habitacion' (None si solo hay literas) y 'comprobado' (True si se miró la ficha;
    False = precio de la lista, sin confirmar que sea habitación privada).
    """
    lista = [h for h in lista if h["precio_lista"] and (h["nota"] or 0) >= NOTA_MINIMA]
    for h in lista:
        if h["token"] in fichas:
            h["comprobado"] = True
            h["habitacion"] = mejor_habitacion(fichas[h["token"]])
        elif h["precio_lista"] < UMBRAL_FICHA:
            h["comprobado"] = False
            h["habitacion"] = {"nombre": "(litera probable, ficha sin abrir)",
                               "precio": h["precio_lista"], "confianza": "sin comprobar"}
        else:
            h["comprobado"] = False
            h["habitacion"] = {"nombre": "(precio de la lista)", "precio": h["precio_lista"],
                               "confianza": "sin comprobar"}
    lista.sort(key=lambda h: (h["habitacion"] is None, (h["habitacion"] or {}).get("precio", 9999)))
    return lista


_CAMA = re.compile(r"hostel|ostello|hostal|capsule|capsula|dorm|backpack|albergue|meininger|a&o|generator|wombat|yellowsquare|combo|maverick|flow spaces|hive|ao hotel|tomato|bayt alice|riad dia", re.I)
MIN_OPINIONES = 50     # como el usuario: descarta lo que casi nadie ha valorado
MAX_KM = 4.0           # a más de esto del centro no es una escapada de 48 h


def _km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def estimar(ciudad, entrada, salida, usar_cache=True):
    """Precio orientativo de una habitación decente y barata esa noche, desde la lista de Google Hotels.

    Una búsqueda. Descarta lo que el usuario descartaría: nota baja, pocas opiniones, lejos del centro y
    hostels/dormitorios (su precio de lista es el de la litera). El estimado es la MEDIANA de los 3 más
    baratos que quedan (no el mínimo, que suele ser un valor extremo). Devuelve None si no hay candidatos.
    """
    datos = vueling._buscar(parametros(ciudad, entrada, salida), usar_cache)
    props = datos.get("properties", [])
    noches = (datetime.strptime(salida, "%Y-%m-%d") - datetime.strptime(entrada, "%Y-%m-%d")).days
    gps = [(p["gps_coordinates"]["latitude"], p["gps_coordinates"]["longitude"]) for p in props
           if p.get("gps_coordinates")]
    if gps:
        centro = (statistics.median(g[0] for g in gps), statistics.median(g[1] for g in gps))
    cand = []
    for p in props:
        precio = (p.get("rate_per_night") or {}).get("extracted_lowest")
        nombre = p.get("name") or ""
        if (not precio or (p.get("overall_rating") or 0) < NOTA_MINIMA or (p.get("reviews") or 0) < MIN_OPINIONES
                or _CAMA.search(nombre) or p.get("type") != "hotel"):
            continue
        km = None
        if gps and p.get("gps_coordinates"):
            km = _km(centro, (p["gps_coordinates"]["latitude"], p["gps_coordinates"]["longitude"]))
            if km > MAX_KM:
                continue
        cand.append({"nombre": nombre, "porNoche": precio, "nota": p.get("overall_rating"),
                     "opiniones": p.get("reviews"), "km": round(km, 1) if km is not None else None,
                     "web": p.get("link")})
    cand.sort(key=lambda c: c["porNoche"])
    if not cand:
        return None
    top = cand[:3]
    por_noche = statistics.median(c["porNoche"] for c in top)
    return {"porNoche": por_noche, "total": round(por_noche * noches, 2), "noches": noches,
            "candidatos": len(cand), "sugerencias": top}


def buscar(ciudad, entrada, salida, fichas_max=6, usar_cache=True):
    """Alojamientos con nota suficiente y su habitación individual más barata.

    Devuelve (lista ordenada por precio, nº de fichas abiertas).
    """
    lista = leer_lista(vueling._buscar(parametros(ciudad, entrada, salida), usar_cache))
    sospechosos = sorted((h for h in lista if h["precio_lista"] and h["precio_lista"] < UMBRAL_FICHA
                          and (h["nota"] or 0) >= NOTA_MINIMA),
                         key=lambda h: -(h["nota"] or 0))[:fichas_max]
    fichas = {}
    for h in sospechosos:
        par = dict(parametros(ciudad, entrada, salida), property_token=h["token"])
        par.pop("rating")
        try:
            fichas[h["token"]] = leer_habitaciones(vueling._buscar(par, usar_cache))
        except vueling.SinPresupuesto as e:
            print(f"  (sin presupuesto para abrir fichas: {e})")
            break
    return resolver(lista, fichas), len(fichas)


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        print(__doc__)
        sys.exit(1)
    sys.stdout.reconfigure(encoding="utf-8")
    vueling.TOPE = 12
    maximo = int(sys.argv[4]) if len(sys.argv) == 5 else 6
    hoteles, nfichas = buscar(sys.argv[1], sys.argv[2], sys.argv[3], maximo)
    print(f"{len(hoteles)} alojamientos con nota ≥ {NOTA_MINIMA}/5; fichas abiertas: {nfichas}; "
          f"búsquedas nuevas gastadas: {vueling.gastadas()}")
    for h in hoteles[:15]:
        hab = h["habitacion"]
        if hab is None:
            print(f"  — solo literas/compartidas   nota {h['nota']}  {h['nombre']}")
            continue
        print(f"{hab['precio']:>5} €  nota {h['nota']!s:<4} ({h['opiniones']!s:>5} op.)  "
              f"{h['nombre']}  → {hab['nombre']}  [{hab['confianza']}]")
