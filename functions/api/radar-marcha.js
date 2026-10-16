// Marcha del Radar: «va por el mes 3 de 12». Los scripts del Radar (radar_datos.py, radar_larga.py), desde el PC o desde GitHub,
// avisan aquí tras cada mes; la pestaña Radar del iPhone lo lee y pinta la barra.
// POST {fuente:"semana"|"larga", hecho, total, texto, fin}   GET → {semana:{…}|null, larga:{…}|null} con `hace_s`.
// Solo guarda cifras y un texto corto (nada de precios ni países elegidos).
import { guardar, leer } from "../_lib/cache.js";

const FUENTES = ["semana", "larga"];
function json(datos, estado = 200) {
  return new Response(JSON.stringify(datos), { status: estado, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}

export async function onRequestGet({ env }) {
  const r = {};
  for (const f of FUENTES) {
    const c = await leer(env, ["nube", "radar-marcha", f]);
    r[f] = c ? { ...c.datos, hace_s: Math.round(Date.now() / 1000 - c.guardado) } : null;
  }
  return json(r);
}

export async function onRequestPost({ env, request }) {
  if (!request.headers.get("X-Escapadas")) return json({ error: "Petición no válida." }, 403);
  let c;
  try { c = await request.json(); } catch (e) { return json({ error: "Petición no válida." }, 400); }
  if (!FUENTES.includes(c.fuente)) return json({ error: "Fuente no válida." }, 400);
  const n = (x) => Math.max(0, Math.min(parseInt(x) || 0, 9999));
  await guardar(env, ["nube", "radar-marcha", c.fuente], { hecho: n(c.hecho), total: n(c.total), texto: String(c.texto || "").slice(0, 80), fin: !!c.fin });
  return json({ ok: true });
}
