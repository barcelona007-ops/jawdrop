"""plan_hoteles.py 0.1 — Calcula vuelos + hotel para TODAS las opciones de TODOS los domingos.

Lee resultados\\AAAA-MM-DD.md (mismo aeropuerto y otro aeropuerto), decide dónde se duerme y pide a LiteAPI
(gratis, sin cupo; caché de 6 h; 1 petición cada 1,5 s con espera si dice 429) los alojamientos.
Escribe resultados\\hoteles_calculo.json (datos, para la vista) y resultados\\hoteles_calculo.md (resumen).

Dónde se duerme:
  · Mismo aeropuerto: todas las noches en la ciudad de la ida.
  · Otro aeropuerto, vuelta el lunes (1 noche): esa noche en la ciudad de la ida.
  · Otro aeropuerto, vuelta el martes (2 noches): 1 noche en la ciudad de la ida y 1 en la de la vuelta
    (si son la misma ciudad, las 2 allí). El traslado entre ambas no está incluido.

Uso:  .venv\\Scripts\\python.exe plan_hoteles.py [--contar] [AAAA-MM-DD ...]
"""
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import liteapi
import ver_resultados as vr

VERSION = "0.2"
AQUI = Path(__file__).parent
SALIDA_JSON = AQUI / "resultados" / "hoteles_calculo.json"
SALIDA_MD = AQUI / "resultados" / "hoteles_calculo.md"


def _dia(base, mas):
    return (datetime.strptime(base, "%Y-%m-%d") + timedelta(days=mas)).strftime("%Y-%m-%d")


def _estancias(dom, ida_a, vuelta_desde, noches):
    """[(ciudad, pais, nombre_visible, entrada, salida)] o None si no se reconoce algún destino."""
    a = liteapi.destino(ida_a)
    if not a:
        return None
    if vuelta_desde is None or noches == 1:
        return [(a[0], a[1], vr._limpia(ida_a), dom, _dia(dom, noches))]
    b = liteapi.destino(vuelta_desde)
    if not b:
        return None
    if b[0] == a[0] and b[1] == a[1]:
        return [(a[0], a[1], vr._limpia(ida_a), dom, _dia(dom, noches))]
    return [(a[0], a[1], vr._limpia(ida_a), dom, _dia(dom, 1)),
            (b[0], b[1], vr._limpia(vuelta_desde), _dia(dom, 1), _dia(dom, noches))]


def _opciones(dom):
    texto = (vr.CARPETA / f"{dom}.md").read_text(encoding="utf-8")
    ops = []
    _, filas = vr._filas(texto, "Mismo aeropuerto")
    for f in filas:
        vuelta = vr._limpia(f.get("Vuelta (sale → llega)", ""))
        noches = vr._noches(vuelta)
        ops.append({"domingo": dom, "tipo": "mismo", "n": f.get("#"), "ida_a": vr._limpia(f["Destino"]),
                    "vuelta_desde": None, "km": None, "total_vuelos": vr._total(f["Total €"]),
                    "ida": vr._limpia(f["Ida (sale → llega)"]), "vuelta": vuelta, "noches": noches,
                    "estancias": _estancias(dom, f["Destino"], None, noches)})
    _, filas = vr._filas(texto, "Otro aeropuerto")
    for f in filas:
        vuelta = vr._limpia(f.get("Vuelta (sale → llega)", ""))
        noches = vr._noches(vuelta)
        ops.append({"domingo": dom, "tipo": "otro", "n": f.get("#"), "ida_a": vr._limpia(f["Ida a"]),
                    "vuelta_desde": vr._limpia(f["Vuelta desde"]), "km": f.get("Km"),
                    "total_vuelos": vr._total(f["Total €"]),
                    "ida": vr._limpia(f["Ida (sale → llega)"]), "vuelta": vuelta, "noches": noches,
                    "estancias": _estancias(dom, f["Ida a"], f["Vuelta desde"], noches)})
    return ops


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    contar = "--contar" in sys.argv
    pedidos = [a for a in sys.argv[1:] if not a.startswith("--")]
    domingos = pedidos or sorted(p.stem for p in vr.CARPETA.glob("20??-??-??.md"))
    todas = []
    for d in domingos:
        todas += _opciones(d)
    sin_reconocer = sorted({o["ida_a"] if not liteapi.destino(o["ida_a"]) else o["vuelta_desde"]
                            for o in todas if o["estancias"] is None})
    unicas = {}
    for o in todas:
        for e in o["estancias"] or []:
            unicas.setdefault((e[0], e[1], e[3], e[4]), 0)
    print(f"{len(domingos)} domingos · {len(todas)} opciones · {len(unicas)} consultas distintas a LiteAPI "
          f"(≈ {len(unicas) * 3 // 60 + 1} min a 1 cada 1,5 s + lo que tarde cada una)")
    if sin_reconocer:
        print("Destinos que no sé traducir (se saltan):", sin_reconocer)
    if contar:
        return
    datos = {}
    for i, (clave, _) in enumerate(unicas.items(), 1):
        ciudad, pais, entrada, salida = clave
        noches = (datetime.strptime(salida, "%Y-%m-%d") - datetime.strptime(entrada, "%Y-%m-%d")).days
        try:
            _, lista = liteapi.buscar(ciudad, pais, entrada, salida)
            props = liteapi.propuestas(lista, noches, 3)
            for p in props:
                p["booking"] = liteapi.enlace_booking(p["nombre"], ciudad, entrada, salida)
                p["mapa"] = liteapi.enlace_mapa(p["nombre"], ciudad)
            datos["|".join(clave)] = {"alojamientos_en_ciudad": len(lista), "propuestas": props}
            print(f"[{i}/{len(unicas)}] {ciudad} {entrada}→{salida}: {len(lista)} alojamientos, "
                  f"mejor {props[0]['total']:.0f} €" if props else
                  f"[{i}/{len(unicas)}] {ciudad} {entrada}→{salida}: {len(lista)} alojamientos, ninguno válido",
                  flush=True)
        except Exception as e:
            datos["|".join(clave)] = {"error": str(e)[:120], "propuestas": []}
            print(f"[{i}/{len(unicas)}] {ciudad} {entrada}→{salida}: ERROR {str(e)[:80]}", flush=True)
            if "429" in str(e):
                print("LiteAPI pide calma: paro aquí (lo hecho queda en la caché).")
                break

    # Cierre: vuelos + mejor alojamiento de cada estancia
    for o in todas:
        o["hoteles"] = []
        ok = bool(o["estancias"])
        for e in o["estancias"] or []:
            props = datos.get("|".join((e[0], e[1], e[3], e[4])), {}).get("propuestas", [])
            if not props:
                ok = False
            o["hoteles"].append({"ciudad": e[2], "entrada": e[3], "salida": e[4], "propuestas": props})
        o["total_hotel"] = round(sum(h["propuestas"][0]["total"] for h in o["hoteles"]), 2) if ok else None
        o["total_cerrado"] = round(o["total_vuelos"] + o["total_hotel"], 2) if ok and o["total_vuelos"] else None
    SALIDA_JSON.write_text(json.dumps({"generado": datetime.now().isoformat(timespec="minutes"),
                                       "version": VERSION, "opciones": todas}, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    # Resumen en castellano
    md = [f"# Vuelos + hotel — todos los domingos (plan_hoteles.py {VERSION}, "
          f"{datetime.now():%d-%m-%Y %H:%M})\n",
          "Precio cerrado = vuelos + la habitación válida más barata (nota ≥ 7/10, sin literas ni baño "
          "compartido) de cada noche. En «otro aeropuerto» con vuelta el martes: 1 noche en cada ciudad. "
          "El traslado entre ciudades no está incluido.\n"]
    for d in domingos:
        md.append(f"\n## Domingo {d}\n")
        md.append("| # | Tipo | Destino (ida → vuelta) | Noches | Vuelos € | Hotel € | **Total €** | Alojamiento(s) |")
        md.append("|---|---|---|---|---|---|---|---|")
        cerradas = sorted((o for o in todas if o["domingo"] == d and o["total_cerrado"]),
                          key=lambda o: o["total_cerrado"])
        for k, o in enumerate(cerradas[:15], 1):
            dest = o["ida_a"] if o["tipo"] == "mismo" else f"{o['ida_a']} → {o['vuelta_desde']} ({o['km']} km)"
            aloj = " · ".join(f"{h['ciudad'].split(' (')[0]}: {h['propuestas'][0]['nombre']} "
                              f"({h['propuestas'][0]['total']:.0f} €)" for h in o["hoteles"])
            md.append(f"| {k} | {'mismo' if o['tipo'] == 'mismo' else 'otro'} | {dest} | {o['noches']} | "
                      f"{o['total_vuelos']:.2f} | {o['total_hotel']:.2f} | **{o['total_cerrado']:.2f}** | {aloj} |")
        sin = sum(1 for o in todas if o["domingo"] == d and not o["total_cerrado"])
        if sin:
            md.append(f"\n_{sin} opciones sin precio cerrado (sin alojamiento válido o destino sin traducir)._")
    SALIDA_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    cerradas = sum(1 for o in todas if o["total_cerrado"])
    print(f"Hecho: {cerradas} de {len(todas)} opciones con precio cerrado → {SALIDA_MD.name}, {SALIDA_JSON.name}")


if __name__ == "__main__":
    main()
