"""
salud_radar.py — ¿El Radar de jawdrop se mantiene al día y Kiwi no nos está frenando? Solo lee, no escribe nada (el usuario, 23-10-2026).

Mira (1) la edad de las lecturas de datos/radar_larga.json de jawdrop según la regla de frescura.py y (2) las últimas pasadas de «Radar diario»:
si terminaron, cuántas casillas leyeron y cuántas fallaron por Kiwi (502/503/«bloqueado»). Imprime ALERTA y sale con código 1 si algo no va bien.
Uso:  .venv\\Scripts\\python.exe salud_radar.py [--pasadas 4]     (necesita `gh` con sesión iniciada)
"""
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone

import frescura
import radar_larga

VERSION = "0.1"
REPO = "TU_USUARIO/jawdrop"
MARGEN = 1.5          # una lectura se da por atrasada cuando pasa 1,5 veces lo que debería valer
MAX_ATRASADAS = 0.05  # alerta si más del 5 % de las casillas están atrasadas
MAX_FALLOS = 0.15     # alerta si más del 15 % de las lecturas de una pasada fallan por Kiwi
MAX_HORAS_SIN_PASADA = 36


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:200])
    return r.stdout


def edades():
    datos = json.loads(gh("api", f"repos/{REPO}/contents/datos/radar_larga.json", "-H", "Accept: application/vnd.github.raw"))
    hoy, y, m, meses = date.today(), date.today().year, date.today().month, []
    for _ in range(12):
        meses.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    total = atrasadas = sin_leer = 0
    mas_vieja = 0
    for zid, z in radar_larga.ZONAS.items():
        for mm in meses:
            total += 1
            f = (datos.get(zid) or {}).get(mm, {}).get("f")
            if not f:
                sin_leer += 1
                continue
            edad = (hoy - date.fromisoformat(f)).days
            mas_vieja = max(mas_vieja, edad)
            vale = radar_larga.HORAS_GOTOGATE if z.get("gotogate") else frescura.horas_validas(mm, hoy)
            if edad * 24 > vale * MARGEN:
                atrasadas += 1
    return total, sin_leer, atrasadas, mas_vieja


def pasadas(n):
    out = []
    for r in json.loads(gh("run", "list", "-R", REPO, "--workflow", "radar.yml", "-L", str(n), "--json", "databaseId,conclusion,status,createdAt")):
        if r["status"] != "completed":
            continue
        log = gh("run", "view", str(r["databaseId"]), "-R", REPO, "--log")
        leidas = len(re.findall(r"leyendo Kiwi", log))
        fallos = len(re.findall(r"NO se ha leído|Kiwi bloqueado", log))
        out.append((r["createdAt"], r["conclusion"], leidas, fallos))
    return out


def main(argv):
    n = int(argv[argv.index("--pasadas") + 1]) if "--pasadas" in argv else 4
    alertas = []
    total, sin_leer, atrasadas, vieja = edades()
    print(f"Casillas: {total}; sin leer {sin_leer}; atrasadas {atrasadas} ({atrasadas / total:.1%}); la lectura más vieja tiene {vieja} días.")
    if (atrasadas + sin_leer) / total > MAX_ATRASADAS:
        alertas.append("Más del 5 % de las casillas están sin leer o atrasadas: jawdrop no da abasto.")
    ps = pasadas(n)
    ahora = datetime.now(timezone.utc)
    for creada, concl, leidas, fallos in ps:
        print(f"Pasada {creada}: {concl}; {leidas} lecturas, {fallos} fallos de Kiwi.")
    if not ps:
        alertas.append("No hay pasadas terminadas de «Radar diario».")
    else:
        horas = (ahora - datetime.fromisoformat(ps[0][0].replace("Z", "+00:00"))).total_seconds() / 3600
        if horas > MAX_HORAS_SIN_PASADA:
            alertas.append(f"Hace {horas:.0f} h de la última pasada terminada.")
        if ps[0][1] != "success":
            alertas.append(f"La última pasada terminó como «{ps[0][1]}».")
        creada, _, leidas, fallos = ps[0]
        if leidas and fallos / leidas > MAX_FALLOS:
            alertas.append(f"Kiwi falló en {fallos} de {leidas} lecturas de la última pasada: puede estar limitándonos.")
    for a in alertas:
        print("ALERTA:", a)
    print("Todo en orden." if not alertas else "")
    return 1 if alertas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
