// GoToGate en la nube: mismas consultas que gotogate.py 0.3 (misma clave de caché: lo que lee la nube sirve en el PC/Raspberry y al revés).
// Ida y vuelta CON PRECIO CERRADO, los 10 vuelos más baratos. Hoy solo Cuba (Kiwi no la vende).
// Si GoToGate responde mal, se lanza GotogateBloqueado y NO se insiste. Presentarse siempre con nombre propio.
import { conCache } from "./cache.js";

export const VERSION = "0.1";
export const HORAS_CACHE = 24;
const URL = "https://es.gotogate.com/graphql/SearchOnResultPage";
const PORTADA = "https://es.gotogate.com/";
const UA = "EscapadasFlash/0.3 (uso personal)";

export class GotogateBloqueado extends Error {}

const CONSULTA = `query SearchOnResultPage($routes: [Route!]!, $cabinClass: CabinClass, $direct: Boolean, $carrierCodes: [String], $adults: Int!, $childAges: [Int], $sortTypeCode: String, $filters: [Filter!]) {
  search(routes: $routes, cabinClass: $cabinClass, direct: $direct, carrierCodes: $carrierCodes, adults: $adults, childAges: $childAges, sortTypeCode: $sortTypeCode, filters: $filters) {
    flightsCount
    flights {
      id
      shareableUrl
      travelerPrices { price { price { value } } }
      bounds { segments { __typename
        ... on TripSegment { departuredAt arrivedAt duration flightNumber origin { code } destination { code } marketingCarrier { code name } }
        ... on EventSegment { duration } } }
    }
  }
}`;

// Sesión = las cookies de la portada (como cualquier navegador). Se abre una por consulta.
async function sesion() {
  let p;
  try { p = await fetch(PORTADA, { headers: { "User-Agent": UA } }); } catch (e) { throw new GotogateBloqueado(String(e.message || e)); }
  return (p.headers.getSetCookie ? p.headers.getSetCookie() : []).map((c) => c.split(";")[0]).join("; ");
}

// Una consulta real. Devuelve la lista de vuelos en bruto (igual que gotogate._consulta de Python). 0 vuelos con sesión nueva: se repite UNA vez.
export async function pedir(origen, destino, ida, vuelta) {
  const rutas = [{ origin: origen, destination: destino, departureDate: ida }];
  if (vuelta) rutas.push({ origin: destino, destination: origen, departureDate: vuelta });
  const cuerpo = { operationName: "SearchOnResultPage", query: CONSULTA,
    variables: { adults: 1, cabinClass: "ECONOMY", carrierCodes: [], childAges: [], direct: false, filters: [], routes: rutas, sortTypeCode: "CHEAP_TRIP" } };
  for (let intento = 1; intento <= 2; intento++) {
    const cookie = await sesion();
    let r;
    try {
      r = await fetch(URL, { method: "POST", headers: { "User-Agent": UA, "Content-Type": "application/json", "X-ETG-GraphQL-Operation": "SearchOnResultPage", cookie }, body: JSON.stringify(cuerpo) });
    } catch (e) { throw new GotogateBloqueado(String(e.message || e)); }
    if (r.status !== 200) throw new GotogateBloqueado(`GoToGate respondió ${r.status}`);
    let s;
    try { s = (await r.json()).data.search; } catch (e) { throw new GotogateBloqueado("respuesta de GoToGate no entendida"); }
    if (s.flightsCount || intento === 2) return s.flights || [];
  }
  return [];
}

// Con caché de 24 h (misma clave que gotogate.buscar de Python: ["gotogate2", origen, destino, ida, vuelta]).
export async function buscar(env, origen, destino, ida, vuelta = null) {
  const { datos, guardado, deCache } = await conCache(env, ["gotogate2", origen, destino, ida, vuelta], HORAS_CACHE, () => pedir(origen, destino, ida, vuelta));
  return { vuelos: datos, guardado, deCache };
}
