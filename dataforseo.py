r"""
dataforseo.py — Google Hotels por DataForSEO para Jawdrop (EXPERIMENTAL).

Lista de alojamientos de una ciudad (hoteles o apartamentos) con precio por noche, nota y nº de
opiniones. Usa la COLA normal (task_post + task_get): ~0,0008 $ por cada 18 resultados, tarda de segundos
a unos 45 min. Todo pasa por la caché (`cache.py`): el id de la tarea se guarda, así que repetir el
comando NO paga dos veces y puede recoger una tarea que quedó pendiente. Las claves salen de .env
(DATAFORSEO_LOGIN y DATAFORSEO_PASSWORD, config.py); nunca se muestran.

Uso de prueba:
  .venv\Scripts\python.exe dataforseo.py 38.1157,13.3615 2026-11-01 2026-11-02 [--apartamentos] [--espera 15]
"""
import math
import sys
import time

import requests

import cache
import config

VERSION = "0.3"
BASE = "https://api.dataforseo.com/v3/business_data/google/hotel_searches"
HORAS_CACHE = 12
HORAS_ID = 48          # cuánto se recuerda el id de una tarea pendiente
PAUSA_SONDEO = 20      # segundos entre comprobaciones


class DataForSEOError(Exception):
    pass


class SinSaldo(DataForSEOError):
    """El crédito se ha acabado (o la cuenta pide pago): hay que dejar de consultar sin molestar."""


NOTA_MIN5 = 3.5        # nota de Google sobre 5 (≈ 7/10, aunque es otra población)
MIN_OPINIONES = 20
MAX_KM = 3.0
# Google da el precio de la CAMA en dormitorio de los hostels (Marrakech 7 €, Tánger 6 €, Londres 11 €):
# no sirve para quien no duerme en litera, y la lista no dice qué habitación es. Se excluyen por el nombre.
_HOSTEL = ("hostel", "ostello", "ostel", "hostal", "albergue", "backpack", "capsule", "dorm", "youth",
           "st christopher", "generator", "pub", "arms", "rose & crown")


def _auth():
    return config.dataforseo_auth()


def _tarea_de(r):
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code == 402 or str(j.get("status_code", "")).startswith("402"):
        raise SinSaldo(f"DataForSEO sin saldo: {j.get('status_code')} {j.get('status_message')}")
    if not r.ok and j.get("status_message"):          # p. ej. 403 «verifica tu cuenta»
        raise DataForSEOError(f"DataForSEO: {j.get('status_code')} {j.get('status_message')}")
    r.raise_for_status()
    if j.get("status_code") != 20000 or not j.get("tasks"):
        raise DataForSEOError(f"DataForSEO: {j.get('status_code')} {j.get('status_message')}")
    t = j["tasks"][0]
    if str(t.get("status_code", "")).startswith("402"):
        raise SinSaldo(f"DataForSEO sin saldo: {t.get('status_code')} {t.get('status_message')}")
    return t


def saldo():
    """Crédito que queda en dólares (consulta gratuita) o None si no se puede saber.
    El campo `cost` de las tareas sale siempre 0: el saldo es la única medida real del gasto."""
    try:
        r = requests.get("https://api.dataforseo.com/v3/appendix/user_data", auth=_auth(), timeout=30)
        return float(r.json()["tasks"][0]["result"][0]["money"]["balance"])
    except (config.FaltaClave, requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return None


def cuerpo(coordenada, entrada, salida, apartamentos=False, profundidad=36, orden="lowest_price",
           nota_min=3.5, moneda="EUR"):
    c = {"location_coordinate": coordenada, "language_code": "es", "check_in": entrada,
         "check_out": salida, "adults": 1, "currency": moneda, "sort_by": orden, "depth": profundidad}
    if nota_min:
        c["min_rating"] = nota_min
    if apartamentos:
        c["is_vacation_rentals"] = True
    return c


def _publicar(c):
    r = requests.post(BASE + "/task_post", json=[c], auth=_auth(), timeout=60)
    t = _tarea_de(r)
    if t.get("status_code") != 20100:
        raise DataForSEOError(f"DataForSEO no creó la tarea: {t.get('status_code')} {t.get('status_message')}")
    return t["id"]


def _recoger(id_tarea):
    """None si aún no está lista; el resultado si lo está."""
    r = requests.get(f"{BASE}/task_get/{id_tarea}", auth=_auth(), timeout=60)
    r.raise_for_status()
    j = r.json()
    t = (j.get("tasks") or [{}])[0]
    codigo = t.get("status_code")
    if codigo == 20000:
        return t
    if codigo in (20100, 40601, 40602):     # creada / en cola / en proceso
        return None
    raise DataForSEOError(f"DataForSEO: {codigo} {t.get('status_message')}")


def buscar(c, espera_min=15, usar_cache=True):
    """Resultado de la tarea (dict con 'result'). Espera hasta `espera_min` minutos; si no llega, lanza
    TimeoutError y deja el id guardado: repetir el mismo comando lo recoge sin pagar de nuevo."""
    def real():
        id_tarea = cache.con_cache(["dataforseo", "id", c], HORAS_ID, lambda: _publicar(c), usar_cache)
        limite = time.time() + espera_min * 60
        while True:
            t = _recoger(id_tarea)
            if t is not None:
                return t
            if time.time() > limite:
                raise TimeoutError(f"La tarea {id_tarea} sigue en cola; vuelve a lanzar el mismo comando "
                                   f"más tarde (no se paga otra vez).")
            time.sleep(PAUSA_SONDEO)

    return cache.con_cache(["dataforseo", "lista", c], HORAS_CACHE, real, usar_cache)


def _km(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def alojamientos(tarea, centro=None):
    """Lista simple: nombre, estrellas, nota (sobre 5 en Google), opiniones, precio/noche, km al centro."""
    salida = []
    for res in tarea.get("result") or []:
        for it in res.get("items") or []:
            rev = it.get("reviews") or {}
            pr = it.get("prices") or {}
            loc = it.get("location") or {}
            km = None
            if centro and loc.get("latitude") is not None:
                km = _km(centro[0], centro[1], loc["latitude"], loc["longitude"])
            salida.append({"nombre": it.get("title"), "estrellas": it.get("stars"),
                           "nota5": rev.get("value"), "opiniones": rev.get("votes_count"),
                           "precio": pr.get("price"), "sin_descuento": pr.get("price_without_discount"),
                           "km": km, "pago": it.get("is_paid"), "id": it.get("hotel_identifier")})
    return salida


def estimar(coordenada, entrada, salida, usar_cache=True):
    """Nivel de precio por noche de una ciudad con Google Hotels (2 listas: hoteles y apartamentos).

    Criba: con precio, nota ≥ 3,5/5, ≥ 20 opiniones, ≤ 3 km del centro dado y sin litera ni baño
    compartido por el nombre (hoteles.clasificar). Se enseñan los 3 más baratos; el nivel es su MEDIANA.
    Precio tal cual lo da Google (por noche, sin factor). Devuelve None si no hay candidatos.
    Puede lanzar SinSaldo. Coste ≈ 0,002 $ por lista, 2 listas por ciudad y noche; en caché 12 h.
    """
    import statistics
    from datetime import datetime
    import hoteles
    noches = max(1, (datetime.strptime(salida, "%Y-%m-%d") - datetime.strptime(entrada, "%Y-%m-%d")).days)
    centro = tuple(float(x) for x in coordenada.split(","))
    cand = []
    for apart in (False, True):
        t = buscar(cuerpo(coordenada, entrada, salida, apartamentos=apart), usar_cache=usar_cache)
        for a in alojamientos(t, centro):
            nombre = a["nombre"] or ""
            if not a["precio"] or a["nota5"] is None or a["nota5"] < NOTA_MIN5:   # precio 0 = sin disponibilidad
                continue
            if (a["opiniones"] or 0) < MIN_OPINIONES or a["km"] is None or a["km"] > MAX_KM:
                continue
            if any(w in nombre.lower() for w in _HOSTEL):
                continue
            if not hoteles.clasificar(nombre):
                continue
            cand.append({"nombre": nombre, "nota5": round(a["nota5"], 1), "opiniones": a["opiniones"],
                         "km": round(a["km"], 1), "porNoche": float(a["precio"]),
                         "apartamento": apart})
    vistos, unicos = set(), []
    for c in sorted(cand, key=lambda c: c["porNoche"]):
        if c["nombre"] not in vistos:
            vistos.add(c["nombre"])
            unicos.append(c)
    if not unicos:
        return None
    top = unicos[:3]
    por_noche = statistics.median(c["porNoche"] for c in top)
    return {"porNoche": round(por_noche, 2), "total": round(por_noche * noches, 2), "noches": noches,
            "candidatos": len(unicos), "sugerencias": top}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 3:
        sys.exit(__doc__)
    espera = 15
    if "--espera" in sys.argv:
        espera = float(sys.argv[sys.argv.index("--espera") + 1])
        args = [a for a in args if a != str(sys.argv[sys.argv.index("--espera") + 1])]
    coord, entrada, salida = args[:3]
    apart = "--apartamentos" in sys.argv
    centro = tuple(float(x) for x in coord.split(","))
    try:
        t = buscar(cuerpo(coord, entrada, salida, apartamentos=apart), espera_min=espera)
    except (config.FaltaClave, DataForSEOError, TimeoutError) as e:
        sys.exit(str(e))
    print(f"coste de la tarea: {t.get('cost')} $")
    lista = alojamientos(t, centro)
    print(f"{len(lista)} alojamientos ({'apartamentos' if apart else 'hoteles'}), {entrada} → {salida}")
    for a in lista:
        km = f"{a['km']:.1f} km" if a["km"] is not None else "-"
        print(f"{a['precio'] or '-':>5} €  nota {a['nota5'] or '-'}/5 ({a['opiniones'] or 0} op.)  {km:>7}  "
              f"{a['nombre']}")
