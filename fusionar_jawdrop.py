"""
fusionar_jawdrop.py 0.1 — Trae las lecturas del Radar largo que ha hecho jawdrop (GitHub) y las mete en las del PC (18-10-2026).

Por cada zona y mes: si el PC no la tiene, o la de jawdrop es de un día posterior, se copia la de jawdrop; si no, se queda la del PC.
NUNCA borra nada: antes de empezar guarda una copia en resultados\\radar_larga.antes_fusion.json y al final comprueba que no falta
ninguna casilla. Guarda con guardar_lectura() (candado), así se puede ejecutar con el lector del PC funcionando.
Después reconstruye cuadricula.json y larga.json (no sube nada a Cloudflare: eso lo hace la tarea «Escapadas desplegar iPhone»).
Uso:  .venv\\Scripts\\python.exe fusionar_jawdrop.py [--seco] [--archivo ruta.json]
"""
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import radar_larga as rl

VERSION = "0.1"
AQUI = Path(__file__).resolve().parent
URL = "https://raw.githubusercontent.com/TU_USUARIO/jawdrop/main/datos/radar_larga.json"
COPIA = AQUI / "resultados" / "radar_larga.antes_fusion.json"


def traer(argv):
    if "--archivo" in argv:
        return json.loads(Path(argv[argv.index("--archivo") + 1]).read_text(encoding="utf-8"))
    req = urllib.request.Request(URL, headers={"User-Agent": "escapadas-flash/1"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def valida(e):
    return isinstance(e, dict) and isinstance(e.get("f"), str) and isinstance(e.get("combos"), list)


def main(argv):
    ajeno = traer(argv)
    if not isinstance(ajeno, dict) or not ajeno:
        sys.exit("El archivo de jawdrop está vacío o no es válido: no se toca nada.")
    propio = rl.cargar()
    pend = [(z, m, e) for z, ms in ajeno.items() if z in rl.ZONAS for m, e in ms.items()
            if valida(e) and (m not in propio.get(z, {}) or e["f"] > propio[z][m].get("f", ""))]
    nuevas = sum(1 for z, m, _ in pend if m not in propio.get(z, {}))
    print(f"Jawdrop: {sum(len(v) for v in ajeno.values())} casillas; PC: {sum(len(v) for v in propio.values())}. "
          f"Por fusionar: {len(pend)} ({nuevas} nuevas, {len(pend) - nuevas} más recientes).")
    if "--seco" in argv or not pend:
        return 0
    shutil.copy2(rl.ALMACEN, COPIA)
    for z, m, e in pend:
        actual = rl.cargar().get(z, {}).get(m)   # el lector del PC pudo escribirla mientras tanto
        if actual is None or e["f"] > actual.get("f", ""):
            rl.guardar_lectura(z, m, e)
    despues = rl.cargar()
    antes = json.loads(COPIA.read_text(encoding="utf-8"))
    perdidas = [(z, m) for z, ms in antes.items() for m in ms if m not in despues.get(z, {})]
    print(f"Ahora: {sum(len(v) for v in despues.values())} casillas. Perdidas respecto a antes: {len(perdidas)}.")
    if perdidas:
        sys.exit(f"¡FALTAN {len(perdidas)} casillas! Copia en {COPIA}; no se reconstruye nada.")
    for args in (["radar_datos.py", "--construir"], ["radar_larga.py", "--construir"]):
        subprocess.run([sys.executable, *args], cwd=AQUI, check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
