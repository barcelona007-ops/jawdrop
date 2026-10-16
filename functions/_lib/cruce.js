// Cruza las idas y vueltas guardadas en D1 (Ryanair y Wizz Air) y las deja en el formato de la pantalla Flash (como movil_datos.py).
// Trozo 2: Ryanair + Wizz y solo «vuelta desde el mismo aeropuerto». Kiwi, Vueling y «otro aeropuerto» van después.
import { leer } from "./cache.js";
import * as ry from "./ryanair.js";
import * as wz from "./wizz.js";
import * as kw from "./kiwi.js";
import { aUTC, ZONAS } from "./tiempo.js";
import { trayecto } from "./geografia.js";

export const VERSION = "4.0";
const ORIGEN = "BCN";
const LLEGADA_MARTES_MAX = "14:30";
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const BCN = [41.2974, 2.0785];

// semaforo.py: topes (verde, ámbar) por tipo de viaje según los km en avión desde BCN.
function kmAire(lat, lon) {
  if (lat == null || lon == null) return null;
  const r = (x) => (x * Math.PI) / 180;
  const a = Math.sin(r(lat - BCN[0]) / 2) ** 2 + Math.cos(r(BCN[0])) * Math.cos(r(lat)) * Math.sin(r(lon - BCN[1]) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}
function kmEntre(a, b) {
  const r = (x) => (x * Math.PI) / 180;
  const h = Math.sin(r(b.lat - a.lat) / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(r(b.lon - a.lon) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}
// Trayecto por tierra (o ferri) de x a y habiendo `dias` fuera, o null (como _tray de escapadas.py).
export function tray(coords, x, y, dias) {
  if (y === x || y === ORIGEN || !coords[x] || !coords[y]) return null;
  const km = kmEntre(coords[x], coords[y]);
  if (km * 1.3 > 250 * Math.max(1, dias)) return null;   // descarte rápido (la regla exacta va en trayecto)
  return trayecto(x, coords[x].pais, y, coords[y].pais, km, dias);
}
// Aeropuertos que interesan para las vueltas: los destinos con ida y los que quedan a menos de 250 km por día fuera de alguno.
export function interesantes(u) {
  const destinos = Object.keys(u.idas).filter((x) => x !== ORIGEN);
  const set = new Set(destinos);
  for (const y of Object.keys(u.coords)) {
    if (y === ORIGEN || set.has(y)) continue;
    if (destinos.some((x) => tray(u.coords, x, y, 2))) set.add(y);
  }
  return [...set].sort();
}
function color(precio, km) {
  const [verde, ambar] = km == null || km <= 2800 ? [60, 100] : km <= 4400 ? [150, 200] : [500, 700];
  return precio <= verde ? "verde" : precio <= ambar ? "ambar" : "rojo";
}

function tramoRy(t, sentido) {
  const otro = sentido === "ida" ? t.arrivalAirport : t.departureAirport;
  const desde = t.departureAirport.iataCode, hasta = t.arrivalAirport.iataCode;
  return {
    aerolinea: "Ryanair", desde, hasta, destino: otro.iataCode,
    ciudad: (otro.city && otro.city.name) || otro.name || "",
    pais: ((otro.city && otro.city.countryCode) || "").toUpperCase(),
    salida: t.departureDate.slice(0, 16), llegada: t.arrivalDate.slice(0, 16), aprox: false, minimo: false,
    precio: Number(t.price.value), enlace: ry.enlace(desde, hasta, t.departureDate.slice(0, 10)),
  };
}

function fmt(t) {
  return { aerolinea: t.aerolinea, sale: t.salida.slice(11), llega: t.llegada ? t.llegada.slice(11) : "",
    mas1: !!t.llegada && t.llegada.slice(0, 10) > t.salida.slice(0, 10), aprox: !!t.aprox, precio: t.precio, minimo: !!t.minimo };
}

// El más barato; a igual precio, mejor uno con precio exacto que uno «mínimo».
const mejor = (lista) => lista.reduce((a, b) => (b.precio < a.precio || (b.precio === a.precio && !b.minimo && a.minimo) ? b : a));

// Reúne las idas y vueltas válidas de un domingo (Ryanair, Wizz, Kiwi) leyendo la caché D1.
export async function reunir(env, domingo, hoy, wizzConsultas, kiwiConsultas) {
  const gi = ry.consultaIdas(ORIGEN, domingo, "06:00", "10:00");
  const lunes = ry.sumarDias(domingo, 1), martes = ry.sumarDias(domingo, 2);
  const gl = ry.consultaVueltas(ORIGEN, domingo, lunes, hoy, "20:00", "23:59");
  const gm = ry.consultaVueltas(ORIGEN, domingo, martes, hoy, "00:00", "23:59");
  const [ci, cl, cm, ca, cr] = await Promise.all([leer(env, ry.partesClave(gi)), leer(env, ry.partesClave(gl)),
    leer(env, ry.partesClave(gm)), leer(env, ry.partesClave(ry.consultaAeropuertos)), leer(env, wz.consultaRed.clave)]);
  if (!ci || !cl || !cm) return null;
  const coords = {};   // iata -> {lat, lon, pais, ciudad}
  for (const a of (ca && ca.datos) || []) {
    if (a.coordinates) coords[a.code] = { lat: a.coordinates.latitude, lon: a.coordinates.longitude,
      pais: String((a.country && a.country.code) || "").toUpperCase(), ciudad: (a.city && a.city.name) || a.name || a.code };
  }
  const wizzAero = cr ? wz.interpretarRed(cr.datos, ORIGEN).aeropuertos : {};
  for (const [k, v] of Object.entries(wizzAero)) if (!coords[k] && v.lat != null) coords[k] = { lat: v.lat, lon: v.lon, pais: v.pais, ciudad: v.ciudad };

  const idas = {};      // destino -> [tramos]
  const vueltas = {};   // aeropuerto -> [{...tramo, noches}]
  const idaValida = (t) => t.salida.slice(0, 10) === domingo && t.salida.slice(11) >= "06:00" && t.salida.slice(11) <= "10:00" && t.pais !== "ES";
  const metoIda = (t) => { if (idaValida(t)) (idas[t.destino] = idas[t.destino] || []).push(t); };
  const metoVuelta = (v) => {
    let noches = 0;
    if (v.salida.slice(0, 10) === lunes && v.salida.slice(11) >= "20:00") noches = 1;
    else if (v.salida.slice(0, 10) === martes && v.llegada && v.llegada <= `${martes}T${LLEGADA_MARTES_MAX}`) noches = 2;
    if (noches) (vueltas[v.destino] = vueltas[v.destino] || []).push({ ...v, noches });
  };
  for (const f of ci.datos.fares || []) metoIda(tramoRy(f.outbound, "ida"));
  for (const f of cl.datos.fares || []) { const v = tramoRy(f.inbound, "vuelta"); if (v.salida.slice(0, 10) === lunes && v.salida.slice(11) >= "20:00") metoVuelta(v); }
  for (const f of cm.datos.fares || []) { const v = tramoRy(f.inbound, "vuelta"); if (v.salida.slice(0, 10) === martes) metoVuelta(v); }

  let viejo = Math.min(ci.guardado, cl.guardado, cm.guardado), conWizz = 0;
  for (const c of wizzConsultas || []) {
    const r = await leer(env, c.clave);
    if (!r) continue;
    conWizz++;
    viejo = Math.min(viejo, r.guardado);
    for (const t of wz.tramos(r.datos.outboundFlights, wizzAero, "ida")) metoIda(t);
    for (const t of wz.tramos(r.datos.returnFlights, wizzAero, "vuelta")) metoVuelta(t);
  }

  // Kiwi: otras aerolíneas (Vueling, easyJet, Turkish…) con precio estimado de la aerolínea
  let conKiwi = 0;
  for (const c of kiwiConsultas || []) {
    const r = await leer(env, c.clave);
    if (!r) continue;
    conKiwi++;
    viejo = Math.min(viejo, r.guardado);
    const esIda = c.destinos.length === 0;
    for (const t of kw.tramos(r.datos, esIda ? "ida" : "vuelta")) {
      if (!coords[t.destino] && t.coords) coords[t.destino] = { lat: t.coords[0], lon: t.coords[1], pais: t.pais, ciudad: t.ciudad };
      if (!coords[t.destino]) continue;
      if (esIda) { if (t.desde === ORIGEN) metoIda(t); } else if (t.hasta === ORIGEN) metoVuelta(t);
    }
  }
  return { idas, vueltas, coords, viejo, conWizz, conKiwi };
}

export async function domingoNube(env, domingo, hoy, visitados, wizzConsultas, kiwiConsultas) {
  const u = await reunir(env, domingo, hoy, wizzConsultas, kiwiConsultas);
  if (!u) return null;
  const { idas, vueltas, coords, viejo, conWizz, conKiwi } = u;
  const opciones = [];
  const nombreOpcion = (x, ida, v, y) => {
    const total = Math.round((ida.precio + v.precio) * 100) / 100;
    const c = coords[x];
    const km = c ? kmAire(c.lat, c.lon) : null;
    const horas = ida.llegada && v.salida
      ? Math.round(((aUTC(v.salida, ZONAS[v.pais] || "Europe/Paris") - aUTC(ida.llegada, ZONAS[ida.pais] || "Europe/Paris")) / 3600000) * 10) / 10 : null;
    const o = { destino: ida.ciudad, desde: "", total, color: color(total, km), ida: fmt(ida), vuelta: fmt(v),
      noches: v.noches, horas, libres: 0, pais: ida.pais, nuevo: !visitados[ida.pais], km: "", traslado: "", linkIda: ida.enlace, linkVuelta: v.enlace };
    if (y !== x) {
      const tr = tray(coords, x, y, v.noches);
      const kmTierra = tr ? tr.km : Math.round(kmEntre(coords[x], coords[y]) * 1.3);
      const h = kmTierra / 75;
      o.desde = (coords[y] && coords[y].ciudad) || v.ciudad;
      o.km = String(kmTierra);
      o.traslado = `≈${(Math.max(1, Math.round(h * 2)) / 2).toString().replace(".", ",")} h`;
    }
    return o;
  };
  for (const [x, lista] of Object.entries(idas)) {
    const ida = mejor(lista);
    const vs = vueltas[x] || [];
    const igual = vs.length ? nombreOpcion(x, ida, mejor(vs), x) : null;
    // vuelta desde otro aeropuerto cercano (solo si no hay desde el mismo o si sale más barata)
    let alt = null;
    for (const y of Object.keys(vueltas)) {
      if (y === x || !tray(coords, x, y, 2)) continue;
      const validas = vueltas[y].filter((v) => tray(coords, x, y, v.noches));
      if (!validas.length) continue;
      const o = nombreOpcion(x, ida, mejor(validas), y);
      if (!alt || o.total < alt.total) alt = o;
    }
    if (igual) opciones.push(igual);
    if (alt && (!igual || alt.total < igual.total)) opciones.push(alt);
  }
  opciones.sort((a, b) => a.total - b.total);
  const d = new Date(domingo + "T00:00:00Z");
  return { dia: domingo, fecha: `${d.getUTCDate()} ${MESES[d.getUTCMonth()]}`, opciones, guardado: viejo, con_wizz: conWizz, con_kiwi: conKiwi };
}
