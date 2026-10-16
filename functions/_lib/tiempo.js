// Horas locales y husos horarios (con Intl, sin librerías).

// Instante UTC (ms) de una hora local "AAAA-MM-DDTHH:MM" en una zona.
export function aUTC(local, zona) {
  const t0 = Date.parse(local + ":00Z");
  const f = new Intl.DateTimeFormat("en-US", { timeZone: zona, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  const p = Object.fromEntries(f.formatToParts(new Date(t0)).map((x) => [x.type, x.value]));
  const visto = Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:00Z`);
  return t0 - (visto - t0);
}

// Hora local "AAAA-MM-DDTHH:MM" de un instante UTC (ms) en una zona.
export function aLocal(ms, zona) {
  const f = new Intl.DateTimeFormat("en-US", { timeZone: zona, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  const p = Object.fromEntries(f.formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

// Zona horaria por país (como wizz.py ZONAS)
export const ZONAS = {
  ES: "Europe/Madrid", PT: "Europe/Lisbon", GB: "Europe/London", IE: "Europe/Dublin", FR: "Europe/Paris", IT: "Europe/Rome",
  DE: "Europe/Berlin", AT: "Europe/Vienna", CH: "Europe/Zurich", NL: "Europe/Amsterdam", BE: "Europe/Brussels", PL: "Europe/Warsaw",
  CZ: "Europe/Prague", SK: "Europe/Bratislava", HU: "Europe/Budapest", SI: "Europe/Ljubljana", HR: "Europe/Zagreb", RS: "Europe/Belgrade",
  BA: "Europe/Sarajevo", ME: "Europe/Podgorica", MK: "Europe/Skopje", AL: "Europe/Tirane", XK: "Europe/Belgrade", RO: "Europe/Bucharest",
  BG: "Europe/Sofia", GR: "Europe/Athens", CY: "Asia/Nicosia", MD: "Europe/Chisinau", UA: "Europe/Kyiv", LT: "Europe/Vilnius",
  LV: "Europe/Riga", EE: "Europe/Tallinn", FI: "Europe/Helsinki", SE: "Europe/Stockholm", NO: "Europe/Oslo", DK: "Europe/Copenhagen",
  IS: "Atlantic/Reykjavik", MT: "Europe/Malta", GE: "Asia/Tbilisi", AM: "Asia/Yerevan", TR: "Europe/Istanbul", IL: "Asia/Jerusalem",
  MA: "Africa/Casablanca", EG: "Africa/Cairo", AE: "Asia/Dubai", SA: "Asia/Riyadh", JO: "Asia/Amman", AZ: "Asia/Baku",
  KZ: "Asia/Almaty", UZ: "Asia/Tashkent", LU: "Europe/Luxembourg",
};
