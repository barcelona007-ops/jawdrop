// Caché en D1 (binding DB). Misma tabla y mismas claves que cache.py del PC: así los precios que subió
// subir_cache.py sirven aquí y lo que guarda la nube lo entiende el PC.
// La clave es sha1(json.dumps(partes, sort_keys=True)) de Python: ver pyJson.

// Reproduce json.dumps de Python con sort_keys=True: separadores ", " y ": ", ensure_ascii, enteros sin ".0".
export function pyJson(v) {
  if (v === null || v === undefined) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(v);
  if (typeof v === "string") {
    let s = '"';
    for (const ch of v) {
      const c = ch.codePointAt(0);
      if (ch === '"') s += '\\"';
      else if (ch === "\\") s += "\\\\";
      else if (ch === "\n") s += "\\n";
      else if (ch === "\r") s += "\\r";
      else if (ch === "\t") s += "\\t";
      else if (ch === "\b") s += "\\b";
      else if (ch === "\f") s += "\\f";
      else if (c < 0x20 || c > 0x7e) {
        if (c > 0xffff) {
          const x = c - 0x10000;
          s += "\\u" + (0xd800 + (x >> 10)).toString(16).padStart(4, "0") + "\\u" + (0xdc00 + (x & 0x3ff)).toString(16).padStart(4, "0");
        } else s += "\\u" + c.toString(16).padStart(4, "0");
      } else s += ch;
    }
    return s + '"';
  }
  if (Array.isArray(v)) return "[" + v.map(pyJson).join(", ") + "]";
  const claves = Object.keys(v).sort();
  return "{" + claves.map((k) => pyJson(String(k)) + ": " + pyJson(v[k])).join(", ") + "}";
}

export async function clave(...partes) {
  const datos = new TextEncoder().encode(pyJson(partes));
  const h = await crypto.subtle.digest("SHA-1", datos);
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Respuesta guardada (objeto) con su hora, o null. `horas` = caducidad; sin `horas` devuelve la guardada aunque sea vieja.
export async function leer(env, partes, horas) {
  const k = await clave(...partes);
  const fila = await env.DB.prepare("SELECT guardado, json, trozos FROM respuestas WHERE clave = ?").bind(k).first();
  if (!fila) return null;
  if (horas !== undefined && Date.now() / 1000 - fila.guardado >= horas * 3600) return null;
  let texto = fila.json;
  if (fila.trozos > 0) {
    const r = await env.DB.prepare("SELECT texto FROM trozos WHERE clave = ? ORDER BY n").bind(k).all();
    texto = r.results.map((x) => x.texto).join("");
  }
  return { datos: JSON.parse(texto), guardado: fila.guardado };
}

// D1 admite filas de hasta ~2 MB con valores «bind»: una respuesta cabe en UNA fila (cada fila escrita cuenta para el tope diario de
// 100.000 filas escritas del plan gratuito, y partirlas en trozos de 40 KB multiplicaba por 20 las escrituras). Solo las enormes se parten.
const LARGO = 1_000_000;
const MAX_UNA_FILA = 1_500_000;

export async function guardar(env, partes, datos) {
  const k = await clave(...partes);
  const texto = JSON.stringify(datos);
  const ahora = Date.now() / 1000;
  const lote = [];
  if (texto.length > MAX_UNA_FILA) {
    const n = Math.ceil(texto.length / LARGO);
    lote.push(env.DB.prepare("DELETE FROM trozos WHERE clave = ?").bind(k));
    lote.push(env.DB.prepare("INSERT OR REPLACE INTO respuestas (clave, guardado, json, trozos) VALUES (?, ?, '', ?)").bind(k, ahora, n));
    for (let i = 0; i < n; i++) {
      lote.push(env.DB.prepare("INSERT INTO trozos (clave, n, texto) VALUES (?, ?, ?)").bind(k, i, texto.slice(i * LARGO, (i + 1) * LARGO)));
    }
  } else {
    lote.push(env.DB.prepare("INSERT OR REPLACE INTO respuestas (clave, guardado, json, trozos) VALUES (?, ?, ?, 0)").bind(k, ahora, texto));
  }
  await env.DB.batch(lote);
}

// Como cache.con_cache de Python: devuelve lo guardado si es reciente; si no, llama a pedir() y lo guarda.
export async function conCache(env, partes, horas, pedir) {
  const hit = await leer(env, partes, horas);
  if (hit) return { datos: hit.datos, guardado: hit.guardado, deCache: true };
  const datos = await pedir();
  await guardar(env, partes, datos);
  return { datos, guardado: Date.now() / 1000, deCache: false };
}
