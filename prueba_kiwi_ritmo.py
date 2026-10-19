"""
prueba_kiwi_ritmo.py 0.1 — Mide qué ritmo aguanta Kiwi desde esta máquina (19-10-2026). NO escribe datos del Radar ni usa la caché.

Escalera de ritmos, cada escalón con consultas distintas (país × mes, así no se repite ninguna):
  1) una a una con pausa 5 → 3 → 2 → 1 → 0,5 s;  2) en paralelo 2, 3, 4 y 6 hilos.
Para en el primer escalón con señal de freno (error de Kiwi, 429/403, >10 % de fallos o latencia mediana >2,5× la de partida)
y NO sigue subiendo. Resultado: tabla en pantalla y en el resumen de GitHub Actions.
Uso:  python prueba_kiwi_ritmo.py [--n 20]
"""
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import kiwi

VERSION = "0.1"
PAISES = ["IT", "FR", "DE", "PT", "GR", "TR", "MA", "EG", "TH", "JP", "MX", "PE", "BR", "AR", "PL", "HU", "CZ", "NO", "SE", "IE",
          "HR", "RO", "BG", "JO", "TN", "SN", "KE", "VN", "ID", "IN"]
N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 20
ESCALERA = [("serie", 5.0, 1), ("serie", 3.0, 1), ("serie", 2.0, 1), ("serie", 1.0, 1), ("serie", 0.5, 1),
            ("paralelo", 1.0, 2), ("paralelo", 1.0, 3), ("paralelo", 0.5, 4), ("paralelo", 0.5, 6)]
_cursor = 0
_cerrojo = threading.Lock()


def siguiente():
    """País y mes distintos en cada consulta (el mes sale de 12 posibles desde el mes que viene)."""
    global _cursor
    with _cerrojo:
        i, _cursor = _cursor, _cursor + 1
    pais = PAISES[i % len(PAISES)]
    m = date.today().month + 1 + (i // len(PAISES)) % 11
    y = date.today().year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return pais, f"{y}-{m:02d}-01", f"{y}-{m:02d}-28"


def una():
    pais, d, h = siguiente()
    t = time.time()
    try:
        its = kiwi._consulta(["Airport:BCN"], [f"Country:{pais}"], d, "00:00", "23:59", 50, h, paradas=1, texto=kiwi.CONSULTA_ESC)
        return time.time() - t, None, len(its)
    except kiwi.KiwiBloqueado as e:
        return time.time() - t, str(e)[:150], 0


def escalon(modo, intervalo, hilos):
    kiwi.PAUSA = 0   # el ritmo lo marca esta prueba, no kiwi.py
    inicio, res = time.time(), []
    ultimo = [0.0]

    def lanzar(_):
        with _cerrojo:   # un solo «disparo» cada `intervalo` s, aunque haya varios hilos
            espera = intervalo - (time.time() - ultimo[0])
            if espera > 0:
                time.sleep(espera)
            ultimo[0] = time.time()
        return una()

    with ThreadPoolExecutor(hilos) as ex:
        res = list(ex.map(lanzar, range(N)))
    dur = time.time() - inicio
    lat = [r[0] for r in res if not r[1]]
    fallos = [r[1] for r in res if r[1]]
    return {"modo": modo, "pausa": intervalo, "hilos": hilos, "consultas": N, "fallos": len(fallos), "ejemplo_fallo": fallos[0] if fallos else "",
            "lat_med": statistics.median(lat) if lat else 0, "lat_max": max(lat) if lat else 0, "seg": dur, "por_min": N / dur * 60,
            "vacias": sum(1 for r in res if not r[1] and r[2] == 0)}


def main():
    filas, base = [], None
    for modo, intervalo, hilos in ESCALERA:
        f = escalon(modo, intervalo, hilos)
        base = base or f["lat_med"]
        f["freno"] = (f["fallos"] > N * 0.1 or (base and f["lat_med"] > base * 2.5))
        filas.append(f)
        print(f"{modo:8} pausa {intervalo:>3} s  hilos {hilos}: {f['por_min']:.0f} consultas/min, latencia med {f['lat_med']:.1f} s "
              f"(máx {f['lat_max']:.1f}), fallos {f['fallos']}/{N}, sin resultados {f['vacias']}"
              + (f"  ← FRENO: {f['ejemplo_fallo']}" if f["freno"] else ""), flush=True)
        if f["freno"]:
            print("Kiwi da señal de freno: no se sube más.")
            break
        time.sleep(30)   # respiro entre escalones
    ok = [f for f in filas if not f["freno"]]
    mejor = max(ok, key=lambda f: f["por_min"]) if ok else None
    resumen = ["| modo | pausa | hilos | consultas/min | latencia med (s) | fallos |", "|---|---|---|---|---|---|"]
    resumen += [f"| {f['modo']} | {f['pausa']} | {f['hilos']} | {f['por_min']:.0f} | {f['lat_med']:.1f} | {f['fallos']}/{N}{' FRENO' if f['freno'] else ''} |" for f in filas]
    resumen.append(f"\nMejor ritmo sin freno: " + (f"{mejor['modo']} pausa {mejor['pausa']} s, {mejor['hilos']} hilos = {mejor['por_min']:.0f}/min "
                                                  f"(hoy el Radar hace 12/min)" if mejor else "ninguno"))
    print("\n".join(resumen))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("\n".join(resumen) + "\n")


if __name__ == "__main__":
    main()
