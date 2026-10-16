// Lógica de la tarea «Actualizar» (Ryanair + Wizz + Kiwi de los próximos domingos), compartida por la función de la página
// (functions/api/actualizar.js, que llama el botón del iPhone) y por el temporizador (cron/, que la llama cada 2 minutos).
// Las respuestas quedan en la caché D1 (misma que la del PC); el cruce de cada domingo se guarda aparte
// (clave ["nube","flash",domingo]) y lo lee /api/movil-flash-nube.
import { conCache, guardar, leer, clave } from "./cache.js";
import * as ry from "./ryanair.js";
import * as wz from "./wizz.js";
import * as kw from "./kiwi.js";
import { domingoNube, reunir, interesantes } from "./cruce.js";

export const VERSION = "5.1";
const ORIGEN = "BCN";
const IDA_DESDE = "06:00", IDA_HASTA = "10:00", VUELTA_LUNES_DESDE = "20:00";
const MAX_REALES = 10;   // consultas reales por trozo (con 3-5 s de pausa, ~50 s)
const MAX_TOTAL = 60;    // lo que sale de la caché es casi gratis, pero no más de esto por trozo
const HORAS_FRESCO = 11; // los precios de la nube caducan a las 11 h (la del PC sigue en 24 h): así dos búsquedas al día (a las 03:00 y a las 15:00) sí se refrescan
const dormir = (ms) => new Promise((x) => setTimeout(x, ms));

function proximosDomingos(n) {
  const hoy = new Date().toISOString().slice(0, 10);
  const d = new Date(hoy + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + ((7 - d.getUTCDay()) % 7));
  const res = [];
  for (let i = 0; i < n; i++) { res.push(d.toISOString().slice(0, 10)); d.setUTCDate(d.getUTCDate() + 7); }
  return { hoy, domingos: res };
}

// Pasos compactos: ra aeropuertos, ri/rl/rm idas y vueltas (lunes, martes) de Ryanair, wh horario de Wizz,
// ki idas de Kiwi, kp (prepara las vueltas de Kiwi para los destinos con ida y los aeropuertos cercanos; añade pasos kv),
// kv vueltas de Kiwi, cx cruce de un domingo.
function consultaDe(p, hoy) {
  if (p.t === "ra") return { ...ry.consultaAeropuertos, etiqueta: "aeropuertos" };
  if (p.t === "ri") return { ...ry.consultaIdas(ORIGEN, p.dom, IDA_DESDE, IDA_HASTA), etiqueta: `ida ${p.dom}` };
  if (p.t === "rl") return { ...ry.consultaVueltas(ORIGEN, p.dom, ry.sumarDias(p.dom, 1), hoy, VUELTA_LUNES_DESDE, "23:59"), etiqueta: `vuelta lunes ${p.dom}` };
  if (p.t === "rm") return { ...ry.consultaVueltas(ORIGEN, p.dom, ry.sumarDias(p.dom, 2), hoy, "00:00", "23:59"), etiqueta: `vuelta martes ${p.dom}` };
  if (p.t === "wh") return wz.consultaHorario(ORIGEN, p.d, p.a, p.b, ry.sumarDias(p.a, 1), ry.sumarDias(p.b, 2));
  if (p.t === "ki") return kw.consultaKiwi(["Airport:" + ORIGEN], [], p.dom, IDA_DESDE, IDA_HASTA);
  if (p.t === "kv") return kw.consultaKiwi(p.o.map((x) => "Airport:" + x), ["Airport:" + ORIGEN], p.dia, p.h, "23:59");
  return null;
}

function plan(domingos, destinosWizz) {
  const q = [{ t: "ra" }];
  for (const dom of domingos) q.push({ t: "ri", dom }, { t: "rl", dom }, { t: "rm", dom });
  // Wizz: una consulta por ruta y mes, del primer al último domingo de ese mes (como servidor.py; más largo lo rechaza Wizz)
  const meses = {};
  for (const dom of domingos) (meses[dom.slice(0, 7)] = meses[dom.slice(0, 7)] || []).push(dom);
  for (const m of Object.values(meses)) for (const d of destinosWizz) q.push({ t: "wh", d, a: m[0], b: m[m.length - 1] });
  for (const dom of domingos) q.push({ t: "ki", dom }, { t: "kp", dom });
  for (const dom of domingos) q.push({ t: "cx", dom });
  return q;
}

export async function ultimaTarea(env) {
  const f = await env.DB.prepare("SELECT * FROM tareas ORDER BY id DESC LIMIT 1").first();
  if (!f) return null;
  return { ...f, detalle: JSON.parse(f.detalle) };
}

export function resumen(t) {
  if (!t) return { estado: "ninguna" };
  const d = t.detalle;
  return { id: t.id, estado: t.estado, total: t.total, hechas: t.hechas, creada: t.creada, errores: d.errores,
    de_cache: d.de_cache, reales: d.reales, wizz: d.wizz_off ? "sin Wizz" : "con Wizz", kiwi: d.kiwi_off ? "sin Kiwi" : "con Kiwi", version: VERSION };
}

// Consultas de Wizz del mes de `dom` y de Kiwi de ese domingo, tal como están en la tarea.
function consultasDe(d, dom) {
  const wiz = d.wizz_off ? [] : d.pasos.filter((x) => x.t === "wh" && x.a.slice(0, 7) === dom.slice(0, 7)).map((x) => consultaDe(x, d.hoy));
  const kiwi = d.kiwi_off ? [] : d.pasos.filter((x) => (x.t === "ki" || x.t === "kv") && x.dom === dom).map((x) => consultaDe(x, d.hoy));
  return { wiz, kiwi };
}

// Registro de lo que pasa (tabla `registro` de D1): niveles «info», «aviso», «ok» (búsqueda terminada) y «error». Se guardan los últimos 300.
export async function anotar(env, nivel, mensaje) {
  try {
    await env.DB.prepare("INSERT INTO registro (cuando, nivel, mensaje) VALUES (?, ?, ?)").bind(Date.now() / 1000, nivel, String(mensaje).slice(0, 600)).run();
    await env.DB.prepare("DELETE FROM registro WHERE id <= (SELECT MAX(id) FROM registro) - 300").run();
  } catch (e) { /* el registro nunca debe romper la búsqueda */ }
}

// Tamaño de la base D1 en MB (el plan gratuito admite 500 MB por base).
export const LIMITE_MB = 500;
export async function tamanoMB(env) {
  const r = await env.DB.prepare("SELECT 1").run();
  return (r.meta && r.meta.size_after ? r.meta.size_after : 0) / 1048576;
}

// Limpieza de la base D1 (el plan gratuito admite 500 MB por base y las respuestas de Wizz/Kiwi pesan mucho): borra las respuestas
// guardadas hace más de 14 h (la nube las da por caducadas a las 11 h) salvo las de vida larga (aeropuertos, red de Wizz, resultados
// de cada domingo y latidos), y las tareas viejas. Se hace al empezar cada búsqueda.
export async function purgar(env, domingos) {
  try {
    const guardar_ = [await clave("ryanair", "aeropuertos"), await clave("ryanair", "aeropuertos_en"), await clave("wizz", "asset/map"),
      await clave("nube", "cron"), await clave("nube", "cron-resultado")];
    for (const dom of domingos) guardar_.push(await clave("nube", "flash", dom));
    const marcas = guardar_.map(() => "?").join(",");
    const corte = Date.now() / 1000 - 14 * 3600;
    await env.DB.prepare(`DELETE FROM respuestas WHERE guardado < ? AND clave NOT IN (${marcas})`).bind(corte, ...guardar_).run();
    await env.DB.prepare("DELETE FROM trozos WHERE clave NOT IN (SELECT clave FROM respuestas)").run();
    await env.DB.prepare("DELETE FROM tareas WHERE id <= (SELECT MAX(id) FROM tareas) - 30").run();
  } catch (e) { await anotar(env, "aviso", "No se pudo limpiar la base de datos: " + e.message); }
}

// Apunta que el temporizador (o quien sea) ha pasado por aquí: para diagnóstico (`cron_hace_s` en /api/actualizar).
export async function anotarLatido(env, quien) {
  await guardar(env, ["nube", quien], { visto: Date.now() / 1000 });
}
export async function latidoHace(env, quien) {
  const c = await leer(env, ["nube", quien]);
  return c ? Math.round(Date.now() / 1000 - c.datos.visto) : null;
}

// Crea la tarea con los pasos de los próximos `n` domingos (cancela la que estuviera en curso).
export async function empezarTarea(env, n) {
  n = Math.min(Math.max(parseInt(n) || 12, 1), 14);
  const { hoy, domingos } = proximosDomingos(n);
  await purgar(env, domingos);
  const errores = [];
  let destinos = [], wizzOff = false;
  try {   // la lista de rutas de Wizz (caché 3 días); si Wizz no responde, se sigue solo con Ryanair
    const r = await conCache(env, wz.consultaRed.clave, wz.HORAS_CACHE_RED, async () => wz.pedirRed(await wz.sesion()));
    destinos = wz.interpretarRed(r.datos, ORIGEN).destinos;
  } catch (e) { wizzOff = true; errores.push(`Wizz: ${e.message}. Se sigue solo con Ryanair.`); }
  const pasos = plan(domingos, destinos);
  const detalle = { pasos, siguiente: 0, errores, de_cache: 0, reales: 0, fallos: 0, wizz_fallos: 0, wizz_off: wizzOff, saltar: false, domingos, hoy };
  await env.DB.prepare("UPDATE tareas SET estado = 'cancelada' WHERE estado = 'en curso'").run();
  await env.DB.prepare("INSERT INTO tareas (creada, estado, total, hechas, detalle) VALUES (?, 'en curso', ?, 0, ?)")
    .bind(Date.now() / 1000, pasos.length, JSON.stringify(detalle)).run();
  await anotar(env, "info", `Empieza la búsqueda de ${n} domingos (${pasos.length} pasos)` + (errores.length ? ` · ${errores[0]}` : ""));
  return resumen(await ultimaTarea(env));
}

// Da un trozo de la tarea en curso (unas 10 consultas reales con pausa, o un cruce). Devuelve el resumen (con `ocupada: true` si
// otro «seguir» tiene el bloqueo: el iPhone y el temporizador de la nube no deben pisarse).
export async function seguirTarea(env, maxReales = MAX_REALES) {
  maxReales = Math.min(Math.max(parseInt(maxReales) || MAX_REALES, 1), MAX_REALES);
  let t = await ultimaTarea(env);
  if (!t || t.estado !== "en curso") return resumen(t);
  const ahora = Date.now() / 1000;
  const g = await env.DB.prepare("UPDATE tareas SET bloqueo = ? WHERE id = ? AND (bloqueo IS NULL OR bloqueo < ?)").bind(ahora + 120, t.id, ahora).run();
  if (!g.meta.changes) return { ...resumen(t), ocupada: true };
  t = await ultimaTarea(env);   // estado fresco tras conseguir el bloqueo
  if (!t || t.estado !== "en curso") { await env.DB.prepare("UPDATE tareas SET bloqueo = 0 WHERE id = ?").bind(t ? t.id : 0).run(); return resumen(t); }
  const d = t.detalle;
  let reales = 0, hechas = 0, ses = null;
  const estadoAntes = { wizz: !!d.wizz_off, kiwi: !!d.kiwi_off, saltar: !!d.saltar };
  try {
    while (d.siguiente < d.pasos.length && reales < maxReales && hechas < MAX_TOTAL) {
      const p = d.pasos[d.siguiente];
      const esWizz = p.t === "wh";
      if (p.t === "cx") {
        if (hechas > 0) break;   // el cruce va en una petición aparte (consume más proceso)
        try {
          const { wiz, kiwi } = consultasDe(d, p.dom);
          const r = await domingoNube(env, p.dom, d.hoy, {}, wiz, kiwi);
          if (r) await guardar(env, ["nube", "flash", p.dom], r);
        } catch (e) { d.errores.push(`cruce ${p.dom}: ${e.message}`); }
        d.siguiente++; hechas++;
        break;
      }
      if (p.t === "kp") {
        if (hechas > 0) break;   // también va sola
        if (!d.kiwi_off && !d.saltar) {
          try {
            const { wiz, kiwi } = consultasDe(d, p.dom);
            const u = await reunir(env, p.dom, d.hoy, wiz, kiwi);
            const destinos = u ? interesantes(u) : [];
            const nuevos = [];
            for (const [dia, h] of [[ry.sumarDias(p.dom, 1), "20:00"], [ry.sumarDias(p.dom, 2), "00:00"]]) {
              for (let i = 0; i < destinos.length; i += kw.LOTE) nuevos.push({ t: "kv", dom: p.dom, dia, h, o: destinos.slice(i, i + kw.LOTE) });
            }
            d.pasos.splice(d.siguiente + 1, 0, ...nuevos);
          } catch (e) { d.errores.push(`preparar Kiwi ${p.dom}: ${e.message}`); }
        }
        d.siguiente++; hechas++;
        break;
      }
      const esKiwi = p.t === "ki" || p.t === "kv";
      if (d.saltar || (esWizz && d.wizz_off) || (esKiwi && d.kiwi_off)) { d.siguiente++; hechas++; continue; }
      const c = consultaDe(p, d.hoy);
      if (c.horas !== 72) c.horas = HORAS_FRESCO;   // aeropuertos y red de Wizz: 3 días; el resto, 11 h
      try {
        const r = await conCache(env, ry.partesClave(c), c.horas, async () => {
          if (esWizz) { ses = ses || await wz.sesion(); return wz.pedirHorario(ses, c); }
          if (esKiwi) return kw.pedir(c);
          return ry.pedir(c);
        });
        if (r.deCache) d.de_cache++; else { d.reales++; reales++; await dormir(esWizz ? wz.PAUSA_MS : esKiwi ? kw.PAUSA_MS : ry.PAUSA_MS); }
        if (esWizz) d.wizz_fallos = 0; else if (esKiwi) d.kiwi_fallos = 0; else d.fallos = 0;
      } catch (e) {
        d.errores.push(`${c.etiqueta}: ${e.message}`);
        if (esWizz) {
          // Wizz: si bloquea, o fallan 5 rutas seguidas, se sigue sin Wizz (Ryanair ya está)
          d.wizz_fallos = (d.wizz_fallos || 0) + 1;
          if (e instanceof wz.WizzBloqueado || d.wizz_fallos >= 5) { d.wizz_off = true; d.errores.push("Wizz: se deja de consultar."); }
        } else if (esKiwi) {
          // Kiwi: si bloquea, o fallan 3 consultas seguidas, se sigue sin Kiwi
          d.kiwi_fallos = (d.kiwi_fallos || 0) + 1;
          if (e instanceof kw.KiwiBloqueado || d.kiwi_fallos >= 3) { d.kiwi_off = true; d.errores.push("Kiwi: se deja de consultar."); }
        } else {
          d.fallos = (d.fallos || 0) + 1;
          if (d.fallos >= 3) { d.saltar = true; }   // Ryanair no responde: no se insiste; se cruza lo que haya
        }
      }
      d.siguiente++; hechas++;
    }
  } finally {
    if (d.siguiente >= d.pasos.length) t.estado = d.saltar ? "parada" : "terminada";
    if (d.wizz_off && !estadoAntes.wizz) await anotar(env, "aviso", "Wizz Air no responde: se sigue sin Wizz. " + (d.errores.slice(-2).join(" · ")));
    if (d.kiwi_off && !estadoAntes.kiwi) await anotar(env, "aviso", "Kiwi no responde: se sigue sin Kiwi. " + (d.errores.slice(-2).join(" · ")));
    if (d.saltar && !estadoAntes.saltar) await anotar(env, "error", "Ryanair no responde: se para la búsqueda. " + (d.errores.slice(-2).join(" · ")));
    if (t.estado !== "en curso") {
      const min = Math.round((Date.now() / 1000 - t.creada) / 60);
      const extra = (d.wizz_off ? " · sin Wizz" : "") + (d.kiwi_off ? " · sin Kiwi" : "") + (d.errores.length ? ` · ${d.errores.length} avisos` : "");
      await anotar(env, t.estado === "terminada" ? "ok" : "error", `Búsqueda ${t.estado} en ${min} min · ${d.reales} consultas nuevas, ${d.de_cache} de caché${extra}`);
      // Espacio de la base de datos: se apunta tras cada búsqueda; aviso al 50 % y error al 80 % del límite
      const mb = await tamanoMB(env);
      await anotar(env, mb > LIMITE_MB * 0.8 ? "error" : mb > LIMITE_MB * 0.5 ? "aviso" : "info", `Base de datos: ${Math.round(mb)} MB de ${LIMITE_MB}`);
    }
    await env.DB.prepare("UPDATE tareas SET estado = ?, hechas = ?, total = ?, detalle = ?, bloqueo = 0 WHERE id = ?")
      .bind(t.estado, d.siguiente, d.pasos.length, JSON.stringify(d), t.id).run();
  }
  return resumen(await ultimaTarea(env));
}
