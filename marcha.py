"""marcha.py — avisa a la página del iPhone de cómo va el Radar («mes 3 de 12»), para que lo vea mientras busca.

Lo usan radar_datos.py (fuente «semana») y radar_larga.py (fuente «larga»), da igual si corren en el PC o en GitHub.
Solo manda cifras y un texto corto; si no hay red o falla, no pasa nada (el Radar sigue como siempre).
"""
import json
import os
import urllib.request

VERSION = "0.2"
URL = (os.environ.get("ESCAPADAS_URL") or "") + "/api/radar-marcha"


def avisar(fuente, hecho, total, texto="", fin=False):
    cuerpo = json.dumps({"fuente": fuente, "hecho": hecho, "total": total, "texto": texto, "fin": fin}).encode("utf-8")
    req = urllib.request.Request(URL, data=cuerpo, method="POST", headers={"X-Escapadas": "radar", "Content-Type": "application/json", "User-Agent": "escapadas-flash/1"})
    try:
        urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        pass   # la marcha es un extra: nunca debe romper una lectura
