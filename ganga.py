"""
ganga.py — ¿Este precio es una ganga de verdad? (Radar único, regla del usuario, 14-10-2026)

Compara el precio de hoy con el histórico de lecturas de la MISMA casilla (mismo país, mismo mes de viaje, mismo tipo de viaje),
no con topes fijos. Es ganga si está al menos un 15 % por debajo de la mediana de las lecturas anteriores y se ahorran al menos
4 € (para que 2 € en un vuelo de 15 € no cuente). También lo es un mínimo histórico nuevo, siempre que ahorre esos 4 € frente
a la mediana. Hasta tener 8 lecturas repartidas en 4 semanas la casilla está «aprendiendo» y no se da ninguna ganga.
La ganga sustituye al semáforo (rojo/ámbar/verde) en el color de la casilla.

Prueba: .venv\\Scripts\\python.exe ganga.py
"""
from datetime import date
from statistics import median

VERSION = "0.1"
PCT_GANGA = 0.15      # al menos un 15 % por debajo de la mediana
AHORRO_MIN = 4        # euros
LECTURAS_MIN = 8      # lecturas anteriores necesarias
DIAS_MIN = 28         # que abarquen al menos 4 semanas


def evaluar(precio, previas):
    """`previas`: lista de (fecha 'AAAA-MM-DD', precio) de lecturas ANTERIORES a la de hoy.
    Devuelve {estado: 'ganga' | 'normal' | 'aprendiendo', n, mediana, ahorro, pct}."""
    n = len(previas)
    if n:
        fechas = sorted(date.fromisoformat(f) for f, _ in previas)
        dias = (fechas[-1] - fechas[0]).days
    else:
        dias = 0
    if n < LECTURAS_MIN or dias < DIAS_MIN:
        return {"estado": "aprendiendo", "n": n}
    precios = [p for _, p in previas]
    med = median(precios)
    ahorro = med - precio
    pct = ahorro / med if med else 0
    es = ahorro >= AHORRO_MIN and (pct >= PCT_GANGA or precio < min(precios))
    return {"estado": "ganga" if es else "normal", "n": n, "mediana": round(med), "ahorro": round(ahorro),
            "pct": round(pct * 100)}


if __name__ == "__main__":
    base = [(f"2026-{m:02d}-{d:02d}", p) for (m, d), p in zip([(9, 1), (9, 8), (9, 15), (9, 22), (9, 29), (10, 3), (10, 7), (10, 10)],
                                                              [33, 30, 35, 32, 34, 31, 33, 32])]
    casos = [("Palermo 25 € (mediana ~32,5)", 25, base), ("Palermo 27,5 €", 27.5, base), ("Palermo 30 €", 30, base),
             ("Cuba 595 € (mediana 700)", 595, [(f, p * 700 / 32.5) for f, p in base]),
             ("Palermo 29 € (no llega ni al 15 % ni al mínimo)", 29, base),
             ("pocas lecturas", 20, base[:5])]
    for nombre, precio, prev in casos:
        print(f"{nombre:<44} -> {evaluar(precio, prev)}")
