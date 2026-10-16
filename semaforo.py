"""
semaforo.py — Semáforo con topes fijos según el tipo de viaje (regla del usuario, 12-10-2026).

Precio total de IDA + VUELTA, solo vuelos, 1 adulto, tarifa básica. El tipo de viaje lo deciden las HORAS de
avión desde BCN hasta el aeropuerto de llegada (regla del usuario, 14-10-2026; antes era por km):

  corto  menos de 4 h   (escapada urbana)   verde ≤  60 €   ámbar ≤ 100 €   rojo más
  medio  de 4 a 6 h                         verde ≤ 150 €   ámbar ≤ 200 €   rojo más
  largo  más de 6 h                         verde ≤ 500 €   ámbar ≤ 700 €   rojo más

Horas aproximadas = km en línea recta / 800 + 0,5 h (despegue y aterrizaje). Nueva York (6.150 km, ~8 h) y
Nueva Delhi son «largo». Los límites están solo aquí.

Los límites (km y precios) están solo aquí: cambiarlos aquí los cambia en todo el programa.
Prueba: .venv\\Scripts\\python.exe semaforo.py
"""
from math import asin, cos, radians, sin, sqrt

VERSION = "0.5"

BCN = (41.2974, 2.0785)   # lat, lon del aeropuerto de El Prat

LIMITE_CORTO_H = 4
LIMITE_MEDIO_H = 6
KMH = 800          # velocidad media de crucero
EXTRA_H = 0.5      # despegue y aterrizaje

# Los mismos límites en km (los usan la demo y la nube): 4 h = 2.800 km, 6 h = 4.400 km
LIMITE_CORTO_KM = round((LIMITE_CORTO_H - EXTRA_H) * KMH)
LIMITE_MEDIO_KM = round((LIMITE_MEDIO_H - EXTRA_H) * KMH)


def horas(km):
    """Horas de vuelo aproximadas desde BCN; None si no hay distancia."""
    return None if km is None else km / KMH + EXTRA_H

# tipo -> (tope verde, tope ámbar) en euros, ida + vuelta
TOPES = {
    "corto": (60, 100),
    "medio": (150, 200),
    "largo": (500, 700),
}


def km_aire(lat, lon):
    """Distancia en línea recta (km) desde BCN; None si faltan las coordenadas."""
    if lat is None or lon is None:
        return None
    p1, p2 = radians(BCN[0]), radians(lat)
    dl = radians(lon - BCN[1])
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def tipo(km):
    """«corto», «medio» o «largo». Sin distancia conocida se trata como corto (el caso habitual)."""
    if km is None or km <= LIMITE_CORTO_KM:
        return "corto"
    return "medio" if km <= LIMITE_MEDIO_KM else "largo"


def color(precio, km, topes=None):
    """«verde», «ambar» o «rojo» (o «» si no hay precio). Solo cuentan las horas de vuelo, no los días de viaje.
    `topes` = (verde, ámbar) propios de un país; sin ellos, los de su tipo de viaje."""
    if precio is None:
        return ""
    verde, ambar = topes or TOPES[tipo(km)]
    return "verde" if precio <= verde else ("ambar" if precio <= ambar else "rojo")


def leyenda():
    """Texto corto para las páginas."""
    n = {"corto": f"menos de {LIMITE_CORTO_H} h de vuelo",
         "medio": f"{LIMITE_CORTO_H}–{LIMITE_MEDIO_H} h",
         "largo": f"más de {LIMITE_MEDIO_H} h"}
    return " · ".join(f"{t} ({n[t]}): verde ≤ {v} €, ámbar ≤ {a} €" for t, (v, a) in TOPES.items())


if __name__ == "__main__":
    print(leyenda())
    for nombre, km, precio in [("Roma", 860, 100), ("Roma", 860, 55), ("El Cairo", 3300, 120), ("Nueva York", 6150, 190), ("Nueva Delhi", 6900, 450),
                               ("Arabia Saudí", 4300, 728), ("Miami", 7500, 480)]:
        print(f"{nombre:<14} {km:>5} km ~{horas(km):.1f} h {precio:>4} €  ->  {tipo(km)}, {color(precio, km)}")
