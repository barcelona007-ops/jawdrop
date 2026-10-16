// Ryanair en la nube: construye las mismas consultas que ryanair.py 3.3 (mismos parámetros → misma clave de caché)
// y las hace despacio. Solo la parte de pedir datos; el cruce de idas y vueltas va aparte.
export const VERSION = "1.0";
export const HORAS_CACHE = 24;
export const PAUSA_MS = 3000;
export const URL_IDA_VUELTA = "https://www.ryanair.com/api/farfnd/v4/roundTripFares";
export const URL_SOLO_IDA = "https://www.ryanair.com/api/farfnd/v4/oneWayFares";
const CABECERAS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
  Accept: "application/json, text/plain, */*",
  "Accept-Language": "es-ES,es;q=0.9",
};
const COMUNES = { currency: "EUR", market: "es-es", adultPaxCount: 1 };

export function sumarDias(iso, n) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

// Consulta de las idas del domingo (como ryanair.idas).
export function consultaIdas(origen, domingo, desde, hasta) {
  return { url: URL_SOLO_IDA, params: { ...COMUNES, departureAirportIataCode: origen,
    outboundDepartureDateFrom: domingo, outboundDepartureDateTo: domingo,
    outboundDepartureTimeFrom: desde, outboundDepartureTimeTo: hasta } };
}

// Consulta de las vueltas de un día desde todos los aeropuertos (como ryanair.vueltas).
export function consultaVueltas(origen, domingo, dia, hoy, desde, hasta) {
  const ini = sumarDias(domingo, -6);
  return { url: URL_IDA_VUELTA, params: { ...COMUNES, departureAirportIataCode: origen,
    outboundDepartureDateFrom: ini > hoy ? ini : hoy, outboundDepartureDateTo: domingo,
    inboundDepartureDateFrom: dia, inboundDepartureDateTo: dia,
    inboundDepartureTimeFrom: desde, inboundDepartureTimeTo: hasta } };
}

export const consultaAeropuertos = { url: "https://www.ryanair.com/api/views/locate/5/airports/es/active", params: null, horas: 72, clave: ["ryanair", "aeropuertos"] };

export function partesClave(c) {
  return c.clave || ["ryanair", c.url, c.params];
}

// Consulta real. Lanza Error si Ryanair no responde 200 (no se insiste).
export async function pedir(c) {
  const url = new URL(c.url);
  if (c.params) for (const [k, v] of Object.entries(c.params)) url.searchParams.set(k, String(v));
  const r = await fetch(url, { headers: CABECERAS });
  if (r.status !== 200) throw new Error(`Ryanair respondió ${r.status}`);
  return await r.json();
}

export function enlace(desde, hasta, dia) {
  return "https://www.ryanair.com/es/es/trip/flights/select?adults=1&teens=0&children=0&infants=0" +
    `&dateOut=${dia}&isConnectedFlight=false&isReturn=false&discount=0&originIata=${desde}&destinationIata=${hasta}`;
}
