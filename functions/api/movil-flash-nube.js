// Flash calculado en la nube (botón «Actualizar»). Mismo formato que /api/movil-flash.
// Lee el cruce de cada domingo que dejó la última tarea de /api/actualizar (D1, clave ["nube","flash",domingo]).
// Ryanair + Wizz Air + Kiwi (Vueling, easyJet, Turkish…), vuelta desde el mismo aeropuerto (ver functions/_lib/cruce.js).
import { leer } from "../_lib/cache.js";

export async function onRequestGet({ env, request }) {
  // «país nuevo» se calcula aquí con el pasaporte (KV, o la semilla publicada si aún no se ha marcado nada)
  let visitados = await env.PASAPORTE.get("visitados", "json");
  if (!visitados) {
    const r = await env.ASSETS.fetch(new URL("/pasaporte_inicial.json", request.url));
    visitados = r.ok ? (await r.json()).visitados || {} : {};
  }
  const tarea = await env.DB.prepare("SELECT detalle FROM tareas ORDER BY id DESC LIMIT 1").first();
  const lista = tarea ? (JSON.parse(tarea.detalle).domingos || []) : [];
  const domingos = [];
  let masViejo = null, conWizz = 0, conKiwi = 0;
  for (const dom of lista) {
    const r = await leer(env, ["nube", "flash", dom]);
    if (!r) continue;
    const x = r.datos;
    domingos.push({ dia: x.dia, fecha: x.fecha, opciones: x.opciones.map((o) => ({ ...o, nuevo: !!o.pais && !visitados[o.pais] })) });
    masViejo = masViejo === null ? x.guardado : Math.min(masViejo, x.guardado);
    conWizz += x.con_wizz || 0;
    conKiwi += x.con_kiwi || 0;
  }
  return new Response(JSON.stringify({ domingos, generado: "", dias: { 1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue" },
    edad_datos: masViejo === null ? null : Date.now() / 1000 - masViejo, con_wizz: conWizz > 0, con_kiwi: conKiwi > 0 }),
  { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}
