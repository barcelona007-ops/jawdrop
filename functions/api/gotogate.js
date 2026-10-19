// GoToGate desde la nube: una consulta de ida y vuelta (o solo ida) con caché de 24 h en D1, para las zonas que Kiwi no vende (Cuba).
// POST {origen:"MAD", destino:"HAV", ida:"2026-11-12", vuelta:"2026-11-26"}  →  {vuelos:[…10 más baratos, en bruto], de_cache, hace_s}
// Una consulta por llamada: quien llama (Raspberry, GitHub) pone la pausa entre ellas. Sin la cabecera X-Escapadas no responde.
import { buscar, GotogateBloqueado } from "../_lib/gotogate.js";

function json(datos, estado = 200) {
  return new Response(JSON.stringify(datos), { status: estado, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}
const AP = /^[A-Z]{3}$/, DIA = /^\d{4}-\d{2}-\d{2}$/;

export async function onRequestPost({ env, request }) {
  if (!request.headers.get("X-Escapadas")) return json({ error: "Petición no válida." }, 403);
  let c;
  try { c = await request.json(); } catch (e) { return json({ error: "Petición no válida." }, 400); }
  if (!AP.test(c.origen || "") || !AP.test(c.destino || "") || !DIA.test(c.ida || "") || (c.vuelta && !DIA.test(c.vuelta))) return json({ error: "Datos no válidos." }, 400);
  try {
    const r = await buscar(env, c.origen, c.destino, c.ida, c.vuelta || null);
    return json({ vuelos: r.vuelos, de_cache: r.deCache, hace_s: Math.round(Date.now() / 1000 - r.guardado) });
  } catch (e) {
    if (e instanceof GotogateBloqueado) return json({ error: "GoToGate no responde: " + e.message }, 502);
    throw e;
  }
}
