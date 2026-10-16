// Estado de salud de las actualizaciones, para la app y para diagnosticar sin ir a ciegas.
// GET /api/estado → {salud, espacio (MB usados de la base de datos y %), ultima_ok, ultimo_error, tarea, registro:[...últimos 40 apuntes]}
//   salud: «ok» (última búsqueda terminada hace menos de 16 h), «en_curso» (hay una buscando), «atrasada» (no se ha actualizado solo: algo ha pasado).
import { ultimaTarea, resumen, tamanoMB, LIMITE_MB } from "../_lib/tarea.js";

const HORAS_MAX = 16;   // se busca cada 12 h; pasadas 16 h sin una terminada, algo ha fallado

export async function onRequestGet({ env }) {
  const ahora = Date.now() / 1000;
  const t = await ultimaTarea(env);
  const ok = await env.DB.prepare("SELECT cuando, mensaje FROM registro WHERE nivel = 'ok' ORDER BY id DESC LIMIT 1").first();
  const err = await env.DB.prepare("SELECT cuando, mensaje FROM registro WHERE nivel = 'error' ORDER BY id DESC LIMIT 1").first();
  const reg = await env.DB.prepare("SELECT cuando, nivel, mensaje FROM registro ORDER BY id DESC LIMIT 40").all();
  const mb = await tamanoMB(env);
  const espacio = { mb: Math.round(mb), limite_mb: LIMITE_MB, porcentaje: Math.round((mb / LIMITE_MB) * 100) };
  let salud = "ok";
  if (t && t.estado === "en curso" && ahora - t.creada < 4 * 3600) salud = "en_curso";
  else if (!ok || ahora - ok.cuando > HORAS_MAX * 3600) salud = "atrasada";
  return new Response(JSON.stringify({ salud, espacio, ahora, ultima_ok: ok || null, ultimo_error: err || null,
    tarea: t ? resumen(t) : null, registro: reg.results }),
  { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}
