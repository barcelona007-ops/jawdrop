"""
escapadas.py — Jawdrop, fase 4: Ryanair + Wizz Air, un domingo o todos los de un mes.

Qué hace:
  Para un domingo (o todos los de un mes), busca escapadas desde Barcelona (BCN):
    - Ida:    domingo, salida de BCN entre 06:00 y 10:00.
    - Vuelta: lunes con salida a partir de las 20:00 (hora local del destino), o
              martes con llegada a BCN como muy tarde a las 14:30.
  Ida y vuelta son dos billetes de solo ida independientes: se puede ir con una aerolínea y volver
  con otra. Precio = tarifa básica (solo bolso de mano), 1 adulto.
  La vuelta puede salir del mismo aeropuerto o de otro: hasta 250 km por cada día fuera (domingo→lunes 250,
  domingo→martes 500, +250 por día libre extra), km por tierra (≈ línea recta × 1,3), del mismo país o de un
  país vecino, y con ferri (⛴) si hay que cruzar el mar. El traslado no se incluye.
  Por defecto se descartan las vueltas que obligan a cruzar el mar (geografia.py).
  De cada destino se queda con la combinación más barata y lo ordena por precio total, en dos listas:
  «mismo aeropuerto» y «otro aeropuerto» (esta solo si no hay vuelta desde el mismo o si sale más barata).

Pasos:
  1. Idas válidas: Ryanair (1 consulta por domingo) y Wizz Air (1 consulta por ruta que trae idas y
     vueltas; en el modo mes cubre el mes entero y se reaprovecha para todos los domingos).
  2. Vueltas de Ryanair desde todos sus aeropuertos con ruta a BCN (2 consultas, más alguna para afinar
     la llegada del martes solo en los aeropuertos que interesan). Las de Wizz ya vienen del paso 1.
  3. Cruza, suma, filtra por horario, distancia, modo España y precio máximo, y ordena.
     Distancias con las coordenadas que dan las propias aerolíneas (lista de aeropuertos de Ryanair y
     mapa de Wizz), sin descargar nada más.

Reglas:
  - Pocas consultas y despacio (pausas de 3-4 s); todo pasa por la caché local (cache.sqlite).
  - Si Wizz Air bloquea, sigue solo con Ryanair y lo avisa.
  - Guarda el resultado en resultados\\<domingo>.md (y resultados\\<AAAA-MM>.md en el modo mes, con un
    resumen por domingo) con enlaces a la web de cada aerolínea.
  - Marcas: «≥» = precio mínimo del día en Wizz (el de esa hora puede ser mayor);
            «≈» = hora de llegada calculada (Wizz no la da).

Uso:
  .venv\\Scripts\\python.exe escapadas.py                 (el próximo domingo)
  .venv\\Scripts\\python.exe escapadas.py 2026-10-18      (un domingo concreto)
  .venv\\Scripts\\python.exe escapadas.py --mes 2026-11   (todos los domingos de noviembre: un archivo
                                                          por domingo y uno del mes con el resumen)
  .venv\\Scripts\\python.exe escapadas.py --con-mar       (mostrar también vueltas cruzando el mar)
  .venv\\Scripts\\python.exe escapadas.py --max 80       (solo hasta 80 € ida y vuelta)
  .venv\\Scripts\\python.exe escapadas.py --espana        (modo España: incluye vuelos nacionales;
                                                          por defecto está apagado)
  .venv\\Scripts\\python.exe escapadas.py --radio 300     (límite a mano en km en línea recta, en vez de 250 km por día;
                                                          --radio 0 = solo el mismo aeropuerto)
  .venv\\Scripts\\python.exe escapadas.py --nuevos         (solo destinos en países que aún no conoces,
                                                          según paises_visitados.txt)
  .venv\\Scripts\\python.exe escapadas.py --sin-wizz      (solo Ryanair)
  .venv\\Scripts\\python.exe escapadas.py --sin-cache     (fuerza preguntar de nuevo)
"""
import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import geografia
import semaforo
import confirmar
import kiwi
import paises
import ryanair
import verificar_wizz
import vueling
import wizz

VERSION = "6.3"
CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
ORIGEN = "BCN"

# Horario de la escapada
IDA_DESDE, IDA_HASTA = "06:00", "10:00"
VUELTA_LUNES_DESDE = "20:00"
LLEGADA_MARTES_MAX = "14:30"

EXTRA = 0  # días libres extra (lo fija main)
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def _mejor(tramos):
    """El más barato; a igual precio, mejor uno con precio exacto que uno «mínimo»."""
    return min(tramos, key=lambda t: (t["precio"], t["precio_minimo"])) if tramos else None


def _repetido(lista, t):
    return any(x["aerolinea"] == t["aerolinea"] and x["salida"] == t["salida"] for x in lista)


def _meter_kiwi(lista, t):
    """Añade un vuelo de Kiwi. Si ya está el mismo vuelo con precio GUARDADO de una búsqueda vieja (lleva
    «visto»), el de Kiwi lo sustituye (es de ahora). True si ha entrado o sustituido algo."""
    for i, x in enumerate(lista):
        if x["aerolinea"] == t["aerolinea"] and x["salida"] == t["salida"]:
            if x.get("visto"):
                lista[i] = t
                return True
            return False
    lista.append(t)
    return True


def _ida_valida(t, domingo):
    return t["salida"][:10] == domingo and IDA_DESDE <= t["salida"][11:16] <= IDA_HASTA


def _ventanas(domingo, extra):
    """Días válidos de vuelta: [(día de salida por la noche, día de llegada por la mañana, días libres)].
    Sin extra: lunes noche / martes mañana. Cada día extra desplaza las dos opciones un día."""
    d = date.fromisoformat(domingo)
    return [((d + timedelta(days=1 + k)).isoformat(), (d + timedelta(days=2 + k)).isoformat(), k)
            for k in range(extra + 1)]


def _tipo_vuelta(t, ventanas):
    """('martes noche', 1) — tipo de vuelta y días libres que hay que pedir — o (None, None)."""
    dia = t["salida"][:10]
    for noche, manana, k in ventanas:
        nombre = DIAS[date.fromisoformat(dia).weekday()]
        if dia == noche and t["salida"][11:16] >= VUELTA_LUNES_DESDE:
            return f"{nombre} noche", k
        if dia == manana and t["llegada"] and t["llegada"] <= f"{manana}T{LLEGADA_MARTES_MAX}":
            return f"{nombre} mañana", k
    return None, None


def _slug(texto):
    """'Venice Treviso' -> 'venice-treviso' (para las direcciones web)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return "-".join("".join(c if c.isalnum() else " " for c in t).split())


def _traslado(x, y, km, nombres, coords):
    """Tiempo aproximado por carretera y enlaces a 12Go y Rome2Rio para ir de la ciudad x al aeropuerto y.

    `km` ya son km por carretera aproximados (línea recta × 1,3, geografia.py); tiempo ≈ km a 75 km/h de media.
    """
    def nombre(iata):
        if iata in nombres:
            return nombres[iata]
        n = coords.get(iata, {}).get("nombre_en") or coords.get(iata, {}).get("ciudad", iata)
        return n, n
    ciudad_x, _ = nombre(x)
    ciudad_y, aeropuerto_y = nombre(y)
    horas = km / 75
    texto = f"≈{max(1, round(horas * 2)) / 2:g} h".replace(".", ",")
    misma_ciudad = _slug(ciudad_x) == _slug(ciudad_y)
    return {
        "traslado_h": horas,
        "traslado_texto": texto,
        # 12Go va de ciudad a ciudad: entre aeropuertos de la misma ciudad no aporta
        "enlace_12go": None if misma_ciudad else
        f"https://12go.asia/en/travel/{_slug(ciudad_x)}/{_slug(ciudad_y)}",
        "enlace_rome2rio": f"https://www.rome2rio.com/map/{_slug(ciudad_x)}/{_slug(aeropuerto_y + ' airport')}",
    }


def buscar(domingo, radio=None, usar_cache=True, con_wizz=True, avisos=None, con_mar=False, periodo_wizz=None,
           extra=0, con_vueling=False, espana=False, verificar_wizz_n=0, candidata=None,
           con_kiwi=False):
    """Devuelve (mismo, otro): escapadas con vuelta desde el mismo aeropuerto y desde otro cercano.

    periodo_wizz = (primer domingo, último domingo) cuando se analiza un mes: la consulta de Wizz de
    cada ruta cubre todo el mes y se reaprovecha (caché) para cada domingo.
    radio = None: regla de 250 km por día fuera (geografia.py); un número fuerza ese límite en km.
    con_mar = False descarta volver desde otro aeropuerto si hay que cruzar el mar sin ferri conocido.
    extra = días libres que se pueden pedir (0, 1 o 2): la vuelta puede ser hasta `extra` días más tarde.
    con_vueling = añade Vueling vía SerpApi (gasta búsquedas; las limita vueling.TOPE).
    espana = incluir destinos de España en la ida de Vueling.
    con_kiwi = añade Kiwi.com (gratis): las aerolíneas que no se leen directo (Turkish, Pegasus, Vueling...),
    con precio orientativo. Una consulta de ida y una por día de vuelta.
    verificar_wizz_n = comprueba en Kiwi (gratis, desde la 6.1; antes SerpApi) los tramos de Wizz de las
    N mejores opciones de cada lista; 0 = no.
    """
    avisos = avisos if avisos is not None else []
    d = date.fromisoformat(domingo)
    ventanas = _ventanas(domingo, extra)
    primer, ultimo = periodo_wizz or (domingo, domingo)
    wizz_fechas = (primer, ultimo, (date.fromisoformat(primer) + timedelta(days=1)).isoformat(),
                   (date.fromisoformat(ultimo) + timedelta(days=2 + extra)).isoformat())
    idas, vueltas = {}, {}  # aeropuerto -> lista de tramos

    # Aeropuertos (país y coordenadas) para medir distancias
    try:
        coords = ryanair.aeropuertos(usar_cache)
    except Exception as e:
        coords = {}
        avisos.append(f"No se pudo leer la lista de aeropuertos de Ryanair ({str(e)[:80]}).")

    try:
        nombres = ryanair.nombres_en(usar_cache)  # para los enlaces de traslados
    except Exception:
        nombres = {}

    # 1) Ryanair: idas
    for t in ryanair.idas(ORIGEN, domingo, IDA_DESDE, IDA_HASTA, usar_cache):
        idas.setdefault(t["destino"], []).append(t)

    # 1b) Wizz Air: idas y vueltas de cada ruta
    if con_wizz:
        try:
            aeropuertos, destinos = wizz.red(ORIGEN, usar_cache)
            for k, v in aeropuertos.items():
                coords.setdefault(k, v)
            for dest in destinos:
                try:
                    wi, wv = wizz.horarios(ORIGEN, dest, *wizz_fechas, aeropuertos, usar_cache)
                except wizz.WizzBloqueado:
                    raise
                except Exception as e:
                    avisos.append(f"Wizz Air {ORIGEN}-{dest}: sin respuesta ({str(e)[:80]}).")
                    continue
                # se guarda por el aeropuerto que da Wizz (a veces no es el pedido: BBU → OTP)
                for t in wi:
                    if _ida_valida(t, domingo) and not _repetido(idas.get(t["destino"], []), t):
                        idas.setdefault(t["destino"], []).append(t)
                for t in wv:
                    if not _repetido(vueltas.get(t["destino"], []), t):
                        vueltas.setdefault(t["destino"], []).append(t)
        except wizz.WizzBloqueado as e:
            avisos.append(f"Wizz Air ha bloqueado las consultas ({str(e)[:80]}). Resultado solo con Ryanair.")

    def km(a, b):
        return wizz.distancia_km(coords[a], coords[b]) if a in coords and b in coords else None

    def _tray(x, y, dias_fuera):
        """Trayecto por tierra (o ferri) de x a y, o None si no vale (geografia.py)."""
        if y in (x, ORIGEN) or x not in coords or y not in coords:
            return None
        return geografia.trayecto(x, coords[x]["pais"], y, coords[y]["pais"], km(x, y), dias_fuera,
                                  radio, con_mar)

    def cerca_de(x, y):
        """¿Puede interesar volver desde y habiendo ido a x? (con la vuelta más tardía posible)"""
        return _tray(x, y, 2 + extra) is not None

    # 1c) Vueling (SerpApi): idas a todos los aeropuertos conocidos; sin ellas no se sabría qué vueltas afinar
    vueling_ok, vy_completo = False, False
    vy_vistos = []   # todo lo que Vueling devuelve en esta ejecución (se guarda con su fecha al final)
    if con_vueling:
        try:
            # solo aeropuertos con coordenadas conocidas (hacen falta para distancias y país)
            destinos_vy = [k for k in vueling.red_conocida(usar_cache) if k in coords and k != ORIGEN
                           and (espana or coords[k].get("pais") != "ES")]
            for t in vueling.idas(ORIGEN, destinos_vy, domingo, coords, usar_cache):
                vy_vistos.append(t)
                if _ida_valida(t, domingo) and not _repetido(idas.get(t["destino"], []), t):
                    idas.setdefault(t["destino"], []).append(t)
            vueling_ok = True
        except vueling.SinPresupuesto as e:
            avisos.append(f"Vueling: {e}. Resultado sin (parte de) Vueling.")
        except Exception as e:
            avisos.append(f"Vueling: sin respuesta ({str(e)[:100]}).")

    # 1d) Vueling guardado: precios de búsquedas anteriores (no gastan). Si esta ejecución acaba de buscar
    #     Vueling entera, lo nuevo sustituye a lo guardado y no hace falta.
    try:
        guardados = vueling.tramos_guardados(domingo)
    except Exception:
        guardados = []
    nuevo_en_vivo = con_vueling and not vueling.SIMULAR
    n_guardados, usados = 0, []
    for t in guardados:
        if nuevo_en_vivo and vueling_ok:
            break   # las idas acaban de buscarse enteras: las guardadas sobran
        if (t["desde"] == ORIGEN and _ida_valida(t, domingo) and (espana or t.get("pais") != "ES")
                and not _repetido(idas.get(t["destino"], []), t)):
            idas.setdefault(t["destino"], []).append(t)
            n_guardados += 1
            usados.append(t)

    # 1e) Kiwi: todas las idas directas del domingo en la franja (sin Ryanair ni Wizz, que ya están)
    kiwi_ok, n_kiwi = False, 0

    if con_kiwi:
        try:
            for t in kiwi.idas(ORIGEN, [], domingo, IDA_DESDE, IDA_HASTA, usar_cache=usar_cache):
                if t["destino"] not in coords and t.get("coords"):
                    coords[t["destino"]] = t["coords"]
                if (t["desde"] == ORIGEN and _ida_valida(t, domingo) and (espana or t["pais"] != "ES")
                        and t["destino"] in coords and _meter_kiwi(idas.setdefault(t["destino"], []), t)):
                    n_kiwi += 1
            kiwi_ok = True
        except kiwi.KiwiBloqueado as e:
            avisos.append(f"Kiwi: sin respuesta ({str(e)[:100]}). Resultado sin Kiwi.")

    # 2) Ryanair: vueltas desde todos sus aeropuertos con ruta a BCN (2 consultas por cada día de vuelta)
    for noche, manana, _ in ventanas:
        for y, t in ryanair.vueltas(ORIGEN, domingo, noche, VUELTA_LUNES_DESDE, "23:59", usar_cache).items():
            vueltas.setdefault(y, []).append(t)
        tope = f"{manana}T{LLEGADA_MARTES_MAX}"
        #  solo se afinan (consultas extra) las del destino o las que están dentro del radio
        for y, t in ryanair.vueltas(ORIGEN, domingo, manana, "00:00", "23:59", usar_cache).items():
            if y in idas or any(cerca_de(x, y) for x in idas):
                t = ryanair.ajustar_llegada(t, ORIGEN, tope, usar_cache)
                if t:
                    vueltas.setdefault(y, []).append(t)

    # 2b) Vueling: vueltas solo desde los aeropuertos que interesan (el destino o a menos del radio)
    if vueling_ok:
        interesan = {y for y in vueling.red_conocida(usar_cache) if y in coords and y != ORIGEN
                     and (y in idas or any(cerca_de(x, y) for x in idas))}
        try:
            for noche, manana, _ in ventanas:
                for dia in (noche, manana):
                    for t in vueling.vueltas(ORIGEN, interesan, dia, coords, usar_cache):
                        vy_vistos.append(t)
                        if not _repetido(vueltas.get(t["destino"], []), t):
                            vueltas.setdefault(t["destino"], []).append(t)
            vy_completo = True
        except vueling.SinPresupuesto as e:
            avisos.append(f"Vueling: {e}. Vueltas de Vueling incompletas.")
        except Exception as e:
            avisos.append(f"Vueling (vueltas): sin respuesta ({str(e)[:100]}).")
    if con_vueling and not vueling.SIMULAR and vy_vistos:
        vueling.guardar_tramos(domingo, vy_vistos, vy_completo)
    for t in guardados:
        if nuevo_en_vivo and vy_completo:
            break   # las vueltas acaban de buscarse enteras
        if t["hasta"] == ORIGEN and not _repetido(vueltas.get(t["destino"], []), t):
            vueltas.setdefault(t["destino"], []).append(t)
            n_guardados += 1
            usados.append(t)
    # 2c) Kiwi: vueltas desde los aeropuertos que interesan (el destino o a menos del radio), una consulta por día
    if kiwi_ok:
        interesan = [y for y in coords if y != ORIGEN and (y in idas or any(cerca_de(x, y) for x in idas))]
        try:
            for noche, manana, _ in ventanas:
                for dia, h1 in ((noche, VUELTA_LUNES_DESDE), (manana, "00:00")):
                    for t in kiwi.vueltas([f"Airport:{y}" for y in interesan], ORIGEN, dia, h1, "23:59",
                                          usar_cache=usar_cache):
                        if t["destino"] not in coords and t.get("coords"):
                            coords[t["destino"]] = t["coords"]
                        if t["destino"] in coords and _meter_kiwi(vueltas.setdefault(t["destino"], []), t):
                            n_kiwi += 1
        except kiwi.KiwiBloqueado as e:
            avisos.append(f"Kiwi (vueltas): sin respuesta ({str(e)[:100]}).")
    if n_kiwi:
        avisos.append(f"Kiwi: {n_kiwi} vuelos de otras aerolíneas (Turkish, Pegasus, Vueling…). En Vueling "
                      "el precio ya está restado de la comisión de Kiwi (estimado, ±3 €); en las demás es el de Kiwi, "
                      "igual o algo mayor que en la aerolínea: confírmalo antes de comprar.")
    avisos.extend(kiwi._avisos)
    kiwi._avisos.clear()

    # Vueling guardado que Kiwi no ha renovado (Kiwi sustituye al guardado cuando trae el mismo vuelo)
    viejos = [t for t in usados if any(x is t for lista in (*idas.values(), *vueltas.values()) for x in lista)]
    if viejos:
        mas_viejo = max((datetime.now() - datetime.fromisoformat(t["visto"])).days for t in viejos)
        avisos.append(f"Vueling: {len(viejos)} vuelos con precio GUARDADO de búsquedas anteriores (el más "
                      f"antiguo, de hace {mas_viejo} días); no se ha gastado nada. Kiwi no los ha traído ahora"
                      + ("" if con_kiwi else " (esta ejecución no usó Kiwi: pulsa «Actualizar» o usa --kiwi)") + ".")

    # 3) Cruzar: mejor ida + mejor vuelta válida, desde el mismo aeropuerto o desde otro cercano
    d_ida = date.fromisoformat(domingo)

    def mejor_vuelta(y, max_dias=extra, desde=None):
        """Vuelta más barata desde y. Con `desde` (aeropuerto de llegada) solo cuentan las vueltas a las que
        se llega a tiempo por tierra o ferri: 250 km por cada día entre la ida y la vuelta."""
        validas = []
        for v in vueltas.get(y, []):
            tipo, dias = _tipo_vuelta(v, ventanas)
            if tipo and dias <= max_dias:
                if desde is not None and desde != y:
                    fuera = (date.fromisoformat(v["salida"][:10]) - d_ida).days
                    if _tray(desde, y, fuera) is None:
                        continue
                validas.append(dict(v, tipo=tipo, dias_libres=dias))
        return _mejor(validas)

    def opcion(x, ida, y, vuelta):
        o = {"domingo": domingo, "destino": x, "vuelta_desde": y, "ida": ida, "vuelta": vuelta,
             "total": round(ida["precio"] + vuelta["precio"], 2),
             "minimo": ida["precio_minimo"] or vuelta["precio_minimo"]}
        ka = semaforo.km_aire(coords[x].get("lat"), coords[x].get("lon"))
        o["km_bcn"] = round(ka) if ka is not None else ""
        if y != x:
            fuera = (date.fromisoformat(vuelta["salida"][:10]) - d_ida).days
            tr = _tray(x, y, fuera) or {"km": geografia.km_por_tierra(km(x, y)), "ferri": False}
            o["km"] = tr["km"]
            o["ferri"] = tr["ferri"]
            o["otro_pais"] = coords[x]["pais"] != coords[y]["pais"]
            o.update(_traslado(x, y, o["km"], nombres, coords))
        return o

    def la_mejor(x, ida, ys, max_dias):
        ops = [opcion(x, ida, y, mejor_vuelta(y, max_dias, x)) for y in ys if mejor_vuelta(y, max_dias, x)]
        return min(ops, key=lambda o: o["total"]) if ops else None

    mismo, otro = [], []
    for x, ts in idas.items():
        ida = _mejor(ts)
        cercanos = [y for y in vueltas if cerca_de(x, y)] if radio != 0 else []
        igual, alt = la_mejor(x, ida, [x], extra), la_mejor(x, ida, cercanos, extra)
        # para comparar: lo mejor sin pedir días libres
        igual_base, alt_base = la_mejor(x, ida, [x], 0), la_mejor(x, ida, cercanos, 0)
        if igual:
            igual["sin_extra"] = igual_base["total"] if igual_base else None
            mismo.append(igual)
        # solo interesa si no hay vuelta desde el mismo aeropuerto o si sale más barata
        if alt and (not igual or alt["total"] < igual["total"]):
            alt["sin_extra"] = alt_base["total"] if alt_base else None
            otro.append(alt)
    orden = lambda o: o["total"]
    mismo, otro = sorted(mismo, key=orden), sorted(otro, key=orden)
    if verificar_wizz_n:
        mismo, otro = _verificar_wizz(mismo, otro, verificar_wizz_n, coords, usar_cache, avisos, candidata)
    return _aplicar_confirmados(mismo, otro)


def _aplicar_confirmados(mismo, otro):
    """Pone el precio y la hora EXACTOS (con ✓) a los tramos que el auditor (auditor.py) contrastó con Google Flights
    y que siguen vigentes (`confirmar.VIGENCIA_DIAS`). No se enseña nada más: el precio estimado «~» pasa a ser el de
    Google con ✓. Recalcula el total y reordena. Sin `confirmados.json` no hace nada."""
    conf = confirmar.cargar()
    if not conf:
        return mismo, otro
    for lista in (mismo, otro):
        for o in lista:
            cambiado = False
            for c in ("ida", "vuelta"):
                t = o[c]
                g = conf.get(f"{t['desde']}-{t['hasta']}-{t['salida'][:10]}T{t['salida'][11:16]}")
                if t.get("verificada") or not g or not confirmar.vigente(g):
                    continue
                base = {k: v for k, v in t.items() if k not in ("precio_estimado", "precio_orientativo", "margen")}
                o[c] = dict(base, precio=g["precio"], llegada=g["llegada"] or t["llegada"], llegada_aprox=False,
                            vuelo=g["vuelo"] or t.get("vuelo", ""), precio_minimo=False, verificada=True)
                cambiado = True
            if cambiado:
                o["total"] = round(o["ida"]["precio"] + o["vuelta"]["precio"], 2)
                o["minimo"] = o["ida"]["precio_minimo"] or o["vuelta"]["precio_minimo"]
    orden = lambda o: o["total"]
    return sorted(mismo, key=orden), sorted(otro, key=orden)


def actualizar_domingos(domingos, periodo=None, con_vueling=False, simular=False, tope=10, avisos=None,
                        progreso=None, reiniciar=True, extras=(0,), con_kiwi=False):
    """Lo mismo que `--mes` pero sin el archivo del mes: lo usa el servidor local (servidor.py).

    Con `con_vueling` busca Vueling en SerpApi (gasta, hasta `tope`); sin él, Ryanair y Wizz salen frescos y
    Vueling con sus precios guardados. Con `simular` no gasta ni escribe nada: solo cuenta las búsquedas
    de Vueling que haría. `periodo` = (primer, último domingo del mes) para Wizz; `reiniciar=False` sigue
    sumando al contador de búsquedas de una llamada anterior. Devuelve {domingo: búsquedas nuevas de Vueling (o que se harían)}."""
    global EXTRA
    avisos = avisos if avisos is not None else []
    EXTRA = 0
    if reiniciar:
        vueling.reiniciar()
    vueling.SIMULAR = simular
    vueling.TOPE = 10 ** 6 if simular else tope
    costes = {}
    try:
        for i, dom in enumerate(domingos, 1):
            if progreso:
                progreso(f"Domingo {dom} ({i} de {len(domingos)})…")
            antes = vueling.gastadas()
            mismo, otro = buscar(dom, radio=None, usar_cache=True, con_wizz=True, avisos=avisos, con_mar=False,
                                 periodo_wizz=periodo, extra=0, con_vueling=con_vueling, espana=False,
                                 con_kiwi=con_kiwi and not simular)
            costes[dom] = vueling.gastadas() - antes
            if not simular:
                mismo = [o for o in mismo if o["ida"]["pais"] != "ES"]
                otro = [o for o in otro if o["ida"]["pais"] != "ES"]
                guardar_md(f"domingo {dom}", f"{dom}.md", mismo, otro, False, None, False, avisos)
                # Con 1 o 2 días libres extra: otro archivo por domingo (`AAAA-MM-DD_diasN.md`). Es la misma
                # búsqueda con la vuelta desplazada (casi todo sale de la caché); Vueling solo con lo guardado.
                for e in extras:
                    if e == 0:
                        continue
                    EXTRA = e
                    m2, o2 = buscar(dom, radio=None, usar_cache=True, con_wizz=True, avisos=avisos,
                                    con_mar=False, periodo_wizz=periodo, extra=e, con_vueling=False,
                                    espana=False, con_kiwi=con_kiwi)
                    m2 = [o for o in m2 if o["ida"]["pais"] != "ES"]
                    o2 = [o for o in o2 if o["ida"]["pais"] != "ES"]
                    guardar_md(f"domingo {dom} (hasta {e} días libres)", f"{dom}_dias{e}.md", m2, o2, False,
                               None, False, avisos)
                    EXTRA = 0
    finally:
        vueling.SIMULAR = False
        vueling.TOPE = 10
    return costes


def _verificar_wizz(mismo, otro, n, coords, usar_cache, avisos, candidata=None):
    """Comprueba en Kiwi (gratis) los tramos de Wizz de las `n` mejores opciones de cada lista:
    llegada real (marca ✓) y, si el de Wizz era «mínimo del día», precio estimado del vuelo. Si el precio de
    Wizz no era mínimo se conserva (es el de la aerolínea). Si la llegada real no cumple el horario,
    descarta la opción.
    `candidata` deja fuera las que luego no se van a enseñar (modo España, precio máximo)."""
    candidata = candidata or (lambda o: True)
    try:
        resultados = verificar_wizz.confirmar([o for o in mismo if candidata(o)][:n]
                                              + [o for o in otro if candidata(o)][:n], coords, usar_cache)
    except kiwi.KiwiBloqueado as e:
        avisos.append(f"Verificación de Wizz: Kiwi sin respuesta ({str(e)[:100]}). Sin verificar.")
        return mismo, otro
    except Exception as e:
        avisos.append(f"Verificación de Wizz: sin respuesta ({str(e)[:100]}).")
        return mismo, otro
    descartadas = set()
    for o, c, g in resultados:
        t = o[c]
        if g is None:
            o[c] = dict(t, no_confirmada=True)
            continue
        nuevo = dict(t, llegada=g["llegada"], llegada_aprox=False, verificada=True)
        if t["precio_minimo"]:   # Wizz solo daba «desde»: el precio del vuelo concreto sale de Kiwi (±3 €)
            nuevo.update(precio=g["precio"], precio_minimo=False, precio_estimado=True, margen=g.get("margen", 3))
        o[c] = nuevo
        if c == "vuelta" and "mañana" in t["tipo"] and g["llegada"] > f"{g['salida'][:10]}T{LLEGADA_MARTES_MAX}":
            descartadas.add(id(o))
            avisos.append(f"Wizz {t['desde']}→BCN {t['salida'][:10]}: la llegada real ({g['llegada'][11:]}) "
                          f"no cumple el límite de {LLEGADA_MARTES_MAX}; opción descartada.")
        o["total"] = round(o["ida"]["precio"] + o["vuelta"]["precio"], 2)
        o["minimo"] = o["ida"]["precio_minimo"] or o["vuelta"]["precio_minimo"]
    orden = lambda o: o["total"]
    quedan = lambda lista: sorted((o for o in lista if id(o) not in descartadas), key=orden)
    return quedan(mismo), quedan(otro)


# ---------------------------------------------------------------- salida

def hora(t, campo):
    """HH:MM, con ≈ si es calculada y (+1) si llega al día siguiente de salir."""
    if not t.get(campo):
        return "?"
    h = t[campo][11:16]
    if campo == "llegada":
        if t["llegada_aprox"]:
            h = "≈" + h
        if t["llegada"][:10] > t["salida"][:10]:
            h += " (+1)"
    return h


def _antiguedad(t):
    """' · precio de hace 4 días' para los precios de Vueling guardados; '' si el precio es de ahora."""
    if not t.get("visto"):
        return ""
    dias = (datetime.now() - datetime.fromisoformat(t["visto"])).days
    return " · precio " + ("guardado de hoy" if dias <= 0 else "de ayer" if dias == 1 else f"de hace {dias} días")


def _precio(t):
    return (("≥" if t["precio_minimo"] else "~" if t.get("precio_estimado") else "") + f"{t['precio']:.2f} €" + (" ✓" if t.get("verificada") else "")
            + (" · precio de Kiwi (en la aerolínea será igual o algo menor)" if t.get("precio_orientativo") else "")
            + _antiguedad(t))


def _sigla(t):
    return t.get("sigla") or {"Ryanair": "FR", "Vueling": "VY"}.get(t["aerolinea"], "W6")


def _etq(t):
    """Siglas con el número de vuelo si se conoce («FR 6881»); si no, solo las siglas («W6»)."""
    m = re.fullmatch(r"([A-Z0-9]{2})(\d{1,4})", (t.get("vuelo") or "").replace(" ", ""))
    return f"{m.group(1)} {m.group(2)}" if m else _sigla(t)


def _fila_ida(t):
    return f"{_etq(t)} {hora(t, 'salida')} → {hora(t, 'llegada')} · {_precio(t)}"


def _fila_vuelta(t):
    n = t["dias_libres"]
    libres = (f" ({n} día libre)" if n == 1 else f" ({n} días libres)") if n else ""
    return f"{_etq(t)} {t['tipo']}{libres}: {hora(t, 'salida')} → {hora(t, 'llegada')} · {_precio(t)}"


def _ahorro(o):
    """Texto de comparación cuando la vuelta necesita pedir días libres."""
    if not o["vuelta"]["dias_libres"]:
        return ""
    if o.get("sin_extra") is None:
        return " (sin días libres no hay vuelta)"
    return f" (−{o['sin_extra'] - o['total']:.2f} € vs sin días libres)"


def _total(o, moneda=""):
    return f"**{'≥' if o['minimo'] else ''}{o['total']:.2f}{' ' + moneda if moneda else ''}**{_ahorro(o)}"


def _fecha(dia):
    d = date.fromisoformat(dia)
    return f"{d.day} {MESES[d.month - 1][:3]}"


def _nuevo_txt(o):
    """Texto de la columna «País nuevo»: 🆕 si el país de la ida (o el de la vuelta) no está en
    paises_visitados.txt. En «mismo aeropuerto» solo hay ida; en «otro», se indica cuál es nuevo."""
    ida = paises.es_nuevo(o["ida"].get("pais"))
    if o.get("vuelta_desde") == o.get("destino"):
        return "🆕 nuevo" if ida else "no"
    vuelta = paises.es_nuevo(o["vuelta"].get("pais"))
    if ida and vuelta and o["ida"].get("pais") != o["vuelta"].get("pais"):
        return "🆕 ida y vuelta"
    return "🆕 ida" if ida else ("🆕 vuelta" if vuelta else "no")


def guardar_md(titulo, archivo, mismo, otro, espana, radio, con_mar, avisos, resumen=None):
    """Escribe el resultado. Con `resumen` (análisis de un mes) añade la columna del domingo."""
    RESULTADOS.mkdir(exist_ok=True)
    mes = resumen is not None
    col = "| Domingo " if mes else ""
    sep = "|---" if mes else ""
    lineas = [
        f"# Jawdrop — {titulo}",
        "",
        f"Ryanair (FR) y Wizz Air (W6) desde BCN, se pueden mezclar. Tarifa básica, 1 adulto. "
        f"Generado {datetime.now():%d-%m-%Y %H:%M} (escapadas.py {VERSION}).",
        f"Ida domingo {IDA_DESDE}-{IDA_HASTA}. Vuelta lunes desde {VUELTA_LUNES_DESDE} "
        f"o martes llegando a BCN antes de {LLEGADA_MARTES_MAX}."
        + (f" Con {EXTRA} día{'s' if EXTRA > 1 else ''} libre{'s' if EXTRA > 1 else ''} extra: la vuelta "
           f"puede ser hasta {EXTRA} día{'s' if EXTRA > 1 else ''} más tarde con el mismo horario; se indica "
           "cuánto se ahorra frente a no pedir días." if EXTRA else ""),
        "Modo España: " + ("encendido (incluye vuelos nacionales)." if espana
                           else "apagado (sin destinos en España)."),
        "País nuevo: 🆕 = país que no está en paises_visitados.txt (cuenta el país de la ida; en «otro "
        "aeropuerto» también se avisa si lo es el de la vuelta, pero eso no descarta la opción).",
        "«≥» = precio mínimo del día en Wizz (el de esa hora puede ser mayor). "
        "«≈» = hora de llegada calculada (Wizz no la da). «(+1)» = llega al día siguiente.",
    ]
    if mes:
        lineas += ["", "## Resumen por domingo", "",
                   "| Domingo | Más barato (mismo aeropuerto) | Más barato (otro aeropuerto) | Opciones |",
                   "|---|---|---|---|"]
        for dom, m, o in resumen:
            bm = f"{m[0]['ida']['ciudad']} {_total(m[0], '€')}" if m else "—"
            bo = (f"{o[0]['ida']['ciudad']} → {o[0]['vuelta']['ciudad']} {_total(o[0], '€')}" if o else "—")
            lineas.append(f"| {_fecha(dom)} | {bm} | {bo} | {len(m)} + {len(o)} |")
    lineas += [
        "",
        "## Mismo aeropuerto",
        "",
        f"{col}| # | Destino | Total € | Ida (sale → llega) | Vuelta (sale → llega) | Comprobar | País nuevo "
        "| Km BCN |",
        f"{sep}|---|---|---|---|---|---|---|---|",
    ]
    for i, o in enumerate(mismo, 1):
        ida, v = o["ida"], o["vuelta"]
        dia = f"| {_fecha(o['domingo'])} " if mes else ""
        lineas.append(
            f"{dia}| {i} | {ida['ciudad']} ({o['destino']}), {ida['pais_nombre']} | {_total(o)} "
            f"| {_fila_ida(ida)} | {_fila_vuelta(v)} | [ida]({ida['enlace']}) · [vuelta]({v['enlace']}) "
            f"| {_nuevo_txt(o)} | {o.get('km_bcn', '')} |")
    if not mismo:
        lineas.append("| | Ningún destino cumple el horario | | | | | | |")
    lineas += [
        "",
        "## Otro aeropuerto (vuelta desde otro: " + (f"a menos de {radio} km en línea recta)" if radio is not None
                                                     else "250 km por cada día fuera)"),
        "",
        "Solo aparece si no hay vuelta desde el mismo aeropuerto o si así sale más barato. "
        "Del mismo país o de un país vecino; km por tierra aproximados (línea recta × 1,3); el precio del "
        "traslado no está incluido. "
        + ("Incluye combinaciones que cruzan el mar sin ferri conocido." if con_mar
           else "Los cruces de mar solo valen con ferri regular conocido (⛴)."),
        "«Traslado»: tiempo aproximado EN COCHE de la ciudad de llegada al aeropuerto de vuelta (en bus suele ser más) "
        "(km a 75 km/h) y enlaces para ver buses, trenes y minivans reales.",
        "",
        f"{col}| # | Ida a | Vuelta desde | Km | ¿Cambio de país? | Traslado | Total € | Ida (sale → llega) "
        "| Vuelta (sale → llega) | Comprobar | País nuevo | Ferri | Km BCN |",
        f"{sep}|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, o in enumerate(otro, 1):
        ida, v = o["ida"], o["vuelta"]
        dia = f"| {_fecha(o['domingo'])} " if mes else ""
        enlaces = ([f"[12Go]({o['enlace_12go']})"] if o.get("enlace_12go") else []) + \
                  [f"[Rome2Rio]({o['enlace_rome2rio']})"]
        lineas.append(
            f"{dia}| {i} | {ida['ciudad']} ({o['destino']}), {ida['pais_nombre']} "
            f"| {v['ciudad']} ({o['vuelta_desde']}), {v['pais_nombre']} | {o['km']} "
            f"| {'sí' if o['otro_pais'] else 'no'} | {o['traslado_texto']} · {' · '.join(enlaces)} "
            f"| {_total(o)} | {_fila_ida(ida)} | {_fila_vuelta(v)} "
            f"| [ida]({ida['enlace']}) · [vuelta]({v['enlace']}) | {_nuevo_txt(o)} "
            f"| {'⛴' if o.get('ferri') else ''} | {o.get('km_bcn', '')} |")
    if not otro:
        lineas.append("| | Ninguna combinación mejora la vuelta desde el mismo aeropuerto | | | | | | | | | | | |")
    if avisos:
        lineas += ["", "## Avisos", ""] + [f"- {a}" for a in dict.fromkeys(avisos)]
    ruta = RESULTADOS / archivo
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def proximo_domingo():
    hoy = date.today()
    return (hoy + timedelta(days=(6 - hoy.weekday()) or 7)).isoformat()


def domingos_del_mes(mes):
    """Domingos de un mes (AAAA-MM) desde hoy en adelante."""
    año, m = map(int, mes.split("-"))
    d = date(año, m, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    res = []
    while d.month == m:
        if d >= date.today():
            res.append(d.isoformat())
        d += timedelta(days=7)
    return res


def _imprimir(mismo, otro, con_fecha=False):
    f = (lambda o: _fecha(o["domingo"]).ljust(7)) if con_fecha else (lambda o: "")
    print("Mismo aeropuerto:")
    for o in mismo[:20]:
        ida, v = o["ida"], o["vuelta"]
        print(f"  {f(o)}{'≥' if o['minimo'] else ' '}{o['total']:7.2f} €  {ida['ciudad'][:20]:<20} "
              f"{_sigla(ida)} {hora(ida, 'salida')}  vuelta {_sigla(v)} {v['tipo']} "
              f"{hora(v, 'salida')}→{hora(v, 'llegada')}")
    print("Otro aeropuerto:")
    for o in otro[:20]:
        ida, v = o["ida"], o["vuelta"]
        print(f"  {f(o)}{'≥' if o['minimo'] else ' '}{o['total']:7.2f} €  {ida['ciudad'][:16]:<16} → vuelta desde "
              f"{v['ciudad'][:16]:<16} {o['km']:>4} km{' (otro país)' if o['otro_pais'] else ''}  "
              f"{_sigla(v)} {v['tipo']} {hora(v, 'salida')}")


def main():
    ap = argparse.ArgumentParser(description="Jawdrop (Ryanair + Wizz Air)")
    ap.add_argument("domingo", nargs="?", help="AAAA-MM-DD (por defecto, el próximo domingo)")
    ap.add_argument("--mes", help="AAAA-MM: todos los domingos de ese mes (desde hoy)")
    ap.add_argument("--max", type=float, help="precio máximo ida+vuelta en euros")
    ap.add_argument("--radio", type=int, default=None,
                    help="fuerza un límite en km (línea recta) para volver desde otro aeropuerto, en vez de "
                         "250 km por día fuera (0 = solo el mismo aeropuerto)")
    ap.add_argument("--con-mar", action="store_true", help="mostrar también vueltas que obligan a cruzar el mar")
    ap.add_argument("--espana", action="store_true", help="modo España: incluir destinos nacionales")
    ap.add_argument("--nuevos", action="store_true",
                    help="solo destinos en países que no están en paises_visitados.txt (cuenta el de la ida)")
    ap.add_argument("--dias-extra", type=int, choices=(0, 1, 2), default=0,
                    help="días libres que podrías pedir: la vuelta puede ser 1 o 2 días más tarde")
    ap.add_argument("--sin-wizz", action="store_true", help="no consultar Wizz Air")
    ap.add_argument("--vueling", action="store_true",
                    help="añadir Vueling por SerpApi (GASTA ~20 búsquedas por domingo del límite de 250/mes; ya no hace "
                         "falta: --kiwi trae Vueling gratis. Solo para una comprobación puntual)")
    ap.add_argument("--kiwi", action="store_true",
                    help="añadir Kiwi.com (gratis): Turkish, Pegasus, Vueling... con precio orientativo")
    ap.add_argument("--simular-vueling", action="store_true",
                    help="con --vueling: no gasta nada, solo cuenta las búsquedas")
    ap.add_argument("--verificar-wizz", type=int, default=0, metavar="N",
                    help="comprueba en Kiwi (gratis) los tramos de Wizz de las N mejores opciones de cada "
                         "lista: llegada real (marca ✓) y precio del vuelo si Wizz solo daba «desde»")
    ap.add_argument("--tope-busquedas", type=int, default=10,
                    help="máximo de búsquedas nuevas de SerpApi en esta ejecución (por defecto 10)")
    ap.add_argument("--sin-cache", action="store_true", help="no usar la caché")
    a = ap.parse_args()
    global EXTRA
    EXTRA = a.dias_extra
    for aviso in paises.cargar()[1]:
        print("  AVISO:", aviso)
    vueling.SIMULAR = a.simular_vueling
    vueling.TOPE = 10 ** 6 if a.simular_vueling else a.tope_busquedas  # al simular no hay nada que limitar

    def vale(o):
        # el modo España mira solo el destino de la ida: la vuelta siempre es a BCN
        return ((a.espana or o["ida"]["pais"] != "ES") and (not a.max or o["total"] <= a.max)
                and (not a.nuevos or paises.es_nuevo(o["ida"]["pais"])))

    def una(domingo, avisos, periodo=None):
        mismo, otro = buscar(domingo, radio=a.radio, usar_cache=not a.sin_cache, con_wizz=not a.sin_wizz,
                             avisos=avisos, con_mar=a.con_mar, periodo_wizz=periodo, extra=a.dias_extra,
                             con_vueling=a.vueling, espana=a.espana, verificar_wizz_n=a.verificar_wizz,
                             candidata=vale, con_kiwi=a.kiwi)
        return [o for o in mismo if vale(o)], [o for o in otro if vale(o)]

    if a.mes:
        domingos = domingos_del_mes(a.mes)
        if not domingos:
            sys.exit(f"No quedan domingos en {a.mes}.")
        periodo = (domingos[0], domingos[-1])
        avisos, resumen, todos_m, todos_o = [], [], [], []
        for dom in domingos:
            print(f"Domingo {dom}…", flush=True)
            m, o = una(dom, avisos, periodo)
            guardar_md(f"domingo {dom}", f"{dom}.md", m, o, a.espana, a.radio, a.con_mar, avisos)
            resumen.append((dom, m, o))
            todos_m += m
            todos_o += o
        todos_m.sort(key=lambda o: o["total"])
        todos_o.sort(key=lambda o: o["total"])
        año, mm = map(int, a.mes.split("-"))
        ruta = guardar_md(f"{MESES[mm - 1]} de {año} (todos los domingos)", f"{a.mes}.md",
                          todos_m, todos_o, a.espana, a.radio, a.con_mar, avisos, resumen=resumen)
        print(f"{len(domingos)} domingos: {len(todos_m)} con el mismo aeropuerto, {len(todos_o)} con otro. "
              f"Resultado en {ruta}")
        _imprimir(todos_m, todos_o, con_fecha=True)
    else:
        domingo = a.domingo or proximo_domingo()
        if date.fromisoformat(domingo).weekday() != 6:
            sys.exit(f"{domingo} no es domingo.")
        avisos = []
        mismo, otro = una(domingo, avisos)
        ruta = guardar_md(f"domingo {domingo}", f"{domingo}.md", mismo, otro, a.espana, a.radio, a.con_mar, avisos)
        print(f"Domingo {domingo}: {len(mismo)} con el mismo aeropuerto, {len(otro)} con otro. Resultado en {ruta}")
        _imprimir(mismo, otro)
    for x in dict.fromkeys(avisos):
        print("  AVISO:", x)
    if a.vueling:
        if a.simular_vueling:
            print(f"SIMULACIÓN: se gastarían {vueling.gastadas()} búsquedas de SerpApi "
                  f"(las ya guardadas en caché no cuentan). No se ha gastado ninguna.")
        else:
            print(f"SerpApi: {vueling.gastadas()} búsquedas nuevas gastadas.")


if __name__ == "__main__":
    main()
