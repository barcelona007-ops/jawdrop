"""Cliente mínimo de Ouigo (API web de venta). Una petición = un día, con horas y precios.

VERSION 0.1. No usa la librería `ouigo` de PyPI (rota desde que Ouigo cambió sus estaciones).
Errores: ErrorOperador con el motivo en claro (bloqueo, límite, cambio de la web...)."""
import json
import requests

VERSION = "0.1"
BASE = "https://mdw02.api-es.ouigo.com/api"
UA = "EscapadasFlash/1.0 (uso personal)"
BCN, MAD = "7171801", "MT1"  # Barcelona-Sants, Madrid (todas las estaciones)


class ErrorOperador(Exception):
    def __init__(self, operador, motivo, codigo=None):
        super().__init__(f"{operador}: {motivo}")
        self.operador, self.motivo, self.codigo = operador, motivo, codigo


def _chk(r, que):
    if r.status_code in (403, 429) or "captcha" in r.text[:2000].lower():
        raise ErrorOperador("Ouigo", f"{que}: bloqueo/límite (HTTP {r.status_code})", r.status_code)
    if r.status_code != 200:
        raise ErrorOperador("Ouigo", f"{que}: HTTP {r.status_code} {r.text[:120]}", r.status_code)
    return r


class Ouigo:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.token = None

    def login(self):
        r = _chk(self.s.post(f"{BASE}/Token/login", timeout=15, json={
            "username": "ouigo.web", "password": "SquirelWeb!2020"}), "token")
        self.token = r.json().get("token")
        if not self.token:
            raise ErrorOperador("Ouigo", "token: respuesta sin token (cambio en su web)")

    def estaciones(self):
        return _chk(self.s.get(f"{BASE}/Data/GetStations", timeout=15), "estaciones").json()

    def dia(self, fecha, origen=BCN, destino=MAD):
        """Lista de trenes de un día: [{salida, llegada, precio, tren}] (solo con plaza)."""
        if not self.token:
            self.login()
        r = _chk(self.s.post(f"{BASE}/Sale/journeysearch", timeout=20,
                             headers={"authorization": "Bearer " + self.token},
                             json={"origin": origen, "destination": destino, "outbound_date": fecha,
                                   "passengers": [{"discount_cards": [], "disability_type": "NH", "type": "A"}]}),
                 "búsqueda")
        return r.json()
