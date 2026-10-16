"""subir_cache.py 1.2 — Copia los precios ya buscados en este PC (cache.sqlite) a la base D1 de Cloudflare.

Así la nube parte con lo que el PC ya consultó (cada precio con la fecha en que se consultó) y no repite búsquedas.
No consulta ninguna aerolínea y no gasta SerpApi. Hace falta `npx wrangler login` hecho en este PC (como publicar_movil.py).
Pocos archivos grandes y sin pedir confirmación (`--yes`): no hay que estar delante.
Uso:  .venv\\Scripts\\python.exe subir_cache.py            (sube lo de los últimos 60 días)
      .venv\\Scripts\\python.exe subir_cache.py --dias 30  (otro plazo)
      .venv\\Scripts\\python.exe subir_cache.py --solo-generar   (crea los archivos SQL y no sube nada)
"""
import argparse
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

VERSION = "1.2"
CARPETA = Path(__file__).resolve().parent
BASE = "escapadas"
SALIDA = CARPETA / "resultados" / "cache_d1.sql"
MAX_ARCHIVO = 5_000_000  # caracteres por archivo SQL: pocos archivos, para que sean pocas subidas
LARGO = 40000  # D1 rechaza sentencias de más de ~100 KB: las respuestas grandes se parten en trozos (tabla `trozos`)


def sql_texto(valor):
    return "'" + str(valor).replace("'", "''") + "'"


def generar(dias):
    ruta = CARPETA / "cache.sqlite"
    if not ruta.exists():
        sys.exit("No encuentro cache.sqlite en esta carpeta: no hay nada que subir.")
    desde = time.time() - dias * 86400
    con = sqlite3.connect(ruta)
    filas = con.execute("SELECT clave, guardado, json FROM respuestas WHERE guardado >= ? ORDER BY guardado",
                        (desde,)).fetchall()
    con.close()
    SALIDA.parent.mkdir(exist_ok=True)
    for viejo in SALIDA.parent.glob("cache_d1_*.sql"):
        viejo.unlink()
    archivos = []
    f = None
    escrito = 0
    for clave, guardado, datos in filas:
        if f is None or escrito > MAX_ARCHIVO:
            if f:
                f.close()
            archivo = SALIDA.with_name(f"cache_d1_{len(archivos):03d}.sql")
            f = open(archivo, "w", encoding="utf-8")
            archivos.append(archivo)
            escrito = 0
        partes = [datos[j:j + LARGO] for j in range(0, len(datos), LARGO)] if len(datos) > LARGO else []
        f.write(f"DELETE FROM trozos WHERE clave = {sql_texto(clave)};\n")
        f.write(f"INSERT OR REPLACE INTO respuestas (clave, guardado, json, trozos) VALUES "
                f"({sql_texto(clave)}, {guardado!r}, {sql_texto('' if partes else datos)}, {len(partes)});\n")
        for n, texto in enumerate(partes):
            f.write(f"INSERT INTO trozos (clave, n, texto) VALUES ({sql_texto(clave)}, {n}, {sql_texto(texto)});\n")
        escrito += len(datos) + 200
    if f:
        f.close()
    return len(filas), archivos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=60)
    ap.add_argument("--solo-generar", action="store_true")
    a = ap.parse_args()
    n, archivos = generar(a.dias)
    print(f"subir_cache {VERSION}: {n} respuestas de los últimos {a.dias} días en {len(archivos)} archivos.")
    if a.solo_generar or not archivos:
        return
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    for k, archivo in enumerate(archivos, 1):
        r = subprocess.run([npx, "wrangler", "d1", "execute", BASE, "--remote", "--yes", f"--file={archivo}"],
                           cwd=CARPETA)
        if r.returncode:
            sys.exit(f"Falló el archivo {k} de {len(archivos)}. Se puede repetir el comando: no duplica nada.")
        print(f"  subido {k} de {len(archivos)}")
    print("Hecho. La nube ya conoce estos precios.")


if __name__ == "__main__":
    main()
