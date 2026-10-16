"""publicar_movil.py 0.1 — Publica la pantalla del iPhone (movil/flash.html) y sus datos en Cloudflare Pages.

Genera la carpeta `publicar` con: la página, el icono y los datos de Flash, Radar y Países nuevos como archivos
(los mismos que sirve servidor.py en /api/movil-…). No consulta ninguna aerolínea y no gasta nada.
El pasaporte vive en Cloudflare (functions/api/pasaporte.js + KV); aquí solo se publica su punto de partida
(`pasaporte_inicial.json`, los países y años de paises_visitados.txt). No se publican claves ni los resultados en bruto.
Con --subir, la carpeta se sube a Cloudflare Pages con wrangler (hace falta `npx wrangler login` hecho en este PC).
Uso:  .venv\\Scripts\\python.exe publicar_movil.py            (solo genera la carpeta)
      .venv\\Scripts\\python.exe publicar_movil.py --subir    (genera y sube)
"""
import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import movil_datos
import pasaporte
import servidor

VERSION = "0.3"
CARPETA = Path(__file__).resolve().parent
MOVIL = CARPETA / "movil"
SALIDA = CARPETA / "publicar"
PROYECTO = "escapadas-flash"

# Ficheros de movil/ que la página necesita (flash.html va aparte, con una marca para saber que está publicada).
ARCHIVOS_MOVIL = ["manifest.webmanifest", "icono-180.png", "icono-192.png", "icono-512.png", "mapa.json", "aeropuertos.json"]
MARCA = "<script>window.ESCAPADAS_PUBLICADA = true;</script>"
CABECERAS = "/api/*\n  Content-Type: application/json; charset=utf-8\n  Cache-Control: no-cache\n"


def _escribir_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def generar():
    """Crea la carpeta publicar\\ desde cero. Devuelve un resumen para imprimir."""
    if SALIDA.exists():
        shutil.rmtree(SALIDA)   # carpeta generada por este script; se rehace entera
    SALIDA.mkdir()

    # Antigüedad: segundos desde la última actualización (igual que /api/movil-flash), y el momento de esta copia.
    # La página suma el tiempo transcurrido desde `generado_en`, así no se queda con «hace 0 min» para siempre.
    flash = movil_datos.datos()
    flash["edad_datos"] = servidor.edad_datos()
    flash["generado_en"] = time.time()
    radar = movil_datos.datos_radar()
    paises = movil_datos.datos_paises()
    _escribir_json(SALIDA / "api" / "movil-flash", flash)
    _escribir_json(SALIDA / "api" / "movil-radar", radar)
    _escribir_json(SALIDA / "api" / "movil-paises", paises)
    _escribir_json(SALIDA / "pasaporte_inicial.json", pasaporte.datos())   # semilla: solo se usa si KV está vacío

    html = (MOVIL / "flash.html").read_text(encoding="utf-8")
    if "<head>" not in html:
        raise SystemExit("flash.html no tiene <head>: no se puede marcar como publicada")
    (SALIDA / "index.html").write_text(html.replace("<head>", "<head>\n" + MARCA, 1), encoding="utf-8")
    for nombre in ARCHIVOS_MOVIL:
        shutil.copy2(MOVIL / nombre, SALIDA / nombre)
    (SALIDA / "_headers").write_text(CABECERAS, encoding="utf-8")

    return {"domingos": len(flash.get("domingos", [])), "edad_h": None if flash["edad_datos"] is None else round(flash["edad_datos"] / 3600, 1)}


def subir():
    """Sube la carpeta a Cloudflare Pages con wrangler (desde el PC, con la sesión de wrangler ya iniciada)."""
    if "PON_AQUI" in (CARPETA / "wrangler.toml").read_text(encoding="utf-8"):
        raise SystemExit("Falta el id de KV en wrangler.toml: ejecuta «npx wrangler kv namespace create PASAPORTE» y pega el id.")
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("No encuentro «npx» (Node.js). Instálalo o revisa el PATH.")
    cmd = [npx, "wrangler", "pages", "deploy", str(SALIDA), "--project-name", PROYECTO,
           "--branch", "main", "--commit-dirty=true"]
    subprocess.run(cmd, cwd=CARPETA, check=True)


def main():
    ap = argparse.ArgumentParser(description="Genera (y opcionalmente sube) la pantalla del iPhone a Cloudflare Pages.")
    ap.add_argument("--subir", action="store_true", help="subir la carpeta a Cloudflare Pages tras generarla")
    args = ap.parse_args()
    resumen = generar()
    print(f"Carpeta lista: {SALIDA} · {resumen['domingos']} domingos · "
          f"datos de hace {resumen['edad_h']} h" if resumen["edad_h"] is not None else
          f"Carpeta lista: {SALIDA} · {resumen['domingos']} domingos · sin fecha de actualización")
    if args.subir:
        subir()
        print("Subida hecha. Abre la dirección que da wrangler (…pages.dev).")


if __name__ == "__main__":
    main()
