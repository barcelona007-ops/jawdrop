// Wizz Air en la nube: mismas consultas que wizz.py 1.8 (asset/map y search/timetableV2, mismas claves de caché).
// La sesión se abre como flywizz: portada → versión de la API → userSession/new (cookie con el token).
// Si Wizz responde 429 / reto antibot, se lanza WizzBloqueado y NO se insiste.
import { ZONAS, aUTC, aLocal } from "./tiempo.js";

export const VERSION = "1.0";
export const HORAS_CACHE = 24;
export const HORAS_CACHE_RED = 72;
export const PAUSA_MS = 4000;
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36";
const CAB = { Accept: "application/json, text/plain, */*", "Accept-Language": "en-GB,en;q=0.9", Origin: "https://www.wizzair.com", Referer: "https://www.wizzair.com/en-gb", "User-Agent": UA };

export class WizzBloqueado extends Error {}

export async function sesion() {
  let version = "29.14.0";
  try {
    const home = await fetch("https://www.wizzair.com/en-gb", { headers: CAB });
    const m = (await home.text()).match(/be\.wizzair\.com\/(\d+\.\d+\.\d+)\/Api/);
    if (m) version = m[1];
  } catch (e) { /* se sigue con la versión por defecto */ }
  const base = `https://be.wizzair.com/${version}/Api`;
  let token = "";
  try {
    const s = await fetch(`${base}/userSession/new`, { headers: CAB });
    for (const c of s.headers.getSetCookie ? s.headers.getSetCookie() : []) {
      const m = c.match(/RequestVerificationToken=([^;]+)/);
      if (m) token = m[1];
    }
  } catch (e) { /* sin token: la respuesta lo dirá */ }
  return { base, token };
}

function cabeceras(ses) {
  const h = { ...CAB, "Content-Type": "application/json" };
  if (ses.token) { h["X-RequestVerificationToken"] = ses.token; h.Cookie = `RequestVerificationToken=${ses.token}`; }
  return h;
}

async function leerRespuesta(r, ruta) {
  if (r.status === 429) throw new WizzBloqueado(`${ruta}: 429 (antibots)`);
  if (r.status !== 200) throw new Error(`Wizz ${ruta} respondió ${r.status}`);
  try { return await r.json(); } catch (e) { throw new WizzBloqueado(`${ruta}: respuesta no válida (¿reto antibots?)`); }
}

export async function pedirRed(ses) {
  const r = await fetch(`${ses.base}/asset/map?languageCode=es-es`, { headers: cabeceras(ses) });
  return leerRespuesta(r, "asset/map");
}

export const consultaRed = { tipo: "wizz_red", clave: ["wizz", "asset/map"], horas: HORAS_CACHE_RED, etiqueta: "wizz red" };

// Cuerpo igual que wizz.horarios (misma clave de caché que en Python).
export function consultaHorario(origen, destino, idaDesde, idaHasta, vueltaDesde, vueltaHasta) {
  const cuerpo = {
    flightList: [
      { departureStation: origen, arrivalStation: destino, from: idaDesde, to: idaHasta },
      { departureStation: destino, arrivalStation: origen, from: vueltaDesde, to: vueltaHasta },
    ],
    priceType: "regular", adultCount: 1, childCount: 0, infantCount: 0,
  };
  return { tipo: "wizz_horario", clave: ["wizz", "timetableV2", cuerpo], cuerpo, horas: HORAS_CACHE, etiqueta: `wizz ${origen}-${destino} ${idaDesde}` };
}

export async function pedirHorario(ses, c) {
  const r = await fetch(`${ses.base}/search/timetableV2`, { method: "POST", headers: cabeceras(ses), body: JSON.stringify(c.cuerpo) });
  return leerRespuesta(r, "timetableV2");
}

// {iata: {ciudad, pais, pais_nombre, lat, lon}} y destinos directos desde `origen` (como wizz.red).
export function interpretarRed(datos, origen) {
  const aeropuertos = {};
  for (const c of datos.cities || []) {
    if (c.isFakeStation || c.mac === c.iata) continue;
    aeropuertos[c.iata] = { ciudad: String(c.shortName || c.iata).split(/\s+/).join(" "), pais: String(c.countryCode || "").toUpperCase(),
      pais_nombre: c.countryName || "", lat: c.latitude, lon: c.longitude };
  }
  let destinos = [];
  for (const c of datos.cities || []) {
    if (c.iata === origen) destinos = (c.connections || []).filter((x) => x.isDirectFlight !== false && aeropuertos[x.iata]).map((x) => x.iata);
  }
  return { aeropuertos, destinos };
}

function distanciaKm(a, b) {
  const r = (x) => (x * Math.PI) / 180;
  const h = Math.sin((r(b.lat) - r(a.lat)) / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin((r(b.lon) - r(a.lon)) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

// Hora local de llegada estimada: 35 min + distancia a 780 km/h, con cambio de huso.
function llegadaEstimada(salida, apDesde, apHasta) {
  const minutos = 35 + (distanciaKm(apDesde, apHasta) / 780) * 60;
  const z1 = ZONAS[apDesde.pais] || "Europe/Madrid", z2 = ZONAS[apHasta.pais] || "Europe/Madrid";
  return aLocal(aUTC(salida, z1) + minutos * 60000, z2);
}

export function enlace(desde, hasta, dia) {
  return `https://www.wizzair.com/es-es/booking/select-flight/${desde}/${hasta}/${dia}/null/1/0/0/null`;
}

// Entradas de horario de Wizz → tramos (uno por hora de salida), como wizz._tramos.
export function tramos(dias, aeropuertos, sentido) {
  const res = [];
  for (const d of dias || []) {
    const precio = d.price || {};
    if (!precio.amount || precio.currencyCode !== "EUR") continue;
    const desde = d.departureStation, hasta = d.arrivalStation;
    const otro = sentido === "ida" ? hasta : desde;
    const ap = aeropuertos[otro] || {};
    const salidas = d.departureDates && d.departureDates.length ? d.departureDates : [{ date: d.departureDate, isCheapestOfTheDay: true }];
    for (const s of salidas) {
      const salida = s.date.slice(0, 16);
      res.push({
        aerolinea: "Wizz Air", desde, hasta, destino: otro, ciudad: ap.ciudad || otro, pais: ap.pais || "",
        salida, llegada: aeropuertos[desde] && aeropuertos[hasta] ? llegadaEstimada(salida, aeropuertos[desde], aeropuertos[hasta]) : null,
        aprox: true, precio: Number(precio.amount), minimo: !s.isCheapestOfTheDay && salidas.length > 1,
        enlace: enlace(desde, hasta, salida.slice(0, 10)),
      });
    }
  }
  return res;
}
