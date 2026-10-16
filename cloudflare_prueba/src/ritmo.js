// Prueba 2: ritmo real. Unas 30 consultas despacio (4 s entre una y otra, sin reintentos) a las cuatro fuentes,
// como haría una actualización de verdad (varios domingos, varias rutas). Se va escribiendo el avance en pantalla.
// Si una fuente da 403/429/reto, se anota y esa fuente se deja de consultar (no se insiste).
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36";
const PAUSA_MS = 4000;
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
const iso = (d) => d.toISOString().slice(0, 10);
const sumar = (d, n) => { const x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; };

function domingos(n) {
  let d = sumar(new Date(), 7);
  while (d.getUTCDay() !== 0) d = sumar(d, 1);
  return Array.from({ length: n }, (_, i) => sumar(d, 7 * i));
}

export async function ritmo(emitir) {
  const bloqueada = new Set();
  const resumen = {};
  let ultima = 0;
  async function consulta(fuente, nombre, f) {
    if (bloqueada.has(fuente)) return;
    const espera = PAUSA_MS - (Date.now() - ultima);
    if (espera > 0) await dormir(espera);
    const t0 = Date.now();
    let linea;
    try {
      const r = await f();
      const txt = await r.text();
      ultima = Date.now();
      let ok = r.status === 200;
      let detalle = "";
      try { const j = JSON.parse(txt); detalle = Array.isArray(j.fares) ? `${j.fares.length} vuelos` : ""; } catch (_) { ok = false; detalle = "no es JSON"; }
      if (r.status === 403 || r.status === 429 || r.headers.get("cf-mitigated")) { bloqueada.add(fuente); detalle += " · BLOQUEO: se deja de consultar"; }
      resumen[fuente] = resumen[fuente] || { ok: 0, mal: 0 };
      resumen[fuente][ok ? "ok" : "mal"]++;
      linea = `${ok ? "✅" : "❌"} ${nombre} · ${r.status} · ${Date.now() - t0} ms ${detalle}`;
    } catch (e) {
      ultima = Date.now();
      resumen[fuente] = resumen[fuente] || { ok: 0, mal: 0 };
      resumen[fuente].mal++;
      linea = `❌ ${nombre} · error ${e}`;
    }
    await emitir(linea);
  }

  const dom = domingos(4);
  const RY = "https://www.ryanair.com/api/farfnd/v4/";
  const cabRy = { "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "es-ES,es;q=0.9" };
  const com = { currency: "EUR", market: "es-es", adultPaxCount: "1" };

  // Ryanair: aeropuertos, ida y vuelta de 4 domingos, y un ida+vuelta
  await consulta("ryanair", "Ryanair lista de aeropuertos", () => fetch("https://www.ryanair.com/api/views/locate/5/airports/es/active", { headers: cabRy }));
  for (const d of dom) {
    const dia = iso(d);
    await consulta("ryanair", `Ryanair ida ${dia}`, () => fetch(RY + "oneWayFares?" + new URLSearchParams({ ...com, departureAirportIataCode: "BCN", outboundDepartureDateFrom: dia, outboundDepartureDateTo: dia, outboundDepartureTimeFrom: "06:00", outboundDepartureTimeTo: "10:00" }), { headers: cabRy }));
    const lun = iso(sumar(d, 1));
    await consulta("ryanair", `Ryanair vuelta ${lun}`, () => fetch(RY + "oneWayFares?" + new URLSearchParams({ ...com, departureAirportIataCode: "BUD", arrivalAirportIataCode: "BCN", outboundDepartureDateFrom: lun, outboundDepartureDateTo: lun, outboundDepartureTimeFrom: "20:00", outboundDepartureTimeTo: "23:59" }), { headers: cabRy }));
  }
  await consulta("ryanair", "Ryanair ida+vuelta (roundTripFares)", () => fetch(RY + "roundTripFares?" + new URLSearchParams({ ...com, departureAirportIataCode: "BCN", outboundDepartureDateFrom: iso(dom[0]), outboundDepartureDateTo: iso(dom[0]), inboundDepartureDateFrom: iso(sumar(dom[0], 1)), inboundDepartureDateTo: iso(sumar(dom[0], 2)) }), { headers: cabRy }));

  // Wizz: portada + sesión una vez, luego mapa de rutas y 6 rutas
  const cab = { "Accept": "application/json, text/plain, */*", "Accept-Language": "en-GB,en;q=0.9", "Origin": "https://www.wizzair.com", "Referer": "https://www.wizzair.com/en-gb", "User-Agent": UA };
  let version = "29.14.0", token = "";
  try {
    const home = await fetch("https://www.wizzair.com/en-gb", { headers: cab });
    const m = (await home.text()).match(/be\.wizzair\.com\/(\d+\.\d+\.\d+)\/Api/);
    if (m) version = m[1];
    await dormir(PAUSA_MS);
    const s = await fetch(`https://be.wizzair.com/${version}/Api/userSession/new`, { headers: cab });
    for (const c of s.headers.getSetCookie()) { const m2 = c.match(/RequestVerificationToken=([^;]+)/); if (m2) token = m2[1]; }
    await emitir(`ℹ️ Wizz: versión ${version}, token ${token ? "obtenido" : "NO obtenido"}`);
  } catch (e) { await emitir(`❌ Wizz sesión: ${e}`); }
  const hw = { ...cab, "Content-Type": "application/json" };
  if (token) { hw["X-RequestVerificationToken"] = token; hw["Cookie"] = `RequestVerificationToken=${token}`; }
  const base = `https://be.wizzair.com/${version}/Api`;
  await consulta("wizz", "Wizz mapa de rutas (asset/map)", () => fetch(`${base}/asset/map?languageCode=es-es`, { headers: hw }));
  for (const dest of ["BUD", "WAW", "KRK", "OTP", "SOF", "VIE"]) {
    const a = iso(dom[0]), b = iso(sumar(dom[0], 1));
    await consulta("wizz", `Wizz BCN↔${dest}`, () => fetch(`${base}/search/timetableV2`, { method: "POST", headers: hw, body: JSON.stringify({
      flightList: [{ departureStation: "BCN", arrivalStation: dest, from: a, to: iso(sumar(dom[3], 0)) }, { departureStation: dest, arrivalStation: "BCN", from: b, to: iso(sumar(dom[3], 2)) }],
      priceType: "regular", adultCount: 1, childCount: 0, infantCount: 0 }) }));
  }

  // Vueling: 3 lotes de 10 destinos
  const lotes = ["ORY,AMS,FCO,LIS,PRG,BRU,CDG,LHR,MXP,ATH", "BUD,WAW,VIE,DUB,CPH,ARN,OSL,HEL,ZRH,GVA", "NAP,BLQ,VCE,FLR,TLS,NCE,MRS,LYS,BOD,NTE"];
  for (const l of lotes) await consulta("vueling", `Vueling bestPrices (${l.slice(0, 11)}…)`, () => fetch("https://apiw.vueling.com/api/v1/bestPrices?" + new URLSearchParams({ originCode: "BCN", destinationCodes: l, months: "1", startDate: iso(dom[0]), currencyCode: "EUR" })));

  // Kiwi: 4 domingos a varios destinos
  const q = `query SearchOneWayItinerariesQuery($search: SearchOnewayInput,$filter: ItinerariesFilterInput,$options: ItinerariesOptionsInput){onewayItineraries(search:$search,filter:$filter,options:$options){__typename ... on AppError{error: message} ... on Itineraries{itineraries{__typename ... on ItineraryOneWay{id priceEur{amount}}}}}}`;
  for (const d of dom) {
    const dia = iso(d);
    await consulta("kiwi", `Kiwi ${dia}`, () => fetch("https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchOneWayItinerariesQuery", { method: "POST", headers: { "User-Agent": "FlightFinder/0.1.0", "Content-Type": "application/json" }, body: JSON.stringify({ query: q, variables: {
      search: { itinerary: { source: { ids: ["Station:airport:BCN"] }, destination: { ids: ["Station:airport:BUD", "Station:airport:WAW", "Station:airport:PRG"] }, outboundDepartureDate: { start: `${dia}T06:00:00`, end: `${dia}T10:00:00` } }, passengers: { adults: 1, children: 0, infants: 0, adultsHoldBags: 0, adultsHandBags: 0, childrenHoldBags: [], childrenHandBags: [] }, cabinClass: { cabinClass: "ECONOMY", applyMixedClasses: false } },
      filter: { transportTypes: ["FLIGHT"], contentProviders: ["KIWI", "FRESH", "KAYAK"], limit: 10, maxStopsCount: 0 },
      options: { sortBy: "PRICE", currency: "eur", locale: "es", partner: "skypicker", affilID: "skypicker", storeSearch: false } } }) }));
  }
  await emitir("— FIN —");
  await emitir(JSON.stringify(resumen));
}
