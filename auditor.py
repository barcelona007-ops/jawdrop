r"""
auditor.py 1.0 — Contrasta EN SEGUNDO PLANO con Google Flights (SerpApi) las mejores opciones. Sin pantalla.

Idea del usuario (13-10-2026): la pantalla se queda limpia; SerpApi se gasta de forma oculta, sobre todo en las
mejores opciones, y se deja una reserva para lo que haga falta a mano.
Qué hace, cada vez que se ejecuta (la tarea diaria, tras actualizar.py):
  1. Coge las TOP mejores opciones de cada domingo con resultados en los próximos DIAS_VISTA días.
  2. De cada opción mira los tramos que no son exactos: todo menos Ryanair (que se lee directo) y Wizz (que da el
     precio exacto salvo que lleve «≥»). Es decir, lo que viene de Kiwi con precio estimado (Vueling, easyJet, Turkish...).
  3. Los que no están contrastados, o cuya confirmación es vieja (REVISAR_DIAS; REVISAR_CERCA si el viaje es dentro de
     una semana), se buscan en Google (confirmar.py). Primero los de los domingos más cercanos y mejores.
  4. Si confirmó algo, regenera los resultados (gratis): el precio estimado «~» pasa a ser el exacto de Google, con ✓.
Presupuesto: nunca deja la cuenta por debajo de RESERVA búsquedas (50 de 250: «200 al mes para el auditor y 50 para
cosas que necesitemos»), con un máximo de MAX_EJECUCION por ejecución. Lo ya buscado en las últimas 12 h no gasta.
Cada confirmación guarda lo estimado y lo real, para afinar las comisiones de Kiwi (kiwi.py) con el tiempo.

Uso:
  .venv\Scripts\python.exe auditor.py              (hace la ronda)
  .venv\Scripts\python.exe auditor.py --simular    (dice qué buscaría y cuánto gastaría; no gasta nada)
"""
import argparse
import re
import sys
import time
from datetime import date, datetime, timedelta

import confirmar
import escapadas
import ver_resultados
import vueling

VERSION = "1.0"
RESERVA = 50          # búsquedas del mes que el auditor NUNCA toca (para comprobaciones a mano)
MAX_EJECUCION = 12    # máximo de búsquedas nuevas en una ejecución
TOP = 3               # mejores opciones de cada domingo
DIAS_VISTA = 42       # solo domingos de las próximas 6 semanas
REVISAR_DIAS = 7      # una confirmación de más de 7 días se vuelve a mirar...
REVISAR_CERCA = 2     # ...y de más de 2 si el viaje es dentro de una semana
WIZZ = ("W6", "W4")


def tramos_de(dia, o):
    """Los dos tramos de una opción (de ver_resultados.leer_domingo) como datos: aeropuertos, día, hora, aerolínea y
    precio estimado si lo hay. Un tramo que no se pueda leer del texto no se incluye."""
    otro = o["tipo"] == "otro"
    lugares = (("BCN", ver_resultados._cod(o["destino"])),
               (ver_resultados._cod(o["desde"] if otro else o["destino"]), "BCN"))
    res = []
    for sentido, texto, (desde, hasta), mas in zip(("ida", "vuelta"), (o["ida"], o["vuelta"]), lugares, (0, o["noches"])):
        sigla = re.match(r"([A-Z0-9]{2})\b", texto)
        hora = re.search(r"(\d\d:\d\d)\s*→", texto)
        if not (sigla and hora and desde and hasta):
            continue
        est = re.search(r"~(\d+(?:\.\d+)?)\s*€", texto)
        res.append({"sentido": sentido, "desde": desde, "hasta": hasta, "sigla": sigla.group(1),
                    "dia": (datetime.strptime(dia, "%Y-%m-%d") + timedelta(days=mas)).strftime("%Y-%m-%d"),
                    "hora": hora.group(1), "estimado": float(est.group(1)) if est else None,
                    "minimo": "≥" in texto})
    return res


def auditable(t):
    """¿Merece contrastarse? Ryanair no (exacto); Wizz solo si su precio es «≥ mínimo del día»."""
    if t["sigla"] in confirmar.EXACTAS:
        return False
    if t["sigla"] in WIZZ:
        return t["minimo"]
    return True


def toca_revisar(t, conf, hoy):
    """¿Falta contrastarlo o la confirmación ya es vieja?"""
    g = conf.get(confirmar.clave(t))
    if not g:
        return True
    dias_viaje = (date.fromisoformat(t["dia"]) - hoy).days
    limite = REVISAR_CERCA if dias_viaje <= 7 else REVISAR_DIAS
    antiguedad = (datetime.now() - datetime.fromisoformat(g["visto"])).days
    return antiguedad >= limite


def pendientes(hoy=None):
    """[(tramo, domingo)] por buscar, de los domingos más cercanos y las mejores opciones primero, sin repetidos."""
    hoy = hoy or date.today()
    conf = confirmar.cargar()
    vistos, res = set(), []
    for archivo in sorted(escapadas.RESULTADOS.glob("20??-??-??.md")):
        dom = archivo.stem
        if not (hoy.isoformat() <= dom <= (hoy + timedelta(days=DIAS_VISTA)).isoformat()):
            continue
        for o in ver_resultados.leer_domingo(archivo)["opciones"][:TOP]:
            for t in tramos_de(dom, o):
                if auditable(t) and confirmar.clave(t) not in vistos and toca_revisar(t, conf, hoy):
                    vistos.add(confirmar.clave(t))
                    res.append((t, dom))
    return res


def presupuesto():
    """Búsquedas que el auditor puede gastar ahora: sin tocar la reserva ni pasar de MAX_EJECUCION."""
    usadas, total, quedan = vueling.cuota()
    return max(0, min(MAX_EJECUCION, total - RESERVA - usadas, quedan))


def main():
    ap = argparse.ArgumentParser(description="Contrasta en segundo plano las mejores opciones con Google Flights.")
    ap.add_argument("--simular", action="store_true", help="no gasta nada: dice qué buscaría")
    a = ap.parse_args()
    ahora = f"[{datetime.now():%d-%m-%Y %H:%M}]"
    pend = pendientes()
    try:
        libre = presupuesto()
        usadas, total, _ = vueling.cuota()
    except Exception as e:
        sys.exit(f"{ahora} auditor.py {VERSION}: no se pudo consultar SerpApi ({str(e)[:100]}). No se busca nada.")
    elegidos = []
    for t, dom in pend:                        # por prioridad; cada tramo se añade si el total sigue dentro del presupuesto
        if confirmar.coste([x for x, _ in elegidos] + [t]) <= libre:
            elegidos.append((t, dom))
    gasto = confirmar.coste([t for t, _ in elegidos])
    print(f"{ahora} auditor.py {VERSION}: SerpApi {usadas}/{total} usadas (reserva {RESERVA}); "
          f"{len(pend)} tramos por contrastar, hoy {len(elegidos)} (≈{gasto} búsquedas, máximo {libre}).")
    for t, dom in elegidos:
        print(f"  {dom}  {t['sentido']:6} {t['desde']}→{t['hasta']} {t['dia']} {t['hora']} {t['sigla']}"
              + (f"  estimado {t['estimado']:.0f} €" if t["estimado"] is not None else ""))
    if a.simular or not elegidos:
        print("  (simulación: no se ha buscado nada)" if a.simular else "  Nada que hacer hoy.")
        return

    vueling.reiniciar()
    vueling.SIMULAR = False
    vueling.TOPE = max(gasto, 0)
    hechos = {}
    try:
        hechos.update(confirmar.confirmar([dict(t) for t, _ in elegidos]))
    except vueling.SinPresupuesto as e:
        print(f"  Parado: {e}")
    except Exception as e:
        print(f"  Parado por un error: {str(e)[:150]}")
    print(f"  Hecho: {len(hechos)} tramos contrastados, {vueling.gastadas()} búsquedas gastadas.")
    for k, g in hechos.items():
        if g.get("no_encontrado"):
            print(f"  {k}: Google no lo encuentra")
        elif g.get("estimado") is not None:
            print(f"  {k}: estimado {g['estimado']:.0f} € → Google {g['precio']:.0f} € ({g['precio'] - g['estimado']:+.0f})")
    if not hechos:
        return
    # regenerar los resultados (gratis: usa la caché de Ryanair, Wizz y Kiwi) para que el precio exacto se vea
    import servidor
    doms = sorted({dom for t, dom in elegidos if confirmar.clave(t) in hechos})
    t, error = servidor.lanzar("actualizar", doms, auto=True)
    if error:
        print(f"  No se pudo regenerar la página ahora ({error}); saldrá en la próxima actualización.")
        return
    while t["estado"] == "corriendo":
        time.sleep(2)
    print("  Resultados regenerados." if t["estado"] == "hecho" else f"  Error al regenerar: {t['mensaje']}")


if __name__ == "__main__":
    main()
