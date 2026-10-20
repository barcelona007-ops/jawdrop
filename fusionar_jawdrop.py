"""
fusionar_jawdrop.py 0.3 — Trae las lecturas del Radar largo que ha hecho jawdrop (GitHub) y las mete en las del PC (18-10-2026).

Por cada zona y mes: si el PC no la tiene, o la de jawdrop es de un día posterior, se copia la de jawdrop; si no, se queda la del PC.
NUNCA borra nada: antes de empezar guarda una copia en resultados\\radar_larga.antes_fusion.json y al final comprueba que no falta
ninguna casilla. Guarda con guardar_lectura() (candado), así se puede ejecutar con el lector del PC funcionando.
Después reconstruye cuadricula.json y larga.json (no sube nada a Cloudflare: eso lo hace la tarea «Escapadas desplegar iPhone»).
Uso:  .venv\\Scripts\\python.exe fusionar_jawdrop.py [--seco] [--auto] [--archivo ruta.json]
0.2 (19-10-2026): una lectura vacía, o sin «vj» (vieja, de zona con vecinos), no pisa a una mejor; comprobación previa en memoria;
--auto para el temporizador de la Raspberry (silencioso si no hay nada, copias con fecha en resultados/copias_fusion, las últimas 24).
0.3 (20-10-2026): fusiona también el Radar semanal (datos/radar_semana.json: Ryanair/Wizz/Kiwi con directo, el que lee jawdrop con radar_datos.py).
Mismo trato: solo añade lo que falta o lo de un día posterior, copia antes, comprobación de que no se pierde ningún país-mes, escritura atómica.
"""
import json
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import radar_datos as rd
import radar_larga as rl

VERSION = "0.3"
AQUI = Path(__file__).resolve().parent
URL = "https://raw.githubusercontent.com/TU_USUARIO/jawdrop/main/datos/radar_larga.json"
COPIA = AQUI / "resultados" / "radar_larga.antes_fusion.json"
URL_SEMANA = "https://raw.githubusercontent.com/TU_USUARIO/jawdrop/main/datos/radar_semana.json"
COPIA_SEMANA = AQUI / "resultados" / "radar_semana.antes_fusion.json"


def traer(argv):
    if "--archivo" in argv:
        return json.loads(Path(argv[argv.index("--archivo") + 1]).read_text(encoding="utf-8"))
    req = urllib.request.Request(URL, headers={"User-Agent": "escapadas-flash/1"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def valida(e):
    return isinstance(e, dict) and isinstance(e.get("f"), str) and isinstance(e.get("combos"), list)


def mejor(actual, ajena):
    """¿Sustituye la casilla ajena a la propia? Solo si es de un día posterior Y no tiene menos información:
    una lectura vacía nunca pisa a una con precios, ni una sin «vj» (lectura vieja de zona con vecinos) a una que lo tiene."""
    if actual is None:
        return True
    if ajena["f"] <= actual.get("f", ""):
        return False
    if actual.get("combos") and not ajena["combos"]:
        return False
    if actual.get("vj") and not ajena.get("vj"):
        return False
    return True


def reconstruir(auto):
    for args in (["radar_datos.py", "--construir"], ["radar_larga.py", "--construir"]):
        subprocess.run([sys.executable, *args], cwd=AQUI, check=False, stdout=subprocess.DEVNULL if auto else None)


def mejor_semana(actual, ajena):
    """Lectura semanal (mes → país → {p, f, …}): la ajena entra si falta, o si es de un día posterior y no trae menos información."""
    if not isinstance(ajena, dict) or not isinstance(ajena.get("f"), str):
        return False
    if actual is None:
        return True
    if ajena["f"] <= actual.get("f", ""):
        return False
    return not (actual.get("p") is not None and ajena.get("p") is None)


def fusionar_semana(argv, auto):
    """Devuelve cuántos país-mes ha fusionado. Un fallo aquí no debe impedir la fusión del Radar largo."""
    try:
        if "--archivo-semana" in argv:
            ajeno = json.loads(Path(argv[argv.index("--archivo-semana") + 1]).read_text(encoding="utf-8"))
        else:
            req = urllib.request.Request(URL_SEMANA, headers={"User-Agent": "escapadas-flash/1"})
            ajeno = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    except Exception as e:
        print(f"Radar semanal de jawdrop no disponible ({e}): no se toca.")
        return 0
    if not isinstance(ajeno, dict) or not ajeno:
        print("Radar semanal de jawdrop vacío o no válido: no se toca.")
        return 0
    propio = rd.cargar()
    pend = [(m, c, e) for m, paises in ajeno.items() if isinstance(paises, dict) for c, e in paises.items()
            if mejor_semana((propio.get(m) or {}).get(c), e)]
    if not pend:
        return 0
    nuevas = sum(1 for m, c, _ in pend if c not in (propio.get(m) or {}))
    print(f"{datetime.now():%d-%m %H:%M} Radar semanal: jawdrop {sum(len(v) for v in ajeno.values() if isinstance(v, dict))} país-mes; "
          f"propios: {sum(len(v) for v in propio.values() if isinstance(v, dict))}. Por fusionar: {len(pend)} ({nuevas} nuevos, {len(pend) - nuevas} más recientes).")
    if "--seco" in argv:
        return 0
    previsto = {m: dict(v) for m, v in propio.items() if isinstance(v, dict)}
    for m, c, e in pend:
        previsto.setdefault(m, {})[c] = e
    if any(c not in previsto.get(m, {}) for m, v in propio.items() if isinstance(v, dict) for c in v):
        print("Radar semanal: comprobación previa fallida (se perdería algo): no se escribe nada.")
        return 0
    if auto:
        carpeta = COPIA_SEMANA.parent / "copias_fusion"
        carpeta.mkdir(parents=True, exist_ok=True)
        copia = carpeta / f"radar_semana.{datetime.now():%Y%m%d_%H%M}.json"
        if rd.ALMACEN.exists():
            shutil.copy2(rd.ALMACEN, copia)
        for vieja in sorted(carpeta.glob("radar_semana.*.json"))[:-24]:
            vieja.unlink()
    else:
        copia = COPIA_SEMANA
        if rd.ALMACEN.exists():
            shutil.copy2(rd.ALMACEN, copia)
    # se relee justo antes de escribir (por si cambió) y se escribe en un archivo aparte que luego sustituye al bueno
    final = rd.cargar()
    for m, c, e in pend:
        if mejor_semana((final.get(m) or {}).get(c), e):
            final.setdefault(m, {})[c] = e
    if any(c not in final.get(m, {}) for m, v in propio.items() if isinstance(v, dict) for c in v):
        print("Radar semanal: comprobación final fallida: no se escribe nada.")
        return 0
    tmp = rd.ALMACEN.with_suffix(".tmp")
    tmp.write_text(json.dumps(final, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(rd.ALMACEN)
    print(f"Radar semanal ahora: {sum(len(v) for v in final.values() if isinstance(v, dict))} país-mes. Perdidos: 0.")
    return len(pend)


def main(argv):
    auto = "--auto" in argv   # desde el temporizador: sin ruido si no hay nada y copia con fecha (se conservan las últimas 24)
    semana = fusionar_semana(argv, auto)
    ajeno = traer(argv)
    if not isinstance(ajeno, dict) or not ajeno:
        sys.exit("El archivo de jawdrop está vacío o no es válido: no se toca nada.")
    propio = rl.cargar()
    pend = [(z, m, e) for z, ms in ajeno.items() if z in rl.ZONAS for m, e in ms.items()
            if valida(e) and mejor(propio.get(z, {}).get(m), e)]
    nuevas = sum(1 for z, m, _ in pend if m not in propio.get(z, {}))
    if auto and not pend:
        if semana and "--seco" not in argv:
            reconstruir(auto)
        return 0
    print(f"{datetime.now():%d-%m %H:%M} Jawdrop: {sum(len(v) for v in ajeno.values())} casillas; propias: {sum(len(v) for v in propio.values())}. "
          f"Por fusionar: {len(pend)} ({nuevas} nuevas, {len(pend) - nuevas} más recientes).")
    if "--seco" in argv or not pend:
        if semana and "--seco" not in argv:
            reconstruir(auto)
        return 0
    # Comprobación ANTES de escribir: el resultado en memoria tiene que contener todas las casillas propias.
    previsto = {z: dict(ms) for z, ms in propio.items()}
    for z, m, e in pend:
        previsto.setdefault(z, {})[m] = e
    faltan = [(z, m) for z, ms in propio.items() for m in ms if m not in previsto.get(z, {})]
    if faltan or sum(len(v) for v in previsto.values()) < sum(len(v) for v in propio.values()):
        sys.exit(f"Comprobación previa fallida ({len(faltan)} casillas se perderían): no se escribe nada.")
    if auto:
        carpeta = COPIA.parent / "copias_fusion"
        carpeta.mkdir(parents=True, exist_ok=True)
        copia = carpeta / f"radar_larga.{datetime.now():%Y%m%d_%H%M}.json"
        shutil.copy2(rl.ALMACEN, copia)
        for vieja in sorted(carpeta.glob("radar_larga.*.json"))[:-24]:
            vieja.unlink()
    else:
        copia = COPIA
        shutil.copy2(rl.ALMACEN, copia)
    for z, m, e in pend:
        if mejor(rl.cargar().get(z, {}).get(m), e):   # el lector pudo escribirla mientras tanto
            rl.guardar_lectura(z, m, e)
    despues = rl.cargar()
    antes = json.loads(copia.read_text(encoding="utf-8"))
    perdidas = [(z, m) for z, ms in antes.items() for m in ms if m not in despues.get(z, {})]
    print(f"Ahora: {sum(len(v) for v in despues.values())} casillas. Perdidas respecto a antes: {len(perdidas)}.")
    if perdidas:
        sys.exit(f"¡FALTAN {len(perdidas)} casillas! Copia en {copia}; no se reconstruye nada.")
    reconstruir(auto)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
