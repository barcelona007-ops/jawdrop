"""
geografia.py — ¿Se puede volver desde otro aeropuerto? Tierra, vecinos, ferri y distancia (regla del usuario).

Reglas (decididas con el usuario el 12-10-2026, valen para TODAS las búsquedas):
  1. Distancia máxima entre el aeropuerto de llegada y el de vuelta: 200 km por cada 24 h de viaje
     (cálculo proporcional: 36 h fuera = 300 km; sin horas exactas, 24 h por cada día fuera). Si los dos
     aeropuertos son del MISMO país se admite más (hay trenes y autopistas): 300 km por 24 h, o 400 km en
     países con buena red ferroviaria (`PAISES_FERROCARRIL`). Cambio del usuario, 14-10-2026 (antes 250 km por
     día para todos). Cuando exista la sección «Configuración», estos números serán ajustables.
  2. Los km son por tierra, no en línea recta: línea recta × 1,3 (carretera), siempre marcados «≈».
  3. La vuelta sale del MISMO país o de un país VECINO (frontera, puente o ferri regular).
  4. El mar no se descarta: un cruce vale si hay ferri regular conocido (se marca «⛴»); sin ferri, se
     descarta, salvo con `con_mar=True` (la opción --con-mar de escapadas.py).

Cada aeropuerto pertenece a una «tierra» (Europa continental, Irlanda, África o una isla concreta).
Los puentes y túneles cuentan como tierra (Canal de la Mancha, Øresund, Bósforo).
Los ferris son una lista de pares conocidos: si falta uno, se añade aquí (un solo sitio).
"""
VERSION = "2.1"

KM_POR_DIA = 200          # km por cada 24 h de viaje, entre países distintos
KM_POR_DIA_MISMO_PAIS = 300      # idem, si los dos aeropuertos son del mismo país
KM_POR_DIA_FERROCARRIL = 400     # idem, mismo país con buena red de tren
# Países con buena red de tren de larga distancia (a ajustar; un solo sitio)
PAISES_FERROCARRIL = {"ES", "FR", "DE", "IT", "CH", "AT", "NL", "BE", "GB", "CZ", "SE", "DK", "PL", "JP", "KR", "CN"}
FACTOR_CARRETERA = 1.3    # línea recta -> km por carretera aproximados

# Islas: aeropuerto -> isla
ISLAS = {
    # Baleares
    "PMI": "Mallorca", "IBZ": "Ibiza", "MAH": "Menorca",
    # Canarias
    "TFS": "Tenerife", "TFN": "Tenerife", "LPA": "Gran Canaria", "ACE": "Lanzarote",
    "FUE": "Fuerteventura", "SPC": "La Palma", "VDE": "El Hierro", "GMZ": "La Gomera",
    # Madeira y Azores
    "FNC": "Madeira", "PXO": "Porto Santo", "PDL": "São Miguel", "TER": "Terceira",
    # Italia y Francia
    "CAG": "Cerdeña", "AHO": "Cerdeña", "OLB": "Cerdeña",
    "PMO": "Sicilia", "CTA": "Sicilia", "TPS": "Sicilia", "CIY": "Sicilia",
    "AJA": "Córcega", "BIA": "Córcega", "FSC": "Córcega", "CLY": "Córcega",
    "LMP": "Lampedusa", "PNL": "Pantelaria",
    # Grecia
    "HER": "Creta", "CHQ": "Creta", "JSH": "Creta", "RHO": "Rodas", "CFU": "Corfú", "KGS": "Cos",
    "JTR": "Santorini", "JMK": "Míconos", "ZTH": "Zante", "EFL": "Cefalonia", "SMI": "Samos",
    "MJT": "Lesbos", "JSI": "Esciatos", "PAS": "Paros", "JNX": "Naxos",
    # Croacia
    "BWK": "Brač",
    # Norte de Europa
    "VBY": "Gotland", "RNN": "Bornholm", "FAE": "Feroe",
    # Gran Bretaña: islas aparte
    "IOM": "Isla de Man", "JER": "Jersey", "GCI": "Guernsey",
}

# Irlanda del Norte está en la isla de Irlanda, no en Gran Bretaña
IRLANDA_NORTE = {"BFS", "BHD", "LDY"}

AFRICA = {"MA", "DZ", "TN", "LY", "EG", "SN", "GM", "CV", "MR"}
PAISES_ISLA = {"MT": "Malta", "CY": "Chipre", "IS": "Islandia"}

CONTINENTE = "Europa continental"

# --- Ferris regulares -----------------------------------------------------------------------------
# Islas con ferri regular al continente (de Europa continental). Quedan fuera las que no lo tienen
# (Canarias, Madeira, Azores) y las que cuelgan de otra isla (Lampedusa, Pantelaria, Porto Santo).
_SIN_FERRI_CONTINENTE = {"Tenerife", "Gran Canaria", "Lanzarote", "Fuerteventura", "La Palma", "El Hierro",
                         "La Gomera", "Madeira", "Porto Santo", "São Miguel", "Terceira", "Lampedusa",
                         "Pantelaria", "Chipre", "Islandia"}
_CON_FERRI = ({t for t in set(ISLAS.values()) if t not in _SIN_FERRI_CONTINENTE} | {"Irlanda", "Malta"})

# Grupos de islas con ferri entre ellas
_GRUPOS = [
    {"Mallorca", "Ibiza", "Menorca"},
    {"Tenerife", "Gran Canaria", "Lanzarote", "Fuerteventura", "La Palma", "El Hierro", "La Gomera"},
    {"Madeira", "Porto Santo"}, {"São Miguel", "Terceira"},
    {"Sicilia", "Malta", "Lampedusa", "Pantelaria"},
    {"Cerdeña", "Córcega"},
    {"Creta", "Rodas", "Corfú", "Cos", "Santorini", "Míconos", "Zante", "Cefalonia", "Samos", "Lesbos",
     "Esciatos", "Paros", "Naxos"},
]


def _conectadas(a, b):
    if CONTINENTE in (a, b):
        otra = b if a == CONTINENTE else a
        return otra in _CON_FERRI
    return any(a in g and b in g for g in _GRUPOS)


# Pares de países unidos por ferri regular (o puente) pero SIN frontera; también cuenta como «vecinos»
FERRIS_PAISES = {frozenset(p.split("-")) for p in """
IT-MT IT-TN IT-DZ IT-ES IT-GR IT-AL IT-HR IT-ME ES-DZ ES-MA FR-TN FR-DZ FR-MA GB-IE GB-NL GB-BE GB-ES
GB-FR IE-FR IE-ES DE-SE DE-DK DK-NO DK-SE PL-SE FI-EE FI-SE FI-DE SE-EE SE-LV GR-TR IM-GB JE-GB GG-GB
JE-FR GG-FR IM-IE
""".split()}

# Fronteras terrestres (y puentes) relevantes: Europa, Turquía, Cáucaso, Oriente Medio, norte de África,
# Asia central y algo más de Asia y América. Países no incluidos: solo cuentan consigo mismos.
FRONTERAS = {frozenset(p.split("-")) for p in """
AD-ES AD-FR AL-GR AL-ME AL-MK AL-XK AT-CH AT-CZ AT-DE AT-HU AT-IT AT-LI AT-SI AT-SK BA-HR BA-ME BA-RS
BE-DE BE-FR BE-LU BE-NL BG-GR BG-MK BG-RO BG-RS BG-TR BY-LT BY-LV BY-PL BY-RU BY-UA CH-DE CH-FR CH-IT
CH-LI CZ-DE CZ-PL CZ-SK DE-DK DE-FR DE-LU DE-NL DE-PL DK-SE EE-LV EE-RU ES-FR ES-GI ES-PT FI-NO FI-RU
FI-SE FR-IT FR-LU FR-MC GB-IE GR-MK GR-TR HR-HU HR-ME HR-RS HR-SI HU-RO HU-RS HU-SK HU-UA IT-SI IT-SM
IT-VA LT-LV LT-PL LT-RU LV-RU MD-RO MD-UA ME-RS ME-XK MK-RS MK-XK NO-RU NO-SE PL-RU PL-SK PL-UA RO-RS
RO-UA RS-XK RU-UA SK-UA
AM-AZ AM-GE AM-IR AM-TR AZ-GE AZ-IR AZ-RU GE-RU GE-TR TR-IR TR-IQ TR-SY
IL-JO IL-EG IL-LB JO-SA JO-IQ JO-SY LB-SY AE-OM AE-SA OM-SA QA-SA BH-SA
MA-DZ DZ-TN DZ-LY TN-LY LY-EG MA-MR DZ-MR SN-MR SN-GM MR-ML
KZ-KG KZ-UZ KG-UZ KG-TJ TJ-UZ KZ-RU KZ-CN KG-CN TJ-CN
TH-LA TH-KH TH-MY VN-LA VN-KH VN-CN LA-KH LA-CN MY-SG ID-MY IN-NP IN-CN NP-CN
US-CA US-MX CR-PA CR-NI
""".split()}


def tierra(iata, pais):
    """Nombre de la «tierra» (continente o isla) donde está el aeropuerto."""
    if iata in ISLAS:
        return ISLAS[iata]
    if iata in IRLANDA_NORTE or pais == "IE":
        return "Irlanda"
    if pais in PAISES_ISLA:
        return PAISES_ISLA[pais]
    if pais in AFRICA:
        return "África"
    return CONTINENTE  # incluye Gran Bretaña (túnel del Canal) y Escandinavia (puentes)


def misma_tierra(a, pais_a, b, pais_b):
    return tierra(a, pais_a) == tierra(b, pais_b)


def son_vecinos(pais_a, pais_b):
    """Mismo país, o con frontera (o puente), o unidos por ferri regular."""
    if pais_a == pais_b:
        return True
    par = frozenset((pais_a, pais_b))
    return par in FRONTERAS or par in FERRIS_PAISES


def km_por_tierra(km_recta):
    """Km aproximados por carretera a partir de la línea recta (siempre «≈»)."""
    return round(km_recta * FACTOR_CARRETERA)


def limite_km(dias_fuera, pais_a=None, pais_b=None, horas=None):
    """Distancia máxima (por tierra) entre aeropuertos: km por cada 24 h de viaje, proporcional.
    `horas` = horas totales fuera; si no se sabe, 24 h por cada día fuera. Mismo país: más margen."""
    h = horas if horas else 24 * max(1, dias_fuera)
    if pais_a and pais_a == pais_b:
        por_dia = KM_POR_DIA_FERROCARRIL if pais_a in PAISES_FERROCARRIL else KM_POR_DIA_MISMO_PAIS
    else:
        por_dia = KM_POR_DIA
    return por_dia * h / 24


def trayecto(a, pais_a, b, pais_b, km_recta, dias_fuera, radio=None, con_mar=False, horas=None):
    """¿Se puede volver desde b habiendo llegado a a? None si no; si sí, {"km": km por tierra, "ferri": bool}.

    `dias_fuera` = días entre la ida y la vuelta; `radio` (km en línea recta) fuerza un límite a mano
    en lugar de la regla de km por 24 h (`horas` = horas totales fuera, si se saben); `con_mar` admite cruces sin ferri conocido."""
    if km_recta is None:
        return None
    ta, tb = tierra(a, pais_a), tierra(b, pais_b)
    ferri = False
    if ta != tb:
        otra = tb if ta == "África" else ta
        africa_ferri = ("África" in (ta, tb) and (otra == CONTINENTE or otra in _CON_FERRI)
                        and frozenset((pais_a, pais_b)) in FERRIS_PAISES)
        if _conectadas(ta, tb) or africa_ferri:
            ferri = True
        elif not con_mar:
            return None
    if not con_mar and not son_vecinos(pais_a, pais_b):
        return None
    km = km_por_tierra(km_recta)
    if radio is not None:
        if km_recta > radio:
            return None
    elif km > limite_km(dias_fuera, pais_a, pais_b, horas):
        return None
    return {"km": km, "ferri": ferri}
