"""Horarios de tren Barcelona-Sants <-> Madrid desde los GTFS oficiales (Ouigo: NAP; Renfe: ssl.renfe.com).

VERSION 0.1. Descarga 1 vez por semana (`python trenes_gtfs.py`), lee en local y deja `datos/trenes_horarios.json`:
[{op, tren, sentido ("BCN-MAD" | "MAD-BCN"), sale, llega, dias: ["AAAA-MM-DD", ...]}].
Iryo NO tiene GTFS publicado (comprobado 16-10-2026): sin horarios. La clave del NAP va en .env (NAP_API_KEY).
Si una descarga falla, se deja el archivo anterior y se escribe el motivo en `avisos` (sin inventar nada)."""
import csv
import io
import json
import os
import sys
import zipfile
from datetime import date, datetime, timedelta

import requests

VERSION = "0.1"
CARPETA = os.path.join("datos", "gtfs")
SALIDA = os.path.join("datos", "trenes_horarios.json")
UA = "EscapadasFlash/1.0 (uso personal)"
FUENTES = {
    "Ouigo": "https://nap.transportes.gob.es/api/Fichero/download/1766",   # necesita ApiKey
    "Renfe": "https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip",
}
BCN = {"71801", "007171801"}                                   # Barcelona-Sants
MAD = {"60000", "17000", "007160000", "007117000"}             # Atocha, Chamartín
DIAS = 400


def _clave_nap():
    for l in open(".env", encoding="utf-8"):
        if l.startswith("NAP_API_KEY="):
            return l.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("Falta NAP_API_KEY en .env")


def descargar(op):
    cab = {"User-Agent": UA}
    if op == "Ouigo":
        cab["ApiKey"] = _clave_nap()
    r = requests.get(FUENTES[op], headers=cab, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"{op}: descarga HTTP {r.status_code}" + (" (¿clave del NAP caducada?)" if r.status_code in (401, 403) else ""))
    return zipfile.ZipFile(io.BytesIO(r.content))


def _filas(z, nombre):
    with z.open(nombre) as f:
        for r in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
            yield {k.strip(): (v or "").strip() for k, v in r.items()}


def _hora(t):   # "25:10:00" (pasa de medianoche) o "7:27:" (Renfe, sin cero) -> "25:10" / "07:27"
    h, m = t.split(":")[:2]
    return f"{int(h):02d}:{int(m):02d}"


def _dias_servicio(z, wanted):
    """service_id -> set de fechas (hoy..+DIAS) en que circula."""
    hoy = date.today()
    fin = hoy + timedelta(days=DIAS)
    cal = {r["service_id"]: r for r in _filas(z, "calendar.txt") if r["service_id"] in wanted}
    out = {}
    for sid, r in cal.items():
        ini, fi = datetime.strptime(r["start_date"], "%Y%m%d").date(), datetime.strptime(r["end_date"], "%Y%m%d").date()
        sem = [r[d] == "1" for d in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")]
        d, s = max(ini, hoy), set()
        while d <= min(fi, fin):
            if sem[d.weekday()]:
                s.add(d.isoformat())
            d += timedelta(days=1)
        out[sid] = s
    if "calendar_dates.txt" in z.namelist():
        for r in _filas(z, "calendar_dates.txt"):
            sid = r["service_id"]
            if sid not in wanted:
                continue
            f = datetime.strptime(r["date"], "%Y%m%d").date().isoformat()
            out.setdefault(sid, set())
            (out[sid].add if r["exception_type"] == "1" else out[sid].discard)(f)
    return out


def trenes(op, z):
    """Trenes BCN<->MAD del GTFS: [{op, tren, sentido, sale, llega, dias}]."""
    paradas = {}   # trip_id -> [(secuencia, stop_id, llegada, salida)]
    for r in _filas(z, "stop_times.txt"):
        if r["stop_id"] in BCN or r["stop_id"] in MAD:
            paradas.setdefault(r["trip_id"], []).append((int(r["stop_sequence"]), r["stop_id"], r["arrival_time"], r["departure_time"]))
    candidatos = {}
    for t, ps in paradas.items():
        ps.sort()
        ids = [p[1] for p in ps]
        b = [p for p in ps if p[1] in BCN]
        m = [p for p in ps if p[1] in MAD]
        if b and m:
            sentido = "BCN-MAD" if b[0][0] < m[0][0] else "MAD-BCN"
            o, d = (b[0], m[0]) if sentido == "BCN-MAD" else (m[0], b[0])
            candidatos[t] = (sentido, _hora(o[3]), _hora(d[2]))
    trips = {r["trip_id"]: r for r in _filas(z, "trips.txt") if r["trip_id"] in candidatos}
    servicios = _dias_servicio(z, {r["service_id"] for r in trips.values()})
    uno = {}   # mismo tren (operador, sentido, horas) repetido por estación o servicio: se unen los días
    for t, (sentido, sale, llega) in candidatos.items():
        dias = servicios.get(trips[t]["service_id"], set())
        k = (sentido, sale, llega)
        if k in uno:
            uno[k]["dias"] |= dias
        elif dias:
            uno[k] = {"op": op, "tren": trips[t].get("trip_short_name") or trips[t].get("trip_headsign") or t,
                      "sentido": sentido, "sale": sale, "llega": llega, "dias": set(dias)}
    return [{**v, "dias": sorted(v["dias"])} for v in uno.values() if v["dias"]]


def actualizar():
    previo = json.load(open(SALIDA, encoding="utf-8")) if os.path.exists(SALIDA) else {"trenes": []}
    res, avisos = [], []
    for op in FUENTES:
        try:
            res += trenes(op, descargar(op))
        except Exception as e:
            avisos.append({"operador": op, "motivo": str(e)[:200], "hora": datetime.now().isoformat(timespec="seconds")})
            res += [t for t in previo.get("trenes", []) if t["op"] == op]   # se queda lo anterior de ese operador
    avisos.append({"operador": "Iryo", "motivo": "no publica horarios abiertos (GTFS)", "hora": datetime.now().isoformat(timespec="seconds")})
    json.dump({"generado": datetime.now().isoformat(timespec="seconds"), "trenes": res, "avisos": avisos},
              open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return res, avisos


def del_dia(fecha, sentido):
    """Trenes de un día y sentido, ordenados por hora de salida; vacío si no hay datos."""
    if not os.path.exists(SALIDA):
        return []
    d = json.load(open(SALIDA, encoding="utf-8"))
    return sorted((t for t in d["trenes"] if t["sentido"] == sentido and fecha in t["dias"]), key=lambda t: t["sale"])


if __name__ == "__main__":
    res, avisos = actualizar()
    n = {}
    for t in res:
        n[(t["op"], t["sentido"])] = n.get((t["op"], t["sentido"]), 0) + 1
    print("Trenes encontrados:", n)
    for a in avisos:
        print("AVISO", a["operador"], a["motivo"])
    f = (date.today() + timedelta(days=20)).isoformat()
    for s in ("BCN-MAD", "MAD-BCN"):
        for t in del_dia(f, s):
            print(f, s, t["op"], t["tren"], t["sale"], "->", t["llega"])
