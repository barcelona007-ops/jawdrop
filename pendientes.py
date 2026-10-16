"""Lista de países pendientes desde Madrid (zonas y hubs) para la pestaña Pasaporte.

Mezcla esta tabla (visado, ruta, facilidad: a mano, de memoria: comprobar antes de pagar) con las lecturas de
Kiwi (gratis) de `resultados/kiwi_zonas_1_3.json` (precio suelto por sentido) y `resultados/mejor_dia_zonas_1_3.json`
(mejor ida + vuelta de cada mes con la duración de la zona) y escribe `movil/pendientes.json`.
Uso: python pendientes.py (con el entorno .venv)
"""
import json
import os
from datetime import date

VERSION = "0.1"
AQUI = os.path.dirname(os.path.abspath(__file__))
ISO = {"Turquía": "TR", "Emiratos Árabes": "AE", "Catar": "QA", "Etiopía": "ET", "Marruecos": "MA", "Singapur": "SG",
       "Corea del Sur": "KR", "Uzbekistán": "UZ", "Azerbaiyán": "AZ", "Kazajistán": "KZ", "Kirguistán": "KG",
       "Tayikistán": "TJ", "Turkmenistán": "TM", "Armenia": "AM", "Georgia": "GE", "Senegal": "SN", "Cabo Verde": "CV",
       "Gambia": "GM", "Mauritania": "MR", "Costa de Marfil": "CI", "Ghana": "GH", "Benín": "BJ", "Togo": "TG",
       "Nigeria": "NG", "Kenia": "KE", "Tanzania": "TZ", "Sudáfrica": "ZA", "Mauricio": "MU", "Ruanda": "RW",
       "Uganda": "UG", "Yibuti": "DJ", "Seychelles": "SC", "Palaos": "PW", "Micronesia": "FM", "Islas Marshall": "MH",
       "República Dominicana": "DO", "Cuba": "CU", "Bahamas": "BS", "Jamaica": "JM", "Barbados": "BB",
       "Trinidad y Tobago": "TT", "Antigua y Barbuda": "AG", "San Cristóbal y Nieves": "KN", "Santa Lucía": "LC",
       "Panamá": "PA", "Guatemala": "GT", "Ecuador": "EC", "Bolivia": "BO", "Uruguay": "UY", "Paraguay": "PY", "Líbano": "LB"}
DURACION = {"0": "escala de 8 h a 2 noches", "1": "5-9 días", "2": "4-8 días", "3": "10-15 días", "4": "15-28 días",
            "5": "15-28 días", "6": "10-21 días"}

# (país, ruta desde Madrid, escalas, visado/entrada (pasaporte español), precio ida+vuelta € estimado, facilidad 1-5, notas)
BLOQUES = [
 ("0. HUBS — cuentan como país con escala larga (8 h+ de día, saliendo del aeropuerto)", [
  ("Turquía", "Directo MAD–Estambul (IST). Turkish / Pegasus (SAW)", "Directo", "Sin visado (90 días)", "150–300", 5, "El más barato. IST está lejos del centro (~45 min): cuenta el tiempo de ida y vuelta. Base para toda la zona 1."),
  ("Emiratos Árabes", "Directo MAD–Abu Dabi (Etihad; Kiwi) y MAD–Dubái (Emirates)", "Directo", "Sin visado (90 días)", "300–550", 5, "Emirates ofrece paquetes de escala con hotel. Metro hasta el centro."),
  ("Catar", "Directo MAD–Doha (Qatar Airways)", "Directo", "Sin visado (90 días)", "350–600", 5, "Qatar Airways tiene paquetes «stopover» con hotel barato. Metro desde el aeropuerto."),
  ("Etiopía", "Directo MAD–Adís Abeba (Ethiopian)", "Directo", "e-visa (~50 USD), se saca online antes", "500–800", 4, "Hub de la zona 3. Ethiopian da hotel gratis en escalas largas (condiciones en su web). Sacar e-visa aunque solo salgas en la escala."),
  ("Marruecos", "Directo MAD–Casablanca (RAM / Iberia) y muchos más", "Directo", "Sin visado (90 días)", "100–250", 5, "Hub de la zona 2."),
  ("Singapur", "1 escala (Doha, Dubái, Estambul…) o Singapore Airlines vía Europa", "1", "Sin visado (90 días) + SG Arrival Card online", "550–800", 3, ""),
  ("Corea del Sur", "Directo MAD–Seúl ICN (Korean Air) o 1 escala", "Directo / 1", "Sin visado (90 días); comprobar si hace falta K-ETA", "650–950", 3, "Hub de la zona 4 (Palaos)."),
 ]),
 ("1. CÁUCASO Y ASIA CENTRAL — hub Estambul (empezar por aquí: lo más barato)", [
  ("Uzbekistán", "MAD–IST–Taskent (Turkish)", "1", "Sin visado (30 días, UE)", "350–550", 4, "Samarcanda, Bujará, Jiva. Muy buena relación precio/países."),
  ("Azerbaiyán", "MAD–IST–Bakú (Turkish)", "1", "e-visa (~25 USD, ASAN), 3 días hábiles; hace falta aunque solo salgas en la escala", "300–500", 4, "Se combina con Georgia por tierra o con vuelo corto."),
  ("Kazajistán", "MAD–IST–Almaty / Astaná (Turkish, Pegasus)", "1", "Sin visado (30 días)", "400–650", 4, ""),
  ("Kirguistán", "MAD–IST–Biskek (Turkish)", "1", "Sin visado (60 días)", "400–700", 3, "Menos frecuencias: mirar días."),
  ("Tayikistán", "MAD–IST–Dusambé (Turkish)", "1", "e-visa (~50 USD)", "450–750", 3, "Pocos vuelos."),
  ("Turkmenistán", "MAD–IST–Asjabad (Turkish)", "1", "Visado difícil (carta de invitación / tránsito de 5 días)", "500–900", 1, "Dejar para el final."),
  ("Armenia", "—", "—", "—", "—", 0, "Ya visitada por el usuario (2026)."),
  ("Georgia", "—", "—", "—", "—", 0, "Ya visitada por el usuario (2026)."),
 ]),
 ("2. ÁFRICA OCCIDENTAL — hub Casablanca (Royal Air Maroc)", [
  ("Senegal", "MAD–Casablanca–Dakar (RAM). Mirar también directo", "1", "Sin visado (90 días)", "350–550", 4, "La más fácil de la zona. Vacuna de fiebre amarilla recomendada."),
  ("Cabo Verde", "MAD–Lisboa–Praia/Sal (TAP) o directo según temporada", "1", "Sin visado, pero registro EASE online + tasa aeroportuaria", "350–600", 4, "Isla: la escala de 8 h no suele servir, es destino en sí."),
  ("Gambia", "MAD–Casablanca–Banjul (RAM)", "1", "Sin visado UE (confirmar)", "400–650", 3, ""),
  ("Mauritania", "MAD–Casablanca–Nuakchot (RAM)", "1", "Visado en llegada o e-visa (~55 €)", "350–600", 3, "Mirar aviso de Exteriores por zonas."),
  ("Costa de Marfil", "MAD–Casablanca–Abiyán (RAM)", "1", "e-visa (~70 €) + certificado de fiebre amarilla obligatorio", "450–700", 3, ""),
  ("Ghana", "MAD–Casablanca–Acra (RAM)", "1", "Visado antes de viajar + fiebre amarilla obligatoria", "550–850", 2, "Trámite más largo."),
  ("Benín", "MAD–Casablanca–Cotonú (RAM)", "1", "e-visa (~50 USD) + fiebre amarilla", "550–850", 2, ""),
  ("Togo", "MAD–Casablanca–Lomé (RAM)", "1", "e-visa (~50 €) + fiebre amarilla", "550–850", 2, ""),
  ("Nigeria", "Directo MAD–Lagos según Kiwi (comprobar) o vía Casablanca", "Directo / 1", "Visado/e-visa (~160 USD) + fiebre amarilla", "600–950", 2, "Mirar aviso de Exteriores."),
  ("Mali, Níger, Burkina Faso, Guinea", "—", "—", "—", "—", 1, "NO recomendables ahora (avisos de Exteriores). No hacer."),
 ]),
 ("3. ÁFRICA ORIENTAL Y CENTRAL — hub Adís Abeba (Ethiopian)", [
  ("Kenia", "MAD–Adís–Nairobi (Ethiopian)", "1", "eTA online (~30 USD)", "600–900", 4, "Safaris. Lo normal es quedarse varios días."),
  ("Tanzania", "MAD–Adís/Abu Dabi–Kilimanjaro/Dar es Salaam/Zanzíbar (Kiwi: sin directo nov–mar)", "1", "e-visa o en llegada (~50 USD)", "650–950", 4, "Zanzíbar cuenta como Tanzania."),
  ("Sudáfrica", "Directo según Kiwi (comprobar) o vía Adís/Doha", "Directo / 1", "Sin visado (90 días)", "650–950", 4, "No está en la lista de zonas, pero el Radar la lee desde Madrid."),
  ("Mauricio", "Sin directo en Kiwi nov–mar (puede ser estacional); 1 escala vía París", "1", "Sin visado (90 días)", "800–1300", 4, "Isla del Índico. Radar la lee desde Madrid."),
  ("Ruanda", "MAD–Adís–Kigali (Ethiopian)", "1", "Visado en llegada o e-visa (~50 USD)", "650–950", 3, "Gorilas: permiso aparte y muy caro."),
  ("Uganda", "MAD–Adís–Entebbe (Ethiopian)", "1", "e-visa (~50 USD) + fiebre amarilla", "650–950", 3, ""),
  ("Yibuti", "MAD–Adís–Yibuti (Ethiopian)", "1", "e-visa (~34 USD)", "600–900", 3, "Muy calurosa; escala corta posible."),
  ("Seychelles", "MAD–Doha/Dubái/Adís–Mahé", "1", "Sin visado + autorización de viaje online (gratis)", "900–1500", 3, ""),
 ]),
 ("4. PACÍFICO — hub Tokio o Seúl, luego Guam u Honolulu", [
  ("Palaos", "MAD–Seúl–Koror (ICN–ROR) o vía Manila/Taipéi/Guam", "1-2", "Sin visado (30 días) + tasa ambiental (~100 USD)", "1400–2200", 2, "Si pasas por EEUU (Guam, Honolulu) hace falta ESTA aunque solo hagas tránsito."),
  ("Micronesia", "Vía Tokio/Seúl + Guam/Honolulu, «Island Hopper» de United", "2", "Sin visado (30 días); ESTA si tocas EEUU", "2000–3200", 1, "Kiwi no devolvió nada (16-10-2026): hay que buscarla en la web de United."),
  ("Islas Marshall", "Vía Honolulu/Guam (Island Hopper)", "2", "Sin visado (90 días); ESTA si tocas EEUU", "2000–3200", 1, ""),
 ]),
 ("5. CARIBE — hub San Juan o Miami, islas por vuelos cortos", [
  ("República Dominicana", "Directo MAD–Punta Cana/Santo Domingo (Iberia, Air Europa)", "Directo", "Sin visado; tasa de entrada incluida o e-ticket gratis", "500–850", 5, "El Radar la lee desde Madrid."),
  ("Cuba", "Directo MAD–La Habana (Iberia, Air Europa, Plus Ultra)", "Directo", "Tarjeta del turista (~25–50 €) + formulario D'Viajeros", "600–950", 4, ""),
  ("Bahamas", "MAD–Miami (Iberia) + Miami–Nasáu (40 min)", "1", "Sin visado (90 días); ESTA para Miami", "650–1000", 4, "Hace falta ESTA."),
  ("Jamaica", "Vía Miami / Panamá / otro hub", "1", "Sin visado (90 días)", "700–1100", 3, ""),
  ("Barbados", "Vía Londres o Miami/Nueva York", "1", "Sin visado (90 días)", "750–1200", 3, ""),
  ("Trinidad y Tobago", "Vía Panamá (Copa) o Miami", "1", "Sin visado (90 días)", "700–1100", 3, ""),
  ("Antigua y Barbuda", "MAD–San Juan (Iberia) + vuelo corto", "1-2", "Sin visado; ESTA para San Juan", "800–1300", 2, "Pocas frecuencias en vuelos cortos."),
  ("San Cristóbal y Nieves", "MAD–San Juan + vuelo corto", "1-2", "Sin visado; ESTA", "800–1300", 2, ""),
  ("Santa Lucía", "MAD–San Juan + vuelo corto, o vía Barbados", "1-2", "Sin visado; ESTA", "800–1300", 2, ""),
  ("Haití", "—", "—", "—", "—", 1, "NO recomendable (aviso de Exteriores)."),
 ]),
 ("6. EXTRA — ya salen directos de Madrid fuera de las zonas (el Radar los lee; directo según Kiwi 16-10-2026)", [
  ("Panamá", "Directo MAD–Panamá (Copa, Air Europa)", "Directo", "Sin visado (180 días)", "500–800", 5, ""),
  ("Guatemala", "Directo MAD–Ciudad de Guatemala (Iberia)", "Directo", "Sin visado (90 días)", "600–900", 5, "Radar: mar 2027 ~869 €."),
  ("Ecuador", "Directo MAD–Quito/Guayaquil", "Directo", "Sin visado (90 días)", "600–900", 5, ""),
  ("Bolivia", "Directo MAD–Santa Cruz (Air Europa)", "Directo", "Sin visado (90 días)", "700–1000", 5, ""),
  ("Uruguay", "Directo MAD–Montevideo", "Directo", "Sin visado (90 días)", "650–1000", 5, ""),
  ("Paraguay", "Directo MAD–Asunción", "Directo", "Sin visado (90 días)", "800–1100", 5, ""),
  ("Líbano", "Directo según Kiwi (comprobar)", "Directo", "Visado en llegada gratis (1 mes)", "250–500", 3, "Mirar aviso de Exteriores antes."),
 ]),
]


def _leer(nombre):
    ruta = os.path.join(AQUI, "resultados", nombre)
    return json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else {}


def _tramo(x):
    return {"dia": x["dia"], "precio": round(x["precio"]), "via": x["via"], "horas": x["horas_escala"], "aero": x["aerolineas"]}


def construir():
    kiwi, mejor = _leer("kiwi_zonas_1_3.json"), _leer("mejor_dia_zonas_1_3.json")
    zonas = []
    for titulo, filas in BLOQUES:
        zid = titulo.split(".")[0]
        paises = []
        for pais, ruta, esc, visa, precio, fac, nota in filas:
            if pais not in ISO:
                continue
            p = {"c": ISO[pais], "ruta": ruta, "esc": esc, "visa": visa, "est": precio, "fac": fac, "nota": nota}
            k = kiwi.get(pais) or {}
            if k.get("ida") and k.get("vuelta") and "error" not in k["ida"] and "error" not in k["vuelta"]:
                d = k.get("directo") or {}
                p["kiwi"] = {"total": round(k["ida"]["precio"] + k["vuelta"]["precio"]),
                             "directo": round(d["ida"]["precio"] + d["vuelta"]["precio"]) if d.get("ida") and d.get("vuelta") else None}
            meses = {}
            for mes, m in (mejor.get(pais) or {}).items():
                if m and "error" not in m:
                    meses[mes] = {"total": round(m["total"]), "noches": m["noches"], "ida": _tramo(m["ida"]), "vuelta": _tramo(m["vuelta"])}
            if meses:
                p["meses"] = meses
            paises.append(p)
        zonas.append({"id": zid, "nombre": titulo.split(" — ")[0].split(". ", 1)[1].split(" — ")[0], "detalle": titulo.split(". ", 1)[1],
                      "dur": DURACION[zid], "paises": paises})
    return {"generado": date.today().isoformat(), "zonas": zonas}


if __name__ == "__main__":
    res = construir()
    destino = os.path.join(AQUI, "movil", "pendientes.json")
    json.dump(res, open(destino, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("escrito", destino, sum(len(z["paises"]) for z in res["zonas"]), "países,",
          sum(1 for z in res["zonas"] for p in z["paises"] if p.get("meses")), "con meses")
