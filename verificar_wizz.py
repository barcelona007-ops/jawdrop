"""
verificar_wizz.py — Comprueba con Kiwi los vuelos de Wizz Air de las mejores opciones. GRATIS (sin SerpApi).

Por qué: Wizz solo da el precio MÁS BARATO DEL DÍA y no da la hora de llegada (se calcula, y sale unos 5-17
minutos corta). Para las pocas opciones que de verdad interesan, se pregunta a Kiwi por el vuelo concreto:
hora de llegada real y, si el de Wizz era «mínimo del día», un precio estimado del vuelo.
Desde la 2.0 sustituye a la comprobación con Google Flights (SerpApi), que gastaba 1-2 búsquedas por consulta.
Prueba del 13-10-2026 (dos domingos, 32 rutas): vueltas 23 de 28 vuelos de Wizz emparejados con Kiwi por
ruta y hora exacta, idas 10 de 14 (faltan los de Londres-Luton y los que salen justo a la hora en punto del
final de la franja, que ahora se piden con una hora de margen). Precio de Kiwi frente a Wizz: de -3 a +9 €,
casi siempre de 0 a 3 €. Un vuelo que Kiwi no trae queda sin ✓ (`no_confirmada`), como antes.
Coste: 0 búsquedas de SerpApi; consultas de Kiwi (caché de 24 h, pausa de 5 s). Se agrupa todo lo posible:
una consulta por día y por grupo de hasta LOTE aeropuertos.
"""
import kiwi

VERSION = "2.0"
SIGLAS = ("W6", "W4")   # Wizz Air Hungría y Malta
LOTE = 4                # aeropuertos por consulta: pocos, para que los de Ryanair no llenen los 50 resultados


def confirmar(opciones, coords, usar_cache=True):
    """Devuelve [(opcion, 'ida'|'vuelta', tramo_de_kiwi | None)] para cada tramo de Wizz de `opciones`.

    No cambia las opciones: eso lo decide escapadas.py. El tramo de Kiwi trae `llegada` real y `precio`
    (estimado de la aerolínea, ±3 €). Puede lanzar kiwi.KiwiBloqueado.
    """
    tramos = [(o, c) for o in opciones for c in ("ida", "vuelta")
              if o[c]["aerolinea"] == "Wizz Air" and not o[c].get("verificada")]
    grupos = {}  # (sentido, día, aeropuerto fijo) -> {aeropuertos que varían}, horas de salida
    for o, c in tramos:
        t = o[c]
        fijo, variable = (t["desde"], t["hasta"]) if c == "ida" else (t["hasta"], t["desde"])
        g = grupos.setdefault((c, t["salida"][:10], fijo), {"variables": set(), "horas": []})
        g["variables"].add(variable)
        g["horas"].append(int(t["salida"][11:13]))

    vistos = {}  # (sentido, desde, hasta, hora de salida) -> tramo de Kiwi
    for (c, dia, fijo), g in grupos.items():
        h1, h2 = f"{min(g['horas']):02d}:00", f"{min(max(g['horas']) + 1, 23):02d}:00"
        variables = sorted(g["variables"])
        for i in range(0, len(variables), LOTE):
            lote = [f"Airport:{x}" for x in variables[i:i + LOTE]]
            if c == "ida":
                its = kiwi._pedir([f"Airport:{fijo}"], lote, dia, h1, h2, 50, usar_cache)
            else:
                its = kiwi._pedir(lote, [f"Airport:{fijo}"], dia, h1, h2, 50, usar_cache)
            for it in its:
                t = kiwi._tramo(it)
                if t and t["sigla"] in SIGLAS:
                    vistos[(c, t["desde"], t["hasta"], t["salida"])] = t
    return [(o, c, vistos.get((c, o[c]["desde"], o[c]["hasta"], o[c]["salida"]))) for o, c in tramos]
