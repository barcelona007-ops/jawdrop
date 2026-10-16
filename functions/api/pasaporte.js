// Pasaporte en Cloudflare (Pages Function). Sustituye a /api/pasaporte de servidor.py.
// Guarda los países visitados en KV (binding PASAPORTE). La primera vez, parte de pasaporte_inicial.json,
// que publicar_movil.py genera desde paises_visitados.txt (los 51 países con sus años).
const VERSION = "1.2";
const MEDIOS = ["avion", "coche", "tren", "barco", "a_pie"];   // los mismos que pasaporte.py
// Cada viaje: "2025" o "2025:avion+tren" (cómo se entró en ese viaje; mismos medios que MEDIOS).
const FECHA = /^(19\d\d|20\d\d)(-(0[1-9]|1[0-2]))?(:(avion|coche|tren|barco|a_pie)(\+(avion|coche|tren|barco|a_pie))*)?$/;
const MAX_VISITAS = 40, MAX_NOTA = 120;
const CLAVE = "visitados";

function json(datos, estado = 200) {
  return new Response(JSON.stringify(datos), {
    status: estado,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

async function leer(env, request) {
  const guardado = await env.PASAPORTE.get(CLAVE, "json");
  if (guardado) return guardado;
  const r = await env.ASSETS.fetch(new URL("/pasaporte_inicial.json", request.url));
  if (!r.ok) return {};
  return (await r.json()).visitados || {};
}

function anios(valor) {
  const lista = Array.isArray(valor) ? valor : String(valor || "").split(/[,;\s]+/);
  return lista.map((x) => String(x).trim()).filter(Boolean).sort();
}

function medios(valor) {
  const lista = (Array.isArray(valor) ? valor : String(valor || "").split(/[,;\s]+/)).map((x) => String(x).trim().toLowerCase());
  return MEDIOS.filter((m) => lista.includes(m));
}

export async function onRequestGet({ env, request }) {
  return json({ visitados: await leer(env, request), version: VERSION });
}

export async function onRequestPost({ env, request }) {
  if (!request.headers.get("X-Escapadas")) return json({ error: "Petición no válida." }, 403);
  let cuerpo;
  try { cuerpo = await request.json(); } catch (e) { return json({ error: "Petición no válida." }, 400); }
  const codigo = String(cuerpo.codigo || "").toUpperCase();
  if (!/^[A-Z]{2}$/.test(codigo)) return json({ error: "Código de país no válido." }, 400);
  const visitado = cuerpo.visitado === true;
  const lista = anios(cuerpo.anios);
  const via = lista.some((a) => a.includes(":")) ? [] : medios(cuerpo.medios);   // con medios por viaje, el de país antiguo se vacía
  const nota = String(cuerpo.nota || "").replace(/\|/g, "/").split(/\s+/).filter(Boolean).join(" ");
  if (lista.some((a) => !FECHA.test(a))) return json({ error: "Cada visita debe ser un año (por ejemplo 2019 o 2019:avion+tren)." }, 400);
  if (lista.length > MAX_VISITAS) return json({ error: "Demasiadas visitas." }, 400);
  if (nota.length > MAX_NOTA) return json({ error: `La nota es demasiado larga (máximo ${MAX_NOTA} letras).` }, 400);

  const visitados = await leer(env, request);
  if (visitado) visitados[codigo] = { anios: lista, nota, medios: via }; else delete visitados[codigo];
  await env.PASAPORTE.put(CLAVE, JSON.stringify(visitados));
  return json({ codigo, visitado, anios: visitado ? lista : [], nota: visitado ? nota : "", medios: visitado ? via : [] });
}
