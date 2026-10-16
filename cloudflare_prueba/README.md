# Prueba de puertas desde Cloudflare (paso 0)

Un Worker mínimo: una consulta despacio (5 s entre una y otra, sin reintentos) a Ryanair, Wizz, Vueling y Kiwi,
para ver cuáles contestan desde Cloudflare. Solo consulta cuando abres `/probar`.

Para desplegarlo (en el PC, una sola vez; Node.js instalado):
1. `cd cloudflare_prueba`
2. `npx wrangler login` (se abre el navegador; cuenta gratuita de Cloudflare)
3. `npx wrangler deploy`
4. Abre la dirección que te da (`https://escapadas-prueba-puertas.<tu-nombre>.workers.dev`) y pulsa «Probar ahora».
5. Copia el cuadro de texto que sale debajo de la tabla y pégaselo a Claude (o hazle una captura de la tabla).

Para borrarlo después: `npx wrangler delete`.

## Prueba 2: ritmo real (versión 1.2)
Después de `npx wrangler deploy`, abre la dirección + `/ritmo` (o el segundo enlace de la portada). Hace unas 30 consultas, una cada 4 s, y va escribiendo cada una en pantalla (✅/❌). No cierres la página (~3 min). Cópiame todo el texto. Conviene repetirla en otro momento del día (por ejemplo mañana por la mañana y por la noche).

## Prueba 3: unas 90 consultas (versión 1.3)
Después de `npx wrangler deploy`, abre la dirección + `/cien` (o el enlace de la portada). La página encadena sola 3 tandas (el plan gratuito deja unas 50 consultas por visita) y tarda unos 6 minutos. No cierres la página ni dejes que el móvil/PC se duerma. Al final sale un cuadro con todo el texto y un resumen: cópialo y pégaselo a Claude.
