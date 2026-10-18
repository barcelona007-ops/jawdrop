"""Sondeo gratis de Kiwi: ¿se puede llegar en avión (hasta 2 escalas) a los países que aún no tienen zona en el Radar?

Una consulta de solo ida por país y origen (BCN, y MAD si BCN no da nada), en una ventana de muestra. Todo por la caché y
la pausa de siempre (kiwi.py). Guarda `datos/sondeo_paises.json` con precio mínimo, horas, aerolíneas y hub de cada país.
Uso: python sondeo_paises.py [--desde 2027-01-10 --hasta 2027-01-31] [--solo XX YY]
"""
import json
import sys
from pathlib import Path

import kiwi

VERSION = "0.1"
SALIDA = Path(__file__).parent / "datos" / "sondeo_paises.json"
# Países sin zona en el Radar (17-10-2026), menos los que van a la lista de «cerrados» sin consultar.
PAISES = ("BY LI RU AF BH BD BT BN IR IQ MV MN MM NP KP OM PK SY TL TM YE AO BW BF BI CM CF TD KM CG CD GQ ER SZ GA GN GW LS LR LY "
          "MG MW ML MZ NA NE ST SL SO SS SD ZM ZW BZ DM GD HT NI VC GY SR AU FJ KI MH FM NR NZ PW PG WS SB TO TV VU").split()


def sondear(cod, desde, hasta):
    for origen in ("BCN", "MAD"):
        try:
            its = kiwi.escalas([f"Airport:{origen}"], [f"Country:{cod}"], desde, hasta, paradas=2, limite=5)
        except kiwi.KiwiBloqueado:
            raise
        except Exception as e:   # país que Kiwi no conoce, etc.
            return {"ok": False, "motivo": f"error: {str(e)[:80]}"}
        if its:
            m = its[0]
            return {"ok": True, "origen": origen, "precio": round(m["precio_kiwi"]), "horas": m["horas_total"], "aerolineas": m["aerolineas"],
                    "hubs": [e["aeropuerto"] for e in m["escalas"]], "destino": m["destino"], "ciudad": m["ciudad"], "n": len(its)}
    return {"ok": False, "motivo": "Kiwi no devuelve itinerarios"}


def main(argv):
    desde, hasta, solo = "2027-01-10", "2027-01-31", None
    if "--desde" in argv:
        desde = argv[argv.index("--desde") + 1]
    if "--hasta" in argv:
        hasta = argv[argv.index("--hasta") + 1]
    if "--solo" in argv:
        solo = [a.upper() for a in argv[argv.index("--solo") + 1:] if not a.startswith("--")]
    res = json.loads(SALIDA.read_text(encoding="utf-8")) if SALIDA.exists() else {}
    for cod in (solo or PAISES):
        if cod in res and res[cod].get("ok") is not None and not solo:
            continue
        res[cod] = sondear(cod, desde, hasta)
        r = res[cod]
        print(cod, f'{r["precio"]} € · {r["horas"]} h · {"+".join(r["hubs"])} · {r["origen"]}' if r["ok"] else r["motivo"], flush=True)
        SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
