// Kiwi.com en la nube: mismas consultas que kiwi.py 1.1 (misma clave de caché). Da las aerolíneas que no leemos directo
// (Vueling, easyJet, Turkish, Pegasus…) con el precio estimado de la aerolínea (precio de Kiwi menos su comisión medida).
// Si Kiwi responde mal, se lanza KiwiBloqueado y NO se insiste.
export const VERSION = "1.0";
export const HORAS_CACHE = 24;
export const PAUSA_MS = 5000;
export const LOTE = 20;   // aeropuertos de origen por consulta de vueltas
const URL = "https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchOneWayItinerariesQuery";
const DIAS_SEMANA = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"];   // getUTCDay()
// Aerolíneas que ya se leen directo: Ryanair (FR, RK, AL, RR) y Wizz (W6, W4, W9, 5W)
const YA_LEIDAS = ["FR", "RK", "AL", "RR", "W6", "W4", "W9", "5W"];

export class KiwiBloqueado extends Error {}

const CONSULTA = `query SearchOneWayItinerariesQuery($search: SearchOnewayInput,$filter: ItinerariesFilterInput,$options: ItinerariesOptionsInput){
onewayItineraries(search:$search,filter:$filter,options:$options){__typename
... on AppError{error: message}
... on Itineraries{itineraries{__typename ... on ItineraryOneWay{id priceEur{amount}
sector{duration sectorSegments{segment{source{station{code name gps{lat lng} city{name country{code name}}} localTime} destination{station{code name gps{lat lng} city{name country{code name}}} localTime} carrier{code name}}}}}}}}}`;

// precio_kiwi = fijo + pendiente × precio de la aerolínea (medido; ver kiwi.py)
const COMISION = {
  VY: { fijo: 2.26, pendiente: 1.071 }, U2: { fijo: 14.5, pendiente: 1.0 }, TK: { fijo: 1.5, pendiente: 1.0 },
  PC: { fijo: 7.0, pendiente: 1.0 }, VF: { fijo: 9.0, pendiente: 1.0 }, W6: { fijo: 1.5, pendiente: 1.0 }, W4: { fijo: 1.5, pendiente: 1.0 },
  EW: { fijo: 3.0, pendiente: 1.0 }, HV: { fijo: 0.0, pendiente: 1.12 }, XQ: { fijo: 0.0, pendiente: 1.0 }, V7: { fijo: 3.0, pendiente: 1.0 },
};
const PORTADAS = { TK: "https://www.turkishairlines.com/es-es/", PC: "https://www.flypgs.com/es", VF: "https://www.ajet.com/es",
  EW: "https://www.eurowings.com/es.html", HV: "https://www.transavia.com/es-ES/home/", XQ: "https://www.sunexpress.com/es-es/", V7: "https://www.volotea.com/es/" };

// Consulta de un día (ida: origenes=["Airport:BCN"], destinos=[]; vueltas: lote de orígenes y destinos=["Airport:BCN"]).
export function consultaKiwi(origenes, destinos, dia, hDesde, hHasta, limite = 50) {
  return { tipo: "kiwi", clave: ["kiwi", "consulta1", origenes, destinos, dia, hDesde, hHasta, limite], horas: HORAS_CACHE,
    origenes, destinos, dia, hDesde, hHasta, limite, etiqueta: `kiwi ${dia} ${origenes.length > 1 ? "vueltas" : origenes[0]}` };
}

export async function pedir(c) {
  const d = new Date(c.dia + "T00:00:00Z");
  const variables = {
    search: { itinerary: { source: { ids: c.origenes }, destination: { ids: c.destinos },
      outboundDepartureDate: { start: `${c.dia}T00:00:00`, end: `${c.dia}T23:59:59` } },
      passengers: { adults: 1, children: 0, infants: 0, adultsHoldBags: 0, adultsHandBags: 0, childrenHoldBags: [], childrenHandBags: [] },
      cabinClass: { cabinClass: "ECONOMY", applyMixedClasses: false } },
    filter: { transportTypes: ["FLIGHT"], contentProviders: ["KIWI", "FRESH", "KAYAK"], limit: c.limite, maxStopsCount: 0,
      outbound: { departureHours: { start: parseInt(c.hDesde.slice(0, 2), 10), end: parseInt(c.hHasta.slice(0, 2), 10) }, days: [DIAS_SEMANA[d.getUTCDay()]] } },
    options: { sortBy: "PRICE", currency: "eur", locale: "es", partner: "skypicker", affilID: "skypicker", storeSearch: false },
  };
  let r;
  try {
    r = await fetch(URL, { method: "POST", headers: { "User-Agent": "FlightFinder/0.1.0", "Content-Type": "application/json" }, body: JSON.stringify({ query: CONSULTA, variables }) });
  } catch (e) { throw new KiwiBloqueado(String(e.message || e)); }
  if (r.status !== 200) throw new KiwiBloqueado(`Kiwi respondió ${r.status}`);
  let res;
  try { res = (await r.json()).data.onewayItineraries; } catch (e) { throw new KiwiBloqueado("respuesta de Kiwi no entendida"); }
  if (!res || res.__typename !== "Itineraries") throw new KiwiBloqueado(`Kiwi devolvió un error: ${res && res.error}`);
  return res.itineraries;
}

function enlace(desde, hasta, dia, sigla) {
  if (sigla === "VY") return `https://www.skyscanner.es/transporte/vuelos/${desde.toLowerCase()}/${hasta.toLowerCase()}/${dia.slice(2, 4)}${dia.slice(5, 7)}${dia.slice(8, 10)}/?adultsv2=1&cabinclass=economy&rtn=0&preferdirects=true`;
  if (sigla === "U2") return `https://www.easyjet.com/es/buy/flights?isOneWay=on&dep=${desde}&dest=${hasta}&dd=${dia}&apax=1&cpax=0&ipax=0&pid=www.easyjet.com`;
  if (PORTADAS[sigla]) return PORTADAS[sigla];
  return `https://www.kiwi.com/es/search/results/${desde}/${hasta}/${dia}/no-return?stopNumber=0`;
}

// Itinerarios de Kiwi → tramos comunes; el más barato por aeropuerto, aerolínea y salida; salta las aerolíneas ya leídas directo.
export function tramos(its, sentido) {
  const mejores = new Map();
  for (const it of its || []) {
    const segs = (it.sector && it.sector.sectorSegments) || [];
    if (segs.length !== 1) continue;
    const s = segs[0].segment, o = s.source, dd = s.destination;
    const sigla = s.carrier.code;
    if (YA_LEIDAS.includes(sigla)) continue;
    const desde = o.station.code, hasta = dd.station.code;
    const precioKiwi = Number(it.priceEur.amount);
    const com = COMISION[sigla];
    const precio = com ? Math.max(Math.round((precioKiwi - com.fijo) / com.pendiente), 0) : precioKiwi;
    const est = sentido === "ida" ? dd.station : o.station;
    const ciudad = est.city || {}, pais = ciudad.country || {};
    const gps = est.gps || {};
    const t = {
      aerolinea: s.carrier.name, sigla, desde, hasta, destino: est.code, ciudad: ciudad.name || est.name || est.code,
      pais: String(pais.code || "").toUpperCase(), salida: o.localTime.slice(0, 16), llegada: dd.localTime.slice(0, 16),
      aprox: false, minimo: false, precio, estimado: !!com, enlace: enlace(desde, hasta, o.localTime.slice(0, 10), sigla),
      coords: gps.lat != null ? [gps.lat, gps.lng] : null,
    };
    const k = `${t.destino}|${t.aerolinea}|${t.salida}`;
    if (!mejores.has(k) || t.precio < mejores.get(k).precio) mejores.set(k, t);
  }
  return [...mejores.values()];
}
