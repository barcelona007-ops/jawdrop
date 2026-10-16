r"""
aeropuertos.py — Tabla general de aeropuertos (código IATA -> ciudad y país) (Jawdrop).

Para qué: Ryanair, Wizz, Kiwi y Vueling no siempre traen el nombre de la ciudad (a veces solo el código, p. ej.
«BOD») o traen uno raro («East Midlands»). Esta tabla se usa como red de seguridad en TODAS las piezas:
  - `corregir(iata, ciudad, pais, pais_nombre)` devuelve los tres datos ya arreglados.
  - `ficha(iata)` devuelve todo lo que se sabe de un aeropuerto (base para las futuras fichas de aeropuerto).

Datos: `datos/aeropuertos.json`, sacado de OurAirports (dominio público) con los aeropuertos que tienen código
IATA y vuelos regulares. Se regenera con `--regenerar` (descarga ~12 MB, una vez; no hace falta casi nunca).
Las ciudades de esa tabla están en inglés/idioma local; por eso `NOMBRES` fija el nombre en castellano de las
ciudades que importan y `AJUSTES` arregla los casos raros. Un nombre que ya vino bien de la fuente NO se toca.

Prueba: .venv\Scripts\python.exe aeropuertos.py [CODIGO ...]
"""
import csv
import io
import json
import sys
from pathlib import Path

VERSION = "1.0"
ARCHIVO = Path(__file__).resolve().parent / "datos" / "aeropuertos.json"
URL_DATOS = "https://davidmegginson.github.io/ourairports-data/airports.csv"

# País (código de dos letras) -> nombre en castellano.
PAISES = {
    "AD": "Andorra", "AE": "Emiratos Árabes Unidos", "AL": "Albania", "AM": "Armenia", "AT": "Austria",
    "AZ": "Azerbaiyán", "BA": "Bosnia y Herzegovina", "BE": "Bélgica", "BG": "Bulgaria", "BH": "Baréin",
    "BY": "Bielorrusia", "CH": "Suiza", "CY": "Chipre", "CZ": "Chequia", "DE": "Alemania", "DK": "Dinamarca",
    "DZ": "Argelia", "EE": "Estonia", "EG": "Egipto", "ES": "España", "FI": "Finlandia", "FR": "Francia",
    "GB": "Reino Unido", "GE": "Georgia", "GI": "Gibraltar", "GR": "Grecia", "HR": "Croacia", "HU": "Hungría",
    "IE": "Irlanda", "IL": "Israel", "IM": "Isla de Man", "IS": "Islandia", "IT": "Italia", "JE": "Jersey",
    "GG": "Guernsey", "JO": "Jordania", "KZ": "Kazajistán", "LB": "Líbano", "LI": "Liechtenstein",
    "LT": "Lituania", "LU": "Luxemburgo", "LV": "Letonia", "MA": "Marruecos", "MC": "Mónaco", "MD": "Moldavia",
    "ME": "Montenegro", "MK": "Macedonia del Norte", "MT": "Malta", "NL": "Países Bajos", "NO": "Noruega",
    "PL": "Polonia", "PT": "Portugal", "QA": "Catar", "RO": "Rumanía", "RS": "Serbia", "RU": "Rusia",
    "SA": "Arabia Saudí", "SE": "Suecia", "SI": "Eslovenia", "SK": "Eslovaquia", "SM": "San Marino",
    "TN": "Túnez", "TR": "Turquía", "UA": "Ucrania", "US": "Estados Unidos", "XK": "Kosovo",
    "CA": "Canadá", "MX": "México", "DO": "República Dominicana", "CO": "Colombia", "PE": "Perú",
    "CL": "Chile", "AR": "Argentina", "BR": "Brasil", "SN": "Senegal", "GM": "Gambia", "CV": "Cabo Verde",
    "KW": "Kuwait", "OM": "Omán", "UZ": "Uzbekistán", "TH": "Tailandia", "IN": "India", "JP": "Japón",
    "CN": "China", "HK": "Hong Kong", "SG": "Singapur", "ID": "Indonesia", "MY": "Malasia", "VN": "Vietnam",
    "LK": "Sri Lanka", "MV": "Maldivas", "NP": "Nepal", "KR": "Corea del Sur", "PH": "Filipinas",
    "ZA": "Sudáfrica", "KE": "Kenia", "TZ": "Tanzania", "MU": "Mauricio", "CU": "Cuba", "PA": "Panamá",
    "CR": "Costa Rica", "SV": "El Salvador", "HN": "Honduras", "BO": "Bolivia", "EC": "Ecuador",
    "UY": "Uruguay", "VE": "Venezuela", "AU": "Australia", "NZ": "Nueva Zelanda",
}

# Ciudad en castellano de los aeropuertos que importan (los de la tabla de Vueling y los habituales de
# Ryanair/Wizz). Fuerza el nombre solo si la fuente trajo el código; los que no están salen como en OurAirports.
NOMBRES = {
    "AMS": "Ámsterdam", "ATH": "Atenas", "BER": "Berlín", "BRU": "Bruselas", "CRL": "Charleroi (Bruselas)",
    "CDG": "París", "ORY": "París", "BVA": "París-Beauvais", "LHR": "Londres", "LGW": "Londres",
    "STN": "Londres-Stansted", "LTN": "Londres-Luton", "LCY": "Londres", "FCO": "Roma", "CIA": "Roma-Ciampino",
    "MXP": "Milán", "LIN": "Milán", "BGY": "Milán-Bérgamo", "VCE": "Venecia", "TSF": "Venecia-Treviso",
    "NAP": "Nápoles", "BLQ": "Bolonia", "FLR": "Florencia", "PSA": "Pisa", "GOA": "Génova", "TRN": "Turín",
    "CTA": "Catania", "PMO": "Palermo", "BRI": "Bari", "BDS": "Brindisi", "VRN": "Verona", "TRS": "Trieste",
    "CAG": "Cagliari", "OLB": "Olbia", "ZRH": "Zúrich", "GVA": "Ginebra", "BSL": "Basilea", "BRN": "Berna",
    "VIE": "Viena", "MUC": "Múnich", "FRA": "Fráncfort", "DUS": "Düsseldorf", "HAM": "Hamburgo",
    "STR": "Stuttgart", "CGN": "Colonia", "NUE": "Núremberg", "LEJ": "Leipzig", "LIS": "Lisboa",
    "OPO": "Oporto", "FAO": "Faro", "DUB": "Dublín", "EDI": "Edimburgo", "GLA": "Glasgow",
    "MAN": "Mánchester", "BHX": "Birmingham", "EMA": "East Midlands (Nottingham)", "LPL": "Liverpool",
    "NCL": "Newcastle", "BRS": "Bristol", "CPH": "Copenhague", "BLL": "Billund", "ARN": "Estocolmo",
    "OSL": "Oslo", "HEL": "Helsinki", "PRG": "Praga", "BUD": "Budapest", "WAW": "Varsovia",
    "WMI": "Varsovia-Modlin", "KRK": "Cracovia", "GDN": "Gdansk", "WRO": "Breslavia", "SKG": "Tesalónica",
    "IST": "Estambul", "SAW": "Estambul-Sabiha", "TLV": "Tel Aviv", "CMN": "Casablanca", "RAK": "Marrakech",
    "TNG": "Tánger", "AGA": "Agadir", "FEZ": "Fez", "ALG": "Argel", "ORN": "Orán", "TUN": "Túnez",
    "NCE": "Niza", "LYS": "Lyon", "MRS": "Marsella", "TLS": "Toulouse", "BOD": "Burdeos", "NTE": "Nantes",
    "BIQ": "Biarritz", "SXB": "Estrasburgo", "MLA": "Malta", "DBV": "Dubrovnik", "SPU": "Split",
    "ZAG": "Zagreb", "TIA": "Tirana", "BEG": "Belgrado", "OTP": "Bucarest", "SOF": "Sofía", "RIX": "Riga",
    "VNO": "Vilna", "TLL": "Tallin", "LUX": "Luxemburgo", "AMM": "Amán", "CAI": "El Cairo",
    "EIN": "Eindhoven", "RTM": "Róterdam", "KUT": "Kutaisi", "TBS": "Tiflis",
    "LJU": "Liubliana", "SKP": "Skopie", "PRN": "Pristina", "SJJ": "Sarajevo", "TGD": "Podgorica",
    "BTS": "Bratislava", "KEF": "Reikiavik", "ALC": "Alicante", "BCN": "Barcelona",
}

# Casos raros: nombres que las fuentes dan mal aunque no sea el código. (ciudad, país, nombre del país)
AJUSTES = {
    "EMA": ("East Midlands (Nottingham)", "GB", "Reino Unido"),
}

_tabla = None


def cargar():
    """{iata: {ciudad, pais, lat, lon, nombre}} de datos/aeropuertos.json ({} si falta el archivo)."""
    global _tabla
    if _tabla is None:
        try:
            _tabla = json.loads(ARCHIVO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _tabla = {}
    return _tabla


def ficha(iata):
    """Todo lo conocido de un aeropuerto: {iata, ciudad, pais, pais_nombre, nombre, lat, lon} o None."""
    iata = (iata or "").upper()
    base = cargar().get(iata)
    if not base and iata not in NOMBRES and iata not in AJUSTES:
        return None
    base = base or {}
    ciudad, pais, pais_nombre = corregir(iata, "", base.get("pais", ""), "")
    return {"iata": iata, "ciudad": ciudad, "pais": pais, "pais_nombre": pais_nombre,
            "nombre": base.get("nombre", ""), "lat": base.get("lat"), "lon": base.get("lon")}


def corregir(iata, ciudad, pais="", pais_nombre=""):
    """Devuelve (ciudad, pais, pais_nombre) ya arreglados.

    - Casos de AJUSTES: mandan siempre.
    - Si la fuente no trajo ciudad (vacía o igual al código): se usa NOMBRES o, si no está, la tabla general.
    - Si falta el país o su nombre: se completa con la tabla.
    Una ciudad buena que ya venía de la fuente no se cambia."""
    iata = (iata or "").upper()
    if iata in AJUSTES:
        return AJUSTES[iata]
    base = cargar().get(iata, {})
    if not ciudad or ciudad.strip().upper() == iata:
        ciudad = NOMBRES.get(iata) or base.get("ciudad") or ciudad or iata
    pais = (pais or base.get("pais") or "").upper()
    if not pais_nombre or pais_nombre.strip().upper() == pais:
        pais_nombre = PAISES.get(pais) or pais_nombre or pais
    return ciudad, pais, pais_nombre


def regenerar():
    """Descarga OurAirports y reescribe datos/aeropuertos.json (aeropuertos con IATA y vuelos regulares)."""
    import requests
    r = requests.get(URL_DATOS, timeout=120)
    r.raise_for_status()
    salida = {}
    for f in csv.DictReader(io.StringIO(r.content.decode("utf-8"))):
        iata = f["iata_code"].strip().upper()
        if (len(iata) != 3 or f["scheduled_service"] != "yes"
                or f["type"] not in ("large_airport", "medium_airport", "small_airport")):
            continue
        salida[iata] = {"ciudad": f["municipality"].strip() or f["name"].strip(), "pais": f["iso_country"],
                        "nombre": f["name"].strip(), "lat": round(float(f["latitude_deg"]), 4),
                        "lon": round(float(f["longitude_deg"]), 4)}
    ARCHIVO.parent.mkdir(exist_ok=True)
    ARCHIVO.write_text(json.dumps(salida, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                       encoding="utf-8")
    return len(salida)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--regenerar" in sys.argv:
        print(f"Guardados {regenerar()} aeropuertos en {ARCHIVO.name}")
    else:
        for c in (sys.argv[1:] or ["BOD", "EMA", "CAI", "EIN", "KUT"]):
            print(c, "→", ficha(c))
