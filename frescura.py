"""
frescura.py — Cuánto dura una lectura de precio según la antelación del viaje (regla del usuario, 14-10-2026).

Cuanto más lejos el viaje, menos hace falta refrescarlo:
  hasta 60 días        -> vale 2 días
  de 61 a 120 días     -> vale 3,5 días (dos lecturas por semana)
  más de 120 días      -> vale 1 semana
Se usa para decidir si una casilla del Radar toca leerla otra vez o ya está fresca (Flash se refresca a diario aparte).
"""
from datetime import date, datetime

VERSION = "0.1"
TRAMOS = [(60, 48), (120, 84), (10_000, 168)]   # (días de antelación hasta, horas que vale la lectura)


def antelacion_dias(mes, hoy=None):
    """Días desde hoy hasta mediados del mes (AAAA-MM); 0 si el mes ya empezó y sigue en curso."""
    hoy = hoy or date.today()
    medio = date.fromisoformat(mes + "-15")
    return max((medio - hoy).days, 0)


def horas_validas(mes, hoy=None):
    d = antelacion_dias(mes, hoy)
    return next(h for tope, h in TRAMOS if d <= tope)


def toca(mes, ultima_lectura, ahora=None):
    """True si la casilla `mes` hay que leerla otra vez. `ultima_lectura`: 'AAAA-MM-DD' o None (nunca leída)."""
    if not ultima_lectura:
        return True
    ahora = ahora or datetime.now()
    edad_h = (ahora - datetime.fromisoformat(ultima_lectura)).total_seconds() / 3600
    return edad_h >= horas_validas(mes, ahora.date())


if __name__ == "__main__":
    hoy = date(2026, 10, 14)
    for m in ("2026-10", "2026-11", "2027-01", "2027-02", "2027-09"):
        print(m, f"antelación {antelacion_dias(m, hoy)} d -> vale {horas_validas(m, hoy)} h")
