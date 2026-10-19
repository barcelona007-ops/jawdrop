"""Trenes Barcelona-Sants <-> Madrid para el Radar: horarios (GTFS) + precio real de Ouigo, con avisos claros.

VERSION 0.1 (17-10-2026). Reglas del usuario: si un operador falla o bloquea, AVISO con su nombre y el motivo; nunca precio
inventado. Hoy: Ouigo = horarios + precio reales; Renfe = solo horarios (su venta pide captcha, no se salta); Iryo = nada
(sin GTFS y su API va tras Cloudflare Turnstile, no se salta).
Cuidado con el operador: caché, UNA petición a la vez, pausa aleatoria, tope diario y freno de 24 h al primer 403/429/captcha.
Todo se apunta en datos/trenes_estado.json (frenos y contador diario de peticiones por operador)."""
import json
import os
import random
import time
from datetime import date, datetime, timedelta

import cache
import trenes_gtfs
import trenes_iryo
import trenes_ouigo
import trenes_renfe

VERSION = "0.6"
ESTADO = os.path.join("datos", "trenes_estado.json")
CACHE_HORAS = 4            # precio del tren: 2-6 h según la nota del 16-10
PAUSA_S = (10, 40)         # pausa aleatoria entre peticiones reales (se afina con pruebas_trenes.json)
TOPE_DIA = {"Ouigo": 300}   # la prueba de aguante aguantó 100 seguidas sin pausa; 300/día es muy prudente   # peticiones reales por día y operador
FRENO_H = 24
AVISO_FIJO = {
    "Renfe": "solo el precio MÍNIMO del día (calendario público de renfe.com); el precio de cada tren pide captcha y no se salta",
}


def _estado():
    return json.load(open(ESTADO, encoding="utf-8")) if os.path.exists(ESTADO) else {}


def _guardar(e):
    json.dump(e, open(ESTADO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def aviso_operador(op):
    """Motivo por el que el operador no da precio ahora mismo, o None si va bien."""
    if op in AVISO_FIJO:
        return AVISO_FIJO[op]
    e = _estado().get(op, {})
    if e.get("parado_hasta", "") > datetime.now().isoformat():
        return f"parado hasta {e['parado_hasta'][:16]}: {e['motivo']} ({e['hora'][:16]})"
    return None


def _freno(op):
    """Motivo del freno de 24 h de ese operador, o None."""
    e = _estado().get(op, {})
    if e.get("parado_hasta", "") > datetime.now().isoformat():
        return f"parado hasta {e['parado_hasta'][:16]}: {e['motivo']} ({e['hora'][:16]})"
    return None


def _desde_renfe(fecha, sentido):
    """Precio mínimo del día en Renfe (€), o None; lanza ErrorOperador. Una petición por mes y sentido (caché CACHE_HORAS)."""
    d = date.fromisoformat(fecha)
    ini = max(date.today(), d.replace(day=1))
    fin = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    def pedir():
        try:
            r = trenes_renfe.calendario(sentido, ini.isoformat(), fin.isoformat())
        except trenes_ouigo.ErrorOperador as e:
            _apuntar("Renfe", e)
            raise
        _apuntar("Renfe")
        return r

    return cache.con_cache(("tren-renfe-cal", sentido, ini.isoformat()[:7]), CACHE_HORAS, pedir).get(fecha)


def _apuntar(op, fallo=None):
    """Cuenta una petición real; si hay fallo de bloqueo, frena al operador 24 h."""
    e = _estado()
    o = e.setdefault(op, {})
    hoy = date.today().isoformat()
    o["peticiones"] = {hoy: o.get("peticiones", {}).get(hoy, 0) + 1}
    if fallo:
        o["motivo"], o["hora"] = fallo.motivo, datetime.now().isoformat(timespec="seconds")
        if fallo.codigo in (401, 403, 429) or "captcha" in fallo.motivo.lower():
            o["parado_hasta"] = (datetime.now() + timedelta(hours=FRENO_H)).isoformat(timespec="seconds")
    _guardar(e)


# Iryo en pausa (20-10-2026, el usuario): su API da 403 (antibot) y no publica horarios; sin horas ni precio no aporta. Ni se consulta ni avisa.
# Para reactivarlo: True (y mirar antes que su API responde).
IRYO_ACTIVO = False
_ouigo = _iryo = None
_ultima = [0.0]
_ultima_op = {}


def _cuidado(op, hacer):
    """Una petición real con todas las reglas: tope diario, pausa aleatoria, contador y freno de 24 h si bloquea."""
    if _estado().get(op, {}).get("peticiones", {}).get(date.today().isoformat(), 0) >= TOPE_DIA.get(op, 300):
        raise trenes_ouigo.ErrorOperador(op, f"tope diario de {TOPE_DIA.get(op, 300)} peticiones alcanzado (configurable)")
    espera = random.uniform(*PAUSA_S) - (time.time() - _ultima_op.get(op, 0))
    if espera > 0:
        time.sleep(espera)
    try:
        r = hacer()
    except trenes_ouigo.ErrorOperador as e:
        _ultima_op[op] = time.time()
        _apuntar(op, e)
        raise
    _ultima_op[op] = time.time()
    _apuntar(op)
    return r


def _precios_iryo(fecha, sentido):
    """[{sale, llega, precio|None}] de Iryo ese día, o lanza ErrorOperador."""
    global _iryo
    o_, d_ = (trenes_iryo.BCN, trenes_iryo.MAD) if sentido == "BCN-MAD" else (trenes_iryo.MAD, trenes_iryo.BCN)

    def pedir():
        global _iryo
        _iryo = _iryo or trenes_iryo.Iryo()
        return _cuidado("Iryo", lambda: _iryo.dia(fecha, o_, d_))

    return cache.con_cache(("tren-iryo", fecha, sentido), CACHE_HORAS, pedir)


def _precios_ouigo(fecha, sentido):
    """{salida "HH:MM": (llegada, precio|None)} del día, o lanza ErrorOperador."""
    global _ouigo
    o_, d_ = (trenes_ouigo.BCN, trenes_ouigo.MAD) if sentido == "BCN-MAD" else (trenes_ouigo.MAD, trenes_ouigo.BCN)

    def pedir():
        global _ouigo
        if _estado().get("Ouigo", {}).get("peticiones", {}).get(date.today().isoformat(), 0) >= TOPE_DIA["Ouigo"]:
            raise trenes_ouigo.ErrorOperador("Ouigo", f"tope diario de {TOPE_DIA['Ouigo']} peticiones alcanzado (configurable)")
        espera = random.uniform(*PAUSA_S) - (time.time() - _ultima[0])
        if espera > 0:
            time.sleep(espera)
        _ouigo = _ouigo or trenes_ouigo.Ouigo()
        try:
            r = _ouigo.dia(fecha, o_, d_)
        except trenes_ouigo.ErrorOperador as e:
            _ultima[0] = time.time()
            _apuntar("Ouigo", e)
            raise
        _ultima[0] = time.time()
        _apuntar("Ouigo")
        return {t["departure_station"]["departure_timestamp"][11:16]: (t["arrival_station"]["arrival_timestamp"][11:16], t.get("price"))
                for t in r.get("outbound", [])}

    return cache.con_cache(("tren-ouigo", fecha, sentido), CACHE_HORAS, pedir)


def opciones(fecha, sentido):
    """Todos los trenes del día: [{op, tren, sale, llega, precio, nota}] + lista de avisos [{operador, motivo}].
    `precio` es None cuando no hay dato real (la `nota` dice por qué)."""
    avisos, out, ahora = [], [], datetime.now().isoformat(timespec="minutes")
    # cada aviso lleva la hora en que se detectó
    precios, motivo_ouigo = {}, aviso_operador("Ouigo")
    if not motivo_ouigo:
        try:
            precios = _precios_ouigo(fecha, sentido)
            if not precios:
                avisos.append({"operador": "Ouigo", "motivo": "sin trenes a la venta ese día (¿aún fuera de su ventana de venta?)"})
        except trenes_ouigo.ErrorOperador as e:
            motivo_ouigo = e.motivo
        except Exception as e:   # red caída, respuesta rara
            motivo_ouigo = f"sin respuesta o cambio en su web ({type(e).__name__})"
    if motivo_ouigo:
        avisos.append({"operador": "Ouigo", "motivo": motivo_ouigo})
    # Ouigo: si su API devuelve trenes, ESA es la lista (horas y precio reales). El GTFS descargado se queda atrás en fechas lejanas
    # (en febrero ni tenía trenes y las horas no coincidían), así que solo se usa para Ouigo cuando la API no responde.
    for sale, (llega, precio) in sorted(precios.items()):
        out.append({"op": "Ouigo", "tren": "", "sale": sale, "llega": llega, "precio": precio, "nota": "agotado o no a la venta" if precio is None else ""})
    iryo, motivo_iryo = [], _freno("Iryo")
    if IRYO_ACTIVO and not motivo_iryo:
        try:
            iryo = _precios_iryo(fecha, sentido)
            if not iryo:
                avisos.append({"operador": "Iryo", "motivo": "sin trenes a la venta ese día (¿fuera de su ventana de venta?)"})
        except trenes_ouigo.ErrorOperador as e:
            motivo_iryo = e.motivo
        except Exception as e:
            motivo_iryo = f"sin respuesta o cambio en su web ({type(e).__name__})"
    if IRYO_ACTIVO and motivo_iryo:
        avisos.append({"operador": "Iryo", "motivo": motivo_iryo})
    for t in iryo:
        out.append({"op": "Iryo", "tren": "", "sale": t["sale"], "llega": t["llega"], "precio": t["precio"], "nota": "agotado o no a la venta" if t["precio"] is None else ""})
    desde, motivo_renfe = None, _freno("Renfe")
    if not motivo_renfe:
        try:
            desde = _desde_renfe(fecha, sentido)
        except trenes_ouigo.ErrorOperador as e:
            motivo_renfe = e.motivo
        except Exception as e:
            motivo_renfe = f"sin respuesta o cambio en su web ({type(e).__name__})"
    if motivo_renfe:
        avisos.append({"operador": "Renfe", "motivo": motivo_renfe})
    for t in trenes_gtfs.del_dia(fecha, sentido):
        if t["op"] == "Ouigo" and precios:
            continue
        precio, nota = None, AVISO_FIJO.get(t["op"], "sin precio")
        if t["op"] == "Ouigo":
            nota = motivo_ouigo or "sin precio"
        extra = {"desde": desde} if t["op"] == "Renfe" and desde is not None else {}
        out.append({"op": t["op"], "tren": t["tren"], "sale": t["sale"], "llega": t["llega"], "precio": precio, "nota": nota, **extra})
    for op in AVISO_FIJO:
        if op == "Renfe" and desde is not None:
            continue   # Renfe da el mínimo del día: ya no es «sin precio»; la nota de cada tren lo explica
        avisos.append({"operador": op, "motivo": AVISO_FIJO[op]})
    for a in avisos:
        a["hora"] = ahora
    return out, avisos


if __name__ == "__main__":
    import sys
    f = sys.argv[1] if len(sys.argv) > 1 else (date.today() + timedelta(days=20)).isoformat()
    for s in ("BCN-MAD", "MAD-BCN"):
        o, a = opciones(f, s)
        print(f, s, len(o), "trenes")
        for t in o:
            if t["op"] == "Ouigo":
                print("  ", t)
        print("  avisos:", a)
