"""ver_hoteles.py 0.2 — Vista web de hoteles (resultados/hoteles.html).

Lee los resultados de vuelos y, para las 3 mejores opciones del domingo, pide los alojamientos a LiteAPI
(sin coste, con caché de 6 h; no gasta búsquedas de SerpApi). Enseña por destino: días, vuelos, los 3
alojamientos válidos más baratos (nota ≥ 7, sin literas ni baño compartido) y el precio cerrado
«desde» = vuelos + estancia. Si hay búsquedas antiguas de SerpApi de ese domingo, también las muestra.

Uso:  .venv\\Scripts\\python.exe ver_hoteles.py [AAAA-MM-DD]   (domingo; por defecto el primero que haya)
"""
import html
import json
import re
import sqlite3
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

import hoteles
import liteapi
import ver_resultados

VERSION = "0.2"
AQUI = Path(__file__).parent
SALIDA = AQUI / "resultados" / "hoteles.html"
ALIAS = {"krakow": "Cracovia", "warsaw": "Varsovia", "wroclaw": "Breslavia", "prague": "Praga",
         "rome": "Roma", "milan": "Milán", "turin": "Turín", "venice": "Venecia", "vienna": "Viena"}


def _norm(t):
    return hoteles._limpio(t).strip()


def _cache_hoteles():
    """({(ciudad, entrada, salida): lista}, {token: habitaciones}) leídos de la caché, sin consultar."""
    listas, fichas = {}, {}
    bd = AQUI / "cache.sqlite"
    if not bd.exists():
        return listas, fichas
    con = sqlite3.connect(f"file:{bd.as_posix()}?mode=ro", uri=True)
    try:
        for (j,) in con.execute("SELECT json FROM respuestas"):
            if "google_hotels" not in j[:3000]:
                continue
            d = json.loads(j)
            p = d.get("search_parameters") or {}
            if p.get("engine") != "google_hotels":
                continue
            if p.get("property_token"):
                fichas[p["property_token"]] = hoteles.leer_habitaciones(d)
            elif d.get("properties") is not None:
                ciudad = re.sub(r"^hoteles\s+", "", p.get("q", ""))
                listas[(ciudad, p.get("check_in_date"), p.get("check_out_date"))] = hoteles.leer_lista(d)
    finally:
        con.close()
    return listas, fichas


def _vuelos(domingo):
    """Filas de «Mismo aeropuerto» del domingo: [{destino, total, ida, vuelta, noches}]."""
    archivo = ver_resultados.CARPETA / f"{domingo}.md"
    if not archivo.exists():
        return []
    texto = archivo.read_text(encoding="utf-8")
    _, filas = ver_resultados._filas(texto, "Mismo aeropuerto")
    out = []
    for f in filas:
        vuelta = ver_resultados._limpia(f.get("Vuelta (sale → llega)", ""))
        out.append({"n": f.get("#"), "destino": ver_resultados._limpia(f.get("Destino", "")),
                    "total": ver_resultados._total(f.get("Total €", "")),
                    "ida": ver_resultados._limpia(f.get("Ida (sale → llega)", "")), "vuelta": vuelta,
                    "noches": ver_resultados._noches(vuelta)})
    return out


def _cuota():
    try:
        import vueling
        return vueling.cuota()
    except Exception:
        return None


def _e(x):
    return html.escape(str(x))


def _euros(x):
    return f"{x:.0f} €" if abs(x - round(x)) < 0.005 else f"{x:.2f} €".replace(".", ",")


def _vuelo_de(ciudad, vuelos):
    n = _norm(ALIAS.get(_norm(ciudad), ciudad))
    for v in vuelos:
        if _norm(v["destino"]).startswith(n):
            return v
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dom = args[0] if args else None
    archivos = sorted(p.stem for p in ver_resultados.CARPETA.glob("20??-??-??.md"))
    dom = dom or (archivos[0] if archivos else "2026-10-18")
    vuelos = _vuelos(dom)
    listas, fichas = _cache_hoteles()
    base = datetime.strptime(dom, "%Y-%m-%d")
    cuota = _cuota()

    bloques = []
    for (ciudad, entrada, salida), lista in sorted(listas.items()):
        if entrada != dom:
            continue
        noches_mir = (datetime.strptime(salida, "%Y-%m-%d") - datetime.strptime(entrada, "%Y-%m-%d")).days
        res = hoteles.resolver(lista, fichas)
        validos = [h for h in res if h["habitacion"]]
        v = _vuelo_de(ciudad, vuelos) if entrada == dom else None
        n_fichas = sum(1 for h in lista if h["token"] in fichas)
        cab = (f"<h3>{_e(ALIAS.get(_norm(ciudad), ciudad))}</h3>"
               f"<p class='dias'>Noche mirada: <b>{_e(entrada)} → {_e(salida)}</b> "
               f"({noches_mir} noche{'s' if noches_mir != 1 else ''}) · {len(lista)} alojamientos en la lista, "
               f"{n_fichas} fichas abiertas = {1 + n_fichas} búsquedas</p>")
        if v:
            falta = v["noches"] - noches_mir
            sale = base + timedelta(days=v["noches"])
            cab += (f"<div class='vuelos'><div><span>Vuelos del domingo (fila {_e(v['n'])} de la lista)</span>"
                    f"<b>Ida dom {base:%d-%m}:</b> {_e(v['ida'])}<br><b>Vuelta {_e(v['vuelta'])}</b> "
                    f"({sale:%d-%m})<br><b>Total vuelos: {_e(_euros(v['total']))}</b> · "
                    f"{v['noches']} noche{'s' if v['noches'] != 1 else ''} de hotel</div>")
            if validos:
                m = validos[0]["habitacion"]
                if falta == 0:
                    tot = v["total"] + m["precio"] * v["noches"]
                    cab += (f"<div class='cierre'>A partir de<b>{_e(_euros(tot))}</b>"
                            f"vuelos {_e(_euros(v['total']))} + hotel {_e(_euros(m['precio'] * v['noches']))}</div>")
                else:
                    tot = v["total"] + m["precio"] * v["noches"]
                    cab += (f"<div class='cierre estim'>≈ A partir de<b>{_e(_euros(tot))}</b>"
                            f"estimado: se miró {noches_mir} noche y harían falta {v['noches']}; "
                            f"precio de 1 noche × {v['noches']}, sin comprobar</div>")
            cab += "</div>"
        filas = []
        for h in validos[:6]:
            hab = h["habitacion"]
            clase = {"privada": "ok", "probable": "prob"}.get(hab["confianza"], "sin")
            etiqueta = {"privada": "baño privado", "probable": "probable",
                        "sin comprobar": "sin comprobar"}[hab["confianza"]]
            filas.append(f"<tr><td class='n'>{_e(_euros(hab['precio']))}</td><td>{_e(h['nombre'])}</td>"
                         f"<td>{_e(hab['nombre'])}</td><td class='n'>{_e(h['nota'])}/5 "
                         f"({_e(h['opiniones'])})</td><td><span class='et {clase}'>{etiqueta}</span></td></tr>")
        solo = [h for h in res if h["habitacion"] is None]
        pie = (f"<p class='nota'>{len(solo)} alojamientos solo tenían literas o baño compartido y se "
               f"descartaron.</p>") if solo else ""
        bloques.append("<section class='ciudad'>" + cab +
                       "<table><tr><th>Desde</th><th>Alojamiento</th><th>Habitación</th><th>Nota</th>"
                       "<th>Baño</th></tr>" + "".join(filas) + "</table>" + pie + "</section>")

    # Esquema de las tres mejores opciones del domingo
    tres = vuelos[:3]
    esquema = []
    for v in tres:
        n = v["noches"]
        cab = (f"<div class='cab'><b>{_e(v['destino'])}</b><span>vuelos {_e(_euros(v['total']))}"
               f" · {n} noche{'s' if n != 1 else ''} ({base:%d-%m} → {(base + timedelta(days=n)):%d-%m})</span></div>"
               f"<p class='nota'>Ida {_e(v['ida'])}<br>Vuelta {_e(v['vuelta'])}</p>")
        try:
            dest = liteapi.destino(v["destino"])
            props = []
            if dest:
                salida_ = (base + timedelta(days=n)).strftime("%Y-%m-%d")
                _, lista_ = liteapi.buscar(dest[0], dest[1], dom, salida_)
                props = liteapi.propuestas(lista_, n, 3)
        except Exception as ex:      # sin clave, sin red...: se deja el hueco
            props = []
            print(f"  (LiteAPI no disponible para {v['destino']}: {str(ex)[:80]})")
        if not props:
            esquema.append(f"<div class='slot'>{cab}<div class='hueco'>Sin alojamientos de LiteAPI para este "
                           f"destino (o no hay clave).</div></div>")
            continue
        tarjetas = ""
        for i, p in enumerate(props, 1):
            cerrado = v["total"] + p["total"]
            tarjetas += (f"<div class='aloj'><div class='precio'><b>{_e(_euros(cerrado))}</b>"
                         f"<span>vuelos + hotel</span></div><div><b>{_e(p['nombre'])}</b> "
                         f"· nota {_e(p['nota'])}/10 · {_e(p['estrellas'])}★<br><span class='nota'>"
                         f"{_e(p['habitacion'])} · {_e(_euros(p['total']))} ({_e(_euros(p['por_noche']))}/noche)"
                         f"{' · cancelable' if p['cancelable'] else ''}</span><br>"
                         f"<a href='{_e(liteapi.enlace_booking(p['nombre'], dest[0], dom, salida_))}' "
                         f"target='_blank' rel='noopener'>Ver en Booking</a> · "
                         f"<a href='{_e(liteapi.enlace_mapa(p['nombre'], dest[0]))}' target='_blank' "
                         f"rel='noopener'>Mapa</a></div></div>")
        esquema.append(f"<div class='slot'>{cab}"
                       f"<div class='cierre'>Desde<b>{_e(_euros(v['total'] + props[0]['total']))}</b>"
                       f"vuelos {_e(_euros(v['total']))} + hotel {_e(_euros(props[0]['total']))}</div>{tarjetas}</div>")

    ndom = max(len(archivos), 1)
    quedan = cuota[2] if cuota else None
    filas_coste = []
    for nombre, f in (("Solo listas (hostels baratos sin comprobar)", 0),
                      ("Listas + 2 fichas por ciudad (recomendado)", 2),
                      ("Listas + 3 fichas por ciudad (más seguro)", 3)):
        por_dom = 3 * (1 + f)
        filas_coste.append(f"<tr><td>{nombre}</td><td class='n'>{por_dom}</td><td class='n'>{por_dom * ndom}</td></tr>")

    pagina = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jawdrop · hoteles</title>
<style>
:root{{--fondo:#f6f7f9;--tarjeta:#fff;--texto:#1d2330;--suave:#667085;--linea:#e3e6ec;--verde:#1b7f4b;
--ambar:#a15c07;--rojo:#b42318;--azul:#175cd3}}
@media (prefers-color-scheme:dark){{:root{{--fondo:#14171d;--tarjeta:#1d222b;--texto:#eceef2;--suave:#98a2b3;
--linea:#323946;--verde:#4cc38a;--ambar:#f0b04a;--rojo:#f97066;--azul:#84adff}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--fondo);color:var(--texto);
font:16px/1.5 system-ui,Segoe UI,sans-serif;padding:16px}}
main{{max-width:980px;margin:0 auto}}h1{{font-size:1.5rem;margin:.2em 0}}h2{{font-size:1.15rem;margin:1.6em 0 .5em}}
h3{{margin:0 0 .2em}}p{{margin:.3em 0}}.suave,.nota,.dias{{color:var(--suave);font-size:.9rem}}
section,.aviso,.slot{{background:var(--tarjeta);border:1px solid var(--linea);border-radius:10px;padding:14px;margin:12px 0}}
.aviso{{border-left:4px solid var(--ambar)}}
table{{width:100%;border-collapse:collapse;font-size:.92rem;margin-top:8px}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--linea);vertical-align:top}}
th{{color:var(--suave);font-weight:600;font-size:.8rem}}td.n{{white-space:nowrap;font-variant-numeric:tabular-nums}}
.vuelos{{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0}}.vuelos>div:first-child{{flex:2 1 280px;font-size:.92rem}}
.vuelos span{{display:block;color:var(--suave);font-size:.8rem}}
.cierre{{flex:1 1 180px;border:2px solid var(--verde);border-radius:10px;padding:8px 12px;font-size:.8rem;
color:var(--suave)}}.cierre b{{display:block;font-size:1.6rem;color:var(--verde)}}
.cierre.estim{{border-style:dashed;border-color:var(--ambar)}}.cierre.estim b{{color:var(--ambar)}}
.et{{padding:1px 8px;border-radius:99px;font-size:.78rem;border:1px solid var(--linea);white-space:nowrap}}
.et.ok{{color:var(--verde);border-color:var(--verde)}}.et.prob{{color:var(--ambar);border-color:var(--ambar)}}
.et.sin{{color:var(--suave)}}
.trio{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}
.slot .cab{{display:flex;justify-content:space-between;gap:8px;margin-bottom:8px;flex-wrap:wrap}}
.slot .cab span{{color:var(--suave);font-size:.85rem}}
.hueco{{border:1px dashed var(--linea);border-radius:8px;padding:8px;margin:6px 0;color:var(--suave);font-size:.9rem}}
.aloj{{display:flex;gap:10px;border-top:1px solid var(--linea);padding:8px 0;font-size:.9rem}}
.aloj .precio{{flex:0 0 92px}}.aloj .precio b{{display:block;font-size:1.15rem;color:var(--verde)}}
a{{color:var(--azul)}}
.aloj .precio span{{color:var(--suave);font-size:.75rem}}
</style></head><body><main>
<h1>Hoteles · domingo {_e(dom)}</h1>
<p class="suave">Solo informativo. Generado {datetime.now():%d-%m-%Y %H:%M} (ver_hoteles.py {VERSION}).
Consulta LiteAPI (sin coste) solo si no tiene el dato guardado de las últimas 6 h; no gasta búsquedas de SerpApi.</p>

<h2>Las tres mejores opciones y sus tres alojamientos más baratos</h2>
<p>Días de viaje: ida <b>domingo {base:%d-%m}</b> · vuelta <b>lunes {(base + timedelta(days=1)):%d-%m}</b>
(1 noche) o <b>martes {(base + timedelta(days=2)):%d-%m}</b> (2 noches). Hoteles: 1 adulto, nota mínima 7
sobre 10, sin literas ni baño compartido. Precio cerrado = vuelos + estancia completa.</p>
<div class="trio">{"".join(esquema)}</div>
<p class="nota">Precios de LiteAPI (clave de sandbox: contrastados con Google Hotels en Turín, salen entre un 5 y
un 25 % más baratos). Pueden no incluir la tasa turística de la ciudad. «Cancelable» = cancelación gratuita.
El baño privado no viene como dato: se deduce del nombre de la habitación (descartadas literas, dormitorios
y «baño compartido»).</p>

{"<h2>Otras búsquedas guardadas (SerpApi)</h2>" + "".join(bloques) if bloques else ""}
</main></body></html>"""
    SALIDA.write_text(pagina, encoding="utf-8")
    print(f"Escrito {SALIDA}")
    if "--no-abrir" not in sys.argv:
        webbrowser.open(SALIDA.as_uri())


if __name__ == "__main__":
    main()
