"""paquetes.py 0.1 — Vuelos + hotel estimado de las mejores opciones de cada domingo.

Para las K opciones de vuelo más baratas de cada domingo (mismo y otro aeropuerto), mira dónde se duerme
(como plan_hoteles.py: otro aeropuerto con vuelta el martes = 1 noche en cada ciudad) y estima el hotel con
LiteAPI (liteapi.estimar: criba parecida a la de Booking del usuario). 1 llamada gratuita por ciudad y noche
distintas; usa la caché de 6 h; no gasta búsquedas de SerpApi. Escribe resultados/paquetes.json, que lee ver_resultados.py.

0.4: segunda fuente, Google Hotels por DataForSEO (dataforseo.estimar; 2 listas por ciudad y noche,
~0,004 $ en total; el crédito gratis de 1 $ da para decenas de ejecuciones). Se guarda aparte como
«google» en cada estancia, junto al estimado de LiteAPI. Si el saldo baja de RESERVA_DFS o la API
responde «sin saldo», se salta en silencio (una línea) y todo sigue con LiteAPI. `--sin-dataforseo` la apaga.

Uso:  .venv/Scripts/python.exe paquetes.py [--contar] [--sin-dataforseo] [--k 3] [AAAA-MM-DD ...]
"""
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

import dataforseo
import liteapi
import plan_hoteles
import ver_resultados as vr

VERSION = "0.4"
RESERVA_DFS = 0.01      # dólares: por debajo de esto no se llama a DataForSEO (no molesta al acabarse)
SALIDA = Path(__file__).parent / "resultados" / "paquetes.json"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    k = int(sys.argv[sys.argv.index("--k") + 1]) if "--k" in sys.argv else 3
    pedidos = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] != "--k"]
    domingos = pedidos or sorted(p.stem for p in vr.CARPETA.glob("20??-??-??.md"))
    elegidas = {}
    unicas = {}
    textos = {}
    for d in domingos:
        ops = sorted((o for o in plan_hoteles._opciones(d) if o["total_vuelos"] and o["estancias"]),
                     key=lambda o: o["total_vuelos"])[:k]
        elegidas[d] = ops
        for o in ops:
            for e in o["estancias"]:
                unicas.setdefault((e[0], e[1], e[3], e[4]), None)
                m = re.match(r"\s*([^(]+?)\s*(?:\(\w{3}\))?\s*,\s*(.+?)\s*$", e[2])
                textos[(e[0], e[1], e[3], e[4])] = f"{m.group(1)}, {m.group(2)}" if m else e[0]
    print(f"{len(domingos)} domingos · {k} mejores opciones de cada uno · {len(unicas)} búsquedas de lista "
          f"(LiteAPI, gratis; en caché no se repiten)")
    if "--contar" in sys.argv:
        return
    saldo0 = None if "--sin-dataforseo" in sys.argv else dataforseo.saldo()
    dfs_ok = saldo0 is not None and saldo0 >= RESERVA_DFS
    if "--sin-dataforseo" not in sys.argv:
        print(f"DataForSEO: saldo {saldo0:.2f} $" + ("" if dfs_ok else " → no se consulta") if saldo0 is not None
              else "DataForSEO: no se pudo leer el saldo → no se consulta")
    google = {}
    for i, (ciudad, pais, ent, sal) in enumerate(unicas, 1):
        try:
            unicas[(ciudad, pais, ent, sal)] = liteapi.estimar(ciudad, pais, ent, sal, texto=textos[(ciudad, pais, ent, sal)])
        except Exception as e:
            print(f"[{i}/{len(unicas)}] {ciudad} {ent}→{sal}: ERROR {str(e)[:80]}", flush=True)
            if "429" in str(e):
                print("LiteAPI pide calma: paro aquí.")
                break
            continue
        est = unicas[(ciudad, pais, ent, sal)]
        if dfs_ok:
            try:
                _, lista = liteapi.buscar(ciudad, pais, ent, sal)
                pts = [(float(h["lat"]), float(h["lon"])) for h in lista if h.get("lat") and h.get("lon")]
                if pts:
                    c = f"{statistics.median(p[0] for p in pts):.4f},{statistics.median(p[1] for p in pts):.4f}"
                    google[(ciudad, pais, ent, sal)] = dataforseo.estimar(c, ent, sal)
            except dataforseo.SinSaldo:
                dfs_ok = False
                print("DataForSEO: sin saldo; sigo solo con LiteAPI (no vuelvo a llamarle).", flush=True)
            except Exception as e:
                print(f"   (Google/DataForSEO {ciudad}: {str(e)[:70]})", flush=True)
        g = google.get((ciudad, pais, ent, sal))
        print(f"[{i}/{len(unicas)}] {ciudad} {ent}→{sal}: "
              + (f"≈ {est['porNoche']:.0f} €/noche ({est['candidatos']} candidatos)" if est else "sin candidatos")
              + (f" · Google ≈ {g['porNoche']:.0f} € ({g['candidatos']})" if g else ""),
              flush=True)
    saldo1 = dataforseo.saldo() if saldo0 is not None else None

    salida = {"generado": datetime.now().isoformat(timespec="minutes"), "version": VERSION, "k": k, "domingos": {},
              "dataforseo": {"saldo_antes": saldo0, "saldo_despues": saldo1,
                             "gasto": round(saldo0 - saldo1, 4) if saldo0 is not None and saldo1 is not None else None,
                             "ciudades": len(google)}}
    for d, ops in elegidas.items():
        lista = []
        for o in ops:
            ests = [unicas.get((e[0], e[1], e[3], e[4])) for e in o["estancias"]]
            ok = all(ests)
            hotel = round(sum(x["total"] for x in ests), 2) if ok else None
            lista.append({"destino": o["ida_a"], "desde": o["vuelta_desde"], "vuelos": o["total_vuelos"],
                          "hotel": hotel, "paquete": round(o["total_vuelos"] + hotel, 2) if ok else None,
                          "noches": o["noches"], "estancias": [
                              {"ciudad": e[2], "entrada": e[3], "salida": e[4], "estimado": x,
                               "google": google.get((e[0], e[1], e[3], e[4]))}
                              for e, x in zip(o["estancias"], ests)]})
        salida["domingos"][d] = lista
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nEscrito {SALIDA.name}. (LiteAPI: sin cupo; no gasta búsquedas de SerpApi)")
    for d, lista in salida["domingos"].items():
        validas = [x for x in lista if x["paquete"]]
        if validas:
            m = min(validas, key=lambda x: x["paquete"])
            print(f"  {d}: desde {m['paquete']:.0f} € ({m['destino']} · vuelos {m['vuelos']:.0f} + hotel ≈ {m['hotel']:.0f})")
        else:
            print(f"  {d}: sin estimación")


if __name__ == "__main__":
    main()
