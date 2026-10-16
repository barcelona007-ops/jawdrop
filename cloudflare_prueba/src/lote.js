// Prueba 3: unas 100 consultas despacio (4 s entre una y otra, sin reintentos), repartidas en 3 tandas porque el plan
// gratuito de Workers solo deja ~50 consultas por visita. Las fuentes van alternadas (nunca dos seguidas a la misma).
// Si una fuente da 403/429/reto, se anota y esa fuente se deja de consultar en esa tanda (no se insiste).
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36";
const PAUSA_MS = 4000;
export const TANDAS = 3;
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
const iso = (d) => d.toISOString().slice(0, 10);
const sumar = (d, n) => { const x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; };

function domingos(n) {
  let d = sumar(new Date(), 7);
  while (d.getUTCDay() !== 0) d = sumar(d, 1);
  return Array.from({ length: n }, (_, i) => sumar(d, 7 * i));
}

const RY = "https://www.ryanair.com/api/farfnd/v4/";
const cabRy = { "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "es-ES,es;q=0.9" };
const com = { currency: "EUR", market: "es-es", adultPaxCount: "1" };
const Q = `query SearchOneWayItinerariesQuery($search: SearchOnewayInput,$filter: ItinerariesFilterInput,$options: ItinerariesOptionsInput){onewayItineraries(search:$search,filter:$filter,options:$options){__typename ... on AppError{error: message} ... on Itineraries{itineraries{__typename ... on ItineraryOneWay{id priceEur{amount}}}}}}`;

// Lista completa de consultas, en orden alternado por fuente
function construir(w) {
  const dom = domingos(8);
  const ry = [], wz = [], vu = [], kw = [];
  ry.push(["Ryanair aeropuertos", () => fetch("https://www.ryanair.com/api/views/locate/5/airports/es/active", { headers: cabRy })]);
  for (const d of dom) {
    const dia = iso(d), lun = iso(sumar(d, 1)), mar = iso(sumar(d, 2));
    ry.push([`Ryanair ida ${dia}`, () => fetch(RY + "oneWayFares?" + new URLSearchParams({ ...com, departureAirportIataCode: "BCN", outboundDepartureDateFrom: dia, outboundDepartureDateTo: dia, outboundDepartureTimeFrom: "06:00", outboundDepartureTimeTo: "10:00" }), { headers: cabRy })]);
    for (const o of ["BUD", "PRG"]) ry.push([`Ryanair vuelta ${o} ${lun}`, () => fetch(RY + "oneWayFares?" + new URLSearchParams({ ...com, departureAirportIataCode: o, arrivalAirportIataCode: "BCN", outboundDepartureDateFrom: lun, outboundDepartureDateTo: lun, outboundDepartureTimeFrom: "20:00", outboundDepartureTimeTo: "23:59" }), { headers: cabRy })]);
    ry.push([`Ryanair vuelta BUD ${mar}`, () => fetch(RY + "oneWayFares?" + new URLSearchParams({ ...com, departureAirportIataCode: "BUD", arrivalAirportIataCode: "BCN", outboundDepartureDateFrom: mar, outboundDepartureDateTo: mar, outboundDepartureTimeFrom: "05:00", outboundDepartureTimeTo: "11:00" }), { headers: cabRy })]);
    ry.push([`Ryanair ida+vuelta ${dia}`, () => fetch(RY + "roundTripFares?" + new URLSearchParams({ ...com, departureAirportIataCode: "BCN", outboundDepartureDateFrom: dia, outboundDepartureDateTo: dia, inboundDepartureDateFrom: lun, inboundDepartureDateTo: mar }), { headers: cabRy })]);
  }
  wz.push(["Wizz mapa de rutas", () => w.get("asset/map?languageCode=es-es")]);
  for (const dest of ["BUD", "WAW", "KRK", "OTP", "SOF", "KTW", "GDN", "POZ", "WRO", "BEG", "TIA", "SKP", "VNO", "RIX", "CLJ", "IAS"]) {
    wz.push([`Wizz BCN↔${dest}`, () => w.post("search/timetableV2", { flightList: [
      { departureStation: "BCN", arrivalStation: dest, from: iso(dom[0]), to: iso(dom[4]) },
      { departureStation: dest, arrivalStation: "BCN", from: iso(sumar(dom[0], 1)), to: iso(sumar(dom[4], 2)) }],
      priceType: "regular", adultCount: 1, childCount: 0, infantCount: 0 })]);
  }
  const lotes = ["ORY,AMS,FCO,LIS,PRG,BRU,CDG,LHR,MXP,ATH", "BUD,WAW,VIE,DUB,CPH,ARN,OSL,HEL,ZRH,GVA", "NAP,BLQ,VCE,FLR,TLS,NCE,MRS,LYS,BOD,NTE"];
  for (const d of [dom[0], dom[4]]) for (const l of lotes) vu.push([`Vueling bestPrices ${iso(d)} (${l.slice(0, 7)}…)`, () => fetch("https://apiw.vueling.com/api/v1/bestPrices?" + new URLSearchParams({ originCode: "BCN", destinationCodes: l, months: "1", startDate: iso(d), currencyCode: "EUR" }))]);
  const sets = [["BUD", "WAW", "PRG"], ["VIE", "OTP", "SOF"], ["KRK", "BEG", "ATH"]];
  for (const d of dom) for (const set of sets) {
    const dia = iso(d);
    kw.push([`Kiwi ${dia} ${set.join("/")}`, () => fetch("https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchOneWayItinerariesQuery", { method: "POST", headers: { "User-Agent": "FlightFinder/0.1.0", "Content-Type": "application/json" }, body: JSON.stringify({ query: Q, variables: {
      search: { itinerary: { source: { ids: ["Station:airport:BCN"] }, destination: { ids: set.map((c) => `Station:airport:${c}`) }, outboundDepartureDate: { start: `${dia}T06:00:00`, end: `${dia}T10:00:00` } }, passengers: { adults: 1, children: 0, infants: 0, adultsHoldBags: 0, adultsHandBags: 0, childrenHoldBags: [], childrenHandBags: [] }, cabinClass: { cabinClass: "ECONOMY", applyMixedClasses: false } },
      filter: { transportTypes: ["FLIGHT"], contentProviders: ["KIWI", "FRESH", "KAYAK"], limit: 10, maxStopsCount: 0 },
      options: { sortBy: "PRICE", currency: "eur", locale: "es", partner: "skypicker", affilID: "skypicker", storeSearch: false } } }) })]);
  }
  // alternar: una de cada fuente por turnos
  const cola = [["ryanair", ry], ["wizz", wz], ["vueling", vu], ["kiwi", kw]];
  const res = [];
  while (cola.some(([, l]) => l.length)) for (const [f, l] of cola) if (l.length) res.push([f, ...l.shift()]);
  return res;
}

// Cliente de Wizz: portada + sesión una sola vez por tanda, solo si hace falta
function wizzCliente(emitir) {
  const cab = { "Accept": "application/json, text/plain, */*", "Accept-Language": "en-GB,en;q=0.9", "Origin": "https://www.wizzair.com", "Referer": "https://www.wizzair.com/en-gb", "User-Agent": UA };
  let listo = null;
  async function sesion() {
    let version = "29.14.0", token = "";
    try {
      const home = await fetch("https://www.wizzair.com/en-gb", { headers: cab });
      const m = (await home.text()).match(/be\.wizzair\.com\/(\d+\.\d+\.\d+)\/Api/);
      if (m) version = m[1];
      await dormir(PAUSA_MS);
      const s = await fetch(`https://be.wizzair.com/${version}/Api/userSession/new`, { headers: cab });
      for (const c of s.headers.getSetCookie()) { const m2 = c.match(/RequestVerificationToken=([^;]+)/); if (m2) token = m2[1]; }
    } catch (e) { await emitir(`❌ Wizz sesión: ${e}`); }
    await emitir(`ℹ️ Wizz: versión ${version}, token ${token ? "obtenido" : "NO obtenido"}`);
    const h = { ...cab, "Content-Type": "application/json" };
    if (token) { h["X-RequestVerificationToken"] = token; h["Cookie"] = `RequestVerificationToken=${token}`; }
    return { base: `https://be.wizzair.com/${version}/Api`, h };
  }
  const asegurar = () => (listo = listo || sesion());
  return {
    get: async (p) => { const s = await asegurar(); return fetch(`${s.base}/${p}`, { headers: s.h }); },
    post: async (p, cuerpo) => { const s = await asegurar(); return fetch(`${s.base}/${p}`, { method: "POST", headers: s.h, body: JSON.stringify(cuerpo) }); },
  };
}

export async function tanda(n, emitir) {
  const todas = construir(wizzCliente(emitir));
  const por = Math.ceil(todas.length / TANDAS);
  const mias = todas.slice((n - 1) * por, n * por);
  await emitir(`Tanda ${n} de ${TANDAS}: ${mias.length} consultas (de ${todas.length} en total)`);
  const bloqueada = new Set();
  let ultima = 0;
  for (const [fuente, nombre, f] of mias) {
    if (bloqueada.has(fuente)) { await emitir(`⏭️ ${nombre} · omitida (fuente bloqueada)`); continue; }
    const espera = PAUSA_MS - (Date.now() - ultima);
    if (espera > 0) await dormir(espera);
    const t0 = Date.now();
    try {
      const r = await f();
      const txt = await r.text();
      ultima = Date.now();
      let ok = r.status === 200, extra = "";
      try { const j = JSON.parse(txt); if (Array.isArray(j.fares)) extra = `${j.fares.length} vuelos`; } catch (_) { ok = false; extra = "no es JSON"; }
      if (r.status !== 200) extra += " · respuesta: " + txt.slice(0, 160).replace(/\s+/g, " ");
      if (r.status === 403 || r.status === 429 || r.headers.get("cf-mitigated")) { bloqueada.add(fuente); extra += " · BLOQUEO: se deja de consultar esta fuente"; }
      await emitir(`${ok ? "✅" : "❌"} [${fuente}] ${nombre} · ${r.status} · ${Date.now() - t0} ms ${extra}`);
    } catch (e) {
      ultima = Date.now();
      await emitir(`❌ [${fuente}] ${nombre} · error ${e}`);
    }
  }
  await emitir(`— FIN TANDA ${n} —`);
}
