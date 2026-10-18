// level_lectura.js — pegar en la consola de flylevel.com (o ejecutar en el navegador de la app de Claude). Lee el calendario «solo ida» de cada ruta de BCN,
// 12 meses, en los dos sentidos, con 1,2 s de pausa, y deja el resultado en window.__g (ver level_mapa.py para el formato del volcado).
// Salida: Object.entries(window.__g).map(([k,v])=>k+'\n'+v.join(',')).join('\n')  → copiar a datos/level_volcado.txt (tras «#leido AAAA-MM-DDTHH:MM»).
window.__r = []; window.__done = false;
(async () => {
  const now = new Date(), rutas = ['BOS','EZE','JFK','LAX','LIM','MIA','SCL'];   // = /nwe/api/routes → originsWithDestinations.BCN
  for (const d of rutas) for (const [a, b] of [['BCN', d], [d, 'BCN']]) {
    let vacios = 0;
    for (let i = 0; i < 12 && vacios < 2; i++) {
      const m0 = now.getMonth() + i, y = now.getFullYear() + Math.floor(m0 / 12), m = (m0 % 12) + 1;
      const r = await fetch(`/nwe/flights/api/calendar/?triptype=OW&origin=${a}&destination=${b}&month=${String(m).padStart(2,'0')}&year=${y}&currencyCode=EUR&originType=flights`);
      const dp = ((await r.json()).data?.dayPrices || []).filter(x => x.price != null);
      vacios = dp.length ? 0 : vacios + 1;
      for (const x of dp) window.__r.push([a, b, x.date, x.price]);
      await new Promise(r => setTimeout(r, 1200));
    }
  }
  const g = {}, u = new Map(); for (const x of window.__r) u.set(x[0]+'-'+x[1]+' '+x[2], x[3]);
  for (const [k, v] of u) { const [r, d] = k.split(' '); (g[r] = g[r] || []).push(d.slice(2).replace(/-/g, '') + '=' + v); }
  window.__g = g; window.__done = true;
})();
