"""ver_resultados.py 0.1 — Convierte los resultados (resultados\\AAAA-MM-DD.md) en una página web local.

No consulta ninguna aerolínea ni gasta búsquedas: solo lee los archivos que ya existen y escribe
resultados\\escapadas.html, que se abre con doble clic en Chrome.

Uso:  .venv\\Scripts\\python.exe ver_resultados.py
"""
import json
import sqlite3
import re
import sys
import webbrowser

import semaforo
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

VERSION = "0.37"
AQUI = Path(__file__).parent
CARPETA = AQUI / "resultados"
SALIDA = CARPETA / "escapadas.html"


def _wizz(m):
    """Los resultados antiguos traen el enlace de Wizz como búsqueda de Google Flights: se cambia por la web de Wizz."""
    return f"https://www.wizzair.com/es-es/booking/select-flight/{m.group(1)}/{m.group(2)}/{m.group(3)}/null/1/0/0/null"


def _sky(m):
    """Los resultados antiguos traen Vueling en tickets.vueling.com (en el móvil cae en la portada): se pasa a Skyscanner."""
    a, mes, d = m.group(3).split("-")
    return (f"https://www.skyscanner.es/transporte/vuelos/{m.group(1).lower()}/{m.group(2).lower()}/{a[2:]}{mes}{d}/"
            "?adultsv2=1&cabinclass=economy&rtn=0&preferdirects=true")


def _enlaces(texto):
    texto = re.sub(r"https://tickets\.vueling\.com/booking/flightSearch\?o=([A-Z]{3})&d=([A-Z]{3})&dd=(\d{4}-\d\d-\d\d)\S*?(?=\))",
                   _sky, texto)
    texto = re.sub(r"https://www\.google\.com/travel/flights\?hl=es&curr=EUR&q=Vuelos%20de%20([A-Z]{3})%20a%20([A-Z]{3})%20el%20([\d-]+)%20solo%20ida%20directo",
                   _wizz, texto)
    return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", texto)


def _limpia(texto):
    return re.sub(r"\*\*|`", "", texto).strip()


def _trozo_vuelo(celda):
    """'FR 06:35 → 08:30 · 57.03 € ✓' -> dict sencillo (se deja el texto tal cual para no perder marcas)."""
    return _limpia(celda)


def _filas(texto, titulo_seccion):
    """Devuelve (cabeceras, filas) de la tabla que sigue a un '## titulo_seccion'."""
    m = re.search(r"^## " + re.escape(titulo_seccion) + r".*?$(.*?)(?=^## |\Z)", texto, re.S | re.M)
    if not m:
        return [], []
    lineas = [l for l in m.group(1).splitlines() if l.startswith("|")]
    if len(lineas) < 3:
        return [], []
    cab = [c.strip() for c in lineas[0].strip("|").split("|")]
    filas = []
    for l in lineas[2:]:
        celdas = [c.strip() for c in re.split(r"(?<!\\)\|", l.strip().strip("|"))]
        if len(celdas) == len(cab):
            filas.append(dict(zip(cab, celdas)))
    return cab, filas


def _total(celda):
    n = re.search(r"(\d+(?:[.,]\d+)?)", celda)
    return float(n.group(1).replace(",", ".")) if n else None


ZONAS = {"Reino Unido": "Europe/London", "Irlanda": "Europe/Dublin", "Portugal": "Europe/Lisbon",
         "Rumanía": "Europe/Bucharest", "Bulgaria": "Europe/Sofia", "Grecia": "Europe/Athens",
         "Chipre": "Asia/Nicosia", "Finlandia": "Europe/Helsinki", "Lituania": "Europe/Vilnius",
         "Letonia": "Europe/Riga", "Estonia": "Europe/Tallinn", "Moldavia": "Europe/Chisinau",
         "Ucrania": "Europe/Kyiv", "Marruecos": "Africa/Casablanca", "Turquía": "Europe/Istanbul"}


def _zona(lugar):
    pais = lugar.rsplit(",", 1)[-1].strip()
    return ZoneInfo(ZONAS.get(pais, "Europe/Paris"))


def _horas_alli(dia, lugar_ida, ida, lugar_vuelta, vuelta):
    """Horas desde que aterriza la ida hasta que despega la vuelta (hora local de cada aeropuerto)."""
    a = re.search(r"→\s*≈?(\d\d):(\d\d)(\s*\(\+1\))?", ida)
    s = re.search(r"(\d\d):(\d\d)\s*→", vuelta)
    if not a or not s:
        return None
    base = datetime.strptime(dia, "%Y-%m-%d")
    llega = (base + timedelta(days=1 if a.group(3) else 0)).replace(hour=int(a.group(1)), minute=int(a.group(2)))
    sale = (base + timedelta(days=_noches(vuelta))).replace(
        hour=int(s.group(1)), minute=int(s.group(2)))
    llega = llega.replace(tzinfo=_zona(lugar_ida))
    sale = sale.replace(tzinfo=_zona(lugar_vuelta))
    return round((sale - llega).total_seconds() / 3600, 1)


_INDICE = None


def _indice_vuelos():
    """Números de vuelo que ya están en la caché (respuestas de Ryanair y de Google Flights), aunque hayan
    caducado: (origen, destino, 'AAAA-MM-DDTHH:MM') -> 'FR 6881'. No consulta nada."""
    global _INDICE
    if _INDICE is not None:
        return _INDICE
    _INDICE = {}
    bd = AQUI / "cache.sqlite"
    if not bd.exists():
        return _INDICE

    def recorre(x):
        if isinstance(x, dict):
            num = x.get("flightNumber") or x.get("flight_number")
            if num and "departureAirport" in x and "departureDate" in x:
                clave = (x["departureAirport"]["iataCode"], x["arrivalAirport"]["iataCode"], x["departureDate"][:16])
                _INDICE[clave] = num
            elif num and "departure_airport" in x and "arrival_airport" in x:
                hora = (x["departure_airport"].get("time") or "").replace(" ", "T")[:16]
                _INDICE[(x["departure_airport"].get("id"), x["arrival_airport"].get("id"), hora)] = num
            for v in x.values():
                recorre(v)
        elif isinstance(x, list):
            for v in x:
                recorre(v)

    con = sqlite3.connect(f"file:{bd.as_posix()}?mode=ro", uri=True)
    try:
        for (j,) in con.execute("SELECT json FROM respuestas"):
            if "flightNumber" in j or "flight_number" in j:
                recorre(json.loads(j))
    finally:
        con.close()
    return _INDICE


def _con_numero(tramo, origen, destino, dia, dias_mas):
    """Pone el número de vuelo a «FR 06:35 → ...» si está en la caché: «FR 6881 06:35 → ...»."""
    m = re.match(r"(FR|W6|W4|VY)\s+(.*)$", tramo)
    if m and re.match(r"\d{1,4}\s", m.group(2)):   # ya trae el número («VY 6514 07:30», «FR 866 lunes noche…»)
        return tramo
    h = re.search(r"(\d\d:\d\d)\s*→", tramo)
    if not m or not h or not origen or not destino:
        return tramo
    fecha = (datetime.strptime(dia, "%Y-%m-%d") + timedelta(days=dias_mas)).strftime("%Y-%m-%d")
    num = _indice_vuelos().get((origen, destino, f"{fecha}T{h.group(1)}"))
    if not num:
        return tramo
    pref = re.fullmatch(r"([A-Z0-9]{2})\s?(\d{1,4})", num.strip())
    return f"{pref.group(1)} {pref.group(2)} {m.group(2)}" if pref else tramo


def _cod(lugar):
    m = re.search(r"\((\w{3})\)", lugar)
    return m.group(1) if m else ""


_DIAS_SEM = {"lunes": 1, "martes": 2, "miércoles": 3, "jueves": 4}


def _noches(vuelta):
    """Noches fuera: días desde el domingo hasta el día de la vuelta (lunes 1, martes 2, miércoles 3…)."""
    v = vuelta.lower()
    for nombre, n in _DIAS_SEM.items():
        if nombre in v:
            return n
    return 2


def _libres(vuelta, total):
    """(días libres a pedir, ahorro frente a no pedirlos, ¿sin días libres no hay vuelta?) de una fila."""
    m = re.search(r"\((\d) días? libres?\)", vuelta)
    a = re.search(r"−\s*([\d.,]+)\s*€ vs sin días libres", total)
    return (int(m.group(1)) if m else 0, float(a.group(1).replace(",", ".")) if a else None,
            "sin días libres no hay vuelta" in total)


_PAQUETES = None


def _paquete(dia, o):
    """Paquete estimado (vuelos + hotel de Google Hotels) que dejó paquetes.py, o None."""
    global _PAQUETES
    if _PAQUETES is None:
        ruta = CARPETA / "paquetes.json"
        _PAQUETES = json.loads(ruta.read_text(encoding="utf-8")).get("domingos", {}) if ruta.exists() else {}
    for x in _PAQUETES.get(dia, []):
        if x["destino"] == o["destino"] and x.get("desde") == o.get("desde") and x["paquete"]:
            return {"paquete": x["paquete"], "hotel": x["hotel"], "vuelos": x["vuelos"], "estancias": x["estancias"]}
    return None


def _busquedas(dia, o):
    """Dónde se duerme y el enlace de búsqueda de Booking de cada noche (método del usuario)."""
    import booking
    import plan_hoteles
    try:
        est = plan_hoteles._estancias(dia, o["destino"], o.get("desde"), o["noches"])
    except Exception:
        est = None
    if not est:
        return []
    salida = []
    for ciudad, pais, vis, ent, sal in est:
        m = re.match(r"\s*([^(]+?)\s*(?:\(\w{3}\))?\s*,\s*(.+?)\s*$", vis)
        texto = f"{m.group(1)}, {m.group(2)}" if m else vis
        noches = (datetime.strptime(sal, "%Y-%m-%d") - datetime.strptime(ent, "%Y-%m-%d")).days
        salida.append({"ciudad": vis, "entrada": ent, "salida": sal, "noches": noches,
                       "url": booking.busqueda(texto, ent, sal)})
    return salida


def _entero(texto):
    """'1234' -> 1234; vacío o raro -> None (el semáforo lo trata como viaje corto)."""
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return None


def leer_domingo(archivo, extra=0):
    """Lee el archivo de un domingo. `extra` = días libres con los que se generó (0, 1 o 2): con extra
    no se enseñan hoteles estimados (el paquete de paquetes.json es de la escapada sin días libres)."""
    texto = archivo.read_text(encoding="utf-8")
    dia = archivo.stem[:10]
    opciones = []
    _, filas = _filas(texto, "Mismo aeropuerto")
    for f in filas:
        links = _enlaces(f.get("Comprobar", ""))
        opciones.append({
            "tipo": "mismo",
            "destino": _limpia(f["Destino"]),
            "total": _total(f["Total €"]),
            "totalTxt": _limpia(f["Total €"]),
            "ida": _con_numero(_trozo_vuelo(f["Ida (sale → llega)"]), "BCN", _cod(f["Destino"]), dia, 0),
            "vuelta": _con_numero(_trozo_vuelo(f["Vuelta (sale → llega)"]), _cod(f["Destino"]), "BCN", dia,
                                  _noches(f["Vuelta (sale → llega)"])),
            "noches": _noches(f["Vuelta (sale → llega)"]),
            "libres": _libres(f["Vuelta (sale → llega)"], f["Total €"])[0],
            "ahorro": _libres(f["Vuelta (sale → llega)"], f["Total €"])[1],
            "sinvuelta": _libres(f["Vuelta (sale → llega)"], f["Total €"])[2],
            "horas": _horas_alli(dia, f["Destino"], f["Ida (sale → llega)"], f["Destino"],
                                 f["Vuelta (sale → llega)"]),
            "linkIda": links[0][1] if links else "",
            "linkVuelta": links[1][1] if len(links) > 1 else "",
            "nuevo": _limpia(f.get("País nuevo", "no")),
            "kmBcn": _entero(f.get("Km BCN")),
        })
    _, filas = _filas(texto, "Otro aeropuerto")
    for f in filas:
        links = _enlaces(f.get("Comprobar", ""))
        tras = f.get("Traslado", "")
        opciones.append({
            "tipo": "otro",
            "destino": _limpia(f["Ida a"]),
            "desde": _limpia(f["Vuelta desde"]),
            "km": f.get("Km", ""),
            "pais": f.get("¿Cambio de país?", ""),
            "traslado": re.split(r"\s·\s", tras)[0].strip(),
            "linksTraslado": _enlaces(tras),
            "total": _total(f["Total €"]),
            "totalTxt": _limpia(f["Total €"]),
            "ida": _con_numero(_trozo_vuelo(f["Ida (sale → llega)"]), "BCN", _cod(f["Ida a"]), dia, 0),
            "vuelta": _con_numero(_trozo_vuelo(f["Vuelta (sale → llega)"]), _cod(f["Vuelta desde"]), "BCN", dia,
                                  _noches(f["Vuelta (sale → llega)"])),
            "noches": _noches(f["Vuelta (sale → llega)"]),
            "libres": _libres(f["Vuelta (sale → llega)"], f["Total €"])[0],
            "ahorro": _libres(f["Vuelta (sale → llega)"], f["Total €"])[1],
            "sinvuelta": _libres(f["Vuelta (sale → llega)"], f["Total €"])[2],
            "horas": _horas_alli(dia, f["Ida a"], f["Ida (sale → llega)"], f["Vuelta desde"],
                                 f["Vuelta (sale → llega)"]),
            "linkIda": links[0][1] if links else "",
            "linkVuelta": links[1][1] if len(links) > 1 else "",
            "nuevo": _limpia(f.get("País nuevo", "no")),
            "kmBcn": _entero(f.get("Km BCN")),
            "ferri": "⛴" in f.get("Ferri", ""),
        })
    generado = re.search(r"Generado ([^.]+?) \(", texto)
    opciones = [o for o in opciones if o["total"] is not None]
    for o in opciones:
        o["paq"] = _paquete(dia, o) if extra == 0 else None
        o["busquedas"] = _busquedas(dia, o)
    opciones.sort(key=lambda o: o["total"])
    return {"dia": dia, "generado": generado.group(1) if generado else "", "opciones": opciones}


PLANTILLA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jawdrop</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--mut:#6a7686;--line:#e2e6ec;--acc:#1b5cff;
--verde:#1f9d55;--verdeb:#e3f6ea;--amar:#c98a00;--amarb:#fff4d6;--rojo:#c53030;--rojob:#fde8e8}
@media (prefers-color-scheme:dark){:root{--bg:#12161c;--card:#1b212a;--ink:#e8ecf2;--mut:#94a0b0;--line:#2b3441;--acc:#6b95ff;
--verde:#4cc47f;--verdeb:#173324;--amar:#e8b43a;--amarb:#3a2f12;--rojo:#f08080;--rojob:#3a1b1b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,Segoe UI,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:20px 16px 60px}
h1{margin:0 0 4px;font-size:26px}.sub{color:var(--mut);margin:0 0 20px}
.reglas{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin-bottom:20px;font-size:14px;color:var(--mut)}
.cal{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;margin-bottom:8px}
.dia{border:2px solid transparent;border-radius:12px;padding:10px 12px;cursor:pointer;text-align:left;font:inherit;color:var(--ink)}
.dia .f{font-weight:600}.dia .p{font-size:22px;font-weight:700}.dia .d{font-size:13px;color:var(--mut)}
.dia.verde{background:var(--verdeb)}.dia.amar{background:var(--amarb)}.dia.rojo{background:var(--rojob)}
.dia.nada{background:var(--rojob);opacity:.6}.dia.nada .p{font-size:18px;color:var(--mut)}
.dia.sel{border-color:var(--acc)}
.leyenda{font-size:13px;color:var(--mut);margin-bottom:22px}
.barra{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin:8px 0 14px}
.tabs button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:7px 14px;cursor:pointer}
.tabs button:first-child{border-radius:8px 0 0 8px}.tabs button:last-child{border-radius:0 8px 8px 0}
.tabs button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.op{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px;display:grid;grid-template-columns:1fr auto;gap:6px 16px}
.op h3{margin:0;font-size:19px}.tot{font-size:26px;font-weight:700;text-align:right}
.tramo{font-size:14px;color:var(--mut)}.tramo b{color:var(--ink);font-weight:600}
.pie{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;align-items:center}
.pie a,.chip{font-size:13px;border:1px solid var(--line);border-radius:999px;padding:3px 11px;text-decoration:none;color:var(--acc)}
.chip{color:var(--mut)}.hotel{border-style:dashed}.chip.libres{color:var(--amar);border-color:var(--amar);font-weight:600}.chip.nuevo{color:var(--verde);border-color:var(--verde);font-weight:600}
.aviso{background:var(--amarb);border-radius:8px;padding:6px 10px;font-size:13px;grid-column:1/-1}
.op.rev{border-color:var(--amar);border-width:2px}.rev .aviso2{grid-column:1/-1;background:var(--amarb);color:var(--ink);border-radius:8px;padding:6px 10px;font-size:13px}
.lugares{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px}
.lugar small{display:block;color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.lugar h3{margin:0;font-size:20px}.lugar span{color:var(--mut);font-size:13px}
.puente{color:var(--mut);font-size:13px;text-align:center;border:1px dashed var(--line);border-radius:10px;padding:4px 10px}
.dosap{background:var(--amarb);border-radius:6px;padding:1px 8px;font-size:13px}
.horas{font-weight:600;color:var(--ink)}
.cont{font-size:14px;color:var(--mut);margin:0 0 14px}.cont b{color:var(--amar)}
.vacio{color:var(--mut);padding:30px;text-align:center}
.cerrado{font-size:13px;color:var(--verde);font-weight:600;text-align:right}
.hoteles{grid-column:1/-1;border-top:1px dashed var(--line);margin-top:6px;padding-top:8px}
.noche{font-size:13px;color:var(--mut);margin:6px 0 2px}.noche b{color:var(--ink)}
.aloj{display:grid;grid-template-columns:78px 1fr;gap:2px 10px;padding:5px 0;font-size:14px;border-top:1px solid var(--line)}
.aloj .pr{font-weight:700;color:var(--verde)}.aloj small{color:var(--mut)}
.aloj a{font-size:12px;color:var(--acc);margin-right:10px}
.vy{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin-bottom:20px;font-size:14px}
.vy-acc{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}
.vy button{font:inherit;font-size:14px;border:1px solid var(--acc);background:var(--card);color:var(--acc);border-radius:8px;padding:6px 12px;cursor:pointer}
.vy button.pri{background:var(--acc);color:#fff}
.vy button:disabled{border-color:var(--line);color:var(--mut);background:var(--bg);cursor:not-allowed}
.vy-nota{color:var(--mut);font-size:13px;margin-top:4px}
.vy-conf{background:var(--amarb);border-radius:8px;padding:10px 12px;margin-top:10px}
.vy-conf .vy-acc{margin-bottom:0}
.pa-barra{height:14px;background:var(--line);border-radius:7px;overflow:hidden;margin:6px 0 2px;max-width:420px}.pa-barra>div{height:100%;background:var(--verde);transition:width .4s}
.pa-vacio{border:1px solid var(--line);border-left:5px solid var(--mut);background:var(--amarb);border-radius:8px;padding:10px 14px;margin:10px 0;font-size:16px}.pa-vacio b{display:block;font-size:17px;margin-bottom:2px}
.pa-aviso{border-left:5px solid var(--rojo);border-radius:8px;padding:8px 12px;margin:8px 0;background:var(--amarb)}
.vy-ok{color:var(--verde);font-weight:600;margin-top:6px}.vy-err{color:var(--rojo);margin-top:6px}
.rad{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 16px;margin-bottom:20px}
.rad summary{cursor:pointer;font-weight:700;font-size:16px}
.rad-barra{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin:10px 0;font-size:14px}
.rad button{font:inherit;font-size:13px;border:1px solid var(--acc);background:var(--card);color:var(--acc);border-radius:8px;padding:4px 10px;cursor:pointer}
.rad button:disabled{border-color:var(--line);color:var(--mut);cursor:not-allowed}
.rad table{width:100%;border-collapse:collapse;font-size:14px}
.rad td,.rad th{padding:5px 6px;border-top:1px solid var(--line);text-align:left;vertical-align:top}
.rad th{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em;border-top:0}
.rad .pr{font-weight:700;white-space:nowrap}.rad small{color:var(--mut)}
.rad .vlt{background:var(--amarb);border-radius:8px;padding:6px 10px;margin:4px 0}
</style></head><body><div class="wrap">
<h1>Jawdrop</h1>
<p class="sub">Desde Barcelona-El Prat · ida el domingo por la mañana · vuelta el lunes noche o el martes por la mañana</p>
<div class="reglas">Esto es una vista de lo que ya hay calculado (no consulta nada nuevo). Precios de ida + vuelta, 1 adulto, solo bolso de mano.
«≥» = mínimo del día en Wizz · «≈» = llegada calculada · «✓» = precio comprobado en Google Flights.
Las opciones en <b style="color:var(--amar)">ámbar</b> llevan un tramo de Wizz con «≥»: el precio real puede ser mayor, hay que comprobarlo antes de decidir.
Los enlaces de Wizz abren la búsqueda en Google Flights (la web de Wizz no carga).
<br>Hoteles: para las 3 mejores opciones de cada domingo el precio grande es solo de vuelos (es lo que está comprobado); el hotel es un NIVEL de precio de la ciudad (3 mejores opciones de cada domingo), sin nombres de hoteles. Cada opción lleva «Elegir hotel»: abre Booking con tus filtros (baño privado, nota 7 o más, más baratos primero, 1 adulto y las noches de esa opción) y, con la extensión de Chrome instalada, un botón ＋ verde en cada alojamiento te lo trae aquí y suma su precio a los vuelos. Si la vuelta sale de otro aeropuerto y hay 2 noches, salen dos búsquedas: 1 noche en cada ciudad. En el iPhone la app de Booking solo respeta destino, fechas y orden por precio: baño privado y nota 7+ hay que ponerlos a mano.</div>
<details class="rad" id="rad" open><summary>🔭 Radar de viajes largos (meses de antelación)</summary>
<div id="rad-in"></div></details>
<details class="rad" id="hist"><summary>📈 Histórico de ofertas (qué es barato en cada destino)</summary>
<div id="hist-in"></div></details>
<details class="rad" id="pais" open><summary>🌍 Un país concreto (entrar por un aeropuerto y salir por otro)</summary>
<div id="pais-in"></div></details>
<details class="rad" id="exp"><summary>🚦 Países nuevos: semáforo de todos a la vez</summary>
<div id="exp-in"></div></details>
<div class="vy" id="vy">Cargando…</div>
<div class="cal" id="cal"></div>
<div class="leyenda">Color del domingo según su opción más barata (ida + vuelta, solo vuelos) y lo lejos que está:
__LEYENDA__. <b style="color:var(--verde)">Verde</b> = buen precio, <b style="color:var(--amar)">amarillo</b> = normal,
<b style="color:var(--rojo)">rojo</b> = caro para esa distancia.</div>
<div class="barra">
 <div class="tabs"><button id="t-todo" class="on">Todas</button><button id="t-mismo">Mismo aeropuerto</button><button id="t-otro">Otro aeropuerto</button></div>
 <label>Mostrar: <select id="lim"><option value="5">las 5 más baratas</option><option value="10" selected>las 10 más baratas</option><option value="20">las 20 más baratas</option><option value="9999">todas</option></select></label>
 <label>Ordenar por: <select id="ord"><option value="vuelos" selected>precio de los vuelos</option><option value="cerrado">vuelos + nivel de hotel</option></select></label>
 <label><input type="checkbox" id="nuevos"> Solo países nuevos 🆕</label>
 <label title="Días libres que pedirías: la vuelta puede ser el miércoles o el jueves">Días libres que pedirías:
  <select id="extra"><option value="0">ninguno</option><option value="1">hasta 1</option><option value="2">hasta 2</option></select></label>
 <label>Precio máximo: <b id="maxv"></b> € <input type="range" id="max" min="30" max="300" step="5" value="300"></label>
</div>
<p class="cont" id="cont"></p>
<details class="cont"><summary>Si un hotel elegido no aparece aquí</summary>
<p>1) En <b>chrome://extensions</b> → «Jawdrop: elegir hotel» → Detalles → activa «Permitir acceso a las URL de archivos» y recarga esta página (F5). 2) Si aun así no aparece, la extensión lo deja copiado: pégalo en esta caja (Ctrl+V): <input id="pega" style="width:50%" placeholder="pega aquí"></p></details>
<div id="lista"></div>
</div>
<script>
const NIVELES = __DATOS__;
let extra = 0, DATOS = NIVELES["0"];
const TOPES = __TOPES__, LIM_CORTO = __LIMC__, LIM_MEDIO = __LIMM__, VERDE_P = 90, AMAR_P = 115;
const MESES=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
let sel = 0, tipo = "todo", max = 300, lim = 10, orden = "vuelos", soloNuevos = false;
// Hoteles que el usuario elige en Booking con la extensión (se guardan en este navegador)
let ELEG = {};
try { ELEG = JSON.parse(localStorage.getItem("escapadas_eleg") || "{}"); } catch(e) {}
const guardaEleg = () => { try { localStorage.setItem("escapadas_eleg", JSON.stringify(ELEG)); } catch(e) {} };
function recibeHotel(m){
  if(!m || m.tipo !== "escapadas-hotel" || !m.clave || !m.hotel || typeof m.hotel.precio !== "number") return false;
  ELEG[m.clave] = m.hotel; guardaEleg(); pinta(); return true;
}
window.addEventListener("message", ev => { recibeHotel(ev.data); });
const AERO = {FR:"Ryanair", W6:"Wizz Air", W4:"Wizz Air", VY:"Vueling"};
const aero = t => t.replace(/^(FR|W6|W4|VY)(?: (\d{1,4}))?(?=\s)/, (m, s, n) =>
  AERO[s] + " " + (n ? "· vuelo " + s + " " + n : (s==="W6"||s==="W4" ? "· nº de vuelo sin confirmar" : "")));
const parte = s => { const m = s.match(/^(.*?) \((\w{3})\), (.*)$/); return m ? {ciudad:m[1], cod:m[2], pais:m[3]} : {ciudad:s, cod:"", pais:""}; };
const horasTxt = (h, aprox) => { if(h==null) return ""; const m = Math.round(h*60); return (aprox?"≈ ":"") + Math.floor(m/60) + " h" + (m%60 ? " " + String(m%60).padStart(2,"0") + " min" : ""); };
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fecha = d => { const [a,m,dd] = d.split("-"); return (+dd) + " " + MESES[+m-1]; };
const esNuevo = o => (o.nuevo||"").startsWith("🆕");
// Opciones que cuentan para el calendario: todas, o solo las de país nuevo si la casilla está activa
const opsCal = d => soloNuevos ? d.opciones.filter(esNuevo) : d.opciones;
const mejorOp = d => opsCal(d)[0];
const minimo = d => opsCal(d).length ? mejorOp(d).total : null;
// País nuevo de una opción: el de la vuelta si solo es nuevo el de la vuelta; si no, el de la ida
const paisNuevo = o => parte((o.nuevo||"").includes("vuelta") && !(o.nuevo||"").includes("ida") ? (o.desde || o.destino) : o.destino).pais;
const claseDia = (d,p) => { const o = opsCal(d); return clase(p, o.length ? mejorOp(d).kmBcn : null); };
const rev = o => /≥/.test(o.totalTxt + o.ida + o.vuelta);
// Semáforo con topes fijos según la distancia en avión desde BCN (semaforo.py): corto / medio / largo
const clase = (p, km) => {
  if(p == null) return "";
  const t = TOPES[km == null || km <= LIM_CORTO ? "corto" : (km <= LIM_MEDIO ? "medio" : "largo")];
  return p <= t[0] ? "verde" : p <= t[1] ? "amar" : "rojo";
};

function pintaCal(){
  document.getElementById("cal").innerHTML = DATOS.map((d,i) => {
    const p = minimo(d), o = opsCal(d).length ? mejorOp(d) : null;
    if(soloNuevos) return `<button class="dia ${p==null?"nada":claseDia(d,p)} ${i===sel?"sel":""}" data-i="${i}">
      <div class="f">Dom ${fecha(d.dia)}</div><div class="p">${p==null?"no hay":p.toFixed(0)+" €"}</div>
      <div class="d">${o?"🆕 "+esc(paisNuevo(o)):(d.opciones.length?"ningún país nuevo":"sin datos")}</div><div class="d">${o?"solo vuelos":""}</div></button>`;
    return `<button class="dia ${claseDia(d,p)} ${i===sel?"sel":""}" data-i="${i}">
      <div class="f">Dom ${fecha(d.dia)}</div><div class="p">${p==null?"—":p.toFixed(0)+" €"}</div>
      <div class="d">${o?esc(o.destino.replace(/ \(.*/,"")):"sin datos"}</div><div class="d">solo vuelos</div></button>`;
  }).join("");
  document.querySelectorAll(".dia").forEach(b => b.onclick = () => { sel = +b.dataset.i; pinta(); });
}
function pintaLista(){
  const d = DATOS[sel];
  const todas = d.opciones.filter(o => (tipo==="todo"||o.tipo===tipo) && o.total <= max && (!soloNuevos || esNuevo(o)));
  if(orden==="cerrado") todas.sort((a,b) => (a.paq ? a.paq.paquete : 1e9) - (b.paq ? b.paq.paquete : 1e9));
  const ops = todas.slice(0, lim);
  const h = document.getElementById("lista");
  const nr = d.opciones.filter(rev).length, ta = DATOS.reduce((s,x)=>s+x.opciones.length,0), tr = DATOS.reduce((s,x)=>s+x.opciones.filter(rev).length,0);
  document.getElementById("cont").innerHTML = `Este domingo: <b>${nr}</b> de ${d.opciones.length} opciones con precio por comprobar. Entre todos los domingos: <b>${tr}</b> de ${ta} (${(100*tr/ta).toFixed(0)} %). Datos generados ${esc(d.generado)}.<br>Con los filtros: ${todas.length} opciones${todas.length>ops.length?`, enseño las ${ops.length} más baratas`:""}.`;
  if(!ops.length){ h.innerHTML = '<div class="vacio">Nada con estos filtros.</div>'; return; }
  h.innerHTML = ops.map(o => {
    const otro = o.tipo === "otro";
    const A = parte(o.destino), B = otro ? parte(o.desde) : A;
    const misma = otro && o.pais !== "sí" && (+o.km < 60 || A.ciudad.split(" ")[0] === B.ciudad.split(" ")[0]);
    let titulo;
    if(!otro){
      titulo = `<div class="lugar"><h3>${esc(A.ciudad)}</h3><span>${esc(A.cod)} · ${esc(A.pais)}</span></div>`;
    } else if(misma){
      titulo = `<div class="lugar"><h3>${esc(A.ciudad.split(" ")[0])}</h3><span>${esc(A.pais)}</span></div>
        <span class="dosap">⚠ dos aeropuertos: llegas a ${esc(A.ciudad)} (${esc(A.cod)}) · vuelves desde ${esc(B.ciudad)} (${esc(B.cod)})</span>`;
    } else {
      titulo = `<div class="lugar"><small>Ida a</small><h3>${esc(A.ciudad)}</h3><span>${esc(A.cod)} · ${esc(A.pais)}</span></div>
        <div class="puente">↔ ≈${esc(o.km)} km${o.ferri?" ⛴":""}${o.pais==="sí"?" · <b>otro país</b>":""}</div>
        <div class="lugar"><small>Vuelta desde</small><h3>${esc(B.ciudad)}</h3><span>${esc(B.cod)} · ${esc(B.pais)}</span></div>`;
    }
    const aprox = /≈/.test(o.ida);
    const tras = otro ? `<div class="aviso">Hay que ir por tu cuenta de ${esc(A.ciudad)} a ${esc(B.ciudad)}: ≈${esc(o.km)} km${o.ferri?" (con ferri ⛴)":""}, traslado ≈ ${esc(o.traslado.replace("≈",""))} en coche (en bus suele ser más; el billete no está incluido)
      ${o.linksTraslado.map(l=>` · <a href="${esc(l[1])}" target="_blank">${esc(l[0])}</a>`).join("")}</div>` : "";
    const r = rev(o);
    const P = o.paq;
    const BUSQ = o.busquedas || [];
    const claveDe = i => d.dia + "|" + o.destino + "|" + (o.desde || "") + "|" + i;
    const elegidos = BUSQ.map((b, i) => ELEG[claveDe(i)] || null);
    const todos = BUSQ.length > 0 && elegidos.every(x => x);
    const totalHoteles = todos ? elegidos.reduce((s, h) => s + h.precio, 0) : null;
    const nivel = P ? P.estancias.map(e => e.estimado ? e.estimado.total : null) : [];
    const ok = P && nivel.length && nivel.every(x => x != null);
    const grande = todos ? (o.total + totalHoteles).toFixed(0) + " €" : esc(o.totalTxt) + " €";
    const cer = todos
      ? `<div class="cerrado">paquete con tu hotel · vuelos ${esc(o.totalTxt)} € + hotel ${totalHoteles.toFixed(0)} €</div>`
      : ok
        ? `<div class="cerrado" style="color:var(--mut)">solo vuelos · hotel ≈ ${P.hotel.toFixed(0)} € (nivel de la ciudad)</div>`
        : `<div class="cerrado" style="color:var(--mut)">solo vuelos · elige hotel ↓</div>`;
    let hotelHtml = '<div class="hoteles">';
    BUSQ.forEach((b, i) => {
      const est = P && P.estancias[i] && P.estancias[i].estimado;
      const gg = P && P.estancias[i] && P.estancias[i].google;
      const h = elegidos[i];
      hotelHtml += `<div class="noche">🏨 <b>${b.noches} noche${b.noches>1?"s":""} en ${esc(parte(b.ciudad).ciudad)}</b> (${fecha(b.entrada)} → ${fecha(b.salida)})` +
        (est ? ` · nivel de precio ≈ ${est.porNoche.toFixed(0)} €/noche${est.candidatos < 5 ? " (pocos datos)" : ""}` : "") +
        (gg ? ` · <span title="Google Hotels vía DataForSEO (prueba): puede incluir camas de hostel; nota sobre 5">Google ≈ ${gg.porNoche.toFixed(0)} €/noche: ${gg.sugerencias.map(x => esc(x.nombre) + " " + x.porNoche.toFixed(0) + " €").join(" · ")}</span>` : "") +
        ` · <a href="${esc(b.url)}" data-abrir="1" data-clave="${esc(claveDe(i))}" target="_blank" rel="noopener"><b>${h ? "Cambiar hotel" : "Elegir hotel"}</b></a> <small>(abre Booking con tu búsqueda; pulsa el ＋ verde del que elijas)</small></div>`;
      if(h) hotelHtml += `<div class="aloj"><div class="pr">${h.precio.toFixed(0)} €<br><small>${b.noches} noche${b.noches>1?"s":""}</small></div>
        <div><b>✔ ${esc(h.nombre)}</b>${h.nota?` · nota ${esc(h.nota)}/10`:""}${h.opiniones?` (${esc(h.opiniones)} op.)`:""}${h.distancia?` · ${esc(h.distancia)}`:""}<br><small>${esc(h.habitacion||"")}</small><br>
        ${h.enlace?`<a href="${esc(h.enlace)}" target="_blank" rel="noopener">Abrir el hotel en Booking</a> · `:""}<a href="#" data-quitar="${esc(claveDe(i))}">Quitar</a></div></div>`;
    });
    if(!BUSQ.length) hotelHtml += '<div class="noche">No sé en qué ciudad dormir en esta opción.</div>';
    hotelHtml += "</div>";
    return `<div class="op ${r?"rev":""}"><div class="lugares">${titulo}</div><div><div class="tot">${grande}</div>${cer}</div>
      <div class="tramo"><b>Ida</b> · ${esc(aero(o.ida))}</div><div></div>
      <div class="tramo"><b>Vuelta</b> · ${esc(aero(o.vuelta))}</div><div></div>
      ${r?'<div class="aviso2">⚠ Precio por comprobar: un tramo de Wizz lleva «≥», el real puede ser mayor. Mira ese vuelo (hora y día de arriba) en la app de Wizz antes de decidir.</div>':""}
      ${tras}
      <div class="pie"><a href="${esc(o.linkIda)}" target="_blank">Ver ida</a><a href="${esc(o.linkVuelta)}" target="_blank">Ver vuelta</a>
        ${/precio (guardado de hoy|de ayer|de hace)/.test(o.ida + o.vuelta) ? '<span class="chip" title="Precio de Vueling de una búsqueda anterior: puede haber cambiado">Vueling: precio guardado (con su fecha)</span>' : ""}
        ${(o.nuevo||"").startsWith("🆕") ? `<span class="chip nuevo" title="País que no está en paises_visitados.txt">🆕 país nuevo${o.nuevo.includes("vuelta") && !o.nuevo.includes("ida") ? " (el de la vuelta)" : o.nuevo.includes("ida y vuelta") ? " (ida y vuelta)" : ""}</span>` : ""}
        ${o.libres ? `<span class="chip libres" title="Para esta vuelta tienes que pedir ese número de días en el trabajo">📅 pide ${o.libres} día${o.libres>1?"s":""} libre${o.libres>1?"s":""}${o.sinvuelta ? " · sin pedirlos no hay vuelta que encaje" : o.ahorro ? " · ahorras " + o.ahorro.toFixed(0) + " € frente a no pedirlos" : ""}</span>` : (extra ? `<span class="chip" title="Con días libres no sale más barato">sin pedir días</span>` : "")}
        <span class="chip">${o.noches} noche${o.noches>1?"s":""}</span>
        ${o.horas!=null?`<span class="chip horas" title="Desde que aterriza la ida hasta que despega la vuelta">${horasTxt(o.horas, aprox)} sobre el terreno${otro?" (con traslado)":""}</span>`:""}
</div>${hotelHtml}</div>`;
  }).join("");
}
function guardaVista(){
  try { localStorage.setItem("escapadas_vista", JSON.stringify({dia: DATOS[sel] && DATOS[sel].dia, tipo, lim, max, orden, soloNuevos, extra})); } catch(e) {}
}
// ---- Panel de actualización y Vueling (necesita servidor.py; abierta como archivo no hay botones) ----
const SERV = location.protocol.indexOf("http") === 0;
const VY = {estado: null, msg: "", pend: null, espera: false, nuevo: false};
const MESES_L = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
const fechaL = iso => { const [a,m,d] = iso.split("-"); return (+d) + " de " + MESES_L[+m-1]; };
const edadVy = iso => { const dias = Math.floor((Date.now() - new Date(iso)) / 864e5);
  return dias <= 0 ? "de hoy" : dias === 1 ? "de ayer" : "de hace " + dias + " días"; };
async function api(ruta, cuerpo){
  const r = await fetch(ruta, cuerpo === undefined ? {cache:"no-store"} :
    {method:"POST", headers:{"Content-Type":"application/json","X-Escapadas":"1"}, body:JSON.stringify(cuerpo)});
  return r.json();
}
async function cargaEstado(){
  try { VY.estado = await api("/api/estado"); } catch(e) { VY.estado = null; VY.msg = "No consigo hablar con el servidor (¿sigue abierta su ventana?)."; }
}
async function lanza(ruta, cuerpo){
  VY.msg = ""; VY.pend = null;
  let r = {};
  try { r = await api(ruta, cuerpo); } catch(e) { r = {error: "No consigo hablar con el servidor."}; }
  if(r.error){ VY.msg = r.error; pintaVy(); return; }
  sondea();
}
async function sondea(){
  VY.espera = true; pintaVy();
  while(true){
    await new Promise(r => setTimeout(r, 2000));
    await cargaEstado();
    const t = VY.estado && VY.estado.trabajo;
    if(!VY.estado || !t || t.estado !== "corriendo") break;
    pintaVy();
  }
  VY.espera = false;
  const t = VY.estado && VY.estado.trabajo;
  if(!t) { pintaVy(); return; }
  if(t.estado === "error"){ VY.msg = t.mensaje; pintaVy(); return; }
  if(t.auto){ VY.nuevo = true; pintaVy(); return; }   // refresco automático: no recargo la página sin avisar
  if(t.accion === "estimar"){ VY.pend = {domingos: t.domingos, total: t.resultado.total, costes: t.resultado.costes}; pintaVy(); return; }
  location.reload();
}
function pintaVy(){
  const el = document.getElementById("vy"); if(!el) return;
  if(!SERV){
    el.innerHTML = "<b>Actualizar y buscar Vueling:</b> esta página está abierta como archivo y no tiene botones. Ábrela con <b>abrir_escapadas.bat</b> (en la carpeta escapadas_flash).";
    return;
  }
  const E = VY.estado;
  if(!E){ el.innerHTML = esc(VY.msg || "Conectando con el servidor…"); return; }
  const c = E.cuota, d = DATOS[sel], t = E.trabajo;
  const ocupado = VY.espera || (t && t.estado === "corriendo");
  const futuros = DATOS.map(x => x.dia).filter(x => x >= E.hoy);
  let h = "";
  if(E.edad_datos != null){
    const hrs = E.edad_datos / 3600, txt = hrs < 1 ? "hace " + Math.max(1, Math.round(hrs * 60)) + " min"
      : hrs < 48 ? "hace " + Math.round(hrs) + " h" : "hace " + Math.round(hrs / 24) + " días";
    const auto = t && t.auto && t.estado === "corriendo";
    h += `<div class="vy-nota">${auto ? "🔄 Actualizando en segundo plano (precios de más de " + E.horas_fresco + " h)…" : "Precios de Ryanair, Wizz y Kiwi actualizados <b>" + txt + "</b>" + (hrs >= E.horas_fresco ? " · se refrescan solos al abrir esta página" : "")}</div>`;
  }
  if(VY.nuevo && !ocupado) h += `<div class="vy-ok">✔ Datos actualizados en segundo plano. <button data-vy="recarga">Ver los datos nuevos</button></div>`;
  if(c){
    h += `<div><b>SerpApi:</b> quedan <b>${c.quedan}</b> de ${c.total}` + (c.renueva ? ` · se renuevan el ${fechaL(c.renueva)}` : "") + `</div>`;
    if(c.utiles < c.quedan) h += `<div class="vy-nota">Freno de seguridad: no se pasa de ${c.limite} búsquedas usadas al mes; se pueden gastar <b>${c.utiles}</b> más.</div>`;
  } else {
    h += `<div class="vy-err">${esc(E.error || "Sin datos de SerpApi.")}</div>`;
  }
  const unDia = d && d.dia >= E.hoy;
  h += `<div class="vy-acc">
    <button data-vy="act1" ${ocupado || !unDia ? "disabled" : ""}>Actualizar este domingo (gratis)</button>
    <button data-vy="act" ${ocupado ? "disabled" : ""}>Actualizar todos los domingos (gratis)</button>
  </div>`;
  h += `<div class="vy-nota">Vueling, Ryanair, Wizz y Kiwi se actualizan gratis con «Actualizar» (Vueling viene de Kiwi, con el precio de la aerolínea estimado ±3 €; pulsa «Comprobar» para verlo en su web). SerpApi queda solo para comprobar un vuelo suelto.</div>`;
  if(VY.pend){
    const P = VY.pend, util = c ? c.utiles : 0, n = P.total;
    h += `<div class="vy-conf"><b>${n > 0 ? `Esto gastará unas ${n} búsquedas de SerpApi` : "Esto no gastará búsquedas nuevas (ya están guardadas)"}</b>`
      + ` (${P.domingos.map(x => fecha(x) + ": " + P.costes[x]).join(" · ")}). Te quedan ${c ? c.quedan : "?"}.`
      + (n > util ? ` <b>Ojo:</b> por el freno del mes solo caben ${util}; se buscará hasta donde llegue.` : "")
      + ` ¿Sigo?<div class="vy-acc"><button class="pri" data-vy="si" ${util > 0 ? "" : "disabled"}>Sí, buscar</button><button data-vy="no">No</button></div></div>`;
  }
  if(ocupado) h += `<div class="vy-nota">⏳ ${esc((t && t.mensaje) || "Trabajando…")} Puede tardar unos minutos; no cierres la ventana negra.</div>`;
  if(VY.msg) h += `<div class="vy-err">${esc(VY.msg)}</div>`;
  if(!ocupado && !VY.pend && t && t.estado === "hecho" && t.fin && Date.now()/1000 - t.fin < 600){
    if(t.accion === "vueling") h += `<div class="vy-ok">✔ Vueling buscado: ${t.resultado.gastadas} búsquedas gastadas.</div>`;
    else if(t.accion === "actualizar") h += `<div class="vy-ok">✔ Ryanair, Wizz y Kiwi actualizados.</div>`;
    (t.avisos || []).forEach(a => { h += `<div class="vy-nota">· ${esc(a)}</div>`; });
  }
  el.innerHTML = h;
}
document.getElementById("vy").addEventListener("click", ev => {
  const b = ev.target.closest("button[data-vy]"); if(!b || b.disabled) return;
  const futuros = DATOS.map(x => x.dia).filter(x => x >= VY.estado.hoy), k = b.dataset.vy;
  if(k === "act") lanza("/api/actualizar", {});
  else if(k === "act1") lanza("/api/actualizar", {domingos: [DATOS[sel].dia]});
  else if(k === "uno") lanza("/api/estimar", {domingos: [DATOS[sel].dia]});
  else if(k === "todos") lanza("/api/estimar", {domingos: futuros});
  else if(k === "recarga") location.reload();
  else if(k === "no"){ VY.pend = null; pintaVy(); }
  else if(k === "si" && VY.pend){ const P = VY.pend; VY.pend = null;
    lanza("/api/vueling", {domingos: P.domingos, maximo: Math.max(P.total, 1), confirmado: true}); }
});
async function iniciaVy(){
  if(!SERV){ pintaVy(); return; }
  await cargaEstado(); pintaVy();
  if(VY.estado && VY.estado.trabajo && VY.estado.trabajo.estado === "corriendo") sondea();
}
function cambiaExtra(n){
  if(!NIVELES[String(n)]) n = 0;
  extra = n; DATOS = NIVELES[String(n)];
  if(sel >= DATOS.length) sel = 0;
}
function pinta(){ pintaCal(); pintaLista(); guardaVista(); pintaVy(); }
["todo","mismo","otro"].forEach(t => document.getElementById("t-"+t).onclick = () => {
  tipo = t; ["todo","mismo","otro"].forEach(x => document.getElementById("t-"+x).classList.toggle("on", x===t)); pintaLista(); });
const rg = document.getElementById("max"), mv = document.getElementById("maxv");
document.getElementById("extra").onchange = e => { cambiaExtra(+e.target.value); pinta(); };
document.getElementById("nuevos").onchange = e => { soloNuevos = e.target.checked; pinta(); };
document.getElementById("ord").onchange = e => { orden = e.target.value; pintaLista(); };
document.getElementById("lista").addEventListener("click", ev => {
  const ab = ev.target.closest("a[data-abrir]");
  if(ab){ ev.preventDefault();
    window.open(ab.href.split("#")[0] + "#escapadas=" + encodeURIComponent(ab.dataset.clave), "escapadas:" + ab.dataset.clave);
    return; }
  const q = ev.target.closest("a[data-quitar]");
  if(q){ ev.preventDefault(); delete ELEG[q.dataset.quitar]; guardaEleg(); pinta(); }
});
document.getElementById("pega").addEventListener("input", ev => {
  try { if(recibeHotel(JSON.parse(ev.target.value))) { ev.target.value = ""; } } catch(e) {}
});
document.getElementById("lim").onchange = e => { lim = +e.target.value; pintaLista(); };
rg.oninput = () => { max = +rg.value; mv.textContent = max >= 300 ? "sin límite" : max; pintaLista(); };
mv.textContent = "sin límite";
// abre el primer domingo con datos
sel = Math.max(0, DATOS.findIndex(d => d.opciones.length));
// ...salvo que ya estuvieras mirando otro: se recuerda el domingo y los filtros tras recargar (F5)
try {
  const v = JSON.parse(localStorage.getItem("escapadas_vista") || "null");
  if(v){
    const i = DATOS.findIndex(d => d.dia === v.dia);
    if(i >= 0 && DATOS[i].opciones.length) sel = i;
    if(["todo","mismo","otro"].includes(v.tipo)) tipo = v.tipo;
    if(+v.lim > 0) lim = +v.lim;
    if(+v.max > 0) max = +v.max;
    if(["vuelos","cerrado"].includes(v.orden)) orden = v.orden;
    soloNuevos = v.soloNuevos === true;
    if(NIVELES[String(v.extra)]) cambiaExtra(+v.extra);
  }
} catch(e) {}
["todo","mismo","otro"].forEach(x => document.getElementById("t-"+x).classList.toggle("on", x===tipo));
document.getElementById("lim").value = String(lim);
document.getElementById("ord").value = orden;
document.getElementById("nuevos").checked = soloNuevos;
document.getElementById("extra").value = String(extra);
[...document.getElementById("extra").options].forEach(o => { if(!NIVELES[o.value]) { o.disabled = true; o.textContent += " (sin datos: actualiza)"; } });
document.getElementById("max").value = String(max);
document.getElementById("maxv").textContent = max >= 300 ? "sin límite" : max;
pinta();
iniciaVy();
</script>
<script>
let HIST = __HIST__;
(function(){
  const el = document.getElementById("hist-in");
  const NM = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  const DS = ["dom","lun","mar","mié","jue","vie","sáb"];
  const f = iso => { const d = new Date(iso.slice(0,10) + "T12:00:00"); return DS[d.getDay()] + " " + d.getDate() + " " + NM[d.getMonth()]; };
  const e = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const eur = n => (Math.round(n * 100) / 100).toLocaleString("es-ES", {minimumFractionDigits: 0, maximumFractionDigits: 2}) + " €";
  const nombreMes = m => NM[+m.slice(5) - 1] + " " + m.slice(0, 4);
  let soloN = false, soloC = false, espera = null;
  function pinta(){
    const filas = (HIST.filas || []).filter(x => (!soloN || x.nuevo) && (!soloC || x.chollo));
    const dias = Math.max(0, ...(HIST.filas || []).map(x => x.dias));
    let h = `<div class="rad-barra"><label><input type="checkbox" id="h-n" ${soloN ? "checked" : ""}> Solo países nuevos 🆕</label>`
      + `<label><input type="checkbox" id="h-c" ${soloC ? "checked" : ""}> Solo chollos 🔥</label>`
      + (SERV ? (espera ? `<span>⏳ ${e(espera.msg)} <small>(unos minutos; no cierres la ventana negra)</small></span>`
                        : `<button id="h-tomar">Tomar lecturas ahora (gratis, 6 meses)</button>`) : "") + `</div>`;
    if(!SERV) h += `<div><small>Para tomar lecturas nuevas abre la página con <b>abrir_escapadas.bat</b>.</small></div>`;
    h += `<div><small>Cada precio mínimo que ven el radar y Vueling se guarda con su fecha. «Típico» = mediana de un valor por día visto, para el mismo mes de salida. `
      + `🔥 chollo = la última lectura está un 20 % o más por debajo de lo típico (hacen falta 3 días de lecturas; ahora hay ${dias}). `
      + `Un precio visto hoy puede haber volado en dos semanas: es memoria, no una reserva.</small></div>`;
    if(!filas.length){ el.innerHTML = h + `<p><small>Aún no hay lecturas${soloC ? " que sean chollo" : ""}.</small></p>`; return; }
    h += `<table><tr><th></th><th>Destino</th><th>Salida en</th><th>Última</th><th>Típico</th><th>Mínimo visto</th><th>Días</th></tr>`;
    filas.slice(0, 80).forEach(x => {
      h += `<tr><td>${x.chollo ? "🔥" : ""}</td><td>${x.nuevo ? "🆕 " : ""}<b>${e(x.ciudad)}</b> (${x.destino})<br><small>${e(x.pais)}</small></td>`
        + `<td>${nombreMes(x.mes)}</td>`
        + `<td><span class="pr">${eur(x.ultima)}</span><br><small>${e(x.fuente)} · ${f(x.salida)} · visto ${f(x.visto)}${x.chollo ? " · " + x.ahorro + " % bajo lo típico" : ""}</small></td>`
        + `<td>${eur(x.tipico)}</td><td>${eur(x.minimo)}<br><small>${e(x.min_fuente)} · ${f(x.min_visto)}</small></td><td>${x.dias}</td></tr>`;
    });
    el.innerHTML = h + "</table>" + (filas.length > 80 ? `<div><small>Enseño los 80 primeros de ${filas.length}.</small></div>` : "");
  }
  el.addEventListener("change", ev => {
    if(ev.target.id === "h-n") soloN = ev.target.checked;
    else if(ev.target.id === "h-c") soloC = ev.target.checked;
    pinta();
  });
  el.addEventListener("click", async ev => {
    const b = ev.target.closest("button"); if(!b || b.id !== "h-tomar" || espera) return;
    espera = {msg: "Empezando…"}; pinta();
    let r = {};
    try { r = await api("/api/historico-tomar", {meses: 6}); } catch(x) { r = {error: "No consigo hablar con el servidor."}; }
    if(r.error){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-err">${e(r.error)}</div>`); return; }
    while(true){
      await new Promise(z => setTimeout(z, 2000));
      let est = null;
      try { est = await api("/api/estado"); } catch(x) {}
      const t = est && est.trabajo;
      if(t && t.estado === "corriendo"){ espera.msg = t.mensaje || "Trabajando…"; pinta(); continue; }
      if(t && t.estado === "error"){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-err">${e(t.mensaje)}</div>`); return; }
      if(t && t.estado === "cancelado"){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-ok">${e(t.mensaje)}</div>`); return; }
      break;
    }
    try { HIST = await api("/api/historico-datos"); } catch(x) {}
    espera = null; pinta();
  });
  pinta();
})();
</script>
<script>
let RADAR = __RADAR__;
(function(){
  const el = document.getElementById("rad-in");
  const meses = Object.keys(RADAR.meses || {}).sort();
  const NM = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  const DS = ["dom","lun","mar","mié","jue","vie","sáb"];
  const f = iso => { const d = new Date(iso + "T12:00:00"); return DS[d.getDay()] + " " + d.getDate() + " " + NM[d.getMonth()]; };
  const e = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const eur = n => (Math.round(n * 100) / 100).toLocaleString("es-ES", {minimumFractionDigits: 0, maximumFractionDigits: 2}) + " €";
  let mes = null, soloN = true, dias = "6-8", soloPrecio = true, espera = null;
  try { const v = JSON.parse(localStorage.getItem("escapadas_radar") || "null");
    if(v){ mes = v.mes; soloN = v.soloN !== false; dias = v.dias || dias; soloPrecio = v.soloPrecio !== false; } } catch(x) {}
  if(!mes || (!meses.includes(mes) && meses.length)) mes = meses[0] || "";
  const guarda = () => { try { localStorage.setItem("escapadas_radar", JSON.stringify({mes, soloN, dias, soloPrecio})); } catch(x) {} };
  const hoy = new Date(); 
  const proximos = []; for(let i = 0; i < 12; i++){ const d = new Date(hoy.getFullYear(), hoy.getMonth() + i, 1);
    proximos.push(d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0")); }
  const nombreMes = m => NM[+m.slice(5) - 1] + " " + m.slice(0, 4);
  const aero = o => e(o.aerolinea) + (o.orientativo ? " ≈" : "");
  function vuelta(destino, ida){
    const v = (RADAR.vueltas || {})[destino + "|" + ida];
    if(espera && espera.que === destino + "|" + ida) return `<div class="vlt">⏳ ${e(espera.msg || "Buscando vueltas…")} <small>(unos 20-60 s; no cierres la ventana negra)</small></div>`;
    if(!v) return SERV ? `<button data-vlt="${destino}|${ida}" ${espera ? "disabled" : ""}>Ver vueltas</button>` : "";
    const filas = v.lista.map(r => `<div>${eur(r.precio)} · ${e(r.ciudad)} (${r.aeropuerto}) · ${e(r.aerolinea)}${r.orientativo ? " ≈" : ""}${r.minimo ? " ≥" : ""} · ${f(r.salida.slice(0,10))} ${r.salida.slice(11,16)}`
      + ` · ${r.km === 0 ? "mismo aeropuerto" : "≈" + r.km + " km" + (r.ferri ? " ⛴" : "") + (r.cambia_pais ? " (otro país)" : "")}</div>`).join("");
    return `<div class="vlt"><b>Vuelta a BCN</b> entre ${v.dias[0]} y ${v.dias[1]} días después (${f(ida)})${filas || "<div>Sin vuelos a BCN en esas fechas.</div>"}`
      + (SERV ? `<button data-vlt="${destino}|${ida}" ${espera ? "disabled" : ""}>Actualizar</button>` : "") + ` <small>buscado ${e(v.generado.replace("T"," "))}</small></div>`;
  }
  function pinta(){
    const M = (RADAR.meses || {})[mes];
    let h = `<div class="rad-barra"><label>Mes <select id="rad-mes">` +
      [...new Set([...meses, ...proximos])].sort().map(m => `<option value="${m}" ${m === mes ? "selected" : ""}>${nombreMes(m)}${(RADAR.meses||{})[m] ? "" : " (sin datos)"}</option>`).join("") +
      `</select></label><label><input type="checkbox" id="rad-n" ${soloN ? "checked" : ""}> Solo países nuevos 🆕</label>` +
      `<label><input type="checkbox" id="rad-p" ${soloPrecio ? "checked" : ""}> Solo con precio de ida y vuelta</label>` +
      `<label>Viaje de <input id="rad-d" value="${e(dias)}" size="4" title="días de ida a vuelta, por ejemplo 6-8"> días</label>` +
      (SERV ? (espera && espera.que === "mes" ? `<span>⏳ ${e(espera.msg)} <small>(unos 6-10 min; no cierres la ventana negra)</small></span>` : `<button id="rad-act" ${espera ? "disabled" : ""}>${M ? "Actualizar" : "Calcular"} este mes (gratis, unos 6-10 min)</button>`) : "") + `</div>`;
    if(!SERV) h += `<div><small>Para calcular o actualizar el radar abre la página con <b>abrir_escapadas.bat</b>.</small></div>`;
    if(!M){ el.innerHTML = h + `<p><small>Este mes no está calculado todavía.</small></p>`; return; }
    const todos = M.lista.filter(x => !soloN || x.nuevo);
    const lista = todos.filter(x => !soloPrecio || x.pareja);
    const ocultos = todos.length - lista.length;
    h += `<div><small>Calculado ${e(M.generado.replace("T"," "))} · viaje de ${M.dias[0]}-${M.dias[1]} días · ida más barata del mes por destino. «≈» = precio orientativo de Kiwi (la aerolínea puede cobrar algo menos).</small></div>`;
    (M.avisos || []).forEach(a => { h += `<div><small>· ${e(a)}</small></div>`; });
    h += `<table><tr><th>Ida y vuelta</th><th>Destino</th><th>Ida más barata</th><th>Vuelta elegida</th><th>Otras vueltas</th></tr>`;
    lista.forEach(x => {
      const m = x.mejor, p = x.pareja;
      const otras = x.otras.length ? `<br><small>también: ` + x.otras.map(o => `${aero(o)} ${eur(o.ida[1])}`).join(" · ") + `</small>` : "";
      const total = p ? `<span class="pr">${eur(p.total)}${p.orientativo ? " ≈" : ""}</span><br><small>${p.noches || ""} días</small>` : `<span class="pr">—</span>`;
      const vta = p ? `${f(p.vuelta)}<br><small>${eur(p.precio_vuelta || (p.total - m.ida[1]))} · ${e(p.aerolinea)}</small>` : "<small>sin vuelta calculada</small>";
      h += `<tr><td>${total}</td><td>${x.nuevo ? "🆕 " : ""}<b>${e(x.ciudad)}</b> (${x.destino})<br><small>${e(x.pais_nombre)}</small></td>`
        + `<td><span class="pr">${eur(m.ida[1])}</span> ${aero(m)}<br>${f(m.ida[0])}${otras}</td>`
        + `<td>${vta}</td><td>${vuelta(x.destino, m.ida[0])}</td></tr>`;
    });
    if(!lista.length) h += `<tr><td colspan="5"><small>${soloN && !todos.length ? "Ningún país nuevo con vuelo directo este mes. Desmarca «Solo países nuevos» para ver todo." : "Sin datos con ida y vuelta."}</small></td></tr>`;
    el.innerHTML = h + "</table>" + (ocultos ? `<div><small>${ocultos} destinos más no tienen vuelta directa calculada (o son de muy largo radio): desmarca «Solo con precio de ida y vuelta» para verlos.</small></div>` : "");
  }
  el.addEventListener("change", ev => {
    if(ev.target.id === "rad-mes") mes = ev.target.value;
    else if(ev.target.id === "rad-n") soloN = ev.target.checked;
    else if(ev.target.id === "rad-p") soloPrecio = ev.target.checked;
    else if(ev.target.id === "rad-d") dias = ev.target.value.trim() || "6-8";
    guarda(); pinta();
  });
  async function corre(ruta, cuerpo, que){
    espera = {que, msg: "Empezando…"}; pinta();
    let r = {};
    try { r = await api(ruta, cuerpo); } catch(x) { r = {error: "No consigo hablar con el servidor (¿sigue abierta su ventana negra?)."}; }
    if(r.error){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-err">${e(r.error)}</div>`); return; }
    while(true){
      await new Promise(z => setTimeout(z, 2000));
      let est = null;
      try { est = await api("/api/estado"); } catch(x) {}
      const t = est && est.trabajo;
      if(t && t.estado === "corriendo"){ espera.msg = t.mensaje || "Trabajando…"; pinta(); continue; }
      if(t && t.estado === "error"){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-err">${e(t.mensaje)}</div>`); return; }
      break;
    }
    try { RADAR = await api("/api/radar-datos"); } catch(x) {}
    espera = null; pinta();
  }
  el.addEventListener("click", ev => {
    const b = ev.target.closest("button"); if(!b || b.disabled) return;
    const d = (document.getElementById("rad-d") || {}).value || dias;
    if(b.id === "rad-act" && mes) corre("/api/radar", {mes, dias: d}, "mes");
    else if(b.dataset.vlt){ const [destino, ida] = b.dataset.vlt.split("|"); corre("/api/radar-vuelta", {destino, ida, dias: d}, b.dataset.vlt); }
  });
  pinta();
})();
</script>
<script>
let PAIS = __PAIS__;
(function(){
  const el = document.getElementById("pais-in");
  const NM = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  const DS = ["dom","lun","mar","mié","jue","vie","sáb"];
  const f = iso => { const d = new Date(iso.slice(0,10) + "T12:00:00"); return DS[d.getDay()] + " " + d.getDate() + " " + NM[d.getMonth()]; };
  const e = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const eur = n => (Math.round(n * 100) / 100).toLocaleString("es-ES", {minimumFractionDigits: 0, maximumFractionDigits: 2}) + " €";
  const DIAS_SEM = ["domingo","lunes","martes","miercoles","jueves","viernes","sabado"];
  const NOMBRES = PAIS.nombres || [], CODIGOS = PAIS.codigos || {};
  const sinTilde = t => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim().replace(/\s+/g, " ");
  const codigoDe = t => { const k = sinTilde(t); if(CODIGOS[k]) return CODIGOS[k]; if(/^[a-z]{2}$/.test(k)) return k.toUpperCase(); return null; };
  const rangoDias = t => { const m = String(t).trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/); return m ? [+m[1], +(m[2] || m[1])] : null; };
  const hace = iso => { const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
    if(isNaN(min)) return ""; if(min < 2) return "hace un momento"; if(min < 90) return "hace " + min + " min";
    if(min < 2880) return "hace " + Math.round(min / 60) + " h"; return "hace " + Math.round(min / 1440) + " días"; };
  let sel = null, texto = "", dias = "4", salida = "domingo", mes = "", mesFin = "", espera = null, estima = null;
  let vuelta = "", desde = "", hasta = "", maximo = "", solo = "", sin = "", radio = "", rango = false;
  try { const v = JSON.parse(localStorage.getItem("escapadas_pais") || "null");
    if(v){ texto = v.texto || ""; dias = v.dias || dias; salida = v.salida || salida; mes = v.mes || ""; mesFin = v.mesFin || ""; sel = v.sel || null;
      vuelta = v.vuelta || ""; desde = v.desde || ""; hasta = v.hasta || ""; maximo = v.maximo || ""; solo = v.solo || ""; sin = v.sin || ""; radio = v.radio || ""; rango = !!v.rango; } } catch(x) {}
  const guarda = () => { try { localStorage.setItem("escapadas_pais", JSON.stringify({texto, dias, salida, mes, mesFin, sel, vuelta, desde, hasta, maximo, solo, sin, radio, rango})); } catch(x) {} };
  const hoy = new Date();
  const proximos = []; for(let i = 0; i < 12; i++){ const d = new Date(hoy.getFullYear(), hoy.getMonth() + i, 1);
    proximos.push(d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0")); }
  if(!proximos.includes(mes)) mes = proximos[1] || proximos[0];
  if(!proximos.includes(mesFin) || mesFin <= mes) mesFin = "";
  const meses = () => mesFin ? proximos.filter(m => m >= mes && m <= mesFin).join(",") : mes;
  const conRango = () => rango && desde && hasta && desde <= hasta;
  const normLista = t => Array.from(new Set(sinTilde(t).split(",").map(x => x.trim()).filter(Boolean))).sort().join(",");
  const num = t => { const n = parseFloat(String(t).replace(",", ".")); return isNaN(n) ? null : n; };
  // lo que se manda al servidor (periodo: o meses, o fechas concretas)
  const cuerpo = () => Object.assign({pais: texto.trim(), dias, salida, vuelta: vuelta === "todos" ? "" : vuelta, maximo, solo, sin, radio},
    conRango() ? {desde, hasta} : {mes: meses()});
  // misma clave que calcula pais.py para reconocer una búsqueda ya hecha
  const claveDe = (cod, rd) => {
    const per = conRango() ? desde + "…" + hasta : meses().replace(/,/g, "+");
    const mx = num(maximo), rc = num(radio), so = normLista(solo), si = normLista(sin);
    return `${cod}|${per}|${rd[0]}-${rd[1]}|${salida}` + (vuelta && vuelta !== "todos" ? `|vuelta=${vuelta}` : "") + (mx != null ? `|max=${mx}` : "")
      + (so ? `|solo=${so}` : "") + (si ? `|sin=${si}` : "") + (rc != null ? `|radio=${rc}` : "");
  };
  const nombreMes = m => NM[+m.slice(5) - 1] + " " + m.slice(0, 4);
  const busquedas = () => Object.values(PAIS.busquedas || {}).sort((a, b) => a.generado < b.generado ? 1 : -1);
  const titulo = b => `${b.nuevo ? "🆕 " : ""}${b.pais} · ${b.periodo.split("+").map(m => /^\d{4}-\d\d$/.test(m) ? nombreMes(m) : m).join(", ")} · salida ${b.salida}${b.vuelta ? " → vuelta " + b.vuelta : ""} · ${b.dias[0] === b.dias[1] ? b.dias[0] : b.dias[0] + "-" + b.dias[1]} días`
    + (b.maximo != null ? ` · máx ${b.maximo} €` : "") + ((b.solo || []).length ? ` · solo ${b.solo.join("/")}` : "") + ((b.sin || []).length ? ` · sin ${b.sin.join("/")}` : "")
    + (b.radio != null ? ` · radio ${b.radio} km` : "");
  const vuelo = t => `<a href="${e(t.enlace)}" target="_blank" rel="noopener">${eur(t.precio)}${e(t.marca)}</a> ${e(t.aerolinea)}`
    + `<br><small>${e(t.salida.slice(11,16))}→${e((t.llegada || "?").slice(11,16))} · ${e(t.ciudad)} (${e(t.aeropuerto)})</small>`;
  function lugar(o){
    if(o.mismo) return `${e(o.entrada)}<br><small>mismo aeropuerto</small>`;
    let h = `${e(o.entrada)} → ${e(o.salida)}`;
    if(o.km != null) h += `<br><small>≈${o.km} km${o.ferri ? " ⛴" : ""}${o.traslado ? " · ≈" + e(o.traslado) + " en coche" : ""}`
      + (o.enlace_12go ? ` · <a href="${e(o.enlace_12go)}" target="_blank" rel="noopener">12Go</a>` : "")
      + (o.enlace_rome2rio ? ` · <a href="${e(o.enlace_rome2rio)}" target="_blank" rel="noopener">Rome2Rio</a>` : "") + `</small>`;
    return h;
  }
  function pinta(){
    const lista = busquedas();
    if(sel && !(PAIS.busquedas || {})[sel]) sel = null;
    const cod = codigoDe(texto), rd = rangoDias(dias);
    const claveAct = cod && rd ? claveDe(cod, rd) : null;
    const B = sel ? PAIS.busquedas[sel] : (claveAct && PAIS.busquedas ? PAIS.busquedas[claveAct] : null) || null;
    let h = `<div class="rad-barra"><label>País <input id="pa-pais" list="pa-lista" value="${e(texto)}" placeholder="Turquía, Georgia…" size="14"></label>`
      + `<datalist id="pa-lista">${NOMBRES.map(n => `<option value="${e(n)}">`).join("")}</datalist>`
      + `<label><input type="checkbox" id="pa-rango" ${rango ? "checked" : ""}> fechas concretas</label>`
      + (rango ? `<label>Del <input type="date" id="pa-desde" value="${e(desde)}"></label><label>al <input type="date" id="pa-hasta" value="${e(hasta)}"></label>`
        : `<label>Mes <select id="pa-mes">${proximos.map(m => `<option value="${m}" ${m === mes ? "selected" : ""}>${nombreMes(m)}</option>`).join("")}</select></label>`
          + `<label>hasta <select id="pa-mesfin"><option value="">— solo ese mes —</option>${proximos.filter(m => m > mes).map(m => `<option value="${m}" ${m === mesFin ? "selected" : ""}>${nombreMes(m)}</option>`).join("")}</select></label>`)
      + `<label>Salida <select id="pa-sal">${DIAS_SEM.map(d => `<option value="${d}" ${d === salida ? "selected" : ""}>${d.replace("miercoles","miércoles").replace("sabado","sábado")}</option>`).join("")}<option value="todos" ${salida === "todos" ? "selected" : ""}>cualquier día</option></select></label>`
      + `<label>Vuelta <select id="pa-vuelta"><option value="">cualquier día</option>${DIAS_SEM.map(d => `<option value="${d}" ${d === vuelta ? "selected" : ""}>${d.replace("miercoles","miércoles").replace("sabado","sábado")}</option>`).join("")}</select></label>`
      + `<label>Viaje de <input id="pa-dias" value="${e(dias)}" size="4" title="días contando ida y vuelta: 4 = domingo a miércoles; 4-5 prueba varios"> días</label>`
      + `<div class="rad-barra" style="flex-basis:100%"><label>Máx. total <input id="pa-max" value="${e(maximo)}" size="4" placeholder="sin tope"> €</label>`
      + `<label>Solo con <input id="pa-solo" value="${e(solo)}" size="12" placeholder="Ryanair, Wizz…" title="solo estas aerolíneas (vacío = todas)"></label>`
      + `<label>Sin <input id="pa-sin" value="${e(sin)}" size="12" placeholder="Vueling…" title="excluir estas aerolíneas"></label>`
      + `<label>Radio <input id="pa-radio" value="${e(radio)}" size="4" placeholder="auto" title="km en línea recta entre el aeropuerto de entrada y el de salida. Vacío = 250 km por día fuera; 0 = el mismo aeropuerto"> km</label></div>`
      + (SERV ? `<button id="pa-buscar" ${texto.trim() && !espera && !estima ? "" : "disabled"}>${espera ? "Buscando…" : (B ? "Buscar de nuevo (gratis)" : "Buscar (gratis)")}</button>`
        + (espera ? `<button id="pa-cancelar">Cancelar</button><span>⏳ ${e(espera.msg)} <small>(no cierres la ventana negra; si cancelas, lo ya consultado se guarda)</small></span>` : "")
        + (espera && espera.prog ? `<div style="flex-basis:100%"><div class="pa-barra" title="Aproximado: Ryanair y Wizz añaden pasos según lo que encuentran"><div style="width:${espera.prog.pct}%"></div></div>`
          + `<small>${espera.prog.pct} %${espera.prog.aproximado ? " aprox." : ""}${espera.prog.bloques > 1 ? " · bloque " + espera.prog.bloque + " de " + espera.prog.bloques : ""} · paso ${espera.prog.hecho} de ~${espera.prog.total}</small></div>` : "") : "") + `</div>`
      + (estima ? `<div class="vy-ok">${e(estima.texto)}<br><b>Tarda bastante</b> (unos ${e(Math.round(estima.minutos))} min). ¿Sigo? <button id="pa-si">Sí, buscar</button> <button id="pa-no">No, cambiar la búsqueda</button></div>` : "");
    const vacio = B && !B.mejores.length;
    if(vacio) h += `<div class="pa-vacio"><b>🔎 Búsqueda terminada: no hay ninguna combinación de ida y vuelta</b>`
      + `Se han mirado ${B.fechas.length} fechas de ida (${e(B.pais)}, ${e(B.salida)}${B.vuelta ? " → " + e(B.vuelta) : ""}, ${B.dias[0] === B.dias[1] ? B.dias[0] : B.dias[0] + "-" + B.dias[1]} días) y ningún vuelo directo cuadra con estas condiciones. `
      + `Prueba a quitar el día de vuelta o el precio máximo, a cambiar los días de viaje o a ampliar las fechas.</div>`;
    if(B && B.parcial) h += `<div class="pa-aviso"><b>Resultado parcial:</b> la búsqueda se canceló y solo cuenta lo ya terminado.</div>`;
    if(B && B.bloques_fallidos) h += `<div class="pa-aviso"><b>Ojo:</b> ${B.bloques_fallidos} de ${B.bloques} bloques fallaron (error técnico) y no cuentan; vuelve a pulsar «Buscar de nuevo» para reintentarlos (lo ya hecho sale de la caché).</div>`;
    if(!SERV) h += `<div><small>Para buscar abre la página con <b>abrir_escapadas.bat</b>. Aquí solo se ven las búsquedas ya hechas.</small></div>`;
    h += `<div><small>Dos billetes de solo ida: entras por un aeropuerto del país y sales por otro (o el mismo), con aerolíneas mezcladas; entre ambos, como mucho 250 km por cada día fuera (km por tierra aproximados «≈»; ⛴ = con ferri). Sin reglas de hora: se enseñan las horas. «~» = precio estimado de la aerolínea desde Kiwi (±3 €) · «≈» = precio de Kiwi sin medir · «≥» = mínimo del día en Wizz. Cada precio enlaza a la aerolínea.</small></div>`;
    if(lista.length){
      h += `<div class="rad-barra"><label>Búsquedas hechas <select id="pa-sel"><option value="" ${B ? "" : "selected"}>— elegir una —</option>${lista.map(b => `<option value="${e(b.clave)}" ${B && b.clave === B.clave ? "selected" : ""}>${e(titulo(b))}</option>`).join("")}</select></label></div>`;
    }
    if(!B){
      let m;
      if(!texto.trim()) m = "Escribe un país, elige el mes y pulsa «Buscar».";
      else if(!cod) m = `No reconozco «${e(texto.trim())}». Elige un país de la lista (o escribe su nombre en castellano).`;
      else if(!rd) m = "Los días son un número (4) o un rango (4-5).";
      else m = `Aún no has buscado esto en <b>${e(texto.trim())}</b> (${e(salida)}${vuelta ? " → " + e(vuelta) : ""}, ${e(dias)} días). Pulsa «Buscar».`;
      el.innerHTML = h + `<p>${m}</p>`; return;
    }
    h += `<div><small>${e(titulo(B))} · ${B.fechas.length} fechas de ida · consultado ${hace(B.generado)} (${e(B.generado.replace("T", " "))})</small></div>`;
    (B.avisos || []).forEach(a => { h += `<div><small>· ${e(a)}</small></div>`; });
    if(!B.mejores.length){ el.innerHTML = h; return; }
    h += `<table><tr><th>Total</th><th>Fechas</th><th>Ida</th><th>Vuelta</th><th>Entrada → salida</th></tr>`;
    B.mejores.forEach(o => {
      h += `<tr><td><span class="pr">${eur(o.total)}</span></td><td>${f(o.ida)} → ${f(o.vuelta)}<br><small>${o.dias} días</small></td>`
        + `<td>${vuelo(o.t_ida)}</td><td>${vuelo(o.t_vuelta)}</td><td>${lugar(o)}</td></tr>`;
    });
    h += `</table><div style="margin-top:8px"><small><b>La más barata de cada fecha:</b> `
      + B.por_fecha.map(o => `${f(o.ida)} → ${f(o.vuelta)}: <b>${eur(o.total)}</b> (${e(o.entrada)}${o.mismo ? "" : " → " + e(o.salida)})`).join(" · ") + `</small></div>`;
    el.innerHTML = h;
  }
  el.addEventListener("input", ev => {
    const campos = {"pa-max": v => maximo = v, "pa-solo": v => solo = v, "pa-sin": v => sin = v, "pa-radio": v => radio = v};
    if(ev.target.id === "pa-pais"){ texto = ev.target.value; guarda();
      const b = document.getElementById("pa-buscar"); if(b) b.disabled = !texto.trim(); }
    else if(campos[ev.target.id]){ campos[ev.target.id](ev.target.value.trim()); guarda(); }
  });
  el.addEventListener("change", ev => {
    if(ev.target.id === "pa-mes"){ mes = ev.target.value; if(mesFin && mesFin <= mes) mesFin = ""; }
    else if(ev.target.id === "pa-mesfin") mesFin = ev.target.value;
    else if(ev.target.id === "pa-sal" || ev.target.id === "pa-vuelta"){
      if(ev.target.id === "pa-sal") salida = ev.target.value; else vuelta = ev.target.value;
      // con un solo día de salida y uno de vuelta, los días de viaje salen solos (miércoles → sábado = 4)
      const i = DIAS_SEM.indexOf(salida), j = DIAS_SEM.indexOf(vuelta);
      if(i >= 0 && j >= 0) dias = String((j - i + 7) % 7 + 1 + ((j - i + 7) % 7 === 0 ? 7 : 0));
    }
    else if(ev.target.id === "pa-rango"){ rango = ev.target.checked;
      if(rango && !desde){ const a = new Date(); a.setDate(a.getDate() + 7); const z = new Date(a); z.setDate(z.getDate() + 14);
        const iso = d => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); desde = iso(a); hasta = iso(z); } }
    else if(ev.target.id === "pa-desde"){ desde = ev.target.value; if(hasta && hasta < desde) hasta = desde; }
    else if(ev.target.id === "pa-hasta") hasta = ev.target.value;
    else if(ev.target.id === "pa-dias") dias = ev.target.value.trim() || "4";
    else if(ev.target.id === "pa-pais") texto = ev.target.value;
    if(ev.target.id === "pa-sel"){
      sel = ev.target.value || null;
      const b = sel && PAIS.busquedas[sel];
      if(b){ texto = b.pais; salida = b.salida; dias = b.dias[0] === b.dias[1] ? String(b.dias[0]) : b.dias[0] + "-" + b.dias[1];
        vuelta = b.vuelta || ""; maximo = b.maximo != null ? String(b.maximo) : ""; solo = (b.solo || []).join(", "); sin = (b.sin || []).join(", ");
        radio = b.radio != null ? String(b.radio) : "";
        if(b.periodo.includes("…")){ const [d1, d2] = b.periodo.split("…"); rango = true; desde = d1; hasta = d2; }
        else { rango = false; const ms = b.periodo.split("+"); if(proximos.includes(ms[0])){ mes = ms[0]; mesFin = ms.length > 1 && proximos.includes(ms[ms.length - 1]) ? ms[ms.length - 1] : ""; } } }
    } else sel = null;
    guarda(); pinta();
  });
  async function calcula(){
    // Primero se cuenta, sin gastar, cuánto tardará; si pasa del umbral se pide confirmación.
    espera = {msg: "Calculando cuánto tardará…"}; pinta();
    let r = {};
    try { r = await api("/api/estimar-pais", cuerpo()); }
    catch(x) { r = {error: "No consigo hablar con el servidor (¿sigue abierta su ventana negra?)."}; }
    espera = null;
    if(r.error){ pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-err">${e(r.error)}</div>`); return; }
    if(r.pide_confirmacion){ estima = r; pinta(); return; }
    corre();
  }
  async function corre(){
    estima = null; espera = {msg: "Empezando…"}; pinta();
    let r = {};
    try { r = await api("/api/pais", cuerpo()); }
    catch(x) { r = {error: "No consigo hablar con el servidor (¿sigue abierta su ventana negra?)."}; }
    if(r.error){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-err">${e(r.error)}</div>`); return; }
    let clave = null, nota = "";
    while(true){
      await new Promise(z => setTimeout(z, 2000));
      let est = null;
      try { est = await api("/api/estado"); } catch(x) {}
      const t = est && est.trabajo;
      if(t && t.estado === "corriendo"){ espera.msg = t.progreso ? t.progreso.fase : (t.mensaje || "Trabajando…"); espera.prog = t.progreso || null; pinta(); continue; }
      if(t && t.estado === "error"){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="pa-aviso"><b>⚠ La búsqueda ha fallado</b> (error técnico, no es que no haya vuelos): ${e(t.mensaje)}</div>`); return; }
      if(t && t.resultado) clave = t.resultado.clave;
      if(t && t.estado === "cancelado") nota = t.mensaje;
      break;
    }
    try { PAIS = await api("/api/pais-datos"); PAIS.nombres = NOMBRES; PAIS.codigos = CODIGOS; } catch(x) {}
    if(clave) sel = clave;
    espera = null; guarda(); pinta();
    if(nota) el.insertAdjacentHTML("afterbegin", `<div class="vlt">${e(nota)}</div>`);
  }
  el.addEventListener("click", ev => {
    const b = ev.target.closest("button"); if(!b || b.disabled) return;
    if(b.id === "pa-buscar" && texto.trim()) calcula();
    else if(b.id === "pa-si") corre();
    else if(b.id === "pa-no"){ estima = null; pinta(); }
    else if(b.id === "pa-cancelar"){ b.disabled = true; espera.msg = "Cancelando…"; api("/api/cancelar", {}).catch(() => {}); }
  });
  pinta();
})();
</script>
<script>
let EXP = __EXP__;
(function(){
  const el = document.getElementById("exp-in");
  const e = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const hace = iso => { const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
    if(isNaN(min)) return ""; if(min < 2) return "hace un momento"; if(min < 90) return "hace " + min + " min";
    if(min < 2880) return "hace " + Math.round(min / 60) + " h"; return "hace " + Math.round(min / 1440) + " días"; };
  let salida = EXP.salida || "domingo", dias = EXP.dias || "3-4", meses = String(EXP.meses || 3), espera = null;
  function pinta(){
    let h = "";
    if(EXP.hay){
      const cuando = EXP.generado ? `Última búsqueda: <b>${e(hace(EXP.generado))}</b> · salida ${e(EXP.salida)} · ${e(EXP.dias)} días · ${e(EXP.meses)} meses vista · ${e(EXP.con_vuelos)} de ${e(EXP.paises)} países con ida y vuelta.`
        : "Búsqueda anterior, sin fecha guardada (con «Calcular de nuevo» se pone al día).";
      h += `<div class="vy-nota">${cuando} Una celda por país y domingo (precio ida+vuelta); el color depende de la distancia (corto / medio / largo). Pasa el ratón por encima para ver los vuelos.</div>
        <iframe src="explorar.html?t=${Date.now()}" style="width:100%;height:520px;border:1px solid var(--line);border-radius:8px;background:#fff"></iframe>`;
    } else h += `<div class="vy-nota">Aún no hay búsqueda de países nuevos: pulsa «Calcular».</div>`;
    if(!SERV) h += `<div><small>Para calcularla de nuevo, abre esta página con <b>abrir_escapadas.bat</b>.</small></div>`;
    else if(espera) h += `<div class="vlt">⏳ ${e(espera.msg)} <small>(no cierres la ventana negra; la primera vez son unos 15-30 min)</small></div>`;
    else h += `<div class="barra" style="margin-top:8px">
      <label>Salida: <select id="ex-s"><option value="domingo" ${salida==="domingo"?"selected":""}>domingo</option><option value="viernes,sabado,domingo" ${salida!=="domingo"?"selected":""}>viernes, sábado y domingo</option></select></label>
      <label>Días de viaje: <input id="ex-d" value="${e(dias)}" size="4"></label>
      <label>Meses vista: <select id="ex-m">${[1,2,3,4,5,6].map(n => `<option ${String(n)===meses?"selected":""}>${n}</option>`).join("")}</select></label>
      <button id="ex-go">${EXP.hay ? "Calcular de nuevo (gratis)" : "Calcular (gratis)"}</button>
      <small>Gratis (Kiwi, Ryanair y Wizz). Solo domingos ≈ 15-20 min la primera vez; viernes, sábado y domingo ≈ 30 min; con la caché, segundos.</small></div>`;
    el.innerHTML = h;
  }
  async function corre(){
    espera = {msg: "Empezando…"}; pinta();
    let r = {};
    try { r = await api("/api/explorar", {salida, dias, meses}); }
    catch(x) { r = {error: "No consigo hablar con el servidor (¿sigue abierta su ventana negra?)."}; }
    if(r.error){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-err">${e(r.error)}</div>`); return; }
    while(true){
      await new Promise(z => setTimeout(z, 2000));
      let est = null;
      try { est = await api("/api/estado"); } catch(x) {}
      const t = est && est.trabajo;
      if(t && t.estado === "corriendo"){ espera.msg = t.mensaje || "Trabajando…"; pinta(); continue; }
      if(t && t.estado === "error"){ espera = null; pinta(); el.insertAdjacentHTML("afterbegin", `<div class="vy-err">${e(t.mensaje)}</div>`); return; }
      break;
    }
    try { EXP = await api("/api/explorar-datos"); EXP.hay = true; } catch(x) {}
    espera = null; pinta();
  }
  el.addEventListener("change", ev => {
    if(ev.target.id === "ex-s") salida = ev.target.value;
    else if(ev.target.id === "ex-d") dias = ev.target.value.trim() || "3-4";
    else if(ev.target.id === "ex-m") meses = ev.target.value;
  });
  el.addEventListener("click", ev => {
    const b = ev.target.closest("button"); if(!b || b.disabled) return;
    if(b.id === "ex-go") corre();
  });
  pinta();
})();
</script>
</body></html>
"""


def construir():
    """Lee los resultados y escribe escapadas.html. Devuelve los datos, o None si no hay resultados.
    No abre nada (lo usa también servidor.py, que se queda en marcha: por eso reinicia las memorias)."""
    global _INDICE, _PAQUETES
    _INDICE = None
    _PAQUETES = None
    archivos = sorted(p for p in CARPETA.glob("20??-??-??.md"))
    if not archivos:
        return None
    datos = [leer_domingo(a) for a in archivos]
    niveles = {"0": datos}
    for e in (1, 2):
        extra = [CARPETA / f"{a.stem}_dias{e}.md" for a in archivos]
        if any(x.exists() for x in extra):
            niveles[str(e)] = [leer_domingo(x, e) if x.exists() else {"dia": a.stem, "generado": "", "opciones": []}
                               for a, x in zip(archivos, extra)]
    try:
        import radar
        rad = radar.cargar()
    except Exception:
        rad = {"meses": {}, "vueltas": {}}
    try:
        import historico
        hist = historico.guardar()
    except Exception:
        hist = {"generado": "", "filas": []}
    try:
        import pais
        pa = dict(pais.cargar(), nombres=pais.nombres(), codigos=pais.codigos_por_nombre())
    except Exception:
        pa = {"busquedas": {}, "nombres": [], "codigos": {}}
    try:
        import explorar
        exp = dict(explorar.cargar(), hay=(CARPETA / "explorar.html").exists())
    except Exception:
        exp = {"hay": False}
    html = (PLANTILLA.replace("__RADAR__", json.dumps(rad, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__HIST__", json.dumps(hist, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__PAIS__", json.dumps(pa, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__EXP__", json.dumps(exp, ensure_ascii=False))
            .replace("__DATOS__", json.dumps(niveles, ensure_ascii=False))
            .replace("__TOPES__", json.dumps(semaforo.TOPES)).replace("__LIMC__", str(semaforo.LIMITE_CORTO_KM))
            .replace("__LIMM__", str(semaforo.LIMITE_MEDIO_KM)).replace("__LEYENDA__", semaforo.leyenda()))
    SALIDA.write_text(html, encoding="utf-8")
    return datos


def main():
    datos = construir()
    if datos is None:
        print("No hay resultados en", CARPETA, "- ejecuta antes escapadas.py")
        sys.exit(1)
    print(f"Hecho: {SALIDA} ({len(datos)} domingos, {sum(len(d['opciones']) for d in datos)} opciones)")
    if "--no-abrir" not in sys.argv:
        webbrowser.open(SALIDA.as_uri())


if __name__ == "__main__":
    main()
