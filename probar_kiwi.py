r"""
probar_kiwi.py 0.1 — Prueba CONTROLADA de cuánto aguanta Kiwi, sin forzarlo.

Hace tandas de consultas reales (sin caché) a Kiwi, cada vez más largas, siempre con la pausa normal
(`kiwi.PAUSA`, 5 s): NO acorta pausas ni pide en paralelo. Se para solo si Kiwi responde con un error,
con un límite o con resultados vacíos seguidos. Apunta, por consulta: tiempo, resultado, nº de vuelos y error.
Escribe `resultados\kiwi_limites.md` (resumen) y `resultados\kiwi_limites.csv` (una fila por consulta).

Uso:
  .venv\Scripts\python.exe probar_kiwi.py [--tandas 6,12,24,48] [--pais TR]
"""
import argparse
import csv
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import kiwi

VERSION = "0.1"
CARPETA = Path(__file__).resolve().parent / "resultados"
VACIAS_SEGUIDAS = 4   # si salen tantas respuestas vacías seguidas, se para (probablemente algo va mal)


def una(pais, dia, filas, tanda):
    t0 = time.time()
    estado, n, error = "ok", 0, ""
    try:
        its = kiwi._consulta(["Airport:BCN"], [f"Country:{pais}"], dia.isoformat(), "00:00", "23:59", 50)
        n = len(its)
        if n == 0:
            estado = "vacía"
    except kiwi.KiwiBloqueado as e:
        estado, error = "error", str(e)[:200]
    seg = round(time.time() - t0, 1)
    filas.append({"hora": datetime.now().strftime("%H:%M:%S"), "tanda": tanda, "dia": dia.isoformat(), "estado": estado,
                  "vuelos": n, "segundos": seg, "error": error})
    return estado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tandas", default="6,12,24,48")
    ap.add_argument("--pais", default="TR")
    a = ap.parse_args()
    tandas = [int(x) for x in a.tandas.split(",")]
    filas, resumen, parar = [], [], False
    dia = date.today() + timedelta(days=14)   # fechas distintas en todas las consultas
    inicio = time.time()
    for k, n in enumerate(tandas, 1):
        t0, vacias, errores = time.time(), 0, 0
        for _ in range(n):
            est = una(a.pais, dia, filas, k)
            dia += timedelta(days=1)
            vacias = vacias + 1 if est == "vacía" else 0
            errores += est == "error"
            if est == "error" or vacias >= VACIAS_SEGUIDAS:
                parar = True
                break
        seg = time.time() - t0
        ok = sum(1 for f in filas if f["tanda"] == k and f["estado"] == "ok")
        hechas = sum(1 for f in filas if f["tanda"] == k)
        resumen.append((k, n, hechas, ok, errores, round(seg), "terminó bien" if not parar else "PARADA"))
        print(f"Tanda {k}: {hechas}/{n} consultas, {ok} con vuelos, {errores} errores, {seg:.0f} s")
        if parar:
            break
    CARPETA.mkdir(exist_ok=True)
    with open(CARPETA / "kiwi_limites.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    md = [f"# Prueba de límites de Kiwi — {datetime.now():%d-%m-%Y %H:%M}", "",
          f"País {a.pais}, un día de ida por consulta, pausa {kiwi.PAUSA} s (la normal). Total {len(filas)} consultas "
          f"en {round(time.time() - inicio)} s.", "", "| Tanda | Previstas | Hechas | Con vuelos | Errores | Segundos | Resultado |",
          "|---|---|---|---|---|---|---|"]
    md += [f"| {' | '.join(str(x) for x in r)} |" for r in resumen]
    err = [f for f in filas if f["estado"] == "error"]
    md += ["", "Errores:" if err else "Sin errores, sin avisos de cuota."] + [f"- {f['dia']}: {f['error']}" for f in err]
    (CARPETA / "kiwi_limites.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("Guardado en resultados\\kiwi_limites.md")


if __name__ == "__main__":
    main()
