"""
booking.py — Enlaces de búsqueda de Booking con el método del usuario (solo construye enlaces: no consulta nada).

El usuario reserva con la app de Booking del iPhone y busca así: una habitación, 1 adulto, filtro «baño privado»
y ordenado por precio. El enlace lleva esos filtros; en el iPhone, un enlace de booking.com suele abrir la
app. Los parámetros salen de una búsqueda real suya (11-10-2026): `nflt=roomfacility=38;min_bathrooms=1`
(baño privado), `review_score=70` (nota 7 o más) y `order=price`. Se dejan fuera `label` y `aid` (identifican su sesión).
"""
from urllib.parse import urlencode

VERSION = "0.4"


FILTROS = "roomfacility=38;min_bathrooms=1;review_score=70"   # baño privado + «Baños: 1» (el contador) + nota 7+


def busqueda(ciudad, entrada, salida, adultos=1, filtros=FILTROS):
    """Enlace a los resultados de Booking: baño privado, más baratos primero.

    ciudad: texto tal cual lo escribiría el usuario («Palermo, Italia»); Booking lo resuelve por nombre.
    """
    return "https://www.booking.com/searchresults.es.html?" + urlencode({
        "ss": ciudad, "lang": "es", "checkin": entrada, "checkout": salida,
        "group_adults": adultos, "no_rooms": 1, "group_children": 0,
        "nflt": filtros, "order": "price", "selected_currency": "EUR"})


def hotel(nombre, ciudad, entrada, salida, adultos=1):
    """Búsqueda por el nombre de un hotel, con el texto que Booking usa en su propio autocompletado
    («Monte Palace Palermo»). Sin filtros: con ellos y sin `dest_id` Booking lo toma por una zona y
    enseña otro alojamiento (el usuario, 11-10-2026: B&B Federico II). OJO: el enlace abre la página con el
    nombre puesto; hay que pulsar «Buscar» para que Booking lo identifique como hotel (dest_type=hotel).
    """
    ciudad = ciudad.split(",")[0].strip()
    texto = nombre if ciudad.lower() in nombre.lower() else f"{nombre} {ciudad}"
    return "https://www.booking.com/searchresults.es.html?" + urlencode({
        "ss": texto, "lang": "es", "checkin": entrada, "checkout": salida,
        "group_adults": adultos, "no_rooms": 1, "group_children": 0, "selected_currency": "EUR"})


if __name__ == "__main__":
    print(busqueda("Palermo, Italia", "2026-11-01", "2026-11-02"))
