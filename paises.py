r"""
paises.py — Países que el usuario ya conoce y cuáles son «nuevos» (Jawdrop).

Lee `paises_visitados.txt` (un país por línea, en inglés; las líneas con # se ignoran) y lo traduce a los
códigos de país de dos letras que ya usan Ryanair y Wizz (`pais`). También vale escribir directamente el
código (por ejemplo «XK»). Si una línea no se reconoce, `cargar()` lo devuelve en la lista de avisos:
nunca se descarta en silencio.

Cada línea puede llevar, tras una barra, la fecha de la primera visita y una nota (lo escribe el pasaporte):
`France | 2019-05 | Con Marta`. Lo que va tras la barra no cuenta para reconocer el país.

Casos raros: Irlanda del Norte cuenta como Reino Unido; Kosovo es «XK» (código no oficial, el que usa
Wizz); Vaticano, San Marino, Mónaco y Andorra no tienen vuelos propios, pero se reconocen para que no
den aviso.

Prueba: .venv\Scripts\python.exe paises.py
"""
from pathlib import Path

VERSION = "0.3"
ARCHIVO = Path(__file__).resolve().parent / "paises_visitados.txt"

# nombre en inglés (en minúsculas) -> código de país
CODIGOS = {
    "albania": "AL", "algeria": "DZ", "andorra": "AD", "armenia": "AM", "austria": "AT", "azerbaijan": "AZ",
    "bahrain": "BH", "belarus": "BY", "belgium": "BE", "bosnia and herzegovina": "BA",
    "bosnia & herzegovina": "BA", "bulgaria": "BG", "cambodia": "KH", "china": "CN", "costa rica": "CR",
    "croatia": "HR", "cyprus": "CY", "czechia": "CZ", "czech republic": "CZ", "denmark": "DK",
    "egypt": "EG", "estonia": "EE", "finland": "FI", "france": "FR", "georgia": "GE", "germany": "DE",
    "gibraltar": "GI", "greece": "GR", "hungary": "HU", "iceland": "IS", "india": "IN", "indonesia": "ID",
    "ireland": "IE", "israel": "IL", "italy": "IT", "japan": "JP", "jordan": "JO", "kazakhstan": "KZ",
    "kosovo": "XK", "kyrgyzstan": "KG", "laos": "LA", "latvia": "LV", "lebanon": "LB",
    "liechtenstein": "LI", "lithuania": "LT", "luxembourg": "LU", "malaysia": "MY", "maldives": "MV",
    "malta": "MT", "moldova": "MD", "monaco": "MC", "montenegro": "ME", "morocco": "MA", "nepal": "NP",
    "netherlands": "NL", "north macedonia": "MK", "norway": "NO", "oman": "OM", "philippines": "PH",
    "poland": "PL", "portugal": "PT", "qatar": "QA", "romania": "RO", "russia": "RU",
    "san marino": "SM", "saudi arabia": "SA", "serbia": "RS", "singapore": "SG", "slovakia": "SK",
    "slovenia": "SI", "south korea": "KR", "spain": "ES", "sri lanka": "LK", "sweden": "SE",
    "switzerland": "CH", "taiwan": "TW", "tajikistan": "TJ", "thailand": "TH", "tunisia": "TN",
    "turkey": "TR", "turkiye": "TR", "ukraine": "UA", "united arab emirates": "AE", "uae": "AE",
    "united kingdom": "GB", "uk": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "northern ireland": "GB", "united states": "US", "usa": "US", "uzbekistan": "UZ",
    "vatican city": "VA", "vatican": "VA", "vietnam": "VN",
    # Países con vuelo directo desde BCN que faltaban (12-10-2026): Level, Iberojet, Air Canada, Avianca...
    "canada": "CA", "mexico": "MX", "dominican republic": "DO", "el salvador": "SV", "honduras": "HN",
    "colombia": "CO", "peru": "PE", "chile": "CL", "argentina": "AR", "brazil": "BR", "bolivia": "BO",
    "gambia": "GM", "senegal": "SN", "cape verde": "CV", "kuwait": "KW", "hong kong": "HK",
}


def cargar(ruta=ARCHIVO):
    """Devuelve (códigos de países visitados, avisos). Si falta el archivo, todo es «nuevo» y avisa."""
    if not Path(ruta).exists():
        return set(), [f"No encuentro {Path(ruta).name}: todos los países saldrán como nuevos."]
    codigos, avisos = set(), []
    for n, linea in enumerate(Path(ruta).read_text(encoding="utf-8").splitlines(), 1):
        t = linea.split("|")[0].strip()
        if not t or linea.strip().startswith("#"):
            continue
        cod = CODIGOS.get(t.lower())
        if cod is None and len(t) == 2 and t.isalpha():
            cod = t.upper()
        if cod is None:
            avisos.append(f"paises_visitados.txt, línea {n}: no reconozco «{t}» (escríbelo en inglés o "
                          "con su código de 2 letras). No cuenta como visitado.")
        else:
            codigos.add(cod)
    return codigos, avisos


_VISITADOS = None


def visitados():
    global _VISITADOS
    if _VISITADOS is None:
        _VISITADOS = cargar()[0]
    return _VISITADOS


def es_nuevo(codigo):
    """True si el país (código de 2 letras) no está en la lista de visitados. Sin código → no se marca."""
    return bool(codigo) and codigo.upper() not in visitados()


if __name__ == "__main__":
    v, avisos = cargar()
    print(f"paises.py {VERSION}: {len(v)} países visitados reconocidos.")
    for a in avisos:
        print("  AVISO:", a)
    for c in ("GB", "XK", "AD", "IE", "TR", "ES", "GE"):
        print(f"  {c}: {'NUEVO' if es_nuevo(c) else 'ya visitado'}")
