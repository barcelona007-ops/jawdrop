// Paso 0 de Cloudflare: prueba de puertas. UNA consulta a cada fuente (Ryanair, Wizz, Vueling, Kiwi),
// despacio (5 s entre una y otra), sin reintentos y sin disfrazarse. Si alguna da 403, 429, captcha
// o reto antibot, se enseña tal cual y NO se insiste.
// Solo consulta cuando se abre /probar; la portada solo explica y tiene el botón.
const VERSION = "1.4";
const PAUSA_MS = 5000;
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36";

import { ritmo } from "./ritmo.js";
import { tanda, TANDAS } from "./lote.js";

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
const iso = (d) => d.toISOString().slice(0, 10);

// Próximo domingo con al menos 7 días de margen (para que haya vuelos a la venta)
function domingo() {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + 7);
  while (d.getUTCDay() !== 0) d.setUTCDate(d.getUTCDate() + 1);
  return d;
}

// Resume una respuesta: código, tiempo, si parece un reto antibot y si el contenido «cuadra»
async function resumir(nombre, peticion, cuadra) {
  const t0 = Date.now();
  const res = { fuente: nombre };
  try {
    const r = await peticion();
    const texto = await r.text();
    res.codigo = r.status;
    res.ms = Date.now() - t0;
    res.tipo = r.headers.get("content-type") || "";
    res.cf_mitigated = r.headers.get("cf-mitigated") || "";
    res.servidor = r.headers.get("server") || "";
    const reto = /just a moment|captcha|kasada|access denied|attention required|px-captcha|incapsula|akamai/i.test(texto.slice(0, 3000));
    res.parece_reto = reto || r.status === 403 || r.status === 429 || res.cf_mitigated !== "";
    let json = null;
    try { json = JSON.parse(texto); } catch (_) { /* no es JSON */ }
    res.es_json = json !== null;
    res.cuadra = json !== null && r.status === 200 ? cuadra(json) : "no";
    res.muestra = texto.slice(0, 200).replace(/\s+/g, " ");
  } catch (e) {
    res.error = String(e);
    res.ms = Date.now() - t0;
    res.cuadra = "no";
  }
  return res;
}

async function ryanair(dia) {
  const p = new URLSearchParams({
    currency: "EUR", market: "es-es", adultPaxCount: "1",
    departureAirportIataCode: "BCN", outboundDepartureDateFrom: dia, outboundDepartureDateTo: dia,
    outboundDepartureTimeFrom: "06:00", outboundDepartureTimeTo: "10:00",
  });
  return resumir("Ryanair (farfnd/oneWayFares)", () => fetch("https://www.ryanair.com/api/farfnd/v4/oneWayFares?" + p, {
    headers: { "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "es-ES,es;q=0.9" },
  }), (j) => (Array.isArray(j.fares) ? `sí: ${j.fares.length} vuelos` : "no"));
}

async function wizz(dia) {
  // Igual que flywizz: portada -> versión de la API -> userSession/new (da la cookie) -> timetableV2
  const cab = { "Accept": "application/json, text/plain, */*", "Accept-Language": "en-GB,en;q=0.9",
    "Origin": "https://www.wizzair.com", "Referer": "https://www.wizzair.com/en-gb", "User-Agent": UA };
  let version = "29.14.0";
  try {
    const home = await fetch("https://www.wizzair.com/en-gb", { headers: cab });
    const m = (await home.text()).match(/be\.wizzair\.com\/(\d+\.\d+\.\d+)\/Api/);
    if (m) version = m[1];
  } catch (_) { /* se sigue con la versión por defecto */ }
  const base = `https://be.wizzair.com/${version}/Api`;
  let token = "";
  try {
    const s = await fetch(`${base}/userSession/new`, { headers: cab });
    for (const c of s.headers.getSetCookie ? s.headers.getSetCookie() : []) {
      const m = c.match(/RequestVerificationToken=([^;]+)/);
      if (m) token = m[1];
    }
  } catch (_) { /* sin token: la respuesta lo dirá */ }
  const d2 = new Date(dia); d2.setUTCDate(d2.getUTCDate() + 2);
  const cuerpo = {
    flightList: [
      { departureStation: "BCN", arrivalStation: "BUD", from: dia, to: dia },
      { departureStation: "BUD", arrivalStation: "BCN", from: iso(d2), to: iso(d2) },
    ],
    priceType: "regular", adultCount: 1, childCount: 0, infantCount: 0,
  };
  const h = { ...cab, "Content-Type": "application/json" };
  if (token) { h["X-RequestVerificationToken"] = token; h["Cookie"] = `RequestVerificationToken=${token}`; }
  const r = await resumir(`Wizz Air (timetableV2 ${version})`, () => fetch(`${base}/search/timetableV2`, {
    method: "POST", headers: h, body: JSON.stringify(cuerpo),
  }), (j) => (Array.isArray(j.outboundFlights) ? `sí: ${j.outboundFlights.length} días de ida` : "no"));
  r.token_obtenido = token !== "";
  return r;
}

async function vueling(dia) {
  const p = new URLSearchParams({ originCode: "BCN", destinationCodes: "ORY,AMS,FCO,LIS,PRG,BRU,CDG,LHR,MXP,ATH", months: "1", startDate: dia, currencyCode: "EUR" });
  return resumir("Vueling (bestPrices)", () => fetch("https://apiw.vueling.com/api/v1/bestPrices?" + p), (j) => {
    const v = j && j.bestPrices && j.bestPrices.value;
    return Array.isArray(v) ? `sí: ${v.length} precios` : "no";
  });
}

async function kiwi(dia) {
  const consulta = `query SearchOneWayItinerariesQuery($search: SearchOnewayInput,$filter: ItinerariesFilterInput,$options: ItinerariesOptionsInput){
onewayItineraries(search:$search,filter:$filter,options:$options){__typename
... on AppError{error: message}
... on Itineraries{itineraries{__typename ... on ItineraryOneWay{id priceEur{amount}}}}}}`;
  const variables = {
    search: {
      itinerary: { source: { ids: ["Station:airport:BCN"] }, destination: { ids: ["Station:airport:BUD"] },
        outboundDepartureDate: { start: `${dia}T00:00:00`, end: `${dia}T23:59:59` } },
      passengers: { adults: 1, children: 0, infants: 0, adultsHoldBags: 0, adultsHandBags: 0, childrenHoldBags: [], childrenHandBags: [] },
      cabinClass: { cabinClass: "ECONOMY", applyMixedClasses: false } },
    filter: { transportTypes: ["FLIGHT"], contentProviders: ["KIWI", "FRESH", "KAYAK"], limit: 5, maxStopsCount: 0 },
    options: { sortBy: "PRICE", currency: "eur", locale: "es", partner: "skypicker", affilID: "skypicker", storeSearch: false },
  };
  return resumir("Kiwi (umbrella graphql)", () => fetch("https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchOneWayItinerariesQuery", {
    method: "POST", headers: { "User-Agent": "FlightFinder/0.1.0", "Content-Type": "application/json" },
    body: JSON.stringify({ query: consulta, variables }),
  }), (j) => {
    const r = j && j.data && j.data.onewayItineraries;
    return r && r.__typename === "Itineraries" ? `sí: ${r.itineraries.length} itinerarios` : "no";
  });
}

async function probar(request) {
  const dia = iso(domingo());
  const fuentes = [ryanair, wizz, vueling, kiwi];
  const resultados = [];
  for (let i = 0; i < fuentes.length; i++) {
    if (i > 0) await dormir(PAUSA_MS);
    resultados.push(await fuentes[i](dia));
  }
  const cf = request.cf || {};
  return {
    version: VERSION, dia_consultado: dia, ruta: "BCN -> BUD (Vueling: 10 destinos)",
    centro_de_datos_cloudflare: cf.colo || "?", pais_del_worker: cf.country || "?",
    resultados,
  };
}

function pagina(datos) {
  const filas = datos.resultados.map((r) => {
    const ok = r.codigo === 200 && !r.parece_reto && String(r.cuadra).startsWith("sí");
    return `<tr><td>${ok ? "✅" : "❌"}</td><td>${r.fuente}</td><td>${r.codigo ?? "—"}</td><td>${r.cuadra}</td><td>${r.ms} ms</td></tr>`;
  }).join("");
  return `<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Prueba de puertas</title><body style="font-family:sans-serif;max-width:640px;margin:1rem auto;padding:0 1rem">
<h2>Prueba de puertas desde Cloudflare</h2>
<p>Día consultado: ${datos.dia_consultado} · centro de datos: ${datos.centro_de_datos_cloudflare}</p>
<table border=1 cellpadding=6 style="border-collapse:collapse"><tr><th></th><th>Fuente</th><th>Código</th><th>¿Cuadra?</th><th>Tiempo</th></tr>${filas}</table>
<p><b>Para pasarle el resultado a Claude:</b> toca el cuadro, selecciona todo, copia y pégalo en el chat.</p>
<textarea readonly onclick="this.select()" style="width:100%;height:16rem;font-size:12px">${JSON.stringify(datos, null, 2).replace(/&/g, "&amp;").replace(/</g, "&lt;")}</textarea></body>`;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/cien") {
      // Prueba 3: página que encadena las 3 tandas (unas 100 consultas, ~7 min) y deja el texto para copiar
      return new Response(`<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Prueba de 90</title><body style="font-family:sans-serif;max-width:720px;margin:1rem auto;padding:0 1rem">
<h2>Prueba de unas 90 consultas</h2><p id=estado>Empezando… unos 6 minutos. No cierres la página ni bloquees el móvil.</p>
<pre id=log style="white-space:pre-wrap;font-size:12px"></pre><textarea id=todo readonly onclick="this.select()" style="width:100%;height:14rem;font-size:12px;display:none"></textarea>
<script>
(async()=>{const log=document.getElementById('log'),est=document.getElementById('estado');let todo='';
for(let n=1;n<=${TANDAS};n++){est.textContent='Tanda '+n+' de ${TANDAS}… no cierres la página.';
try{const r=await fetch('/tanda?n='+n);const rd=r.body.getReader(),dec=new TextDecoder();
for(;;){const {done,value}=await rd.read();if(done)break;const t=dec.decode(value);log.textContent+=t;todo+=t;}}
catch(e){const t='❌ Se cortó la tanda '+n+': '+e+'\\n';log.textContent+=t;todo+=t;}}
const ok=(todo.match(/✅/g)||[]).length,mal=(todo.match(/❌/g)||[]).length,blo=(todo.match(/BLOQUEO/g)||[]).length;
const res='RESUMEN: '+ok+' bien, '+mal+' con error, '+blo+' bloqueos. '+new Date().toISOString();
est.textContent='Terminado. '+res+'. Copia el cuadro de abajo y pégaselo a Claude.';
const ta=document.getElementById('todo');ta.value=res+'\\n'+todo;ta.style.display='block';})();
</script></body>`, { headers: { "content-type": "text/html; charset=utf-8" } });
    }
    if (url.pathname === "/tanda") {
      const n = Math.min(Math.max(parseInt(url.searchParams.get("n") || "1", 10) || 1, 1), TANDAS);
      const { readable, writable } = new TransformStream();
      const w = writable.getWriter();
      const enc = new TextEncoder();
      const emitir = (t) => w.write(enc.encode(t + "\n"));
      ctx.waitUntil((async () => {
        try { await emitir(`Centro de datos: ${(request.cf || {}).colo || "?"} · ${new Date().toISOString()}`); await tanda(n, emitir); }
        catch (e) { await emitir("ERROR: " + e); }
        finally { await w.close(); }
      })());
      return new Response(readable, { headers: { "content-type": "text/plain; charset=utf-8", "x-content-type-options": "nosniff" } });
    }
    if (url.pathname === "/ritmo") {
      // Prueba 2: unas 30 consultas despacio (~2,5 min). El avance sale en pantalla línea a línea.
      const { readable, writable } = new TransformStream();
      const w = writable.getWriter();
      const enc = new TextEncoder();
      const emitir = (t) => w.write(enc.encode(t + "\n"));
      ctx.waitUntil((async () => {
        try { await emitir(`Centro de datos: ${(request.cf || {}).colo || "?"} · ${new Date().toISOString()}`); await ritmo(emitir); }
        catch (e) { await emitir("ERROR: " + e); }
        finally { await w.close(); }
      })());
      return new Response(readable, { headers: { "content-type": "text/plain; charset=utf-8", "x-content-type-options": "nosniff" } });
    }
    if (url.pathname === "/probar") {
      const datos = await probar(request);
      if (url.searchParams.get("json")) {
        return new Response(JSON.stringify(datos, null, 2), { headers: { "content-type": "application/json; charset=utf-8" } });
      }
      return new Response(pagina(datos), { headers: { "content-type": "text/html; charset=utf-8" } });
    }
    return new Response(`<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<body style="font-family:sans-serif;max-width:640px;margin:1rem auto;padding:0 1rem"><h2>Prueba de puertas</h2>
<p>Hace UNA consulta despacio a Ryanair, Wizz, Vueling y Kiwi desde Cloudflare y cuenta cuáles abren. Tarda unos 20 segundos.</p>
<p><a href="/probar" style="font-size:1.3rem">▶ Probar ahora</a></p>
<p><a href="/cien" style="font-size:1.1rem">▶ Prueba 3: unas 90 consultas (~6 min; no cierres la página)</a></p>
<p><a href="/ritmo" style="font-size:1.1rem">▶ Prueba 2: ritmo real (~30 consultas, unos 3 minutos; no cierres la página)</a></p></body>`, { headers: { "content-type": "text/html; charset=utf-8" } });
  },
};
