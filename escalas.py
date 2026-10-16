"""
escalas.py — Viajes largos con escala (1 escala), piloto con Tailandia (el usuario, 15-10-2026).

Reglas acordadas con el usuario:
  - De momento hasta 1 escala. Vale billete único o billetes sueltos encadenados, y open-jaw total. Si el itinerario mezcla
    aerolíneas se marca «posibles billetes sueltos» (riesgo: si el primer vuelo se retrasa, el segundo se pierde).
  - Tres tipos de escala según su duración (hora local del aeropuerto de escala):
      conexión          menos de 6 h
      escala larga      de 6 a 8 h (ni una cosa ni otra)
      stopover          8 h o más con al menos HORAS_DIA_MIN horas entre las 07:00 y las 22:00 (de día: da para ver la ciudad)
      noche en aeropuerto  8 h o más pero casi todo de noche (menos de HORAS_DIA_MIN h de día): una «putada», no cuenta como visita
    PROPUESTAS de Claude pendientes de confirmar: el corte de 6 h, las 5 h de día mínimas y el horario 07:00-22:00.
  - Un país cuenta como visitado solo si se sale a la ciudad. El programa NO puede saberlo: si el stopover es en un país que
    El usuario no ha pisado, lo marca «posible país nuevo (si sales a la ciudad)». Pisar solo el aeropuerto no cuenta.
Precios: los de Kiwi, solo ida, orientativos (sin comisión descontada, en la aerolínea serán iguales o algo menores).

Uso:  .venv\\Scripts\\python.exe escalas.py TH --mes 2027-02 [--vuelta-mes 2027-03] [--paradas 1]
"""
import sys
from datetime import date, timedelta

import kiwi
import paises

VERSION = "0.7"
HORAS_CONEXION_MAX = 6
HORAS_STOPOVER_MIN = 8
HORAS_DIA_MIN = 5
DIA_DESDE, DIA_HASTA = 7, 22   # «de día» en el aeropuerto de escala

# Aeropuertos de escala habituales entre Europa y el sudeste asiático (para ordenar y nombrar; no limitan nada: se ven todos los que salen)
HUBS = {"IST": "Estambul", "SAW": "Estambul-Sabiha", "DOH": "Doha", "DXB": "Dubái", "AUH": "Abu Dabi", "MCT": "Mascate", "BAH": "Baréin",
        "KWI": "Kuwait", "JED": "Yeda", "RUH": "Riad", "AMM": "Amán", "TLV": "Tel Aviv", "CAI": "El Cairo", "ADD": "Adís Abeba",
        "DEL": "Delhi", "BOM": "Bombay", "CMB": "Colombo", "PEK": "Pekín", "PKX": "Pekín-Daxing", "PVG": "Shanghái", "CAN": "Cantón",
        "CTU": "Chengdu", "KMG": "Kunming", "HKG": "Hong Kong", "TPE": "Taipéi", "ICN": "Seúl", "NRT": "Tokio-Narita", "HND": "Tokio-Haneda",
        "BKK": "Bangkok", "DMK": "Bangkok-Don Mueang", "KUL": "Kuala Lumpur", "SIN": "Singapur", "SGN": "Ho Chi Minh", "HAN": "Hanói",
        "MNL": "Manila", "CGK": "Yakarta", "DPS": "Bali", "FRA": "Fráncfort", "MUC": "Múnich", "AMS": "Ámsterdam", "CDG": "París", "LHR": "Londres",
        "ZRH": "Zúrich", "VIE": "Viena", "HEL": "Helsinki", "WAW": "Varsovia", "SVO": "Moscú", "TAS": "Taskent", "ALA": "Almatý"}


def horas_de_dia(llega, sale):
    """Horas de la escala (hora local, 'AAAA-MM-DDTHH:MM') que caen entre DIA_DESDE y DIA_HASTA."""
    from datetime import datetime
    a, b = datetime.fromisoformat(llega), datetime.fromisoformat(sale)
    total, t = 0.0, a
    while t < b:
        paso = min(b, t + timedelta(minutes=15))
        if DIA_DESDE <= t.hour < DIA_HASTA:
            total += (paso - t).total_seconds() / 3600
        t = paso
    return round(total, 1)


def clasificar(esc):
    """Una escala de kiwi.escalas() -> {tipo, dia_h, pais_nuevo}."""
    h = esc["horas"]
    dia = horas_de_dia(esc["llega_local"], esc["sale_local"])
    if h < HORAS_CONEXION_MAX:
        tipo = "conexión"
    elif h < HORAS_STOPOVER_MIN:
        tipo = "escala larga"
    elif dia >= HORAS_DIA_MIN:
        tipo = "stopover"
    else:
        tipo = "noche en aeropuerto"
    nuevo = tipo == "stopover" and bool(esc["pais"]) and paises.es_nuevo(esc["pais"])
    return {"tipo": tipo, "dia_h": dia, "pais_nuevo": nuevo}


def buscar(origen, destino_pais, desde, hasta, paradas=1, sentido="ida", limite=200):
    """`destino_pais`: un código de país o una lista (['TH', 'MY', 'SG']: Kiwi los busca a la vez)."""
    paises_ids = [f"Country:{p}" for p in ([destino_pais] if isinstance(destino_pais, str) else destino_pais)]
    o, d = ([f"Airport:{origen}"], paises_ids) if sentido == "ida" else (paises_ids, [f"Airport:{origen}"])
    # Kiwi devuelve como mucho 50 por consulta y casi todos por el mismo aeropuerto: se pide por tramos de 5 días para ver más escalas distintas
    res, vistos, dia, fin = [], set(), date.fromisoformat(desde), date.fromisoformat(hasta)
    while dia <= fin:
        tope = min(dia + timedelta(days=4), fin)
        for it in kiwi.escalas(o, d, dia.isoformat(), tope.isoformat(), paradas, limite):
            k = (it["precio_kiwi"], tuple((t["desde"], t["sale_local"]) for t in it["tramos"]))
            if k not in vistos:
                vistos.add(k)
                res.append(it)
        dia = tope + timedelta(days=1)
    res.sort(key=lambda x: x["precio_kiwi"])
    for it in res:
        for e in it["escalas"]:
            e.update(clasificar(e))
    return res


def _linea(it):
    t = it["tramos"]
    via = " · ".join(f"{e['aeropuerto']} {HUBS.get(e['aeropuerto'], e['ciudad'])} {e['horas']:g} h {e['tipo']}" + (" 🆕" if e["pais_nuevo"] else "")
                     for e in it["escalas"]) or "directo"
    via = "vía " + via if it["escalas"] else via
    if len(it["aerolineas"]) > 1:
        via += " ⚠ posibles billetes sueltos"
    return (f"{it['precio_kiwi']:>5.0f} €  {t[0]['sale_local'][5:16].replace('T', ' ')} → {t[-1]['hasta']} {it['ciudad']:<14} "
            f"{it['horas_total']:>5.1f} h  {' + '.join(it['aerolineas'])[:34]:<34} {via}")


def openjaw(paises, mes, noches=(25, 35), paradas=2, origen="BCN"):
    """Ida a cualquiera de `paises` (códigos) con la ida en `mes` y vuelta desde cualquiera de ellos, `noches` más tarde.
    Devuelve (combinaciones de más barata a más cara, idas, vueltas). Cada combinación: ida, vuelta, total, noches, mismo_aeropuerto."""
    p = date.fromisoformat(mes + "-01")
    fin_mes = date(p.year + p.month // 12, p.month % 12 + 1, 1) - timedelta(days=1)
    d1 = max(p, date.today())
    idas = buscar(origen, paises, d1.isoformat(), fin_mes.isoformat(), paradas, "ida")
    vueltas = buscar(origen, paises, (d1 + timedelta(days=noches[0])).isoformat(), (fin_mes + timedelta(days=noches[1])).isoformat(), paradas, "vuelta")
    combos = []
    for i in idas[:150]:
        di = date.fromisoformat(i["salida"])
        for v in vueltas:
            n = (date.fromisoformat(v["salida"]) - di).days
            if noches[0] <= n <= noches[1]:
                combos.append({"ida": i, "vuelta": v, "total": i["precio_kiwi"] + v["precio_kiwi"], "noches": n,
                               "mismo_aeropuerto": i["destino"] == v["tramos"][0]["desde"]})
    combos.sort(key=lambda c: c["total"])
    return combos, idas, vueltas


def con_tramo_interno(combos, max_pares=20, avisar=print):
    """Open-jaw de verdad: si la ida llega a X y la vuelta sale de Y, hay que ir de X a Y. Para las `max_pares` parejas de aeropuertos
    más baratas, busca el vuelo DIRECTO X→Y más barato entre dos días después de llegar y el día antes de la vuelta, y lo suma al total.
    Sin vuelo directo: `interno` = None y la combinación queda fuera del orden (el traslado lo buscaría él, por tierra u otra ruta).
    Una consulta por pareja. Devuelve las combinaciones (también las de mismo aeropuerto, sin tramo) ordenadas por `total_real`."""
    mejores = {}
    for c in combos:
        mejores.setdefault((c["ida"]["destino"], c["vuelta"]["tramos"][0]["desde"]), c)
    res = []
    for k, (par, c) in enumerate(list(mejores.items())[:max_pares], 1):
        a, b = par
        c = dict(c, interno=None)
        if a == b:
            c["interno"] = {"precio": 0.0, "mismo": True}
        else:
            di = date.fromisoformat(c["ida"]["salida"]) + timedelta(days=2)
            dv = date.fromisoformat(c["vuelta"]["salida"]) - timedelta(days=1)
            if di <= dv:
                avisar(f"  tramo interno {k}/{min(len(mejores), max_pares)}: {a} → {b}")
                try:
                    vs = kiwi.rango([f"Airport:{a}"], [f"Airport:{b}"], di.isoformat(), dv.isoformat(), excluir=(), limite=10)
                except kiwi.KiwiBloqueado:
                    vs = []
                if vs:
                    v = vs[0]
                    c["interno"] = {"precio": v["precio"], "fecha": v["salida"][:10], "aerolinea": v["aerolinea"],
                                    "orientativo": bool(v.get("precio_orientativo"))}
        c["total_real"] = c["total"] + c["interno"]["precio"] if c["interno"] else None
        res.append(c)
    res.sort(key=lambda c: c["total"])   # el precio que cuenta es el de los dos vuelos desde/hasta BCN; el interno es un extra (ver abajo)
    return res


def _resumen_combo(c):
    i, v = c["ida"], c["vuelta"]
    return (f"{c['total']:>5.0f} € · {c['noches']} noches · ida {i['salida'][5:]} {i['destino']} ({i['precio_kiwi']:.0f} €, {i['horas_total']:g} h) · "
            f"vuelta {v['salida'][5:]} desde {v['tramos'][0]['desde']} ({v['precio_kiwi']:.0f} €, {v['horas_total']:g} h)"
            + (" · mismo aeropuerto" if c["mismo_aeropuerto"] else " · OPEN-JAW"))


def main(argv):
    if argv and argv[0] == "--openjaw":
        paises_oj = argv[1].upper().split(",")
        mes = argv[argv.index("--mes") + 1]
        paradas = int(argv[argv.index("--paradas") + 1]) if "--paradas" in argv else 2
        n = argv[argv.index("--noches") + 1] if "--noches" in argv else "25-35"
        a, _, b = n.partition("-")
        combos, idas, vueltas = openjaw(paises_oj, mes, (int(a), int(b or a)), paradas)
        print(f"\nOPEN-JAW {'+'.join(paises_oj)} · ida en {mes} · {n} noches · hasta {paradas} escalas · {len(idas)} idas, {len(vueltas)} vueltas, {len(combos)} combinaciones")
        mejores = {}   # la más barata de cada pareja de aeropuertos (ida a X, vuelta desde Y)
        for c in combos:
            mejores.setdefault((c["ida"]["destino"], c["vuelta"]["tramos"][0]["desde"]), c)
        print(f"  {len(mejores)} parejas de aeropuertos distintas (sin contar el tramo entre ellas); las 8 más baratas:")
        for c in list(mejores.values())[:8]:
            print("  " + _resumen_combo(c))
        if "--sin-interno" not in argv:
            print("\n  PRECIO DEL VIAJE = los dos vuelos desde/hasta BCN (regla del usuario: viajar entre países del sudeste es parte del viaje, no cuesta «de más»).\n"
                  "  Solo si el destino fuese UN sitio concreto (p. ej. solo Hanói), hay que añadir el vuelo interno, que se enseña aparte:")
            for c in con_tramo_interno(combos)[:10]:
                i = c["interno"]
                extra = ("mismo aeropuerto" if i and i.get("mismo") else f"si solo quieres ver {c['vuelta']['tramos'][0]['desde']}: +{i['precio']:.0f} € ({i['aerolinea']} {i['fecha'][5:]}) = {c['total_real']:.0f} €" if i else "sin vuelo directo entre ambos")
                print(f"    {c['total']:>5.0f} € · {c['noches']} n · {c['ida']['destino']} → {c['vuelta']['tramos'][0]['desde']} · ida {c['ida']['precio_kiwi']:.0f} + vuelta {c['vuelta']['precio_kiwi']:.0f} · {extra}")
            print("      ida:    " + _linea(c["ida"]))
            print("      vuelta: " + _linea(c["vuelta"]))
        mismo = [c for c in combos if c["mismo_aeropuerto"]]
        if mismo:
            print("  Mejor con el MISMO aeropuerto de ida y vuelta:\n  " + _resumen_combo(mismo[0]))
        scoot = [it for it in idas + vueltas if any(t["sigla"] == "TR" for t in it["tramos"])]
        print(f"  Con Scoot (TR): {len(scoot)} itinerarios" + (f"; el más barato: {_linea(min(scoot, key=lambda x: x['precio_kiwi']))}" if scoot else ""))
        return 0
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 1
    pais = argv[0].upper()
    mes = argv[argv.index("--mes") + 1] if "--mes" in argv else None
    vmes = argv[argv.index("--vuelta-mes") + 1] if "--vuelta-mes" in argv else None
    paradas = int(argv[argv.index("--paradas") + 1]) if "--paradas" in argv else 1
    if not mes:
        print(__doc__)
        return 1
    def rango(m):
        p = date.fromisoformat(m + "-01")
        u = date(p.year + p.month // 12, p.month % 12 + 1, 1) - timedelta(days=1)
        return max(p, date.today()).isoformat(), u.isoformat()
    for sentido, m in (("ida", mes), ("vuelta", vmes)):
        if not m:
            continue
        d, h = rango(m)
        lista = buscar("BCN", pais, d, h, paradas, sentido)
        print(f"\n{sentido.upper()} {'BCN → ' + pais if sentido == 'ida' else pais + ' → BCN'} · salida en {m} · hasta {paradas} escala · {len(lista)} itinerarios")
        vistos = {}
        for it in lista:   # el más barato por aeropuerto de escala
            e = it["escalas"][0]["aeropuerto"] if it["escalas"] else "directo"
            vistos.setdefault(e, it)
        for it in sorted(vistos.values(), key=lambda x: x["precio_kiwi"]):
            print("  " + _linea(it))
        st = [it for it in lista if any(e["tipo"] == "stopover" for e in it["escalas"])]
        if st:
            print("  — con stopover:")
            for it in st[:5]:
                print("    " + _linea(it))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
