// Puerto de geografia.py 2.1 (reglas del usuario: ¿se puede volver desde otro aeropuerto? tierra, vecinos, ferri y 200 km por 24 h (más en el mismo país)).
// Las tablas están generadas desde geografia.py; si se cambia allí, hay que regenerarlas (ver ESTADO.md).
export const VERSION = "1.0";
const T = {"ISLAS": {"PMI": "Mallorca", "IBZ": "Ibiza", "MAH": "Menorca", "TFS": "Tenerife", "TFN": "Tenerife", "LPA": "Gran Canaria", "ACE": "Lanzarote", "FUE": "Fuerteventura", "SPC": "La Palma", "VDE": "El Hierro", "GMZ": "La Gomera", "FNC": "Madeira", "PXO": "Porto Santo", "PDL": "São Miguel", "TER": "Terceira", "CAG": "Cerdeña", "AHO": "Cerdeña", "OLB": "Cerdeña", "PMO": "Sicilia", "CTA": "Sicilia", "TPS": "Sicilia", "CIY": "Sicilia", "AJA": "Córcega", "BIA": "Córcega", "FSC": "Córcega", "CLY": "Córcega", "LMP": "Lampedusa", "PNL": "Pantelaria", "HER": "Creta", "CHQ": "Creta", "JSH": "Creta", "RHO": "Rodas", "CFU": "Corfú", "KGS": "Cos", "JTR": "Santorini", "JMK": "Míconos", "ZTH": "Zante", "EFL": "Cefalonia", "SMI": "Samos", "MJT": "Lesbos", "JSI": "Esciatos", "PAS": "Paros", "JNX": "Naxos", "BWK": "Brač", "VBY": "Gotland", "RNN": "Bornholm", "FAE": "Feroe", "IOM": "Isla de Man", "JER": "Jersey", "GCI": "Guernsey"}, "IRLANDA_NORTE": ["BFS", "BHD", "LDY"], "AFRICA": ["CV", "DZ", "EG", "GM", "LY", "MA", "MR", "SN", "TN"], "PAISES_ISLA": {"MT": "Malta", "CY": "Chipre", "IS": "Islandia"}, "SIN_FERRI": ["Chipre", "El Hierro", "Fuerteventura", "Gran Canaria", "Islandia", "La Gomera", "La Palma", "Lampedusa", "Lanzarote", "Madeira", "Pantelaria", "Porto Santo", "São Miguel", "Tenerife", "Terceira"], "CON_FERRI": ["Bornholm", "Brač", "Cefalonia", "Cerdeña", "Corfú", "Cos", "Creta", "Córcega", "Esciatos", "Feroe", "Gotland", "Guernsey", "Ibiza", "Irlanda", "Isla de Man", "Jersey", "Lesbos", "Mallorca", "Malta", "Menorca", "Míconos", "Naxos", "Paros", "Rodas", "Samos", "Santorini", "Sicilia", "Zante"], "GRUPOS": [["Ibiza", "Mallorca", "Menorca"], ["El Hierro", "Fuerteventura", "Gran Canaria", "La Gomera", "La Palma", "Lanzarote", "Tenerife"], ["Madeira", "Porto Santo"], ["São Miguel", "Terceira"], ["Lampedusa", "Malta", "Pantelaria", "Sicilia"], ["Cerdeña", "Córcega"], ["Cefalonia", "Corfú", "Cos", "Creta", "Esciatos", "Lesbos", "Míconos", "Naxos", "Paros", "Rodas", "Samos", "Santorini", "Zante"]], "FERRIS_PAISES": ["AL-IT", "BE-GB", "DE-DK", "DE-FI", "DE-SE", "DK-NO", "DK-SE", "DZ-ES", "DZ-FR", "DZ-IT", "EE-FI", "EE-SE", "ES-GB", "ES-IE", "ES-IT", "ES-MA", "FI-SE", "FR-GB", "FR-GG", "FR-IE", "FR-JE", "FR-MA", "FR-TN", "GB-GG", "GB-IE", "GB-IM", "GB-JE", "GB-NL", "GR-IT", "GR-TR", "HR-IT", "IE-IM", "IT-ME", "IT-MT", "IT-TN", "LV-SE", "PL-SE"], "FRONTERAS": ["AD-ES", "AD-FR", "AE-OM", "AE-SA", "AL-GR", "AL-ME", "AL-MK", "AL-XK", "AM-AZ", "AM-GE", "AM-IR", "AM-TR", "AT-CH", "AT-CZ", "AT-DE", "AT-HU", "AT-IT", "AT-LI", "AT-SI", "AT-SK", "AZ-GE", "AZ-IR", "AZ-RU", "BA-HR", "BA-ME", "BA-RS", "BE-DE", "BE-FR", "BE-LU", "BE-NL", "BG-GR", "BG-MK", "BG-RO", "BG-RS", "BG-TR", "BH-SA", "BY-LT", "BY-LV", "BY-PL", "BY-RU", "BY-UA", "CA-US", "CH-DE", "CH-FR", "CH-IT", "CH-LI", "CN-IN", "CN-KG", "CN-KZ", "CN-LA", "CN-NP", "CN-TJ", "CN-VN", "CR-NI", "CR-PA", "CZ-DE", "CZ-PL", "CZ-SK", "DE-DK", "DE-FR", "DE-LU", "DE-NL", "DE-PL", "DK-SE", "DZ-LY", "DZ-MA", "DZ-MR", "DZ-TN", "EE-LV", "EE-RU", "EG-IL", "EG-LY", "ES-FR", "ES-GI", "ES-PT", "FI-NO", "FI-RU", "FI-SE", "FR-IT", "FR-LU", "FR-MC", "GB-IE", "GE-RU", "GE-TR", "GM-SN", "GR-MK", "GR-TR", "HR-HU", "HR-ME", "HR-RS", "HR-SI", "HU-RO", "HU-RS", "HU-SK", "HU-UA", "ID-MY", "IL-JO", "IL-LB", "IN-NP", "IQ-JO", "IQ-TR", "IR-TR", "IT-SI", "IT-SM", "IT-VA", "JO-SA", "JO-SY", "KG-KZ", "KG-TJ", "KG-UZ", "KH-LA", "KH-TH", "KH-VN", "KZ-RU", "KZ-UZ", "LA-TH", "LA-VN", "LB-SY", "LT-LV", "LT-PL", "LT-RU", "LV-RU", "LY-TN", "MA-MR", "MD-RO", "MD-UA", "ME-RS", "ME-XK", "MK-RS", "MK-XK", "ML-MR", "MR-SN", "MX-US", "MY-SG", "MY-TH", "NO-RU", "NO-SE", "OM-SA", "PL-RU", "PL-SK", "PL-UA", "QA-SA", "RO-RS", "RO-UA", "RS-XK", "RU-UA", "SK-UA", "SY-TR", "TJ-UZ"]};
const KM_POR_DIA = 200, KM_MISMO_PAIS = 300, KM_FERROCARRIL = 400,
  PAISES_FERROCARRIL = new Set(["ES","FR","DE","IT","CH","AT","NL","BE","GB","CZ","SE","DK","PL","JP","KR","CN"]), FACTOR_CARRETERA = 1.3, CONTINENTE = "Europa continental";
const CON_FERRI = new Set(T.CON_FERRI);
const FERRIS = new Set(T.FERRIS_PAISES), FRONT = new Set(T.FRONTERAS);
const GRUPOS = T.GRUPOS.map((g) => new Set(g));
const par = (a, b) => [a, b].sort().join("-");

export function tierra(iata, pais) {
  if (T.ISLAS[iata]) return T.ISLAS[iata];
  if (T.IRLANDA_NORTE.includes(iata) || pais === "IE") return "Irlanda";
  if (T.PAISES_ISLA[pais]) return T.PAISES_ISLA[pais];
  if (T.AFRICA.includes(pais)) return "África";
  return CONTINENTE;
}
function conectadas(a, b) {
  if (a === CONTINENTE || b === CONTINENTE) return CON_FERRI.has(a === CONTINENTE ? b : a);
  return GRUPOS.some((g) => g.has(a) && g.has(b));
}
export function sonVecinos(a, b) { return a === b || FRONT.has(par(a, b)) || FERRIS.has(par(a, b)); }
export const kmPorTierra = (kmRecta) => Math.round(kmRecta * FACTOR_CARRETERA);

// ¿Se puede volver desde b habiendo llegado a a? null si no; si sí, {km, ferri}.
export function trayecto(a, paisA, b, paisB, kmRecta, diasFuera, radio = null, conMar = false) {
  if (kmRecta == null) return null;
  const ta = tierra(a, paisA), tb = tierra(b, paisB);
  let ferri = false;
  if (ta !== tb) {
    const otra = ta === "África" ? tb : ta;
    const africaFerri = (ta === "África" || tb === "África") && (otra === CONTINENTE || CON_FERRI.has(otra)) && FERRIS.has(par(paisA, paisB));
    if (conectadas(ta, tb) || africaFerri) ferri = true;
    else if (!conMar) return null;
  }
  if (!conMar && !sonVecinos(paisA, paisB)) return null;
  const km = kmPorTierra(kmRecta);
  if (radio !== null) { if (kmRecta > radio) return null; }
  else {
    const porDia = paisA === paisB ? (PAISES_FERROCARRIL.has(paisA) ? KM_FERROCARRIL : KM_MISMO_PAIS) : KM_POR_DIA;
    if (km > porDia * Math.max(1, diasFuera)) return null;
  }
  return { km, ferri };
}
