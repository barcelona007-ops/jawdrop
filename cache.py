"""
cache.py — Caché local (SQLite) común a todas las aerolíneas.

Guarda cada respuesta de internet con su hora. Si se repite la misma consulta antes de que caduque,
se devuelve la guardada y no se pregunta a la aerolínea.
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path

RUTA = Path(__file__).resolve().parent / "cache.sqlite"


def _con():
    con = sqlite3.connect(RUTA)
    con.execute("CREATE TABLE IF NOT EXISTS respuestas (clave TEXT PRIMARY KEY, guardado REAL, json TEXT)")
    return con


def clave(*partes):
    return hashlib.sha1(json.dumps(partes, sort_keys=True).encode()).hexdigest()


def leer(partes, horas):
    """Respuesta guardada para `partes` si tiene menos de `horas`, o None. No consulta nada (lo usa el
    estimador de coste para saber qué consultas saldrían de la caché)."""
    con = _con()
    try:
        fila = con.execute("SELECT guardado, json FROM respuestas WHERE clave=?", (clave(*partes),)).fetchone()
    finally:
        con.close()
    if fila and time.time() - fila[0] < horas * 3600:
        return json.loads(fila[1])
    return None


def con_cache(partes, horas, pedir, usar_cache=True):
    """Devuelve la respuesta guardada para `partes` si tiene menos de `horas`; si no, llama a pedir()."""
    k = clave(*partes)
    con = _con()
    try:
        if usar_cache:
            fila = con.execute("SELECT guardado, json FROM respuestas WHERE clave=?", (k,)).fetchone()
            if fila and time.time() - fila[0] < horas * 3600:
                return json.loads(fila[1])
        datos = pedir()
        con.execute("INSERT OR REPLACE INTO respuestas VALUES (?,?,?)", (k, time.time(), json.dumps(datos)))
        con.commit()
        return datos
    finally:
        con.close()


# ---- Lecturas con fecha (histórico de precios; lo usan el radar y el histórico de ofertas) --------

def _con_lecturas():
    con = _con()
    con.execute("CREATE TABLE IF NOT EXISTS lecturas (fuente TEXT, origen TEXT, destino TEXT, salida TEXT, "
                "precio REAL, directo INTEGER, visto TEXT, PRIMARY KEY (fuente, origen, destino, salida, visto))")
    return con


def guardar_lecturas(fuente, filas, visto):
    """Guarda lecturas de precio. `filas`: dicts con origen, destino, salida (AAAA-MM-DDTHH:MM) y precio.
    `visto` es el día (AAAA-MM-DD): repetir el mismo día no duplica."""
    con = _con_lecturas()
    try:
        con.executemany(
            "INSERT OR REPLACE INTO lecturas VALUES (?,?,?,?,?,?,?)",
            [(fuente, f["origen"], f["destino"], f["salida"], f["precio"], int(f.get("directo", True)), visto)
             for f in filas])
        con.commit()
    finally:
        con.close()


def lecturas(fuente, origen=None, destino=None):
    """Lecturas guardadas (más recientes primero) como lista de dicts."""
    sql, args = "SELECT origen, destino, salida, precio, directo, visto FROM lecturas WHERE fuente=?", [fuente]
    for campo, valor in (("origen", origen), ("destino", destino)):
        if valor:
            sql += f" AND {campo}=?"
            args.append(valor)
    con = _con_lecturas()
    try:
        filas = con.execute(sql + " ORDER BY visto DESC, precio", args).fetchall()
    finally:
        con.close()
    return [dict(zip(("origen", "destino", "salida", "precio", "directo", "visto"), f)) for f in filas]
