r"""
radar.py — Radar de viajes largos con meses de antelación (Jawdrop).

Dos pasos, como lo pensó el usuario:

  1) IDA: el día más barato del mes a cada destino (Ryanair y Wizz), con los países nuevos marcados.
       radar.py --mes 2027-09 [--nuevos] [--dias 6-8] [--horas-max 4]   (tope de horas de vuelo; 0 = sin tope)
     Además enseña, si existe, la mejor pareja ida+vuelta del MISMO aeropuerto de esa duración.

  2) VUELTA: elegido un destino y un día de ida, el día más barato para volver a BCN desde ese
     aeropuerto y desde los cercanos (mismo país o vecino, 200 km por cada 24 h fuera y más en el mismo país, km por tierra y
     ferri si hay mar: geografia.py), con km. Ryanair, Wizz y Kiwi.
       radar.py --vuelta KUT --ida 2027-09-12 [--dias 6-8] [--radio 500]   (--radio fuerza un límite a mano)

Gratis (no toca SerpApi), siempre por la caché, con las pausas de cada pieza. Cada lectura de la ida
se guarda con su fecha en la tabla `lecturas` (histórico). Precios de Wizz: mínimo del día (sin
Discount Club), sin comprobar en su web.
"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import geografia
import kiwi
import paises
import semaforo
import cache
import ryanair
import vueling
import wizz

VERSION = "0.12"
HORAS_MAX = 4   # el Radar es de escapadas urbanas de fin de semana: nada de más de 4 h de vuelo (el usuario, 14-10-2026)
ORIGEN = "BCN"
RUTA = Path(__file__).resolve().parent / "resultados" / "radar.json"   # lo lee ver_resultados.py (la demo)
# Países que no están en la tabla de nombres pero a los que se puede volar (se suman a los «nuevos»)
EXTRA_PAISES = ["MR", "GH"]   # SN y CV ya están en paises.CODIGOS


def paises_nuevos_candidatos():
    """Códigos de país que el usuario no ha visitado y a los que merece la pena preguntar (sin España)."""
    return sorted((set(paises.CODIGOS.values()) | set(EXTRA_PAISES)) - paises.visitados() - {"ES"})


def cargar():
    """Lo guardado: {"meses": {AAAA-MM: {...}}, "vueltas": {"KUT|2027-09-12": {...}}}."""
    try:
        return json.loads(RUTA.read_text(encoding="utf-8"))
    except Exception:
        return {"meses": {}, "vueltas": {}}


def _escribir(datos):
    RUTA.parent.mkdir(exist_ok=True)
    RUTA.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def guardar_mes(mes, lista, avisos, dias_min, dias_max):
    """Guarda el radar de ida de un mes (lo que enseña la demo)."""
    filas = []
    for x in lista:
        m = x["mejor"]
        filas.append({
            "destino": x["destino"], "ciudad": x["ciudad"], "pais": x["pais"], "pais_nombre": x["pais_nombre"],
            "nuevo": x["nuevo"],
            "mejor": {"aerolinea": m["aerolinea"], "ida": list(m["ida"]), "orientativo": m["orientativo"]},
            "otras": sorted(({"aerolinea": o["aerolinea"], "ida": list(o["ida"]), "orientativo": o["orientativo"]}
                             for o in x["opciones"] if o is not m), key=lambda o: o["ida"][1])[:3],
            "pareja": x["pareja"]})
    datos = cargar()
    datos["meses"][mes] = {"generado": datetime.now().isoformat(timespec="minutes"),
                           "dias": [dias_min, dias_max], "lista": filas, "avisos": avisos}
    _escribir(datos)


def guardar_vuelta(destino, ida, lista, avisos, dias_min, dias_max):
    """Guarda la vuelta más barata desde `destino` y cercanos para una ida concreta."""
    filas = []
    for r in lista:
        t = r["tramo"]
        filas.append({"aeropuerto": r["aeropuerto"], "ciudad": r["ciudad"], "pais": r["pais"], "km": r["km"],
                      "ferri": bool(r.get("ferri")), "cambia_pais": r["cambia_pais"], "precio": t["precio"], "aerolinea": t["aerolinea"],
                      "salida": t["salida"], "minimo": bool(t.get("precio_minimo")),
                      "orientativo": bool(t.get("precio_orientativo")),
                      "enlace": t.get("enlace", "")})
    datos = cargar()
    datos["vueltas"][f"{destino}|{ida}"] = {"generado": datetime.now().isoformat(timespec="minutes"),
                                            "dias": [dias_min, dias_max], "lista": filas, "avisos": avisos}
    _escribir(datos)


def _dias(texto):
    a, _, b = (texto or "6-8").partition("-")
    return int(a), int(b or a)


def radar_ida(mes, dias_min=6, dias_max=8, con_wizz=True, con_vueling=True, con_kiwi=True, avisar=None,
              horas_max=HORAS_MAX):
    """Por destino, la ida más barata del mes entre Ryanair, Wizz, Vueling (bestPrices, exacto) y Kiwi
    (otras aerolíneas, precio orientativo). Devuelve (lista de dicts de más barata a más cara, avisos).
    Cada dict lleva país nuevo y, si hay, la mejor pareja ida+vuelta del mismo aeropuerto (Ryanair/Wizz)."""
    por_destino = {}
    avisos = []
    coords = {}      # aeropuerto -> {lat, lon}, para el tope de horas de vuelo
    paises_de = {}   # aeropuerto -> (ciudad, código país, nombre país) para los que no traen país

    def anotar(destino, ciudad, pais, pais_nombre, ida, aerolinea, pareja, orientativo=False):
        x = por_destino.setdefault(destino, {"destino": destino, "ciudad": ciudad, "pais": pais,
                                             "pais_nombre": pais_nombre, "opciones": []})
        x["opciones"].append({"aerolinea": aerolinea, "ida": ida, "pareja": pareja,
                              "orientativo": orientativo})

    lecturas_ryr = []
    for d, r in ryanair.radar(ORIGEN, mes, dias_min, dias_max, avisar=avisar).items():
        anotar(d, r["ciudad"], r["pais"], r["pais_nombre"], r["ida"], "Ryanair", r["pareja"])
        paises_de[d] = (r["ciudad"], r["pais"], r["pais_nombre"])
        lecturas_ryr.append({"origen": ORIGEN, "destino": d, "salida": r["ida"][0] + "T00:00",
                             "precio": r["ida"][1]})
    if lecturas_ryr:   # histórico: la misma tabla que Wizz y Vueling (una lectura por destino y día visto)
        cache.guardar_lecturas("ryanair", lecturas_ryr, date.today().isoformat())
    if con_wizz:
        try:
            for r in wizz.radar(ORIGEN, mes, None, dias_min, dias_max, avisar=avisar):
                anotar(r["destino"], r["ciudad"], r["pais"], r["pais_nombre"], r["ida"], "Wizz Air",
                       r["pareja"])
                paises_de.setdefault(r["destino"], (r["ciudad"], r["pais"], r["pais_nombre"]))
        except wizz.WizzBloqueado as e:
            avisos.append(f"Wizz Air ha cerrado la puerta ({str(e)[:80]}). Sigo sin Wizz.")
    if con_kiwi:   # Kiwi primero: sus resultados traen país y nombre de los aeropuertos que no conocemos
        try:
            tramos, av = kiwi.radar_mes(ORIGEN, paises_nuevos_candidatos(), mes, avisar=avisar)
            avisos += av
            mejor = {}
            for t in tramos:
                paises_de.setdefault(t["destino"], (t["ciudad"], t["pais"], t["pais_nombre"]))
                if t.get("coords"):
                    coords.setdefault(t["destino"], (t["coords"]["lat"], t["coords"]["lon"]))
                k = (t["destino"], t["aerolinea"])
                if k not in mejor or t["precio"] < mejor[k]["precio"]:
                    mejor[k] = t
            if mejor:   # histórico: solo los destinos de países nuevos (precio orientativo)
                cache.guardar_lecturas("kiwi", [
                    {"origen": ORIGEN, "destino": t["destino"], "salida": t["salida"][:10] + "T00:00",
                     "precio": t["precio"]} for t in mejor.values()], date.today().isoformat())
            for t in mejor.values():
                anotar(t["destino"], t["ciudad"], t["pais"], t["pais_nombre"], (t["salida"][:10], t["precio"]),
                       t["aerolinea"], None, orientativo=bool(t.get("precio_orientativo")))
        except kiwi.KiwiBloqueado as e:
            avisos.append(f"Kiwi no responde ({str(e)[:80]}). Sigo sin Kiwi.")
    if con_vueling:
        try:
            primero = date.fromisoformat(mes + "-01")
            desde = max(primero, date.today()).isoformat()
            for t in vueling.mejores_precios(ORIGEN, vueling.red_conocida(), desde, 1):
                if not t["salida"].startswith(mes):
                    continue
                ciudad, pais, pais_nombre = paises_de.get(t["destino"]) or vueling.ciudad(t["destino"])
                anotar(t["destino"], ciudad, pais, pais_nombre, (t["salida"][:10], t["precio"]), "Vueling", None)
        except vueling.VuelingBloqueado as e:
            avisos.append(f"Vueling no responde ({str(e)[:80]}). Sigo sin Vueling.")
    if horas_max:   # coordenadas de Ryanair y Wizz (las de Kiwi se anotaron arriba)
        try:
            for d, a in ryanair.aeropuertos().items():
                coords.setdefault(d, (a["lat"], a["lon"]))
        except Exception:
            pass
        try:
            for d, a in wizz.red(ORIGEN)[0].items():
                if a.get("lat") is not None:
                    coords.setdefault(d, (a["lat"], a["lon"]))
        except Exception:
            pass
    res = []
    lejos = 0
    for x in por_destino.values():
        if horas_max and x["destino"] in coords:
            h = semaforo.horas(semaforo.km_aire(*coords[x["destino"]]))
            if h is not None and h > horas_max:
                lejos += 1
                continue
        if not x["pais"] and x["destino"] in paises_de:
            x["ciudad"], x["pais"], x["pais_nombre"] = paises_de[x["destino"]]
        if x["pais"] == "ES":
            continue
        if any(o["aerolinea"] == "Vueling" and not o["orientativo"] for o in x["opciones"]):
            # el precio de Vueling de bestPrices es el exacto: el de Kiwi (estimado) sobra
            x["opciones"] = [o for o in x["opciones"] if not (o["aerolinea"] == "Vueling" and o["orientativo"])]
        x["mejor"] = min(x["opciones"], key=lambda o: (o["ida"][1], o["orientativo"]))
        parejas = [o["pareja"] for o in x["opciones"] if o["pareja"]]
        x["pareja"] = min(parejas, key=lambda p: p["total"]) if parejas else None
        x["nuevo"] = paises.es_nuevo(x["pais"]) if x["pais"] else False
        res.append(x)
    res = sorted(res, key=lambda x: x["mejor"]["ida"][1])
    if lejos:
        avisos.append(f"{lejos} destinos de más de {horas_max} h de vuelo quedan fuera del Radar (tope de escapada urbana).")
    if con_kiwi:
        avisos += completar_vueltas(res, dias_min, dias_max, avisar)
    return res, avisos


def completar_vueltas(lista, dias_min, dias_max, avisar=None, tope_ida=300):
    """A los destinos sin pareja ida+vuelta (otras aerolíneas, o ida y vuelta de aerolíneas distintas) les
    busca la vuelta más barata desde ese aeropuerto a BCN entre `dias_min` y `dias_max` días después de la
    ida más barata (Kiwi, una consulta por destino). Rellena `pareja` con las dos aerolíneas. Solo para
    idas de hasta `tope_ida` €: más allá es largo radio y no merece la pena la consulta."""
    avisos = []
    pend = [x for x in lista if not x["pareja"] and x["mejor"]["ida"][1] <= tope_ida]
    for i, x in enumerate(pend, 1):
        if avisar:
            avisar(i, len(pend), "vuelta " + x["destino"])
        m = x["mejor"]
        d0 = date.fromisoformat(m["ida"][0])
        try:
            vs = []
            # primero la duración pedida; si ese día no hay vuelo directo, margen ampliado (se ve en «días»)
            for a, b in ((dias_min, dias_max), (max(dias_min - 2, 1), dias_max + 6)):
                vs = kiwi.rango([f"Airport:{x['destino']}"], [f"Airport:{ORIGEN}"],
                                (d0 + timedelta(days=a)).isoformat(),
                                (d0 + timedelta(days=b)).isoformat(), excluir=())
                if vs:
                    break
        except kiwi.KiwiBloqueado as e:
            avisos.append(f"Kiwi (vuelta {x['destino']}): {str(e)[:60]}")
            break
        if not vs:
            continue
        v = min(vs, key=lambda t: t["precio"])
        orient = m["orientativo"] or bool(v.get("precio_orientativo"))
        x["pareja"] = {"aerolinea": m["aerolinea"] if m["aerolinea"] == v["aerolinea"]
                       else f"{m['aerolinea']} + {v['aerolinea']}",
                       "ida": m["ida"][0], "vuelta": v["salida"][:10], "precio_ida": m["ida"][1],
                       "precio_vuelta": v["precio"], "total": m["ida"][1] + v["precio"],
                       "noches": (date.fromisoformat(v["salida"][:10]) - d0).days, "orientativo": orient,
                       "auto": True}
    return avisos


def radar_vuelta(destino, dia_ida, dias_min=6, dias_max=8, radio=None, con_mar=False, avisar=None,
                 con_kiwi=True):
    """Vuelta más barata a BCN desde `destino` y desde aeropuertos cercanos, para volver entre
    `dias_min` y `dias_max` días después de `dia_ida`. Devuelve (lista, avisos)."""
    d0 = date.fromisoformat(dia_ida)
    desde = (d0 + timedelta(days=dias_min)).isoformat()
    hasta = (d0 + timedelta(days=dias_max)).isoformat()
    coords = dict(ryanair.aeropuertos())
    aeropuertos, red_wizz = wizz.red(ORIGEN)
    for k, v in aeropuertos.items():
        coords.setdefault(k, v)
    avisos = []
    desconocido = destino not in coords
    if desconocido:   # no es de Ryanair ni de Wizz (Argel, Túnez, Estambul...): sin coordenadas, solo ese aeropuerto
        ciudad, pais, _ = vueling.ciudad(destino)
        for m in cargar().get("meses", {}).values():
            for x in m.get("lista", []):
                if x["destino"] == destino:
                    ciudad, pais = x["ciudad"], x["pais"]
        coords[destino] = {"ciudad": ciudad, "pais": pais, "lat": None, "lon": None}
    c = coords[destino]
    candidatos = []
    for k, v in ([] if desconocido else coords.items()):
        if k in (ORIGEN,) or v.get("lat") is None:
            continue
        if k == destino:
            candidatos.append((k, 0, False))
            continue
        # regla general (geografia.py): 250 km por día fuera (como mucho `dias_max`), vecino, ferri si hay mar
        tr = geografia.trayecto(destino, c["pais"], k, v["pais"], wizz.distancia_km(c, v), dias_max, radio, con_mar)
        if tr is not None:
            candidatos.append((k, tr["km"], tr["ferri"]))
    if desconocido:
        candidatos = [(destino, 0, False)]
    res = []
    for i, (ap, km, ferri) in enumerate(sorted(candidatos, key=lambda x: x[1]), 1):
        if avisar:
            avisar(i, len(candidatos), ap)
        tramos = []
        try:   # Ryanair: la vuelta más barata del tramo AP -> BCN en la ventana
            p = dict(ryanair.COMUNES, departureAirportIataCode=ap, arrivalAirportIataCode=ORIGEN,
                     outboundDepartureDateFrom=desde, outboundDepartureDateTo=hasta)
            for f in ryanair._pedir(ryanair.URL_SOLO_IDA, p, True).get("fares", []):
                t = ryanair._tramo(f["outbound"], "vuelta")
                tramos.append(t)
        except Exception as e:
            if "400" not in str(e):
                avisos.append(f"Ryanair {ap}-{ORIGEN}: {str(e)[:70]}")
        if ap in red_wizz:   # Wizz: vueltas AP -> BCN (una consulta por ruta y mes)
            try:
                _, vs = wizz.horarios(ORIGEN, ap, desde, hasta, desde, hasta, aeropuertos)
                tramos += [t for t in vs if desde <= t["salida"][:10] <= hasta]
            except wizz.WizzBloqueado as e:
                avisos.append(f"Wizz Air ha cerrado la puerta ({str(e)[:60]}).")
            except Exception as e:
                avisos.append(f"Wizz Air {ap}-{ORIGEN}: {str(e)[:70]}")
        if con_kiwi:   # Kiwi: otras aerolíneas (Vueling, Turkish, Pegasus...) en la ventana
            try:
                for t in kiwi.rango([f"Airport:{ap}"], [f"Airport:{ORIGEN}"], desde, hasta):
                    tramos.append(t)
            except kiwi.KiwiBloqueado as e:
                avisos.append(f"Kiwi {ap}: {str(e)[:60]}")
                con_kiwi = False
        if ap != destino:   # el día de cada vuelta decide la distancia que da tiempo a recorrer
            tramos = [t for t in tramos if geografia.trayecto(
                destino, c["pais"], ap, coords[ap]["pais"], wizz.distancia_km(c, coords[ap]),
                (date.fromisoformat(t["salida"][:10]) - d0).days, radio, con_mar)]
        if tramos:
            t = min(tramos, key=lambda t: t["precio"])
            res.append({"aeropuerto": ap, "ciudad": coords[ap].get("ciudad", ap), "pais": coords[ap]["pais"],
                        "km": km, "ferri": ferri, "cambia_pais": coords[ap]["pais"] != c["pais"], "tramo": t})
    return sorted(res, key=lambda r: r["tramo"]["precio"]), avisos


def _fecha(f):
    d = date.fromisoformat(f[:10])
    return f"{['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'][d.weekday()]} {d.day:02d}/{d.month:02d}"


def main(argv):
    def valor(nombre, defecto=None):
        return argv[argv.index(nombre) + 1] if nombre in argv and argv.index(nombre) + 1 < len(argv) else defecto

    dmin, dmax = _dias(valor("--dias"))
    for aviso in paises.cargar()[1]:
        print("Aviso:", aviso)
    prog = lambda i, n, d: print(f"  [{i}/{n}] {d}...   ", end="\r", flush=True)
    if "--vuelta" in argv:
        destino, ida = valor("--vuelta", "").upper(), valor("--ida")
        if not destino or not ida:
            sys.exit("Uso: python radar.py --vuelta KUT --ida AAAA-MM-DD [--dias 6-8] [--radio 500]")
        lista, avisos = radar_vuelta(destino, ida, dmin, dmax, int(valor("--radio")) if valor("--radio") else None,
                                     "--con-mar" in argv, prog, "--sin-kiwi" not in argv)
        guardar_vuelta(destino, ida, lista, avisos, dmin, dmax)
        print(f"Vuelta a BCN desde {destino} y cercanos, ida el {_fecha(ida)}, volver entre {dmin} y {dmax} "
              f"días después (solo ida, el día más barato de cada aeropuerto):      ")
        for r in lista:
            t = r["tramo"]
            donde = "mismo aeropuerto" if r["km"] == 0 else (f"a ≈{r['km']} km" + (" ⛴ ferri" if r.get("ferri") else "") +
                                                              (" · OTRO PAÍS" if r["cambia_pais"] else ""))
            print(f"  {t['precio']:6.2f} €  {r['ciudad'] + ' (' + r['aeropuerto'] + ')':28s} {t['aerolinea']:9s} "
                  f"sale {_fecha(t['salida'])} {t['salida'][11:16]}  · {donde}"
                  + ("  · ≥ (precio mínimo)" if t.get("precio_minimo") else ""))
        if not lista:
            print("  Sin vuelos a BCN en esas fechas.")
        for a in avisos:
            print("  Aviso:", a)
        return
    mes = valor("--mes")
    if not mes:
        sys.exit(__doc__)
    hmax = float(valor("--horas-max", HORAS_MAX))   # 0 = sin tope
    lista, avisos = radar_ida(mes, dmin, dmax, "--sin-wizz" not in argv, "--sin-vueling" not in argv,
                              "--sin-kiwi" not in argv, prog, horas_max=hmax)
    guardar_mes(mes, lista, avisos, dmin, dmax)   # siempre completo (la demo filtra por países nuevos)
    try:   # deja la demo al día (si no está abierta no pasa nada)
        import ver_resultados
        ver_resultados.construir()
    except Exception:
        pass
    if "--nuevos" in argv:
        lista = [x for x in lista if x["nuevo"]]
    print(f"Radar de ida desde BCN, {mes} (el día más barato de cada destino"
          f"{', solo países nuevos' if '--nuevos' in argv else ''}):      ")
    for x in lista:
        m = x["mejor"]
        p = x["pareja"]
        par = (f"  · mismo aeropuerto ida y vuelta {_fecha(p['ida'])} → {_fecha(p['vuelta'])}: "
               f"{p['total']:.0f} € ({p['aerolinea']})") if p else ""
        print(f"  {m['ida'][1]:6.2f} €  {x['ciudad'] + ' (' + x['destino'] + ')':28s} {x['pais_nombre']:16s} "
              f"{m['aerolinea']:12s} {_fecha(m['ida'][0])}{' ≈' if m['orientativo'] else ''}"
              f"{'  🆕' if x['nuevo'] else ''}{par}")
    for a in avisos:
        print("Aviso:", a)


if __name__ == "__main__":
    main(sys.argv[1:])
