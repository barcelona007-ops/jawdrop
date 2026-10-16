r"""
pais.py — Búsqueda por país concreto (Jawdrop).

Para un país elegido por el usuario (Turquía, Georgia, Irlanda...), busca vuelos de ida y vuelta entrando por
UN aeropuerto del país y saliendo por OTRO (o el mismo): dentro de un país grande, entrar por Estambul y
salir por Antalya es normal. La distancia entre ambos obedece a la regla general (geografia.py): 250 km por
cada día fuera, km por tierra, mismo país o vecino, ferri si hay mar. Ida y vuelta son dos billetes de solo ida.

  - Fechas: los días de la semana elegidos (domingo por defecto) de uno o varios meses o de un rango,
    desde hoy. Sirve para meses vista.
  - Duración: `--dias 4` = 4 días contando ida y vuelta (domingo → miércoles). También `--dias 4-5`.
  - Fuentes (todas gratis, sin SerpApi): Kiwi (`Country:XX`: Turkish, Pegasus, AJet, Vueling, easyJet...),
    y Ryanair y Wizz directos por si el país es de los que ellos cubren (Georgia, Polonia...).
  - Sin reglas de hora (domingo por la mañana, lunes desde las 20:00): se enseñan las horas y decide el usuario.
  - Por cada fecha, la mejor combinación ida+vuelta; abajo, las mejores de todo el periodo con los km
    entre el aeropuerto de entrada y el de salida y el enlace de traslado.
  - Siempre por la caché y con las pausas de cada pieza. Si una fuente cierra la puerta, sigue sin ella.

Uso:
  .venv\Scripts\python.exe pais.py Turquia --mes 2027-04 [--dias 4] [--salida domingo]
  .venv\Scripts\python.exe pais.py Georgia --mes 2027-04,2027-05 --dias 7-8 --salida sabado
  .venv\Scripts\python.exe pais.py TR --desde 2027-03-01 --hasta 2027-03-31 --n 20
  Opciones: --sin-kiwi --sin-ryanair --sin-wizz --sin-cache --max-fechas 12

Marcas: «~» precio estimado de la aerolínea desde Kiwi (±3 €), «≈» precio de Kiwi sin medir,
«≥» mínimo del día en Wizz (el de esa hora puede ser mayor).
"""
import argparse
import json
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import geografia
import kiwi
import paises
import ryanair
import wizz

VERSION = "1.2"


class Cancelado(BaseException):
    """El usuario pulsó «Cancelar». Hereda de BaseException para que los `except Exception` de cada fuente no
    lo confundan con un fallo y se lo traguen. Lo hecho hasta ese momento ya está en la caché.
    Si ya había bloques terminados, `parcial` trae la búsqueda guardable con lo conseguido."""
    parcial = None


GRANDES = {"BG"}   # países con tantos vuelos que Kiwi llega a su tope de 50 resultados: van en su propia consulta
ORIGEN = "BCN"
CARPETA = Path(__file__).resolve().parent / "resultados"
RUTA = CARPETA / "pais.json"   # lo lee ver_resultados.py (panel «Un país concreto» de la demo)
GUARDAR_MAX = 30
BLOQUE = 12        # fechas de ida por bloque: una búsqueda más larga se parte en bloques de este tamaño
MAX_FECHAS = 120   # tope de fechas de ida de una sola búsqueda (4 meses de «cualquier día»)
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# nombre en español (sin tildes, minúsculas) -> código de país
ES = {
    "albania": "AL", "argelia": "DZ", "andorra": "AD", "armenia": "AM", "austria": "AT", "azerbaiyan": "AZ",
    "barein": "BH", "bielorrusia": "BY", "belgica": "BE", "bosnia": "BA", "bosnia y herzegovina": "BA",
    "bulgaria": "BG", "camboya": "KH", "china": "CN", "costa rica": "CR", "croacia": "HR", "chipre": "CY",
    "chequia": "CZ", "republica checa": "CZ", "dinamarca": "DK", "egipto": "EG", "estonia": "EE",
    "finlandia": "FI", "francia": "FR", "georgia": "GE", "alemania": "DE", "gibraltar": "GI", "grecia": "GR",
    "hungria": "HU", "islandia": "IS", "india": "IN", "indonesia": "ID", "irlanda": "IE", "israel": "IL",
    "italia": "IT", "japon": "JP", "jordania": "JO", "kazajistan": "KZ", "kosovo": "XK", "kirguistan": "KG",
    "laos": "LA", "letonia": "LV", "libano": "LB", "liechtenstein": "LI", "lituania": "LT",
    "luxemburgo": "LU", "malasia": "MY", "maldivas": "MV", "malta": "MT", "moldavia": "MD", "monaco": "MC",
    "montenegro": "ME", "marruecos": "MA", "nepal": "NP", "paises bajos": "NL", "holanda": "NL",
    "macedonia": "MK", "macedonia del norte": "MK", "noruega": "NO", "oman": "OM", "filipinas": "PH",
    "polonia": "PL", "portugal": "PT", "catar": "QA", "qatar": "QA", "rumania": "RO", "rusia": "RU",
    "san marino": "SM", "arabia saudi": "SA", "arabia saudita": "SA", "serbia": "RS", "singapur": "SG",
    "eslovaquia": "SK", "eslovenia": "SI", "corea del sur": "KR", "espana": "ES", "sri lanka": "LK",
    "suecia": "SE", "suiza": "CH", "taiwan": "TW", "tayikistan": "TJ", "tailandia": "TH", "tunez": "TN",
    "turquia": "TR", "ucrania": "UA", "emiratos": "AE", "emiratos arabes": "AE", "dubai": "AE",
    "reino unido": "GB", "inglaterra": "GB", "escocia": "GB", "estados unidos": "US", "eeuu": "US",
    "uzbekistan": "UZ", "vaticano": "VA", "vietnam": "VN", "senegal": "SN", "cabo verde": "CV",
    "mauritania": "MR", "ghana": "GH", "tanzania": "TZ", "kenia": "KE", "jamaica": "JM", "mexico": "MX",
    "canada": "CA", "republica dominicana": "DO", "el salvador": "SV", "honduras": "HN", "colombia": "CO",
    "peru": "PE", "chile": "CL", "argentina": "AR", "brasil": "BR", "bolivia": "BO", "gambia": "GM",
    "kuwait": "KW", "hong kong": "HK",
}

# nombres con tilde para enseñar (la tabla ES va sin tildes para poder comparar lo que se escribe)
CON_TILDE = {
    "azerbaiyan": "Azerbaiyán", "barein": "Baréin", "belgica": "Bélgica", "hungria": "Hungría", "japon": "Japón",
    "kazajistan": "Kazajistán", "kirguistan": "Kirguistán", "libano": "Líbano", "paises bajos": "Países Bajos",
    "oman": "Omán", "arabia saudi": "Arabia Saudí", "arabia saudita": "Arabia Saudí", "taiwan": "Taiwán",
    "tayikistan": "Tayikistán", "tunez": "Túnez", "turquia": "Turquía", "uzbekistan": "Uzbekistán",
    "monaco": "Mónaco", "republica checa": "República Checa", "espana": "España", "mexico": "México",
    "canada": "Canadá", "republica dominicana": "República Dominicana", "peru": "Perú", "hong kong": "Hong Kong",
    "emiratos arabes": "Emiratos Árabes", "macedonia del norte": "Macedonia del Norte", "catar": "Catar",
}


def _bonito(k):
    return CON_TILDE.get(k, k.title())


def _sin_tildes(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def codigo_pais(texto):
    """'Turquia' / 'turkey' / 'TR' -> 'TR' (o None si no se reconoce)."""
    t = _sin_tildes(texto)
    if t in ES:
        return ES[t]
    if t in paises.CODIGOS:
        return paises.CODIGOS[t]
    if len(t) == 2 and t.isalpha():
        return t.upper()
    return None


def _dia_semana(texto):
    t = _sin_tildes(texto)
    for i, d in enumerate(DIAS):
        if _sin_tildes(d).startswith(t[:3]) and len(t) >= 3:
            return i
    return None


def semana(texto):
    """Conjunto de días de la semana (0 = lunes) de un texto como «domingo», «viernes,sabado» o «todos».
    None si el texto está vacío. Lanza ValueError si no entiende algún día."""
    if not texto or not str(texto).strip():
        return None
    if str(texto).lower() in ("todos", "cualquiera"):
        return set(range(7))
    sem = set()
    for p in str(texto).split(","):
        i = _dia_semana(p)
        if i is None:
            raise ValueError(f"No entiendo el día «{p}» (lunes, martes... o «todos»).")
        sem.add(i)
    return sem


def fechas_vuelta_de(fechas, dmin, dmax, vuelta=None):
    """Fechas posibles de vuelta; si `vuelta` (texto de días de la semana) viene, solo esos días."""
    sem = semana(vuelta) if isinstance(vuelta, str) else vuelta
    return sorted({f + timedelta(days=n - 1) for f in fechas for n in range(dmin, dmax + 1)
                   if sem is None or (f + timedelta(days=n - 1)).weekday() in sem})


def _norm_lista(texto):
    """«Ryanair, Wizz» -> ('ryanair', 'wizz'): sin tildes, en minúsculas, ordenado y sin repetir."""
    t = _sin_tildes(texto or "") if not isinstance(texto, (list, tuple, set)) else _sin_tildes(",".join(texto))
    return tuple(sorted({x.strip() for x in t.split(",") if x.strip()}))


def aerolinea_vale(nombre, solo=(), sin=()):
    """¿Entra esta aerolínea con los filtros «solo con» / «sin»? Compara por trozos del nombre (wizz = Wizz Air)."""
    n = _sin_tildes(nombre or "")
    if solo and not any(x in n for x in solo):
        return False
    return not any(x in n for x in sin)


def fechas_de(salida="domingo", meses=None, desde=None, hasta=None):
    """Fechas de ida: días de la semana pedidos dentro de los meses (AAAA-MM, separados por comas) o del
    rango desde-hasta, desde hoy. Lanza ValueError con un mensaje claro si algo no vale."""
    sem = semana(salida) or semana("domingo")
    rangos = []
    if meses:
        for m in meses.split(","):
            try:
                a = date.fromisoformat(m.strip() + "-01")
            except ValueError:
                raise ValueError(f"Mes no válido «{m}»: usa AAAA-MM.") from None
            rangos.append((a, date(a.year + a.month // 12, a.month % 12 + 1, 1) - timedelta(days=1)))
    elif desde and hasta:
        try:
            rangos.append((date.fromisoformat(desde), date.fromisoformat(hasta)))
        except ValueError:
            raise ValueError("Fechas no válidas: usa AAAA-MM-DD.") from None
    else:
        raise ValueError("Falta el periodo: un mes (AAAA-MM) o --desde y --hasta.")
    hoy = date.today()
    fechas = []
    for a, b in rangos:
        d = max(a, hoy)
        while d <= b:
            if d.weekday() in sem and d not in fechas:
                fechas.append(d)
            d += timedelta(days=1)
    return sorted(fechas)


def _dias(texto):
    a, _, b = (str(texto) or "4").partition("-")
    try:
        lo, hi = int(a), int(b or a)
    except ValueError:
        raise ValueError("Los días son un número (4) o un rango (4-5).") from None
    if lo < 2 or hi < lo or hi > 21:
        raise ValueError("Duración: entre 2 y 21 días contando ida y vuelta, y el segundo número no menor que el primero.")
    return lo, hi


def _mejor_por_aeropuerto(tramos):
    """{aeropuerto: tramo más barato}; a igual precio, el que no es «mínimo del día»."""
    res = {}
    for t in tramos:
        k = t["destino"]
        if k not in res or (t["precio"], t.get("precio_minimo", False)) < (res[k]["precio"],
                                                                           res[k].get("precio_minimo", False)):
            res[k] = t
    return res


def buscar(codigo, fechas, dmin, dmax, con_kiwi=True, con_ryanair=True, con_wizz=True, usar_cache=True,
           avisar=None, codigos_vuelta=None, cancelar=None, vuelta=None, radio=None, solo=(), sin=()):
    """Devuelve (opciones, coords, avisos). `opciones` = una por (fecha de ida, fecha de vuelta, aeropuerto
    de entrada, aeropuerto de salida), con el tramo de ida y el de vuelta. Sin filtros de hora; la distancia
    entre aeropuertos sí obedece a geografia.py (250 km por día fuera, o `radio` km en línea recta si se fuerza).
    `vuelta` = días de la semana permitidos para volver (None = cualquiera); `solo` / `sin` = trozos de nombre de
    aerolíneas admitidas / excluidas."""
    codigos = {codigo} if isinstance(codigo, str) else set(codigo)   # un país o varios a la vez
    lotes = [sorted(codigos)[i:i + 10] for i in range(0, len(codigos), 10)]   # 10 países por consulta a Kiwi
    # países de los que solo se miran VUELTAS (vecinos de algún país de entrada, a distancia alcanzable)
    extra = sorted(set(codigos_vuelta or ()) - codigos)
    solos = [c for c in extra if c in GRANDES]
    resto = [c for c in extra if c not in GRANDES]
    lotes_v = lotes + [[c] for c in solos] + [resto[i:i + 10] for i in range(0, len(resto), 10)]
    todos = codigos | set(extra)
    avisos = []
    coords = {}
    idas = {}      # fecha ida -> [tramos]
    vueltas = {}   # fecha vuelta -> [tramos]
    fechas_vuelta = fechas_vuelta_de(fechas, dmin, dmax, vuelta)
    total = [len(fechas) * len(lotes) + len(fechas_vuelta) * len(lotes_v)]   # crece al conocer Ryanair y Wizz
    paso = [0]

    def alto():
        if cancelar is not None and cancelar.is_set():
            raise Cancelado()

    def prog(texto):
        alto()
        paso[0] += 1
        if avisar:
            avisar(paso[0], total[0], texto)

    try:
        coords.update(ryanair.aeropuertos(usar_cache))
    except Exception as e:
        avisos.append(f"Lista de aeropuertos de Ryanair: {str(e)[:70]}")
    aeropuertos_wizz, red_wizz = {}, []
    if con_wizz:
        try:
            aeropuertos_wizz, red_wizz = wizz.red(ORIGEN, usar_cache)
            for k, v in aeropuertos_wizz.items():
                coords.setdefault(k, v)
        except wizz.WizzBloqueado as e:
            con_wizz = False
            avisos.append(f"Wizz Air ha cerrado la puerta ({str(e)[:70]}). Sigo sin Wizz.")
    de_pais = lambda k: coords.get(k, {}).get("pais") in codigos

    # --- Kiwi: una consulta por día de ida y otra por día de vuelta
    kiwi_ok = con_kiwi
    for f in fechas:
        for lote in lotes:
            prog(f"Kiwi ida {f}")
            if kiwi_ok:
                try:
                    for t in kiwi.rango([f"Airport:{ORIGEN}"], [f"Country:{c}" for c in lote], f.isoformat(),
                                        f.isoformat(), usar_cache=usar_cache):
                        idas.setdefault(f, []).append(t)
                except kiwi.KiwiBloqueado as e:
                    kiwi_ok = False
                    avisos.append(f"Kiwi no responde ({str(e)[:70]}). Sigo sin Kiwi.")
    for f in fechas_vuelta:
        for lote in lotes_v:
            prog(f"Kiwi vuelta {f}")
            if kiwi_ok:
                try:
                    for t in kiwi.rango([f"Country:{c}" for c in lote], [f"Airport:{ORIGEN}"], f.isoformat(),
                                        f.isoformat(), usar_cache=usar_cache):
                        vueltas.setdefault(f, []).append(t)
                except kiwi.KiwiBloqueado as e:
                    kiwi_ok = False
                    avisos.append(f"Kiwi no responde ({str(e)[:70]}). Sigo sin Kiwi.")
    for t in [x for l in idas.values() for x in l] + [x for l in vueltas.values() for x in l]:
        if t.get("coords"):
            coords.setdefault(t["destino"], t["coords"])
    avisos += kiwi._avisos
    kiwi._avisos.clear()

    # --- Ryanair: idas de ese día a todos los destinos (se queda con el país) y vueltas desde sus aeropuertos
    if con_ryanair:
        aps = set()
        total[0] += len(fechas)
        try:
            for f in fechas:
                prog(f"Ryanair ida {f}")
                for t in ryanair.idas(ORIGEN, f.isoformat(), "00:00", "23:59", usar_cache):
                    if t["pais"] in codigos:
                        idas.setdefault(f, []).append(t)
                        aps.add(t["destino"])
            total[0] += len(aps)
            for ap in sorted(aps):
                prog(f"Ryanair vuelta {ap}")
                for f in fechas_vuelta:
                    try:
                        v = ryanair.vuelta_desde(ap, ORIGEN, f.isoformat(), "00:00", "23:59", usar_cache)
                    except RuntimeError as e:
                        if "400" not in str(e):
                            avisos.append(f"Ryanair {ap}-{ORIGEN} {f}: {str(e)[:60]}")
                        continue
                    if v:
                        vueltas.setdefault(f, []).append(v)
        except Exception as e:
            avisos.append(f"Ryanair: {str(e)[:80]}")
        if extra and fechas_vuelta:
            d0, d1 = min(fechas_vuelta).isoformat(), max(fechas_vuelta).isoformat()
            for ap in sorted(k for k, v in coords.items() if v.get("pais") in extra):
                prog(f"Ryanair vuelta {ap}")
                p = dict(ryanair.COMUNES, departureAirportIataCode=ap, arrivalAirportIataCode=ORIGEN,
                         outboundDepartureDateFrom=d0, outboundDepartureDateTo=d1)
                try:
                    for fa in ryanair._pedir(ryanair.URL_SOLO_IDA, p, usar_cache).get("fares", []):
                        t = ryanair._tramo(fa["outbound"], "vuelta")
                        fv = date.fromisoformat(t["salida"][:10])
                        if fv in fechas_vuelta:
                            vueltas.setdefault(fv, []).append(t)
                except Exception as e:
                    if "400" not in str(e):
                        avisos.append(f"Ryanair {ap}-{ORIGEN}: {str(e)[:60]}")

    # --- Wizz: una consulta por ruta del país y mes (cubre idas y vueltas)
    if con_wizz:
        rutas = [d for d in red_wizz if aeropuertos_wizz.get(d, {}).get("pais") in todos]
        meses = {}
        for f in fechas:
            meses.setdefault((f.year, f.month), []).append(f)
        total[0] += len(rutas) * len(meses)
        try:
            for d in rutas:
                for _, fs in meses.items():
                    prog(f"Wizz {d}")
                    a, b = min(fs), max(fs)
                    wi, wv = wizz.horarios(ORIGEN, d, a.isoformat(), b.isoformat(),
                                           (a + timedelta(days=dmin - 1)).isoformat(),
                                           (b + timedelta(days=dmax - 1)).isoformat(),
                                           aeropuertos_wizz, usar_cache)
                    for t in wi:
                        f = date.fromisoformat(t["salida"][:10])
                        if f in fechas and t["destino"] in aeropuertos_wizz and de_pais(t["destino"]):
                            idas.setdefault(f, []).append(t)
                    for t in wv:
                        f = date.fromisoformat(t["salida"][:10])
                        if f in fechas_vuelta and aeropuertos_wizz.get(t["destino"], {}).get("pais") in todos:
                            vueltas.setdefault(f, []).append(t)
        except wizz.WizzBloqueado as e:
            avisos.append(f"Wizz Air ha cerrado la puerta ({str(e)[:70]}). Sigo sin Wizz.")
        except Exception as e:
            avisos.append(f"Wizz Air: {str(e)[:80]}")

    # --- Combinar: la vuelta sale del mismo aeropuerto o de otro al que se llega por tierra (o ferri) en
    # los días del viaje: 250 km por día fuera, mismo país o vecino (geografia.py)
    def pais_de(t, ap):
        return t.get("pais") or coords.get(ap, {}).get("pais") or ""

    def compatible(a, ti, b, tv, dias_fuera):
        if a == b:
            return {"km": 0, "ferri": False}
        pa, pb = pais_de(ti, a), pais_de(tv, b)
        ca, cb = coords.get(a), coords.get(b)
        if not ca or not cb or ca.get("lat") is None or cb.get("lat") is None:
            return None
        return geografia.trayecto(a, pa, b, pb, wizz.distancia_km(ca, cb), dias_fuera, radio=radio)

    opciones = []
    vale = lambda l: [t for t in l if aerolinea_vale(t.get("aerolinea"), solo, sin)]
    for f in fechas:
        mi = _mejor_por_aeropuerto(vale(idas.get(f, [])))
        for n in range(dmin, dmax + 1):
            fv = f + timedelta(days=n - 1)
            if fv not in fechas_vuelta:
                continue
            mv = _mejor_por_aeropuerto(vale(vueltas.get(fv, [])))
            for a, ti in mi.items():
                for b, tv in mv.items():
                    tr = compatible(a, ti, b, tv, n - 1)
                    if tr is None:
                        continue
                    opciones.append({"ida": f.isoformat(), "vuelta": fv.isoformat(), "dias": n, "entrada": a,
                                     "salida_ap": b, "t_ida": ti, "t_vuelta": tv, "ferri": tr["ferri"],
                                     "total": ti["precio"] + tv["precio"]})
    return opciones, coords, avisos


def _marca(t):
    if t.get("precio_estimado"):
        return "~"
    if t.get("precio_orientativo"):
        return "≈"
    if t.get("precio_minimo"):
        return "≥"
    return ""


def _fecha(f):
    d = date.fromisoformat(f[:10])
    return f"{DIAS[d.weekday()][:3]} {d.day} {MESES[d.month - 1]}"


def noches(ida, vuelta):
    """Noches fuera: días entre la ida y la vuelta (ISO). dom 17 → mié 20 = 3 noches."""
    n = (date.fromisoformat(vuelta[:10]) - date.fromisoformat(ida[:10])).days
    return f"{n} noche" + ("" if n == 1 else "s")


def _tramo_txt(t, otro):
    nombre = t.get("ciudad") or otro
    lleg = (t.get("llegada") or "")[11:16]
    return (f"{t['precio']:.0f} €{_marca(t)} {t['aerolinea']} {t['salida'][11:16]}→{lleg or '?'} "
            f"{nombre} ({otro})")


def _km(coords, a, b):
    """Km por tierra aproximados entre dos aeropuertos (línea recta × 1,3, geografia.py)."""
    ca, cb = coords.get(a, {}), coords.get(b, {})
    if ca.get("lat") is None or cb.get("lat") is None:
        return None
    return geografia.km_por_tierra(wizz.distancia_km(ca, cb))


def _traslado(a, b, km, coords):
    """Texto y enlaces del traslado entre aeropuertos del país (el cálculo es el de escapadas.py)."""
    try:
        import escapadas
        try:
            nombres = ryanair.nombres_en()
        except Exception:
            nombres = {}
        return escapadas._traslado(a, b, km, nombres, coords)
    except Exception:
        return None


def por_fecha(opciones):
    """La mejor combinación de cada (ida, vuelta)."""
    mejor = {}
    for o in opciones:
        k = (o["ida"], o["vuelta"])
        if k not in mejor or o["total"] < mejor[k]["total"]:
            mejor[k] = o
    return sorted(mejor.values(), key=lambda o: (o["ida"], o["vuelta"]))


def _linea(o, coords):
    km = None if o["entrada"] == o["salida_ap"] else _km(coords, o["entrada"], o["salida_ap"])
    if o["entrada"] == o["salida_ap"]:
        donde = "mismo aeropuerto"
    elif km is None:
        donde = f"{o['entrada']} → {o['salida_ap']}"
    else:
        tr = _traslado(o["entrada"], o["salida_ap"], km, coords)
        donde = f"≈{km:.0f} km entre aeropuertos{' ⛴' if o.get('ferri') else ''}" + (f" (≈{tr['traslado_texto'][1:]} en coche)" if tr else "")
    return (f"{o['total']:6.0f} €  {_fecha(o['ida'])} → {_fecha(o['vuelta'])} · {noches(o['ida'], o['vuelta'])}\n"
            f"           ida:    {_tramo_txt(o['t_ida'], o['entrada'])}\n"
            f"           vuelta: {_tramo_txt(o['t_vuelta'], o['salida_ap'])}\n"
            f"           {donde}")


def guardar_md(ruta, nombre, codigo, periodo, dmin, dmax, mejores, por_dia, coords, avisos):
    lineas = [f"# {nombre}: ida y vuelta desde BCN, {periodo}", "",
              f"- Duración: {dmin if dmin == dmax else f'{dmin}-{dmax}'} días contando ida y vuelta.",
              "- Dos billetes de solo ida (se pueden mezclar aerolíneas y aeropuertos; entre el de llegada y el de vuelta, 250 km por día fuera).",
              "- Marcas: «~» estimado de la aerolínea (±3 €), «≈» precio de Kiwi sin medir, «≥» mínimo del día en Wizz.",
              "", "## Las mejores combinaciones", "",
              "| Total | Ida | Vuelta | Entrada → salida | Ida: vuelo | Vuelta: vuelo | Traslado |",
              "|---|---|---|---|---|---|---|"]
    for o in mejores:
        km = None if o["entrada"] == o["salida_ap"] else _km(coords, o["entrada"], o["salida_ap"])
        tr = _traslado(o["entrada"], o["salida_ap"], km, coords) if km is not None else None
        tras = ("mismo aeropuerto" if o["entrada"] == o["salida_ap"] else
                (f"≈{km:.0f} km{' ⛴' if o.get('ferri') else ''}" + (f", ≈{tr['traslado_texto'][1:]} · [12Go]({tr['enlace_12go']})"
                                   f" · [Rome2Rio]({tr['enlace_rome2rio']})" if tr and tr['enlace_12go'] else
                                   (f", ≈{tr['traslado_texto'][1:]} · [Rome2Rio]({tr['enlace_rome2rio']})" if tr else ""))
                 if km is not None else "—"))
        lineas.append(f"| **{o['total']:.0f} €** | {_fecha(o['ida'])} | {_fecha(o['vuelta'])} · {noches(o['ida'], o['vuelta'])} | "
                      f"{o['entrada']} → {o['salida_ap']} | "
                      f"[{_tramo_txt(o['t_ida'], o['entrada'])}]({o['t_ida'].get('enlace', '')}) | "
                      f"[{_tramo_txt(o['t_vuelta'], o['salida_ap'])}]({o['t_vuelta'].get('enlace', '')}) | {tras} |")
    lineas += ["", "## La más barata de cada fecha", "", "| Ida | Vuelta | Total | Entrada → salida |", "|---|---|---|---|"]
    for o in por_dia:
        lineas.append(f"| {_fecha(o['ida'])} | {_fecha(o['vuelta'])} | {o['total']:.0f} € | "
                      f"{o['entrada']} → {o['salida_ap']} |")
    if avisos:
        lineas += ["", "## Avisos", ""] + [f"- {a}" for a in avisos]
    ruta.parent.mkdir(exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def nombre_pais(codigo, texto=""):
    """Nombre en castellano para enseñar (el primero de la tabla ES para ese código)."""
    for k, v in ES.items():
        if v == codigo:
            return _bonito(k)
    return texto.strip().capitalize() or codigo


def nombres():
    """Nombres en castellano para la lista desplegable de la demo."""
    return sorted({_bonito(k) for k in ES})


def codigos_por_nombre():
    """{nombre sin tildes en minúsculas: código} para que la demo sepa de qué país es lo que se escribe."""
    return {k: v for k, v in ES.items()}


def _t(t, otro):
    return {"precio": t["precio"], "aerolinea": t["aerolinea"], "salida": t["salida"],
            "llegada": t.get("llegada") or "", "ciudad": t.get("ciudad") or otro, "aeropuerto": otro,
            "marca": _marca(t), "enlace": t.get("enlace", "")}


def resumen(o, coords):
    """Una combinación como diccionario sencillo (para guardar en JSON y enseñar en la demo)."""
    mismo = o["entrada"] == o["salida_ap"]
    km = None if mismo else _km(coords, o["entrada"], o["salida_ap"])
    tr = _traslado(o["entrada"], o["salida_ap"], km, coords) if km is not None else None
    return {"total": o["total"], "ida": o["ida"], "vuelta": o["vuelta"], "dias": o["dias"],
            "entrada": o["entrada"], "salida": o["salida_ap"], "mismo": mismo,
            "km": None if km is None else round(km), "ferri": bool(o.get("ferri")),
            "traslado": tr["traslado_texto"][1:] if tr else None,
            "enlace_12go": tr["enlace_12go"] if tr else None,
            "enlace_rome2rio": tr["enlace_rome2rio"] if tr else None,
            "t_ida": _t(o["t_ida"], o["entrada"]), "t_vuelta": _t(o["t_vuelta"], o["salida_ap"])}


def _mejores(opciones, n):
    mejores, vistos = [], set()
    for o in sorted(opciones, key=lambda o: o["total"]):
        k = (o["ida"], o["vuelta"], o["entrada"], o["salida_ap"])
        if k not in vistos:
            vistos.add(k)
            mejores.append(o)
        if len(mejores) >= n:
            break
    return mejores


def filtro_fuentes(solo, sin, con_kiwi=True, con_ryanair=True, con_wizz=True):
    """Apaga las fuentes que no sirven con los filtros de aerolínea (no se consulta a quien no va a contar).
    Si solo se pide Ryanair y/o Wizz, Kiwi sobra: ya se les pregunta directamente."""
    con_ryanair = con_ryanair and aerolinea_vale("Ryanair", solo, sin)
    con_wizz = con_wizz and aerolinea_vale("Wizz Air", solo, sin)
    if solo and all(x in ("ryanair", "wizz", "wizz air") for x in solo):
        con_kiwi = False
    return con_kiwi, con_ryanair, con_wizz


def partir(fechas, tamano=BLOQUE):
    """Parte la lista de fechas de ida en bloques de `tamano` (el último puede ser más corto)."""
    return [fechas[i:i + tamano] for i in range(0, len(fechas), tamano)]


def _juntar(opciones):
    """Quita repetidos (misma ida, vuelta y aeropuertos) quedándose con el más barato."""
    mejor = {}
    for o in opciones:
        k = (o["ida"], o["vuelta"], o["entrada"], o["salida_ap"])
        if k not in mejor or o["total"] < mejor[k]["total"]:
            mejor[k] = o
    return list(mejor.values())


def ejecutar(texto, meses=None, desde=None, hasta=None, salida="domingo", dias="4", n=10, max_fechas=BLOQUE,
             con_kiwi=True, con_ryanair=True, con_wizz=True, usar_cache=True, avisar=None, cancelar=None,
             vuelta=None, maximo=None, solo="", sin="", radio=None, progreso=None):
    """Búsqueda completa. Devuelve (entrada guardable, crudo), con crudo = (opciones, coords, mejores, por_dia).
    Si hay más de `max_fechas` fechas de ida, la parte en bloques de ese tamaño, los hace uno tras otro (con las
    pausas de cada fuente) y junta todo; si un bloque falla, sigue con los demás y lo avisa. Lanza ValueError
    si el país, las fechas o los días no valen, o si pasan de MAX_FECHAS fechas de ida.
    `avisar(i, n, texto)` = progreso de cada paso; `progreso(dict)` = progreso global de la búsqueda:
    {"fase", "bloque", "bloques", "hecho", "total", "pct", "aproximado"}."""
    codigo = codigo_pais(texto)
    if not codigo:
        raise ValueError(f"No reconozco el país «{texto}». Prueba con su nombre en castellano o inglés, "
                         "o el código de 2 letras.")
    dmin, dmax = _dias(dias)
    fechas = fechas_de(salida, meses, desde, hasta)
    if not fechas:
        raise ValueError("No hay ninguna fecha de salida en ese periodo (¿ya pasó?).")
    if len(fechas) > MAX_FECHAS:
        raise ValueError(f"{len(fechas)} fechas de ida son demasiadas para una búsqueda (tope {MAX_FECHAS}). "
                         "Acota el periodo o los días de salida.")
    vuelta = (vuelta or "").strip().lower()
    if vuelta in ("todos", "cualquiera"):
        vuelta = ""
    semana(vuelta)   # avisa si no entiende algún día
    solo, sin = _norm_lista(solo), _norm_lista(sin)
    con_kiwi, con_ryanair, con_wizz = filtro_fuentes(solo, sin, con_kiwi, con_ryanair, con_wizz)
    if radio is not None and radio < 0:
        raise ValueError("El radio no puede ser negativo.")
    bloques = partir(fechas, max(1, max_fechas))
    # pasos previstos de cada bloque (Kiwi); Ryanair y Wizz se suman al conocerlos, por eso es aproximado
    previstos = [len(b) + len(fechas_vuelta_de(b, dmin, dmax, vuelta or None)) for b in bloques]
    hechos = [0]    # pasos de los bloques ya terminados
    pct_max = [0.0]

    def informar(fase, k, i=0, n_bloque=None, final=False):
        if not progreso:
            return
        total = sum(previstos) - previstos[k] + (n_bloque if n_bloque is not None else previstos[k]) if bloques else 1
        hecho = hechos[0] + i
        pct = 100.0 if final else min(99.0, 100.0 * hecho / max(1, total))
        pct_max[0] = max(pct_max[0], pct)   # nunca baja aunque aparezcan pasos nuevos
        progreso({"fase": fase, "bloque": k + 1, "bloques": len(bloques), "hecho": hecho, "total": total,
                  "pct": round(pct_max[0]), "aproximado": not final})

    informar("Preparando búsqueda", 0)
    opciones, coords, avisos, hechos_ok, fallos = [], {}, [], 0, 0
    orden = ["primer", "segundo", "tercer", "cuarto", "quinto", "sexto", "séptimo", "octavo", "noveno", "décimo"]
    try:
        for k, bl in enumerate(bloques):
            nombre = f"{orden[k]} bloque" if k < len(orden) else f"bloque {k + 1}"
            cuerpo = f" ({_fecha(bl[0].isoformat())} … {_fecha(bl[-1].isoformat())})" if len(bloques) > 1 else ""
            informar(f"Consultando fechas del {nombre}{cuerpo}" if k == 0 else f"Completando el {nombre}{cuerpo}", k)

            def paso(i, n_b, texto, k=k, nombre=nombre):
                if avisar:
                    avisar(i, n_b, texto)
                informar(f"{'Consultando' if k == 0 else 'Completando'} el {nombre}: {texto}", k, i, n_b)

            try:
                op, co, av = buscar(codigo, bl, dmin, dmax, con_kiwi, con_ryanair, con_wizz, usar_cache, paso,
                                    cancelar=cancelar, vuelta=vuelta or None, radio=radio, solo=solo, sin=sin)
            except Cancelado:
                raise
            except Exception as e:   # un bloque que falla no tira los demás
                fallos += 1
                avisos.append(f"El {nombre} ({_fecha(bl[0].isoformat())} … {_fecha(bl[-1].isoformat())}) "
                              f"ha fallado y no cuenta: {str(e)[:80]}")
                hechos[0] += previstos[k]
                continue
            hechos_ok += 1
            opciones += op
            coords.update(co)
            avisos += av
            hechos[0] += previstos[k]
    except Cancelado as c:
        if hechos_ok:   # lo ya terminado se conserva
            opciones = _juntar(opciones)
            c.parcial = _entrada(codigo, texto, meses, desde, hasta, salida, dmin, dmax, vuelta, maximo, solo, sin,
                                 radio, fechas, opciones, coords,
                                 avisos + [f"Cancelada: solo {hechos_ok} de {len(bloques)} bloques terminados."], n)[0]
            c.parcial["parcial"] = True
        raise
    if hechos_ok == 0:
        raise RuntimeError("No ha podido terminar ningún bloque: " + (avisos[-1] if avisos else "sin detalle"))
    informar("Procesando resultados", len(bloques) - 1, previstos[-1], previstos[-1])
    opciones = _juntar(opciones)
    entrada, crudo = _entrada(codigo, texto, meses, desde, hasta, salida, dmin, dmax, vuelta, maximo, solo, sin,
                              radio, fechas, opciones, coords, avisos, n)
    entrada["bloques"] = len(bloques)
    entrada["bloques_fallidos"] = fallos
    informar("Búsqueda finalizada", len(bloques) - 1, final=True)
    return entrada, crudo


def _entrada(codigo, texto, meses, desde, hasta, salida, dmin, dmax, vuelta, maximo, solo, sin, radio, fechas,
             opciones, coords, avisos, n):
    """Monta la búsqueda guardable a partir de las opciones juntas. Devuelve (entrada, crudo)."""
    if maximo is not None:
        opciones = [o for o in opciones if o["total"] <= maximo]
    por_dia = por_fecha(opciones)
    mejores = _mejores(opciones, n)
    periodo = (meses or f"{desde}…{hasta}").replace(",", "+")
    extras = "".join([f"|vuelta={vuelta}" if vuelta else "", f"|max={maximo:g}" if maximo is not None else "",
                      f"|solo={','.join(solo)}" if solo else "", f"|sin={','.join(sin)}" if sin else "",
                      f"|radio={radio:g}" if radio is not None else ""])
    entrada = {
        "clave": f"{codigo}|{periodo}|{dmin}-{dmax}|{salida.lower()}{extras}",
        "vuelta": vuelta, "maximo": maximo, "solo": list(solo), "sin": list(sin), "radio": radio,
        "codigo": codigo, "pais": nombre_pais(codigo, texto), "nuevo": paises.es_nuevo(codigo),
        "periodo": periodo, "salida": salida.lower(), "dias": [dmin, dmax],
        "fechas": [f.isoformat() for f in fechas],
        "generado": datetime.now().isoformat(timespec="minutes"),
        "mejores": [resumen(o, coords) for o in mejores],
        "por_fecha": [resumen(o, coords) for o in por_dia],
        "avisos": list(dict.fromkeys(avisos))[:8],
    }
    return entrada, (opciones, coords, mejores, por_dia)


def cargar():
    """Búsquedas guardadas: {"busquedas": {clave: entrada}}."""
    try:
        d = json.loads(RUTA.read_text(encoding="utf-8"))
        d.setdefault("busquedas", {})
        return d
    except Exception:
        return {"busquedas": {}}


def guardar(entrada):
    """Guarda la búsqueda (sustituye a la misma clave); conserva las GUARDAR_MAX más recientes."""
    datos = cargar()
    datos["busquedas"].pop(entrada["clave"], None)
    datos["busquedas"][entrada["clave"]] = entrada
    vistas = sorted(datos["busquedas"].values(), key=lambda e: e["generado"])[-GUARDAR_MAX:]
    datos["busquedas"] = {e["clave"]: e for e in vistas}
    CARPETA.mkdir(exist_ok=True)
    RUTA.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ida y vuelta a un país entrando y saliendo por aeropuertos distintos")
    ap.add_argument("pais", help="Turquia, Georgia, Irlanda... (o código de 2 letras: TR)")
    ap.add_argument("--mes", help="AAAA-MM (varios con comas: 2027-04,2027-05)")
    ap.add_argument("--desde", help="AAAA-MM-DD (con --hasta)")
    ap.add_argument("--hasta", help="AAAA-MM-DD")
    ap.add_argument("--salida", default="domingo", help="día(s) de salida: domingo (defecto), sabado, 'viernes,sabado', todos")
    ap.add_argument("--dias", default="4", help="duración contando ida y vuelta (4 = domingo a miércoles; 4-5 = varias)")
    ap.add_argument("--vuelta", default="", help="día(s) de la semana de la vuelta (vacío = cualquiera)")
    ap.add_argument("--max", type=float, default=None, help="precio máximo del total ida+vuelta, en euros")
    ap.add_argument("--solo", default="", help="solo estas aerolíneas (Ryanair,Wizz)")
    ap.add_argument("--sin", default="", help="sin estas aerolíneas")
    ap.add_argument("--radio", type=float, default=None, help="km en línea recta entre entrada y salida (0 = mismo aeropuerto; vacío = 250 km por día)")
    ap.add_argument("--n", type=int, default=10, help="cuántas mejores combinaciones enseñar (10)")
    ap.add_argument("--bloque", type=int, default=BLOQUE, help=f"fechas de ida por bloque; si hay más se parte en bloques ({BLOQUE})")
    ap.add_argument("--sin-kiwi", action="store_true")
    ap.add_argument("--sin-ryanair", action="store_true")
    ap.add_argument("--sin-wizz", action="store_true")
    ap.add_argument("--sin-cache", action="store_true")
    a = ap.parse_args(argv)

    for aviso in paises.cargar()[1]:
        print("Aviso:", aviso)
    try:
        codigo = codigo_pais(a.pais)
        dmin, dmax = _dias(a.dias)
        fechas = fechas_de(a.salida, a.mes, a.desde, a.hasta)
        if codigo and fechas:
            vueltas = fechas_vuelta_de(fechas, dmin, dmax, a.vuelta)
            print(f"pais.py {VERSION}: {a.pais} ({codigo}){' 🆕 país nuevo' if paises.es_nuevo(codigo) else ''}, "
                  f"{len(fechas)} fechas de ida ({_fecha(fechas[0].isoformat())} … {_fecha(fechas[-1].isoformat())}), "
                  f"{dmin if dmin == dmax else f'{dmin}-{dmax}'} días. Unas {len(fechas) + len(vueltas)} consultas a Kiwi "
                  f"(~{(len(fechas) + len(vueltas)) * 5 / 60:.0f} min la primera vez; con caché, segundos).")
        prog = lambda i, n, d: print(f"  [{i}/{n}] {d}...        ", end="\r", flush=True)
        entrada, (opciones, coords, mejores, por_dia) = ejecutar(
            a.pais, a.mes, a.desde, a.hasta, a.salida, a.dias, a.n, a.bloque, not a.sin_kiwi,
            not a.sin_ryanair, not a.sin_wizz, not a.sin_cache, prog, vuelta=a.vuelta, maximo=a.max,
            solo=a.solo, sin=a.sin, radio=a.radio)
    except ValueError as e:
        sys.exit(str(e))
    print(" " * 60)
    if not opciones:
        print("Sin combinaciones de ida y vuelta directas en esas fechas.")
        for x in entrada["avisos"]:
            print("Aviso:", x)
        return
    print(f"\nLas {len(mejores)} mejores combinaciones (dos billetes de solo ida, directos):\n")
    for o in mejores:
        print(_linea(o, coords) + "\n")
    print("La más barata de cada fecha:")
    for o in por_dia:
        print(f"  {_fecha(o['ida'])} → {_fecha(o['vuelta'])} · {noches(o['ida'], o['vuelta'])}: {o['total']:.0f} €  ({o['entrada']} → {o['salida_ap']})")
    guardar(entrada)   # la demo (panel «Un país concreto») lo enseña
    ruta = CARPETA / f"pais_{entrada['codigo']}_{entrada['periodo']}.md"
    guardar_md(ruta, entrada["pais"], entrada["codigo"], entrada["periodo"], *entrada["dias"], mejores, por_dia,
               coords, entrada["avisos"])
    print(f"\nGuardado en {ruta.relative_to(ruta.parent.parent)} (y en la demo)")
    for x in entrada["avisos"]:
        print("Aviso:", x)
    try:   # deja la demo al día (si no está abierta no pasa nada)
        import ver_resultados
        ver_resultados.construir()
    except Exception:
        pass


if __name__ == "__main__":
    main()
