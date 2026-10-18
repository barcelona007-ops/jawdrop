"""
lectura_por_etapas.py — Lee el Radar largo por etapas para no llenar el disco (17-10-2026).

Cada etapa: radar_larga.py --meses 6 --max 100 -> borra de la caché las respuestas de Kiwi caducadas
(cache.limpiar_kiwi) -> reconstruye la cuadrícula. Para sola si en C: quedan menos de 500 MB libres
o si una etapa ya no lee nada (todo al día). Uso: python lectura_por_etapas.py [etapas] [meses]  (por defecto 12 etapas y 6 meses)
"""
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import cache

VERSION = "0.2"
AQUI = Path(__file__).resolve().parent
MIN_LIBRE_MB = 500
POR_ETAPA = 100


def libre_mb():
    return shutil.disk_usage(AQUI).free // 2**20


def correr(args, log):
    return subprocess.run([sys.executable, *args], cwd=AQUI, stdout=log, stderr=subprocess.STDOUT, text=True).returncode


def main(etapas=12, meses=6):
    ruta = AQUI / "resultados" / "lectura_radar_log.txt"
    with open(ruta, "a", encoding="utf-8") as log:
        for n in range(1, etapas + 1):
            if libre_mb() < MIN_LIBRE_MB:
                log.write(f"PARO: quedan {libre_mb()} MB libres en C: (mínimo {MIN_LIBRE_MB}).\n")
                return 1
            log.write(f"=== Etapa {n} {datetime.now():%d/%m %H:%M} ({libre_mb()} MB libres) ===\n")
            log.flush()
            antes = ruta.stat().st_size
            correr(["radar_larga.py", "--meses", str(meses), "--max", str(POR_ETAPA)], log)
            log.write(f"Caché: borradas {cache.limpiar_kiwi_sin_compactar()} respuestas de Kiwi caducadas.\n")
            correr(["radar_datos.py", "--construir"], log)
            log.flush()
            with open(ruta, encoding="utf-8", errors="replace") as f:
                f.seek(antes)
                if "leyendo Kiwi" not in f.read():
                    log.write("Todo al día: no hay nada que leer.\n")
                    return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 12, int(sys.argv[2]) if len(sys.argv) > 2 else 6))
