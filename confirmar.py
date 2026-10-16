"""
confirmar.py 1.0 — «Confirmar con Google»: contrasta con Google Flights (SerpApi) los vuelos de UNA opción.

NOTA (13-10-2026): el botón «Confirmar con Google» se retiró (el usuario: emborrona la pantalla). Queda el motor,
sin interfaz; lo usa el auditor (auditor.py) en segundo plano.

Para qué: Ryanair y Wizz se leen directos; Vueling, easyJet, Turkish, Pegasus, Eurowings... vienen de Kiwi con
el precio de la aerolínea ESTIMADO (±3 €). Antes de comprar, el usuario pulsa «Confirmar con Google» en la opción
que le interesa y Google da la hora y el precio exactos de cada tramo.
Coste: 1 búsqueda de SerpApi por grupo de tramos (varios destinos el mismo día y aerolínea caben en una). Los tramos de Ryanair no se
buscan (ya son exactos). Lo ya buscado en las últimas 12 h sale de la caché y no gasta. Antes de gastar,
`coste()` cuenta las búsquedas SIN gastar y el botón pide confirmación.
Lo confirmado se guarda en `resultados\\confirmados.json` con su fecha, para enseñarlo como ✓ y, de paso,
comparar con lo estimado (sirve para afinar las comisiones de Kiwi en kiwi.py).
Reutiliza el freno de vueling.py: tope por ejecución y límite del mes.
"""
import json
import re
from datetime import datetime
from pathlib import Path

import cache
import vueling

VERSION = "1.1"
ARCHIVO = Path(__file__).parent / "resultados" / "confirmados.json"
VIGENCIA_DIAS = 14   # un precio confirmado se enseña (con ✓) hasta 14 días; luego vuelve el estimado
EXACTAS = ("FR", "RK", "AL", "RR")   # Ryanair: se lee directo, no hace falta contrastarla
AEROLINEAS_GOOGLE = {"W6": "W4,W6", "W4": "W4,W6"}   # Wizz sale en Google con el código W4 (y a veces W6)


def clave(t):
    return f"{t['desde']}-{t['hasta']}-{t['dia']}T{t['hora']}"


def valido(t):  # (lo usó el botón de la pantalla, ya retirado; se deja por si vuelve a hacer falta)
    """Un tramo bien formado, tal como lo manda la página (nada de texto libre hacia SerpApi)."""
    try:
        return (re.fullmatch(r"[A-Z]{3}", t["desde"]) and re.fullmatch(r"[A-Z]{3}", t["hasta"])
                and re.fullmatch(r"20\d\d-\d\d-\d\d", t["dia"]) and re.fullmatch(r"\d\d:\d\d", t["hora"])
                and re.fullmatch(r"[A-Z0-9]{2}", t["sigla"])) is not None
    except (KeyError, TypeError):
        return False


def _grupos(tramos):
    """Agrupa los tramos que caben en UNA búsqueda de Google (que admite varios aeropuertos a la vez, hasta
    vueling.LOTE): mismo sentido, día y aerolínea, y mismo aeropuerto fijo (BCN en las idas, BCN en las vueltas).
    Sin Ryanair y sin repetidos. Devuelve [(parámetros de la búsqueda, [tramos])]."""
    vistos, grupos = set(), {}
    for t in tramos:
        if t["sigla"] in EXACTAS or clave(t) in vistos:
            continue
        vistos.add(clave(t))
        ida = t["desde"] == "BCN"
        grupos.setdefault((ida, t["dia"], t["sigla"], t["desde"] if ida else t["hasta"]), []).append(t)
    res = []
    for (ida, dia, sigla, fijo), ts in grupos.items():
        for i in range(0, len(ts), vueling.LOTE):
            parte = ts[i:i + vueling.LOTE]
            otros = sorted({(t["hasta"] if ida else t["desde"]) for t in parte})
            aero = AEROLINEAS_GOOGLE.get(sigla, sigla)
            res.append((vueling._parametros([fijo], otros, dia, aero) if ida
                        else vueling._parametros(otros, [fijo], dia, aero), parte))
    return res


def coste(tramos):
    """Búsquedas NUEVAS que gastaría confirmar estos tramos (las que ya están en la caché no cuentan)."""
    return sum(1 for p, _ in _grupos(tramos) if cache.leer(["serpapi", "google_flights", p], vueling.HORAS_CACHE) is None)


def vigente(g, dias=None):
    """¿Esta confirmación es de un vuelo encontrado y de hace menos de `dias` (VIGENCIA_DIAS por defecto)?"""
    if g.get("no_encontrado") or "precio" not in g:
        return False
    return (datetime.now() - datetime.fromisoformat(g["visto"])).days < (dias or VIGENCIA_DIAS)


def cargar():
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar(datos):
    ARCHIVO.parent.mkdir(exist_ok=True)
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def confirmar(tramos):
    """Busca en Google los tramos (agrupados: una búsqueda por grupo) y guarda lo que encuentra. Devuelve {clave: confirmación}.

    Puede lanzar vueling.SinPresupuesto (tope o freno del mes). Lo ya confirmado antes de que pase queda
    guardado. El llamador fija `vueling.TOPE` (= `coste()`) y llama a `vueling.reiniciar()` antes.
    """
    guardados = cargar()
    nuevos = {}
    try:
        for params, parte in _grupos(tramos):
            datos = vueling._buscar(params, True)
            vuelos = vueling._tramos(datos, {}, "ida", parte[0]["sigla"])
            visto = datetime.now().isoformat(timespec="seconds")
            for t in parte:
                hora = f"{t['dia']}T{t['hora']}"
                g = next((v for v in vuelos if v["desde"] == t["desde"] and v["hasta"] == t["hasta"]
                          and v["salida"] == hora), None)
                if g is None:
                    nuevos[clave(t)] = {"no_encontrado": True, "visto": visto}
                else:
                    nuevos[clave(t)] = {"precio": g["precio"], "salida": g["salida"], "llegada": g["llegada"],
                                        "vuelo": g["vuelo"], "visto": visto, "estimado": t.get("estimado")}
    finally:
        if nuevos:
            guardados.update(nuevos)
            _guardar(guardados)
    return nuevos
