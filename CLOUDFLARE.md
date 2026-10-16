# Jawdrop en Cloudflare (encargo para Claude Code)

Fecha: 11 de octubre de 2026. Para el Claude Code que trabaja en `C:\escapadas_flash` (repositorio TU_USUARIO/jawdrop). Lee también ESTADO.md y CLAUDE.md.

## Qué quiere el usuario
- Una web en Cloudflare que se abre desde el iPhone como si fuera una app (icono en la pantalla de inicio).
- Nada de búsquedas automáticas: solo cuando él pulsa **Actualizar**.
- Al abrir la app se ven **los resultados de la última actualización**, con su fecha, sin gastar ninguna búsqueda.
- Una pulsación busca los próximos **8 domingos** (ajustable), con todas las reglas actuales: horarios, días libres extra, modo España, otro aeropuerto, precio máximo, filtro de mar, columna de traslado.
- Si se acaban las búsquedas de SerpApi (Vueling, hoteles), **no falla**: enseña el último precio guardado con su antigüedad, por ejemplo «Vueling: 54 € · precio de hace 6 días». Lo mismo si Ryanair o Wizz no responden.
- Lenguaje sencillo, nada técnico en pantalla.

## Arquitectura propuesta
- **Cloudflare Pages**: la web (HTML + JS), instalable en el iPhone (manifest + icono, "Añadir a pantalla de inicio").
- **Cloudflare Worker**: hace las búsquedas. Reutiliza la lógica de ryanair.py, wizz.py y escapadas.py, reescrita en JavaScript/TypeScript (Workers no ejecuta Python de forma práctica para esto).
- **Cloudflare Workflows** (o Queues): una actualización son unas 300 consultas lentas (8 domingos × ~40). No caben en una sola petición de un Worker; hay que repartirlas en pasos. La web enseña el progreso («buscando domingo 3 de 8…»).
- **D1** (base de datos de Cloudflare): sustituye a la caché SQLite. Cada precio se guarda con la fecha y hora en que se consultó.
- **Clave de SerpApi**: como secreto de Cloudflare, puesta por el usuario desde su PC con `wrangler secret put SERPAPI_KEY`. Nunca en el código, en el repositorio ni en el chat.
- **Acceso privado**: Cloudflare Access (gratis hasta 50 usuarios) con el correo del usuario, para que nadie más pueda pulsar Actualizar y gastar sus búsquedas.
- Plan: el gratuito de Workers limita las consultas por petición; probablemente haga falta el plan de pago de Workers (5 $/mes). Confirmar al montarlo.

## Precios con antigüedad
- Cada resultado lleva su «consultado hace X».
- Ryanair y Wizz: se refrescan en cada Actualizar.
- Vueling y hoteles (SerpApi): se refrescan solo si quedan búsquedas; si no, se usa lo guardado y se marca «precio de hace N días». En pantalla, un contador: «SerpApi: quedan 112 de 250 este mes».

## Riesgo principal (probar ANTES de construir nada)
- Desde el PC de casa Ryanair y Wizz responden. Desde servidores en la nube no está garantizado: pueden bloquear las direcciones de Cloudflare.
- Paso 0: un Worker mínimo que haga 1 consulta a Ryanair (oneWayFares desde BCN) y 1 a Wizz (timetableV2) y enseñe la respuesta. Si funciona, adelante. Si no, plan B: la web sigue en Cloudflare, pero las búsquedas de Ryanair/Wizz las hace el PC de casa cuando está encendido y sube los resultados a D1.

## Orden de trabajo
1. Paso 0 (la prueba de arriba). Contar al usuario el resultado.
2. Web mínima en Pages con los resultados ya calculados en el PC (subidos a D1), para ver el diseño en el iPhone.
3. Worker + Workflows con Ryanair y Wizz, botón Actualizar y progreso.
4. Vueling y hoteles con SerpApi, contador de búsquedas y precios con antigüedad.
5. Calendario semáforo (fase 5).

El usuario necesitará una cuenta gratuita de Cloudflare. El inicio de sesión se hace en su PC con `wrangler login` (se abre el navegador); no hay que copiar ninguna clave en ningún chat.
