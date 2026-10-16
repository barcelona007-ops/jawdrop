r"""
explorar.py — Ida y vuelta a TODOS los países nuevos a la vez, con semáforo (Jawdrop).

Lo que `nuevos.py` hace país por país (lento), aquí se hace de golpe: por cada fecha de ida y de vuelta,
una consulta a Kiwi por cada 10 países (en vez de una por país), más Ryanair (todos los destinos en una
llamada por día) y Wizz (por ruta). Todo gratis y por la caché; sin SerpApi.

Entrada y salida con varias vías: se entra por cualquier aeropuerto del país nuevo y se vuelve desde el
mismo país o de un país vecino, con la regla general de geografia.py: 250 km por cada día fuera, km por
tierra (≈ línea recta × 1,3) y ferri si hay mar de por medio (por ejemplo, entrar por Estambul y volver desde
Sofía). Para eso, tras la primera pasada se piden también las vueltas desde los países vecinos.

Semáforo con topes fijos según el tipo de viaje (semaforo.py): corto / medio / largo según la distancia en
avión desde BCN al aeropuerto de llegada. Lo «normal» de cada país (mediana del periodo) queda como nota
al pasar el ratón por la celda.

Saca `resultados\explorar.html` (rejilla país × domingo, en colores) y `explorar_AAAA-MM-DD.md`.

  .venv\Scripts\python.exe explorar.py                         (3 meses vista, domingo, 3-4 días)
  .venv\Scripts\python.exe explorar.py --meses-vista 2 --salida domingo,viernes --dias 3-4
"""
import argparse
import html
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median

import pais
import paises
import radar
import wizz
import geografia
import semaforo

VERSION = "0.6"
CARPETA = Path(__file__).resolve().parent / "resultados"
SIN_VUELOS = {"LI", "GI", "BY", "RU", "ES"}   # sin aeropuerto con vuelos directos desde BCN


def nuevos():
    return sorted(c for c in radar.paises_nuevos_candidatos() if c not in SIN_VUELOS)


def vecinos(codigos, coords, dias_fuera=3):
    """Países (no nuevos, sin España) con algún aeropuerto alcanzable (250 km por día fuera, vecino, ferri si
    hay mar) desde algún aeropuerto de los países nuevos."""
    entradas = [(k, v) for k, v in coords.items() if v.get("pais") in codigos and v.get("lat") is not None]
    res = set()
    for k, v in coords.items():
        c = v.get("pais")
        if not c or c in codigos or c == "ES" or v.get("lat") is None or k == "BCN":
            continue
        for ka, va in entradas:
            if geografia.trayecto(ka, va["pais"], k, c, wizz.distancia_km(va, v), dias_fuera):
                res.add(c)
                break
    return sorted(res)


def _hora(iso):
    return str(iso)[11:16]


def _tramo(t):
    return f"{t['precio']:.0f} € {t['aerolinea']} {_hora(t['salida'])}→{_hora(t['llegada'])}{pais._marca(t)}"


def _color(o, coords):
    """Semáforo con topes fijos (semaforo.py) según lo lejos que está el aeropuerto de llegada."""
    c = coords.get(o["entrada"], {})
    return semaforo.color(o["total"], semaforo.km_aire(c.get("lat"), c.get("lon")))


def _vuelta_txt(o, coords):
    if o["entrada"] == o["salida_ap"]:
        return ""
    km = pais._km(coords, o["entrada"], o["salida_ap"])
    otro = coords.get(o["salida_ap"], {}).get("pais") != coords.get(o["entrada"], {}).get("pais")
    return f" ← vuelve desde {o['salida_ap']}" + (f", ≈{km:.0f} km" if km is not None else "") + \
        (", otro país" if otro else "")


def cargar():
    """Datos de la última búsqueda (para la demo): {} si no hay."""
    try:
        return json.loads((CARPETA / "explorar.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def main(argv=None, avisar=None):
    ap = argparse.ArgumentParser(description="Ida y vuelta a todos los países nuevos, con semáforo")
    ap.add_argument("--meses-vista", type=int, default=3)
    ap.add_argument("--salida", default="domingo", help="día(s) de salida: domingo (defecto), 'viernes,sabado'...")
    ap.add_argument("--dias", default="3-4", help="duración contando ida y vuelta (3-4)")
    ap.add_argument("--top", type=int, default=15, help="cuántas ofertas enseñar en la lista corta")
    ap.add_argument("--sin-vecinos", action="store_true", help="no mirar vueltas desde otros países (vecinos)")
    a = ap.parse_args(argv)

    dmin, dmax = pais._dias(a.dias)
    hoy = date.today()
    fin = hoy + timedelta(days=30 * a.meses_vista)
    fechas = pais.fechas_de(a.salida, None, hoy.isoformat(), fin.isoformat())
    codigos = nuevos()
    vueltas = {f + timedelta(days=n - 1) for f in fechas for n in range(dmin, dmax + 1)}
    lotes = (len(codigos) + 9) // 10
    print(f"explorar.py {VERSION}: {len(codigos)} países nuevos, {len(fechas)} fechas de ida "
          f"({pais._fecha(fechas[0].isoformat())} … {pais._fecha(fechas[-1].isoformat())}), {a.dias} días. "
          f"Primera pasada: unas {(len(fechas) + len(vueltas)) * lotes} consultas a Kiwi.", flush=True)
    t0 = time.time()
    prog = avisar or (lambda i, n, d: print(f"  [{i}/{n}] {d}...        ", end="\r", flush=True))
    opciones, coords, avisos = pais.buscar(codigos, fechas, dmin, dmax, avisar=prog)
    print(" " * 60)
    extra = [] if a.sin_vecinos else vecinos(set(codigos), coords, dmax - 1)
    if extra:
        print(f"Segunda pasada: vueltas desde {len(extra)} países vecinos a distancia alcanzable "
              f"(250 km por día fuera): {', '.join(extra)}.", flush=True)
        opciones, coords, avisos = pais.buscar(codigos, fechas, dmin, dmax, avisar=prog, codigos_vuelta=extra)
        print(" " * 60)
    print(f"Búsqueda hecha en {(time.time() - t0) / 60:.1f} min; {len(opciones)} combinaciones.")

    def pais_de(t, ap_):
        return t.get("pais") or coords.get(ap_, {}).get("pais") or "?"

    # mejor combinación por país, y por país y fecha de ida
    por_pais, por_fecha = {}, {}
    for o in opciones:
        c = pais_de(o["t_ida"], o["entrada"])
        if c not in codigos:
            continue
        if c not in por_pais or o["total"] < por_pais[c]["total"]:
            por_pais[c] = o
        k = (c, o["ida"])
        if k not in por_fecha or o["total"] < por_fecha[k]["total"]:
            por_fecha[k] = o
    tipico = {}
    for c in por_pais:
        precios = [o["total"] for (cc, _), o in por_fecha.items() if cc == c]
        tipico[c] = (median(precios), len(precios))

    filas = sorted(por_pais.items(), key=lambda kv: kv[1]["total"])
    emoji = {"verde": "🟢", "ambar": "🟡", "rojo": "🔴", "gris": "⚪"}
    lineas = [f"# Todos los países nuevos: ida y vuelta ({a.meses_vista} meses vista, salida {a.salida}, "
              f"{a.dias} días)", "",
              "| | País | Mejor total | Fechas | Ida | Vuelta |", "|---|---|---|---|---|---|"]
    for c, o in filas:
        col = _color(o, coords)
        lineas.append(f"| {emoji[col]} | {pais.nombre_pais(c)} | **{o['total']:.0f} €** | {pais._fecha(o['ida'])} → "
                      f"{pais._fecha(o['vuelta'])} · {pais.noches(o['ida'], o['vuelta'])} | "
                      f"{_tramo(o['t_ida'])} ({o['entrada']}) | {_tramo(o['t_vuelta'])} "
                      f"({o['salida_ap']}{_vuelta_txt(o, coords)}) |")
    sin = [pais.nombre_pais(c) for c in codigos if c not in por_pais]
    lineas += ["", "Sin ida y vuelta directos en el periodo: " + (", ".join(sin) or "ninguno") + ".", ""]
    # lista corta: las ofertas más baratas de todas las fechas (verdes primero)
    todas = sorted(por_fecha.items(), key=lambda kv: kv[1]["total"])
    lineas += [f"## Las {a.top} ofertas más baratas (una por país y fecha)", "",
               "| | País | Total | Fechas | Cómo |", "|---|---|---|---|---|"]
    for (c, _), o in todas[:a.top]:
        col = _color(o, coords)
        lineas.append(f"| {emoji[col]} | {pais.nombre_pais(c)} | **{o['total']:.0f} €** | {pais._fecha(o['ida'])} → "
                      f"{pais._fecha(o['vuelta'])} · {pais.noches(o['ida'], o['vuelta'])} | "
                      f"ida {_tramo(o['t_ida'])} ({o['entrada']}) / vuelta {_tramo(o['t_vuelta'])} "
                      f"({o['salida_ap']}{_vuelta_txt(o, coords)}) |")
    for x in dict.fromkeys(avisos):
        lineas.append(f"- Aviso: {x}")
    texto = "\n".join(lineas)
    print("\n" + texto)
    CARPETA.mkdir(exist_ok=True)
    ruta = CARPETA / f"explorar_{hoy.isoformat()}.md"
    ruta.write_text(texto + "\n", encoding="utf-8")

    # rejilla en colores: filas = países, columnas = fechas de ida
    cols = sorted({ida for (_, ida) in por_fecha})
    celdas = []
    for c, _ in filas:
        tds = []
        for ida in cols:
            o = por_fecha.get((c, ida))
            if not o:
                tds.append('<td class="vacio">·</td>')
                continue
            col = _color(o, coords)
            tip = (f"{pais._fecha(o['ida'])} → {pais._fecha(o['vuelta'])} · {pais.noches(o['ida'], o['vuelta'])}\n"
                   f"ida {_tramo(o['t_ida'])} ({o['entrada']})\nvuelta {_tramo(o['t_vuelta'])} "
                   f"({o['salida_ap']}{_vuelta_txt(o, coords)})\n"
                   f"lo normal en {pais.nombre_pais(c)}: {tipico[c][0]:.0f} € ({tipico[c][1]} fechas)")
            tds.append(f'<td class="{col}" title="{html.escape(tip)}">{o["total"]:.0f}</td>')
        celdas.append(f"<tr><th>{html.escape(pais.nombre_pais(c))}</th>{''.join(tds)}</tr>")
    cab = "".join(f"<th>{html.escape(pais._fecha(d))}</th>" for d in cols)
    pagina = f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Países nuevos</title>
<style>
:root{{--bg:#fff;--fg:#1b1b1b;--l:#ddd;--v:#2e9e5b;--a:#e0a800;--r:#d64545;--g:#bbb}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#eee;--l:#333}}}}
body{{background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;margin:16px}}
h1{{font-size:18px}} table{{border-collapse:collapse}} th,td{{border:1px solid var(--l);padding:4px 8px;text-align:right}}
th:first-child{{text-align:left}} td{{color:#fff;font-weight:600}} .verde{{background:var(--v)}}
.ambar{{background:var(--a);color:#000}} .rojo{{background:var(--r)}} .gris{{background:var(--g);color:#000}}
.vacio{{color:var(--l);background:none;font-weight:400}} .nota{{max-width:60em;margin-top:12px}}
.tabla{{overflow-x:auto}}
</style><h1>Países nuevos: ida y vuelta ({a.dias} días, salida {html.escape(a.salida)})</h1>
<div class="tabla"><table><tr><th>País</th>{cab}</tr>{''.join(celdas)}</table></div>
<p class="nota">Cada celda es el total ida+vuelta más barato saliendo ese día. Colores según la distancia:
{html.escape(semaforo.leyenda())}. Pasa el ratón por encima para ver las fechas, los vuelos, desde qué
aeropuerto vuelves y lo normal de ese país. Vuelta desde el mismo país o de un vecino, 250 km por día fuera.
Sin vuelos directos en el periodo: {html.escape(', '.join(sin) or 'ninguno')}.</p></html>"""
    (CARPETA / "explorar.html").write_text(pagina, encoding="utf-8")
    (CARPETA / "explorar.json").write_text(json.dumps(
        {"generado": datetime.now().isoformat(timespec="seconds"), "salida": a.salida, "dias": a.dias,
         "meses": a.meses_vista, "fechas": len(fechas), "paises": len(codigos), "con_vuelos": len(por_pais)},
        ensure_ascii=False), encoding="utf-8")
    print(f"\nGuardado en {ruta.relative_to(ruta.parent.parent)} y resultados\\explorar.html")


if __name__ == "__main__":
    main()
