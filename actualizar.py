r"""
actualizar.py — Deja los precios de Jawdrop frescos sin abrir la página (para la tarea diaria).

Hace lo mismo que el botón «Actualizar todos (gratis)» de la demo: vuelve a leer Ryanair, Wizz y Kiwi para
todos los domingos que ya tienen resultados y reconstruye la página. Vueling se queda con lo guardado (no gasta
SerpApi). Siempre despacio y por la caché. Si los datos tienen menos de `--horas` horas (6 por defecto) no hace
nada, así que se puede programar varias veces al día sin gastar consultas de más.

Uso:
  .venv\Scripts\python.exe actualizar.py              (solo si los datos pasan de 6 horas)
  .venv\Scripts\python.exe actualizar.py --horas 0    (forzar)
"""
import argparse
import sys
import time
from datetime import datetime

import servidor

VERSION = "0.1"


def main():
    ap = argparse.ArgumentParser(description="Refresca los precios de Jawdrop sin abrir la página.")
    ap.add_argument("--horas", type=float, default=servidor.HORAS_FRESCO,
                    help="no hacer nada si los datos tienen menos de tantas horas (por defecto 6)")
    a = ap.parse_args()
    ahora = f"{datetime.now():%d-%m-%Y %H:%M}"
    edad = servidor.edad_datos()
    if edad is None:
        sys.exit(f"[{ahora}] No hay resultados: ejecuta antes escapadas.py --mes AAAA-MM")
    if edad < a.horas * 3600:
        print(f"[{ahora}] Datos de hace {edad / 3600:.1f} h: ya están frescos, no hago nada.")
        return
    t, error = servidor.lanzar("actualizar", [], auto=True)
    if error:
        sys.exit(f"[{ahora}] {error}")
    print(f"[{ahora}] actualizar.py {VERSION}: actualizando {len(servidor.domingos_con_datos())} domingos…")
    while t["estado"] == "corriendo":
        time.sleep(2)
    for av in t.get("avisos", []):
        print("  AVISO:", av)
    if t["estado"] != "hecho":
        sys.exit(f"[{datetime.now():%d-%m-%Y %H:%M}] Error: {t['mensaje']}")
    print(f"[{datetime.now():%d-%m-%Y %H:%M}] Listo en {(t['fin'] - t['inicio']) / 60:.1f} min.")


if __name__ == "__main__":
    main()
