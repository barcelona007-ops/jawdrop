"""Cliente mínimo de Iryo (la misma búsqueda que hace iryo.eu al pulsar «Buscar»): trenes de un día con hora y precio mínimo.

VERSION 0.1 (17-10-2026). Cadena abierta, sin captcha ni cuenta: 1) GET `api.iryo.eu/b2c/config/sales-channel` da el `cfgToken` del día, 2) POST `availability/search`;
las dos con la clave pública de la web (`apiManager` de su config.json, la misma para todo visitante). OJO: la WEB `iryo.eu` (Cloudflare) da 403 a
programas sin navegador y NO se toca: solo se usa la API, que contesta. Si la API pusiera captcha/Turnstile, o un 403/429, o rechazara la clave
(401/403: la habrán cambiado; hay que releerla de la config.json en un navegador), se para y se avisa. Errores con operador y motivo."""
import uuid

import requests

from trenes_ouigo import ErrorOperador

VERSION = "0.1"
WEB = "https://iryo.eu"
API = "https://api.iryo.eu/b2c"
CLAVE = "7c9b9b1ea0fe4f0c9d1739fcbf8b5438"   # clave pública de iryo.eu (apiManager), vista el 17-10-2026
UA = "EscapadasFlash/1.0 (uso personal)"
BCN, MAD = "71801", "60000"   # Barcelona-Sants, Madrid-Atocha


def _chk(r, que):
    if r.status_code in (403, 429) or "turnstile" in r.text[:3000].lower() or "captcha" in r.text[:3000].lower():
        raise ErrorOperador("Iryo", f"{que}: bloqueo/límite o captcha (HTTP {r.status_code})", r.status_code)
    if r.status_code != 200:
        raise ErrorOperador("Iryo", f"{que}: HTTP {r.status_code} {r.text[:120]}", r.status_code)
    return r


class Iryo:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "referer": WEB + "/", "accept-language": "es-ES"})
        self.clave, self.cfg = CLAVE, None

    def _cab(self):
        return {"ocp-apim-subscription-key": self.clave, "request-channel": "WEB", "accept": "application/json",
                "x-request-id": str(uuid.uuid4()), "x-pwa-sessid": self.sess}

    def preparar(self):
        self.sess = str(uuid.uuid4())
        try:
            self.cfg = _chk(self.s.get(API + "/config/sales-channel", headers=self._cab(), timeout=20), "configuración de venta (¿clave pública cambiada?)").json()["cfgToken"]
        except (KeyError, ValueError):
            raise ErrorOperador("Iryo", "configuración: respuesta no entendida (cambio en su web)")

    def dia(self, fecha, origen=BCN, destino=MAD):
        """[{sale "HH:MM", llega "HH:MM", precio (mínimo de sus tarifas) o None si agotado}] de un día."""
        if not self.cfg:
            self.preparar()
        r = _chk(self.s.post(API + "/availability/search", timeout=30, headers=self._cab(),
                             json={"cfgToken": self.cfg, "currency": "EUR", "passengers": [{"id": "passenger_1", "type": "AD"}],
                                   "travels": [{"origin": origen, "destination": destino, "direction": "outbound", "departure": fecha}]}),
                 "búsqueda")
        try:
            rutas = r.json()["data"]["offer"]["travels"][0]["routes"]
            out = []
            for ru in rutas:
                if ru.get("transfers"):
                    continue   # solo trenes directos
                l = ru["legs"][0]
                precios = [b["price"] for b in ru.get("bundles", []) if b.get("price") is not None]
                out.append({"sale": l["departure_station"]["departure_timestamp"][11:16],
                            "llega": l["arrival_station"]["arrival_timestamp"][11:16], "precio": min(precios) if precios else None})
            return sorted(out, key=lambda t: t["sale"])
        except (KeyError, ValueError, TypeError, IndexError):
            raise ErrorOperador("Iryo", "búsqueda: respuesta no entendida (cambio en su web)")
