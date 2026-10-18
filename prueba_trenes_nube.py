"""prueba_trenes_nube.py 0.1 — UNA petición a cada operador (Ouigo, Iryo, Renfe) desde un servidor de GitHub Actions (IP de centro de datos).
Solo comprueba si contestan o bloquean. No salta nada: ante un 403/429/captcha, lo cuenta y sigue con el siguiente."""
import requests

import trenes_iryo
import trenes_ouigo
import trenes_renfe

FECHA = "2026-11-20"


def probar(nombre, f):
    try:
        r = f()
        print(f"{nombre}: FUNCIONA ({r})")
        return True
    except Exception as e:
        print(f"{nombre}: FALLA -> {getattr(e, 'motivo', None) or type(e).__name__ + ': ' + str(e)[:200]}")
        return False


def ouigo():
    o = trenes_ouigo.Ouigo()
    t = o.dia(FECHA)
    return f"{len([x for x in t.get('outbound', []) if x.get('price') is not None])} trenes con precio"


def iryo():
    t = trenes_iryo.Iryo().dia(FECHA)
    return f"{len([x for x in t if x['precio'] is not None])} trenes con precio, el más barato {min(x['precio'] for x in t if x['precio'] is not None)} €"


def renfe():
    c = trenes_renfe.calendario("BCN-MAD", "2026-11-15", "2026-11-30")
    return f"{len([v for v in c.values() if v is not None])} días con precio, el {FECHA} desde {c.get(FECHA)} €"


if __name__ == "__main__":
    print("IP de salida:", requests.get("https://api.ipify.org", timeout=10).text)
    res = [probar("Ouigo", ouigo), probar("Iryo", iryo), probar("Renfe (calendario)", renfe)]
    print("RESULTADO:", f"{sum(res)} de 3 operadores contestan desde GitHub Actions")
