"""Pruebas de aguante de los operadores de tren (Ouigo, Renfe, Iryo).

VERSION 0.1. Uso: python probar_trenes.py ouigo [--ritmos 30,10,0] [--tandas 10,25,50,100]
Manda tandas crecientes (misma ruta, fechas distintas) con 3 ritmos y PARA en el primer
403/429/captcha. Cada tanda se anota en datos/pruebas_trenes.json."""
import argparse
import json
import os
import random
import time
from datetime import date, datetime, timedelta

import trenes_iryo
import trenes_ouigo
import trenes_renfe

VERSION = "0.2"
SALIDA = os.path.join("datos", "pruebas_trenes.json")
DESCANSO_TANDA, DESCANSO_RITMO = 300, 900  # segundos entre tandas / entre ritmos


def fechas(n, ini=14, ventana=55):
    """n fechas futuras; ida BCN→MAD y, si hacen falta más que la ventana, vuelta MAD→BCN."""
    base = date.today() + timedelta(days=ini)
    return [(str(base + timedelta(days=i % ventana)), i < ventana) for i in range(n)]


def adaptador_ouigo():
    o = trenes_ouigo.Ouigo()

    def pedir(fecha, ida):
        o_, d_ = (trenes_ouigo.BCN, trenes_ouigo.MAD) if ida else (trenes_ouigo.MAD, trenes_ouigo.BCN)
        r = o.dia(fecha, o_, d_)
        return len([t for t in r.get("outbound", []) if t.get("price") is not None])
    return pedir


def adaptador_iryo():
    i = trenes_iryo.Iryo()

    def pedir(fecha, ida):
        o_, d_ = (trenes_iryo.BCN, trenes_iryo.MAD) if ida else (trenes_iryo.MAD, trenes_iryo.BCN)
        return len([t for t in i.dia(fecha, o_, d_) if t["precio"] is not None])
    return pedir


def adaptador_renfe():
    """Calendario de precios mínimos de Renfe: cada petición pide 30 días desde la fecha (rangos distintos)."""
    def pedir(fecha, ida):
        fin = str(date.fromisoformat(fecha) + timedelta(days=30))
        return len([v for v in trenes_renfe.calendario("BCN-MAD" if ida else "MAD-BCN", fecha, fin).values() if v is not None])
    return pedir


ADAPTADORES = {"ouigo": adaptador_ouigo, "iryo": adaptador_iryo, "renfe": adaptador_renfe}


def guardar(reg):
    datos = json.load(open(SALIDA, encoding="utf-8")) if os.path.exists(SALIDA) else []
    datos.append(reg)
    json.dump(datos, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def tanda(op, n, pausa):
    r = dict(operador=op, ritmo_s=pausa, pedidas=n, enviadas=0, con_datos=0, vacias=0,
             primer_fallo=None, codigo=None, hora=datetime.now().isoformat(timespec="seconds"))
    try:
        pedir = ADAPTADORES[op]()  # sesión nueva por tanda
    except Exception as e:
        r["primer_fallo"] = f"{type(e).__name__}: {e}"[:200]
        r["codigo"] = getattr(e, "codigo", None)
        guardar(r)
        print(r, flush=True)
        return r
    for f, ida in fechas(n):
        r["enviadas"] += 1
        try:
            r["con_datos" if pedir(f, ida) else "vacias"] += 1
        except Exception as e:  # ErrorOperador (403/429/captcha...), red caída, JSON raro
            r["primer_fallo"] = (getattr(e, "motivo", None) or f"{type(e).__name__}: {e}")[:200]
            r["codigo"] = getattr(e, "codigo", None)
            break
        if pausa:
            time.sleep(pausa * random.uniform(0.7, 1.3))
    r["fin"] = datetime.now().isoformat(timespec="seconds")
    guardar(r)
    print(r, flush=True)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("operador", choices=list(ADAPTADORES))
    ap.add_argument("--ritmos", default="30,10,0")
    ap.add_argument("--tandas", default="10,25,50,100")
    a = ap.parse_args()
    for ritmo in map(int, a.ritmos.split(",")):
        for n in map(int, a.tandas.split(",")):
            if tanda(a.operador, n, ritmo)["primer_fallo"]:
                print("PARO: primer fallo, no sigo con", a.operador, flush=True)
                return
            time.sleep(DESCANSO_TANDA)
        time.sleep(DESCANSO_RITMO)
    print("Sin fallos en todo el protocolo", flush=True)


if __name__ == "__main__":
    main()
