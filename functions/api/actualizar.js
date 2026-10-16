// Botón «Actualizar» en la nube (la lógica está en ../_lib/tarea.js, que también usa el temporizador de cron/).
// POST {accion:"empezar", domingos:12}  crea la tarea (lista de pasos pendientes) en D1.
// POST {accion:"seguir"}                hace un trozo (unas 10 consultas reales con pausa, o un cruce) y dice cómo va.
// GET                                   estado de la última tarea (y, para diagnóstico, cuándo pasó el temporizador).
import { ultimaTarea, resumen, empezarTarea, seguirTarea, latidoHace } from "../_lib/tarea.js";

function json(datos, estado = 200) {
  return new Response(JSON.stringify(datos), { status: estado, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}

export async function onRequestGet({ env }) {
  const r = resumen(await ultimaTarea(env));
  const c = await latidoHace(env, "cron");
  if (c !== null) r.cron_hace_s = c;
  return json(r);
}

export async function onRequestPost({ env, request }) {
  if (!request.headers.get("X-Escapadas")) return json({ error: "Petición no válida." }, 403);
  let cuerpo;
  try { cuerpo = await request.json(); } catch (e) { return json({ error: "Petición no válida." }, 400); }
  if (cuerpo.accion === "empezar") return json(await empezarTarea(env, cuerpo.domingos));
  if (cuerpo.accion === "seguir") return json(await seguirTarea(env, cuerpo.reales));
  return json({ error: "Acción no válida." }, 400);
}
