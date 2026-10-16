"""movil_datos.py 0.3 — Datos de las pantallas Flash, Radar y Países nuevos del iPhone (movil/flash.html), en JSON sencillo.

Lee los mismos archivos de resultados que la demo del portátil (resultados\\AAAA-MM-DD.md y los `_dias1`/`_dias2`,
con ver_resultados.leer_domingo) y los deja listos para el móvil: por domingo, los viajes del más barato al más
caro, con ciudad, precio, horas, noches, horas allí, semáforo, enlaces y lo que cuesta con 1 o 2 días libres.
No consulta nada ni gasta nada. Lo sirve servidor.py en /api/movil-flash.
Prueba:  .venv\\Scripts\\python.exe movil_datos.py
"""
import html as _html
import re
from datetime import date

import json

import semaforo
import ver_resultados as vr

VERSION = "0.4"

AEROLINEAS = {"FR": "Ryanair", "W6": "Wizz Air", "W4": "Wizz Air", "VY": "Vueling"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS_VUELTA = {1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue"}


def _ciudad(texto):
    """'Cracovia (KRK), Polonia' -> 'Cracovia'."""
    return re.sub(r"\s*\(\w{3}\).*$", "", texto).strip() or texto


def _codigo(texto):
    """'Cracovia (KRK), Polonia' -> 'KRK' ('' si no lleva código)."""
    m = re.search(r"\((\w{3})\)", texto or "")
    return m.group(1).upper() if m else ""


def _tramo(texto):
    """'FR 6881 06:35 → ≈08:30 (+1) · ≥57.03 € ✓ …' -> dict; None si no se entiende."""
    m = re.search(r"(\d\d:\d\d)\s*→\s*(≈?)(\d\d:\d\d)(\s*\(\+1\))?", texto)
    if not m:
        return None
    p = re.search(r"([≥≈]?)\s*([\d]+(?:[.,]\d+)?)\s*€", texto[m.end():])
    sigla = re.match(r"\s*([A-Z0-9]{2})\b", texto)
    sig = sigla.group(1) if sigla else ""
    return {
        "aerolinea": AEROLINEAS.get(sig, sig),
        "sale": m.group(1), "llega": m.group(3), "mas1": bool(m.group(4)),
        "aprox": bool(m.group(2)),                      # hora de llegada calculada (Wizz)
        "precio": float(p.group(2).replace(",", ".")) if p else None,
        "minimo": bool(p and p.group(1) == "≥"),       # el vuelo que encaja no es el más barato del día
    }


def _opcion(o):
    ida, vuelta = _tramo(o["ida"]), _tramo(o["vuelta"])
    if not ida or not vuelta or o.get("total") is None:
        return None
    nuevo = (o.get("nuevo") or "").startswith("🆕")
    return {
        "destino": _ciudad(o["destino"]),
        "desde": _ciudad(o["desde"]) if o.get("tipo") == "otro" and o.get("desde") else "",
        "iata": _codigo(o["destino"]),
        "iataDesde": _codigo(o["desde"]) if o.get("tipo") == "otro" and o.get("desde") else "",
        "total": o["total"],
        "color": semaforo.color(o["total"], o.get("kmBcn")),
        "ida": ida, "vuelta": vuelta,
        "noches": o.get("noches") or 2,
        "horas": o.get("horas"),
        "libres": o.get("libres") or 0,
        "nuevo": nuevo,
        "km": o.get("km") or "", "traslado": o.get("traslado") or "",
        "linkIda": o.get("linkIda") or "", "linkVuelta": o.get("linkVuelta") or "",
    }


def _fecha(dia):
    d = date.fromisoformat(dia)
    return f"{d.day} {MESES[d.month - 1]}"


def datos(hoy=None):
    """{domingos: [{dia, fecha, opciones: [...]}], generado}. Solo domingos de hoy en adelante."""
    hoy = (hoy or date.today()).isoformat()
    vr._INDICE = None
    vr._PAQUETES = None
    archivos = sorted(p for p in vr.CARPETA.glob("20??-??-??.md") if p.stem >= hoy)
    domingos, generado = [], ""
    for a in archivos:
        base = vr.leer_domingo(a)
        generado = max(generado, base.get("generado", ""))
        opciones = [x for x in map(_opcion, base["opciones"]) if x]
        # Con 1 o 2 días libres: el total más barato del mismo destino (y misma vuelta desde) en ese nivel
        for e in (1, 2):
            extra = vr.CARPETA / f"{a.stem}_dias{e}.md"
            if not extra.exists():
                continue
            mejor = {}
            for x in map(_opcion, vr.leer_domingo(extra, e)["opciones"]):
                if x:
                    k = (x["destino"], x["desde"])
                    mejor[k] = min(mejor.get(k, x["total"]), x["total"])
            for x in opciones:
                if (x["destino"], x["desde"]) in mejor:
                    x.setdefault("conLibres", {})[str(e)] = mejor[(x["destino"], x["desde"])]
        domingos.append({"dia": a.stem, "fecha": _fecha(a.stem), "opciones": opciones})
    return {"domingos": domingos, "generado": generado, "dias": DIAS_VUELTA}


MESES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
               "noviembre", "diciembre"]


def _dia(f):
    d = date.fromisoformat(f)
    return f"{d.day} {MESES[d.month - 1]}"


def _cargar_radar():
    # Se lee el archivo directamente (sin importar radar.py, que arrastra las aerolíneas): solo lectura.
    try:
        return json.loads((vr.CARPETA / "radar.json").read_text(encoding="utf-8"))
    except Exception:
        return {"meses": {}}


def datos_radar(hoy=None):
    """Radar de ida guardado (resultados\\radar.json), por mes, de este mes en adelante. Solo lee: no consulta nada."""
    hoy = hoy or date.today()
    mes_hoy = hoy.isoformat()[:7]
    meses = []
    for mes, m in sorted(_cargar_radar().get("meses", {}).items()):
        if mes < mes_hoy:
            continue
        lista = []
        for x in m.get("lista", []):
            b = x["mejor"]
            if b["ida"][0] < hoy.isoformat():
                continue
            p = x.get("pareja")
            lista.append({
                "destino": x["ciudad"] or x["destino"], "codigo": x["destino"], "pais": x.get("pais_nombre") or "",
                "nuevo": bool(x.get("nuevo")),
                "aerolinea": b["aerolinea"], "fecha": _dia(b["ida"][0]), "precio": b["ida"][1], "aprox": bool(b["orientativo"]),
                "otras": [{"aerolinea": o["aerolinea"], "fecha": _dia(o["ida"][0]), "precio": o["ida"][1],
                           "aprox": bool(o["orientativo"])} for o in x.get("otras", [])],
                "pareja": ({"aerolinea": p["aerolinea"], "ida": _dia(p["ida"]), "vuelta": _dia(p["vuelta"]),
                            "total": p["total"], "noches": p.get("noches"), "aprox": bool(p.get("orientativo"))}
                           if p else None)})
        a, mm = mes.split("-")
        meses.append({"mes": mes, "nombre": f"{MESES_LARGO[int(mm) - 1]} {a}", "generado": m.get("generado", ""),
                      "dias": m.get("dias"), "avisos": m.get("avisos", []), "lista": lista})
    return {"meses": meses}


def datos_paises():
    """Países nuevos (explorar.py): lee resultados\\explorar.html y explorar.json. Solo lectura, no consulta nada.
    Devuelve {hay, generado, salida, dias, paises: [{pais, total, color, normal, fechas: [...]}]} del más barato al más caro."""
    try:
        pagina = (vr.CARPETA / "explorar.html").read_text(encoding="utf-8")
    except Exception:
        return {"hay": False, "paises": []}
    try:
        meta = json.loads((vr.CARPETA / "explorar.json").read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    cab = [_html.unescape(x) for x in re.findall(r"<th>([^<]*)</th>", pagina.split("</tr>", 1)[0])][1:]
    paises = []
    for nombre, resto in re.findall(r"<tr><th>(.*?)</th>(.*?)</tr>", pagina, re.S)[1:]:
        fechas = []
        for i, (clase, titulo, total) in enumerate(re.findall(r'<td class="(\w+)"(?: title="(.*?)")?>(.*?)</td>', resto, re.S)):
            if clase == "vacio" or not titulo or i >= len(cab):
                continue
            lin = _html.unescape(titulo).split("\n")
            try:
                fechas.append({"salida": cab[i], "total": float(total), "color": clase,
                               "cuando": lin[0], "ida": lin[1].replace("ida ", "", 1), "vuelta": lin[2].replace("vuelta ", "", 1),
                               "normal": lin[3].split(": ", 1)[1] if len(lin) > 3 and ": " in lin[3] else ""})
            except (ValueError, IndexError):
                continue
        if fechas:
            fechas.sort(key=lambda f: f["total"])
            paises.append({"pais": _html.unescape(nombre), "total": fechas[0]["total"], "color": fechas[0]["color"],
                           "normal": fechas[0]["normal"], "fechas": fechas})
    paises.sort(key=lambda x: x["total"])
    return {"hay": True, "generado": meta.get("generado", ""), "salida": meta.get("salida", ""), "dias": meta.get("dias", ""),
            "paises": paises}


if __name__ == "__main__":
    d = datos()
    print(f"movil_datos {VERSION}: {len(d['domingos'])} domingos, {len(datos_radar()['meses'])} meses de radar")
    for dom in d["domingos"]:
        mejor = dom["opciones"][0] if dom["opciones"] else None
        print(f"  {dom['fecha']:>7}: {len(dom['opciones']):>3} viajes" + (f", el mejor {mejor['destino']} {mejor['total']} €" if mejor else ""))
