"""Precio mínimo por día de Renfe (AVE/Avlo...) Barcelona <-> Madrid, del calendario público de la portada de renfe.com.

VERSION 0.1 (17-10-2026). Llamada abierta (la hace cualquier visitante de renfe.com): sin captcha ni clave. Una petición trae
muchos días. OJO: es el PRECIO MÁS BAJO DEL DÍA (de cualquier tren), no el de un tren concreto. El de cada tren sale
de su web de venta, que pide captcha (no se salta)."""
import requests

import trenes_ouigo

VERSION = "0.1"
URL = "https://wsrestcorp.renfe.es/api/wsrviajeros/vhi_priceCalendar"
UA = "EscapadasFlash/1.0 (uso personal)"
ESTACIONES = {"BCN-MAD": ("BARCE", "MADRI"), "MAD-BCN": ("MADRI", "BARCE")}


def calendario(sentido, desde, hasta):
    """{fecha: precio mínimo (€) o None si no hay} entre `desde` y `hasta` (AAAA-MM-DD). Lanza ErrorOperador con motivo claro."""
    o, d = ESTACIONES[sentido]
    try:
        r = requests.post(URL, json={"originId": o, "destinyId": d, "initDate": desde, "endDate": hasta,
                                     "salesChannel": {"codApp": "VLP"}},
                          headers={"User-Agent": UA}, timeout=20)
    except requests.RequestException as e:
        raise trenes_ouigo.ErrorOperador("Renfe", f"calendario de precios sin respuesta ({type(e).__name__})")
    if r.status_code in (403, 429) or "captcha" in r.text[:2000].lower():
        raise trenes_ouigo.ErrorOperador("Renfe", f"calendario de precios: bloqueo/límite (HTTP {r.status_code})", r.status_code)
    if r.status_code != 200:
        raise trenes_ouigo.ErrorOperador("Renfe", f"calendario de precios: HTTP {r.status_code} {r.text[:100]}", r.status_code)
    try:
        return {x["date"]: (x["minPrice"] if x.get("minPriceAvailable") else None) for x in r.json()["journeysPriceCalendar"]}
    except (ValueError, KeyError, TypeError):
        raise trenes_ouigo.ErrorOperador("Renfe", "calendario de precios: respuesta no entendida (cambio en su web)")
