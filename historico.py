r"""
historico.py — Histórico de mejores ofertas (Jawdrop).

Lee la tabla `lecturas` de la caché, donde Ryanair, Wizz, Vueling y Kiwi guardan cada precio mínimo
que ven (con la fecha en que lo vieron), y dice por destino y mes de salida:
  · mínimo visto, precio típico (mediana de un valor por día visto) y última lectura;
  · «CHOLLO» si hay 3 o más días de lecturas y la última está un 20 % o más por debajo de lo típico.
Se compara siempre el MISMO mes de salida, para que mirar más o menos meses un día no falsee el típico.

Es el mismo sistema del radar (no hay dos): cada vez que se calcula un mes del radar, o `--tomar`, se
suman lecturas. No gasta SerpApi.

  historico.py                 tabla en pantalla (chollos primero)
  historico.py --destino TRN   solo ese destino
  historico.py --tomar [--meses 6] [--kiwi]   toma lecturas nuevas ahora (Ryanair, Wizz, Vueling; gratis)
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import median

import cache

VERSION = "0.1"
ORIGEN = "BCN"
FUENTES = ("ryanair", "wizz", "vueling", "kiwi")
MIN_DIAS_CHOLLO = 3
UMBRAL_CHOLLO = 0.8   # la última, a un 80 % o menos de lo típico
RUTA_SALIDA = Path(__file__).resolve().parent / "resultados" / "historico.json"


def _nombres():
    """{aeropuerto: (ciudad, país, país nuevo?)} con lo que ya sabe el radar guardado."""
    try:
        import paises
        import radar
        res = {}
        for m in radar.cargar().get("meses", {}).values():
            for x in m.get("lista", []):
                res[x["destino"]] = (x["ciudad"], x.get("pais_nombre", ""), bool(x.get("nuevo")))
        return res
    except Exception:
        return {}


def resumen(origen=ORIGEN, destino=None):
    """Lista de dicts (uno por destino y mes de salida), chollos primero y luego de más barato a más caro:
    destino, ciudad, pais, nuevo, mes, dias, minimo, tipico, ultima (precio), visto, salida, fuente,
    min_fuente, chollo, ahorro (% frente a lo típico)."""
    por_dia = {}   # (destino, mes, día visto) -> la lectura más barata de ese día entre todas las fuentes
    for fuente in FUENTES:
        for l in cache.lecturas(fuente, origen, destino):
            if not l["directo"]:
                continue
            k = (l["destino"], l["salida"][:7], l["visto"])
            if k not in por_dia or l["precio"] < por_dia[k]["precio"]:
                por_dia[k] = dict(l, fuente=fuente)
    grupos = {}
    for (d, mes, visto), l in por_dia.items():
        grupos.setdefault((d, mes), []).append(l)
    nombres = _nombres()
    res = []
    for (d, mes), ls in grupos.items():
        ls.sort(key=lambda l: l["visto"], reverse=True)   # la más reciente primero
        precios = [l["precio"] for l in ls]
        tipico = median(precios)
        ult = ls[0]
        mejor = min(ls, key=lambda l: l["precio"])
        ciudad, pais, nuevo = nombres.get(d, (d, "", False))
        res.append({
            "destino": d, "ciudad": ciudad, "pais": pais, "nuevo": nuevo, "mes": mes, "dias": len(ls),
            "minimo": mejor["precio"], "min_fuente": mejor["fuente"], "min_visto": mejor["visto"],
            "tipico": round(tipico, 2), "ultima": ult["precio"], "visto": ult["visto"],
            "salida": ult["salida"][:10], "fuente": ult["fuente"],
            "ahorro": round((1 - ult["precio"] / tipico) * 100) if tipico else 0,
            "chollo": len(ls) >= MIN_DIAS_CHOLLO and ult["precio"] <= tipico * UMBRAL_CHOLLO})
    return sorted(res, key=lambda x: (not x["chollo"], x["ultima"]))


def guardar(origen=ORIGEN):
    """Escribe resultados/historico.json (lo lee la demo al construirse)."""
    datos = {"generado": datetime.now().isoformat(timespec="minutes"), "filas": resumen(origen)}
    RUTA_SALIDA.parent.mkdir(exist_ok=True)
    RUTA_SALIDA.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return datos


def cargar():
    try:
        return json.loads(RUTA_SALIDA.read_text(encoding="utf-8"))
    except Exception:
        return {"generado": "", "filas": []}


def tomar(meses=6, con_kiwi=False, avisar=None):
    """Toma lecturas nuevas de los próximos `meses` meses con el radar (gratis; ~6-10 min por mes la
    primera vez, segundos con caché). Devuelve el nº de meses leídos."""
    import radar
    hoy = date.today()
    hechos = 0
    for i in range(meses):
        m = hoy.month - 1 + i
        mes = f"{hoy.year + m // 12}-{m % 12 + 1:02d}"
        if avisar:
            avisar(f"Leyendo precios de {mes} ({i + 1}/{meses})…")
        radar.radar_ida(mes, con_kiwi=con_kiwi, avisar=avisar)
        hechos += 1
    guardar()
    return hechos


def _tabla(filas):
    print(f"{'':2}{'Destino':26}{'Mes':8}{'Última':>9}{'Típico':>9}{'Mín.':>8}{'Días':>6}  Fuente / visto")
    for x in filas:
        marca = "🔥" if x["chollo"] else "  "
        nombre = f"{x['ciudad']} ({x['destino']})"
        print(f"{marca}{nombre[:25]:26}{x['mes']:8}{x['ultima']:>8.0f}€{x['tipico']:>8.0f}€{x['minimo']:>7.0f}€"
              f"{x['dias']:>6}  {x['fuente']} {x['visto']}"
              + (f"  ({x['ahorro']} % bajo lo típico)" if x["chollo"] else ""))


def main(argv):
    def valor(n, defecto=None):
        return argv[argv.index(n) + 1] if n in argv and argv.index(n) + 1 < len(argv) else defecto
    if "--tomar" in argv:
        n = tomar(int(valor("--meses", 6)), "--kiwi" in argv, avisar=print)
        print(f"Hecho: {n} meses leídos.")
    filas = guardar()["filas"]
    if valor("--destino"):
        filas = [x for x in filas if x["destino"] == valor("--destino").upper()]
    if not filas:
        print("Aún no hay lecturas. Calcula un mes del radar o usa --tomar.")
        return
    _tabla(filas[:60])
    dias = max(x["dias"] for x in filas)
    print(f"\n{len(filas)} destinos/mes. Máximo de días con lecturas: {dias}"
          + ("" if dias >= MIN_DIAS_CHOLLO else f" (hacen falta {MIN_DIAS_CHOLLO} para marcar chollos)."))


if __name__ == "__main__":
    main(sys.argv[1:])
