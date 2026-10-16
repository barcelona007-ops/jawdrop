// Temporizador de Jawdrop (Cloudflare Worker con cron). Usa la misma lógica que la página (functions/_lib/tarea.js) y la misma
// base de datos D1; no hace falta llamar a la página (un Worker no puede pedir una dirección *.pages.dev de su propia cuenta).
//  - Cada 2 min: si hay una búsqueda «en curso», da el siguiente paso (el iPhone no tiene que estar abierto).
//  - Cada día a las 04:00 UTC (05:00-06:00 en España): empieza una búsqueda nueva de 12 domingos si no hay otra en curso.
// Para diagnóstico, la dirección del Worker (con la cabecera X-Escapadas: cron) permite ver el último latido/error y dar un paso a mano.
import { ultimaTarea, empezarTarea, seguirTarea, anotarLatido, latidoHace } from "../../functions/_lib/tarea.js";
import { guardar, leer } from "../../functions/_lib/cache.js";

async function trabajo(cron, env) {
  await anotarLatido(env, "cron");
  const t = await ultimaTarea(env);
  if (cron === "0 4 * * *") {
    if (!t || t.estado !== "en curso") return await empezarTarea(env, 12);
    return { estado: "ya hay una en curso" };
  }
  if (t && t.estado === "en curso" && Date.now() / 1000 - t.creada < 6 * 3600) return await seguirTarea(env);
  return { estado: t ? t.estado : "ninguna" };
}

export default {
  async scheduled(evento, env, ctx) {
    ctx.waitUntil((async () => {
      try {
        const r = await trabajo(evento.cron, env);
        await guardar(env, ["nube", "cron-resultado"], { cuando: Date.now() / 1000, cron: evento.cron, resultado: r });
      } catch (e) {
        await guardar(env, ["nube", "cron-resultado"], { cuando: Date.now() / 1000, cron: evento.cron, error: String(e && e.stack || e).slice(0, 800) });
      }
    })());
  },

  // Solo diagnóstico (necesita la cabecera X-Escapadas: cron)
  async fetch(request, env) {
    if (request.headers.get("X-Escapadas") !== "cron") return new Response("No.", { status: 403 });
    const url = new URL(request.url);
    let salida;
    if (url.pathname === "/paso") {
      try { salida = { resultado: await trabajo("*/2 * * * *", env) }; } catch (e) { salida = { error: String(e && e.stack || e).slice(0, 800) }; }
    } else {
      const r = await leer(env, ["nube", "cron-resultado"]);
      salida = { latido_hace_s: await latidoHace(env, "cron"), ultimo: r && r.datos };
    }
    return new Response(JSON.stringify(salida, null, 1), { headers: { "Content-Type": "application/json" } });
  },
};
