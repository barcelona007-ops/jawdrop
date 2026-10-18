# Jawdrop

Buscador personal de escapadas low cost desde Barcelona: ida el domingo por la mañana, vuelta el lunes
por la noche o el martes por la mañana. El encargo completo está en `encargo_escapadas_flash.md`.

## Cómo se usa

```
.venv\Scripts\python.exe escapadas.py              (el próximo domingo)
.venv\Scripts\python.exe escapadas.py 2026-10-18   (un domingo concreto)
.venv\Scripts\python.exe escapadas.py --mes 2026-11 (todos los domingos de noviembre que queden)
.venv\Scripts\python.exe escapadas.py --max 80     (solo hasta 80 € ida y vuelta)
.venv\Scripts\python.exe escapadas.py --radio 300  (fuerza un límite a mano, en km en línea recta; 0 = solo el mismo aeropuerto)
.venv\Scripts\python.exe escapadas.py --con-mar    (mostrar también vueltas que cruzan el mar sin ferri conocido)
.venv\Scripts\python.exe escapadas.py --dias-extra 1 (si pidieras 1 día libre: vuelta hasta el martes noche
                                                     o el miércoles mañana; con 2, hasta el jueves)
.venv\Scripts\python.exe escapadas.py --espana     (modo España: incluye vuelos nacionales)
.venv\Scripts\python.exe escapadas.py --nuevos     (solo países que aún no conoces; ver paises_visitados.txt)
.venv\Scripts\python.exe escapadas.py --sin-wizz   (solo Ryanair)
.venv\Scripts\python.exe escapadas.py --sin-cache  (preguntar de nuevo a las aerolíneas)
```

El resultado queda en `resultados\<domingo>.md` (y, con `--mes`, también `resultados\<AAAA-MM>.md` con un
resumen por domingo y todas las escapadas del mes juntas), ordenado de más barato a más caro, en dos
listas: «mismo aeropuerto» y «otro aeropuerto» (vuelta desde otro aeropuerto cercano, con km y si cambia
de país; solo aparece si no hay vuelta desde el mismo o si sale más barata). Lleva enlaces a la web de
cada aerolínea para la ida y para la vuelta. En «otro aeropuerto», la columna «Traslado» da el tiempo
aproximado en coche (distancia × 1,3 a 75 km/h; en bus suele ser más) y enlaces a 12Go y Rome2Rio con el
trayecto ya puesto, para ver buses, trenes y minivans reales con un clic.

Los enlaces «Comprobar» de Wizz abren la búsqueda de Google Flights del trayecto (la web de Wizz no carga).

Marcas: «FR» = Ryanair, «W6» = Wizz Air. «(+1)» = llega al día siguiente. «≥» = precio mínimo del día en
Wizz (el de esa hora puede ser mayor). «≈» = hora de llegada calculada (Wizz no la da).

## Piezas

| Archivo | Versión | Qué hace |
|---|---|---|
| `escapadas.py` | 6.2 | Programa principal: junta las aerolíneas, cruza idas y vueltas (mismo u otro aeropuerto), filtra y ordena; un domingo o un mes. Con `--kiwi` añade Kiwi (gratis). |
| `aeropuertos.py` | 1.0 | Tabla general de aeropuertos (`datos/aeropuertos.json`, 4.008 con código IATA y vuelos regulares, de OurAirports): ciudad en castellano, país y coordenadas. `corregir()` la usa Ryanair, Wizz, Kiwi y Vueling cuando la fuente trae el código en vez de la ciudad, no trae país o pone un nombre raro («East Midlands» → «East Midlands (Nottingham)»). `ficha(CÓDIGO)` da todo lo conocido: base de las futuras fichas de aeropuerto. `.venv\Scripts\python.exe aeropuertos.py [CÓDIGO ...]`; `--regenerar` descarga los datos de nuevo (casi nunca hace falta). |
| `movil/aeropuertos.json` | — | Fichas de aeropuerto del iPhone (14): web, mapa, cómo llegar al centro, taxi y apps, con fecha de revisión y fiabilidad. Se edita a mano; se publica con `publicar_movil.py`. |
| `kiwi.py` | 1.9 | Kiwi.com (consulta pública sin clave): easyJet, Turkish, Pegasus, AJet, Eurowings, Transavia, SunExpress, Volotea, Vueling... Solo ida y directos, un día por consulta, caché 24 h y 5 s de pausa. Los vuelos salen con el precio estimado de la aerolínea (precio de Kiwi menos su comisión, medida con vuelos reales: easyJet +14,5 €, Transavia +12 %, Vueling 2,26 € + 7 %, etc.; Iberojet, por ruta; Level +6,4 %; ver `COMISION`) y el enlace va a la web de la aerolínea (easyJet y Vueling al día; el resto, a su portada). Vueltas en lotes de 20 aeropuertos. Probado. `.venv\Scripts\python.exe kiwi.py ida TR 2027-01-17` |
| `level_mapa.py` | 0.2 | Pasa un volcado de precios de Level (`datos/level_volcado.txt`) a `datos/level_precios.json` con historial. El volcado lo saca `level_lectura.js` pegado en la consola de flylevel.com (o en el navegador de la app de Claude): Playwright recibe «403 Access Denied» del antibot de Level y no se esquiva. 7 rutas BCN (BOS, EZE, JFK, LAX, LIM, MIA, SCL), 12 meses, ida suelta Economy Light. Luego `contraste_comision.py --sigla LL`. |
| `iberojet_mapa.py` | 0.2 | Lee con Playwright (tu Chrome) los precios por trayecto de la web de Iberojet, 12 meses, MAD y BCN, ida y vuelta; guarda `datos/iberojet_precios.json` con historial de cambios de precio. Despacio (6 s), para si no hay respuesta. `.venv\Scripts\python.exe iberojet_mapa.py [--origenes MAD,BCN] [--meses 12]` |
| `contraste_comision.py` | 0.1 | Compara los precios de la web de una aerolínea con los de Kiwi y ajusta `Kiwi = fijo + pendiente × web` por ruta; imprime las líneas para `kiwi.COMISION`. No escribe nada. `.venv\Scripts\python.exe contraste_comision.py [--sigla E9]` |
| `vueling.py` | 2.5 | Vueling vía SerpApi (Google Flights), lotes de 10 aeropuertos y red aprendida. Desde la 2.4, la ciudad y el país de cada aeropuerto de su red salen de una tabla (`CIUDADES`) cuando ninguna otra fuente los trae: ya no aparece el código (p. ej. «BOD»). Gasta búsquedas: solo con `--vueling`, con tope por ejecución, freno del mes (245) y modo simulación. Probado. Desde la 2.0, además, el **radar gratis** (`--radar`, `--historico`) con `bestPrices` de la web de Vueling: no gasta SerpApi (hora de salida pasada de UTC a hora local en la 2.1). Los vuelos de Vueling enlazan directo a la lista de vuelos de ese día en la web de Vueling (`tickets.vueling.com`, 2.2). |
| `servidor.py` | 0.25 | Servidor local (`abrir_escapadas.bat` → http://localhost:8793/): sirve la demo con botones «Actualizar Ryanair y Wizz» (gratis) y «Buscar también Vueling» (un domingo o todos; calcula antes las búsquedas sin gastar y pide confirmación), con el contador de SerpApi y su fecha de renovación. Solo escucha en este PC. Desde la 0.9 también lanza la búsqueda por país (`/api/pais`, gratis). Desde la 0.11, **refresco automático**: al abrir la demo (y cada 30 min con el servidor abierto), si los datos pasan de 6 h se actualizan solos en segundo plano (gratis; como mucho una vez por hora). Desde la 0.12, `/api/estimar-pais` calcula cuánto tardaría una búsqueda por país sin hacerla. Desde la 0.14, `/api/cancelar` para la búsqueda por país (lo ya consultado queda en la caché) y la búsqueda por país admite varios meses. |
| `verificar_wizz.py` | 2.0 | Comprueba en Kiwi (GRATIS, ya no SerpApi) los vuelos de Wizz de las mejores opciones: llegada real (marca ✓) y, si Wizz solo daba «desde», el precio del vuelo (~, ±3 €). Con `--verificar-wizz N` en `escapadas.py`. |
| `comprobar.py` | 1.0 | Lo único que queda para SerpApi: comprueba UN vuelo suelto en Google Flights (1 búsqueda). Sin `--gastar` solo dice cuántas quedan. Ej.: `comprobar.py BCN IST 2026-11-28 --aerolinea TK --gastar`. |
| `confirmar.py` | 1.1 | Motor (sin pantalla) que contrasta con Google Flights (SerpApi) tramos sueltos: hora y precio exactos. Agrupa varios destinos del mismo día y aerolínea en UNA búsqueda; sin Ryanair; caché de 12 h. Guarda en `resultados\\confirmados.json` (vigente 14 días). |
| `auditor.py` | 1.0 | **SerpApi oculto**: en segundo plano contrasta los tramos no exactos (Vueling, easyJet, Turkish...) de las 3 mejores opciones de cada domingo de las próximas 6 semanas. Nunca baja de 50 búsquedas libres (reserva) y gasta como mucho 12 por ejecución. El precio «~» pasa a ser el de Google con ✓, sin tocar la pantalla. Va en `actualizar_diario.bat`; `--simular` no gasta nada. |
| `paquetes.py` | 0.4 | Vuelos + hotel ESTIMADO de las K (3) mejores opciones de cada domingo con la criba del usuario sobre LiteAPI (`liteapi.estimar`: nota ≥ 7/10, 50+ opiniones, ≤ 3 km del centro, habitación sin litera ni baño compartido; mediana de los 3 más baratos × 1,0, calibrado con Booking/Genius en Palermo). Gratis, sin SerpApi. Desde la 0.4 añade como segunda fuente Google Hotels por DataForSEO (`dataforseo.estimar`), guardada aparte como «google»; si el crédito se acaba, la salta sin molestar. Escribe `resultados/paquetes.json`. `--contar`, `--k N`, `--sin-dataforseo`. |
| `booking.py` | 0.3 | Construye el enlace de búsqueda de Booking con el método del usuario (1 adulto, filtro «baño privado», más baratos primero, fechas de la noche). No consulta nada. En iPhone suele abrir la app. |
| `plan_hoteles.py` | 0.2 | Calcula vuelos + hotel de TODAS las opciones de TODOS los domingos con LiteAPI (≈ 290 consultas, gratis, 1 cada 1,5 s; ~1 h). Mismo aeropuerto: noches en la ciudad de ida. Otro aeropuerto con vuelta el martes: 1 noche en cada ciudad. Escribe `resultados\hoteles_calculo.md` y `.json`. `--contar` solo cuenta. |
| `dataforseo.py` | 0.3 | Google Hotels por DataForSEO (EXPERIMENTAL; `DATAFORSEO_LOGIN` y `DATAFORSEO_PASSWORD` en `.env`). Cola normal: ~0,0009 $ por lista, responde en segundos o pocos minutos. `estimar()` da el nivel de precio de una ciudad (hoteles + apartamentos, sin hostels por el nombre, nota ≥ 3,5/5, 20+ opiniones, ≤ 3 km). `saldo()` lee el crédito (gratis; el campo `cost` sale siempre 0). Todo por la caché; si no hay saldo lanza `SinSaldo`. Prueba: `.venv\Scripts\python.exe dataforseo.py 45.0711,7.6858 2026-10-18 2026-10-19 [--apartamentos]` |
| `liteapi.py` | 0.7 | Hoteles por LiteAPI (EXPERIMENTAL, clave de sandbox `sand_…` en `.env` como `LITEAPI_KEY`). Una llamada a `/hotels/rates` por ciudad y noche trae toda la ciudad (≈ 150 alojamientos); sin cupo mensual; caché de 6 h. `propuestas()` da los 3 más baratos con nota ≥ 7 y habitación válida (sin literas ni baño compartido). Prueba: `.venv\Scripts\python.exe liteapi.py "Turin" IT 2026-11-29 2026-12-01` |
| `ver_hoteles.py` | 0.2 | Vista web de hoteles (`resultados\hoteles.html`): para las 3 mejores opciones del domingo, 3 alojamientos (LiteAPI) y el precio cerrado «desde» (vuelos + estancia); aparte, búsquedas antiguas de SerpApi de ese domingo. Uso: `.venv\Scripts\python.exe ver_hoteles.py 2026-11-29` |
| `hoteles.py` | 0.4 | Hoteles vía SerpApi (Google Hotels). Una búsqueda de lista por ciudad y noche (nota ≥ 3,5/5) y, para los alojamientos baratos (< 30 €, probable litera), una ficha por alojamiento: lee las habitaciones tal como las pone Booking.com y descarta literas, dormitorios y baño compartido. Deja hostels y homestays. Cada resultado dice si la habitación está comprobada. Usa el freno de `vueling.py`. Aún no está enchufado a `escapadas.py`. Prueba: `.venv\Scripts\python.exe hoteles.py "Krakow" 2026-10-18 2026-10-19 [fichas_max]` |
| `extension/` | 0.2.1 | Extensión de Chrome (sin Web Store: «Cargar descomprimida», ver `extension/LEEME.txt`). En Booking, abierto desde «Elegir hotel» de la demo, añade un botón ＋ verde a cada alojamiento; al pulsarlo (botón abajo a la izquierda de la foto) manda nombre, precio, nota, distancia, habitación y enlace a la demo por una cola de `chrome.storage` que recoge `puente.js` (requiere activar «Permitir acceso a las URL de archivos»; Booking corta `window.opener`) y cierra la pestaña. Respaldo: portapapeles + caja de la demo. No hace peticiones. |
| `paises.py` | 0.3 | Lee `paises_visitados.txt` (un país por línea, en inglés, o su código de 2 letras; `#` = comentario) y dice si un país es nuevo. Avisa de las líneas que no reconoce. Prueba: `.venv\Scripts\python.exe paises.py` |
| `pasaporte.py` | 0.4 | Lee y escribe `paises_visitados.txt` para la pestaña **Pasaporte** del iPhone (`movil/flash.html`): marcar/desmarcar un país y guardar los años de visita (varios por país), una nota y los medios de entrada (avion, coche, tren, barco, a_pie; salen como iconos en el sello). Cada línea queda `Francia en inglés \| 2019, 2022 \| nota \| avion, tren`; cada viaje puede llevar cómo se entró: `2025:avion+tren` (avion, coche, tren, barco, a_pie); las líneas antiguas valen igual. Prueba: `.venv\Scripts\python.exe pasaporte.py` |
| `publicar_movil.py` | 0.2 | Genera la carpeta `publicar\` (página del iPhone + datos de Flash, Radar y Países como archivos + `pasaporte_inicial.json`) para **Cloudflare Pages**. No gasta nada. Con `--subir` la sube con wrangler (con `functions/api/pasaporte.js` y `wrangler.toml`, que guardan el pasaporte en Cloudflare KV). Uso: `.venv\Scripts\python.exe publicar_movil.py --subir` |
| `mapa_construir.py` | 0.3 | Genera `movil/mapa.json` (mapamundi para el pasaporte, contornos de Natural Earth, simplificados con Douglas-Peucker por tramo de frontera, sin rejilla; ~480 KB). Solo hace falta si se quiere rehacer el mapa; necesita `pip install pycountry` y el archivo `countries-50m.json` de `world-atlas`. |
| `ver_resultados.py` | 0.37 | Vista web local: convierte `resultados\AAAA-MM-DD.md` en `resultados\escapadas.html` y lo abre en el navegador. Marca en ámbar las opciones con «≥» (precio por comprobar). Etiqueta «🆕 país nuevo» y casilla «Solo países nuevos» (recalcula también el calendario: la opción más barata a un país nuevo por domingo, o «no hay»). Selector «Días libres que pedirías» (ninguno / hasta 1 / hasta 2): lee `AAAA-MM-DD_dias1.md` y `_dias2.md` y enseña cuántos días pedir y cuánto se ahorra. No consulta ni gasta nada. Prueba: `.venv\Scripts\python.exe ver_resultados.py` Desde la 0.26, panel «🌍 Un país concreto» (escribes país, mes, salida y días; botón Buscar con `abrir_escapadas.bat`). Desde la 0.28, al cambiar país, mes, salida o días enseña la búsqueda guardada de ESA combinación (con «consultado hace X») o dice que aún no se ha buscado; el botón se deshabilita mientras busca. Desde la 0.29, arriba dice «Precios actualizados hace X» y avisa cuando termina un refresco automático (botón «Ver los datos nuevos», no recarga solo). |
| `ryanair.py` | 3.4 | Ryanair: idas con 1 consulta; vueltas desde todos sus aeropuertos con 2 (más alguna para afinar el martes); lista de aeropuertos con coordenadas y nombres en inglés. |
| `wizz.py` | 2.0 | Wizz Air (2.0: la pareja ida+vuelta lleva el detalle de cada vuelo para la ficha del Radar): red de rutas y 1 consulta por ruta que trae idas y vueltas de todo el periodo (un fin de semana o un mes). |
| `radar.py` | 0.11 | Radar de viajes largos con meses de antelación (gratis, sin SerpApi), en dos pasos. 1) **Ida:** el día más barato del mes a cada destino (Ryanair, Wizz, Vueling `bestPrices` y Kiwi por país), con 🆕 en países nuevos y, si existe, la mejor pareja ida+vuelta del mismo aeropuerto de 6-8 días: `.venv\Scripts\python.exe radar.py --mes 2027-09 [--nuevos] [--dias 6-8] [--sin-kiwi] [--sin-vueling]` (~6-10 min la 1.ª vez). 2) **Vuelta:** elegido destino y día de ida, el día más barato para volver a BCN desde ese aeropuerto y los cercanos: `radar.py --vuelta KUT --ida 2027-09-12 [--radio 500]`. Guarda en `resultados
| `trenes_gtfs.py` | 0.1 | Horarios de tren Barcelona-Sants ↔ Madrid de Ouigo (GTFS del NAP, clave `NAP_API_KEY` en `.env`) y Renfe (GTFS de `ssl.renfe.com`). Descarga 1 vez por semana: `.venv\Scripts\python.exe trenes_gtfs.py` y deja `datos/trenes_horarios.json`. **Iryo no publica GTFS.** |
| `trenes_ouigo.py` | 0.1 | Cliente propio de la API web de Ouigo (la librería `ouigo` de PyPI está rota): una petición = un día con horas y precios. Errores con nombre y motivo. |
| `trenes_iryo.py` | 0.1 | Cliente de la API de Iryo (la misma búsqueda de iryo.eu, sin captcha): trenes de un día con hora y precio mínimo. No toca la web (Cloudflare), solo `api.iryo.eu`. |
| `trenes_renfe.py` | 0.1 | Precio mínimo por día de Renfe BCN↔MAD (calendario público de renfe.com, sin captcha). Una petición trae un mes. No es el precio de un tren concreto. |
| `trenes.py` | 0.3 | Tren para el Radar vía Madrid: Ouigo = su API (horas y precio reales; también en fechas lejanas, donde el GTFS ya no coincide), Renfe = horarios GTFS (caché 4 h, pausa 10-40 s, tope 300 peticiones/día, freno 24 h al primer 403/429/captcha, contador en `datos/trenes_estado.json`). Ouigo e Iryo: horas y precio reales; Renfe: horarios GTFS + precio mínimo del día (su venta por tren pide captcha). Nunca precios inventados: el aviso lleva operador, motivo y hora. |
| `probar_trenes.py` | 0.2 | Pruebas de aguante: `python probar_trenes.py ouigo|iryo|renfe` (tandas 10/25/50/100 a 30 s, 10 s y sin pausa; para al primer fallo). Resultados en `datos/pruebas_trenes.json`. |
| `actualizar.py` | 0.1 | Refresca los precios **sin abrir la página** (gratis: Ryanair, Wizz y Kiwi; Vueling se queda con lo guardado): hace lo mismo que el botón «Actualizar todos» y reconstruye la demo. Si los datos tienen menos de 6 h no hace nada (`--horas 0` fuerza). `actualizar_diario.bat` es lo que se programa en el Programador de tareas de Windows (log en `actualizar_log.txt`). |
| `nuevos.py` | 0.2 | Los N países nuevos más cercanos (por defecto 10, `--n-nuevos`) con **ida y vuelta**, gratis y por la caché: para cada país llama a `pais.py` (Kiwi, Ryanair, Wizz) y saca la mejor combinación de 3-4 días saliendo en domingo (cambiable con `--salida`, `--dias`, `--mes`). Liechtenstein se busca por Zúrich con aviso de traslado. Tabla comparativa en `resultados
uevos_<periodo>.md`; marca «(estimado)» si algún precio es de Kiwi sin medir. Prueba: `.venv\Scripts\python.exe nuevos.py --solo-listar` (sin consultar) o `nuevos.py --mes 2026-12,2027-01` (~15 min la 1.ª vez). |
| `historico.py` | 0.1 | Histórico de mejores ofertas (gratis): lee la tabla `lecturas` de la caché (Ryanair, Wizz, Vueling y Kiwi guardan cada mínimo con su fecha) y dice por destino y mes de salida el mínimo visto, el precio típico (mediana de un valor por día) y la última lectura; «🔥 chollo» con 3+ días de lecturas y la última un 20 % o más bajo lo típico. `.venv\Scripts\python.exe historico.py [--destino TRN] [--tomar [--meses 6] [--kiwi]]`. Escribe `resultados/historico.json`; la demo lo muestra en el panel «📈 Histórico de ofertas» (con botón «Tomar lecturas ahora» en `abrir_escapadas.bat`). |
| `seguimiento.py` | 0.1 | **Seguimiento diario de vuelos concretos** (gratis, solo Ryanair): lee `vigilados.txt` (una línea por vuelo: `ORIGEN DESTINO AAAA-MM-DD HH:MM NºVUELO [viaje]`), pide el precio de ese día y hora, comprueba el número de vuelo y apunta una línea en `seguimiento_precios.csv` (sin precio → «sin precio»; repetir el mismo día no duplica). Enseña el total por viaje y avisa si cambia ±10 € o ±20 %. `.venv\Scripts\python.exe seguimiento.py [--subir] [--resumen]`. `--subir` hace commit y push solo del CSV. `seguimiento_diario.bat` es lo que se programa en el Programador de tareas de Windows. |
adar.json` y la demo lo enseña en el panel «Radar» (botones «Calcular este mes» y «Ver vuelta» con `abrir_escapadas.bat`). Usa `ryanair.radar` (3.3), `wizz.radar` (1.7), `kiwi.radar_mes` (0.8). Probado con sept-2027. |
| `pais.py` | 1.2 | **Búsqueda por país concreto** (gratis, sin SerpApi): ida y vuelta a un país entrando por un aeropuerto y saliendo por otro, con la regla de 250 km por día fuera entre ellos (km por tierra «≈», ⛴ si hay ferri) y traslado. Fechas a meses vista; por defecto domingo de ida y 4 días contando ida y vuelta (domingo → miércoles). Kiwi (`Country:XX`) + Ryanair y Wizz directos. Sin reglas de hora. `.venv\Scripts\python.exe pais.py Turquia --mes 2027-04 [--dias 4] [--salida domingo] [--n 10]`. Escribe `resultados\pais_TR_2027-04.md`. Desde la 1.2 una búsqueda de más de 12 fechas de ida se parte sola en bloques de 12 (tope 120 fechas), con progreso global y resultado parcial si cancelas (`--bloque N`). Desde la 1.1 afinas más: `--desde/--hasta` (fechas libres), `--vuelta sabado` (día de vuelta), `--max 150` (precio máximo), `--solo Ryanair,Wizz` / `--sin Vueling` (aerolíneas) y `--radio 0` (km entre entrada y salida; 0 = mismo aeropuerto). Desde la 0.2 guarda en `resultados\pais.json` y la demo lo enseña en su panel. |
| `geografia.py` | 2.0 | La regla de la vuelta desde otro aeropuerto: 250 km por día fuera, km por tierra (× 1,3), mismo país o vecino, y ferri si hay mar (tabla de ferris y fronteras). |
| `explorar.py` | 0.6 | **Todos los países nuevos de golpe, con semáforo** (gratis, sin SerpApi): ida y vuelta a los países que no has visitado y a sus vecinos (regla de 250 km por día fuera), rejilla país × fecha en colores según el tipo de viaje (`semaforo.py`). `.venv\Scripts\python.exe explorar.py [--meses-vista 3] [--salida domingo,viernes,sabado] [--dias 3-4]`. Escribe `resultados\explorar.html` y `explorar_AAAA-MM-DD.md`; la demo lo enseña en el panel «🚦 Países nuevos» con un botón «Calcular» (con `abrir_escapadas.bat`; primera vez 15-30 min, con caché segundos). |
| `semaforo.py` | 0.1 | Semáforo con topes fijos según el tipo de viaje (corto / medio / largo por distancia desde BCN). Lo usan la demo y `explorar.py`. |
| `config.py` | 1.0 | Lee las claves privadas del archivo `.env` (nunca las muestra). |
| `cache.py` | 1.1 | Caché común (`cache.sqlite`): 24 h para precios de Ryanair y Wizz (6 h el resto), 3 días para la red de Wizz y los aeropuertos. `leer()` (1.1) mira la caché sin consultar nada. |
| `estimar.py` | 0.2 | Cuánto costará una búsqueda por país SIN hacerla: consultas nuevas (las que no están en caché) y minutos, por fuente (Kiwi, Ryanair, Wizz). Pasa de 5 min → pedirá confirmación. Base del «buscador a medida». `.venv\Scripts\python.exe estimar.py Turquia --mes 2027-04 --dias 4` |
| `probar_kiwi.py` | 0.1 | Prueba controlada de cuánto aguanta Kiwi: tandas de 6, 12, 24 y 48 consultas reales con la pausa normal de 5 s (no la acorta); se para si hay error o vacías seguidas. Escribe `resultados\kiwi_limites.md/.csv`. `.venv\Scripts\python.exe probar_kiwi.py [--tandas 6,12,24,48]` |

Reglas actuales (fase 4):
- Ida: domingo, salida de BCN entre 06:00 y 10:00.
- Vuelta: lunes saliendo a partir de las 20:00 (hora del destino), o martes llegando a BCN como muy tarde
  a las 14:30.
- Vuelta desde el mismo aeropuerto o desde otro, con la regla de distancia del usuario (12-10-2026, vale para
  TODAS las búsquedas: escapadas, explorar, radar y país concreto): **250 km por cada día fuera**
  (domingo→lunes 250, domingo→martes 500, +250 por día libre extra). Los km son **por tierra**, aproximados:
  línea recta × 1,3, siempre con «≈». La vuelta sale del **mismo país o de un país vecino** (frontera,
  puente o ferri regular). Solo aeropuertos con vuelo directo a BCN. El traslado no se incluye.
- El mar no se descarta: un cruce vale si hay **ferri regular** conocido (se marca «⛴»; la lista está en
  `geografia.py`). Sin ferri se descarta (con `--con-mar` se muestra). Gran Bretaña cuenta como continente
  (túnel del Canal).
- **Semáforo con topes fijos** (`semaforo.py`), por precio ida+vuelta y distancia en avión desde BCN: corto
  (hasta 2.700 km) verde ≤ 60 €, ámbar ≤ 100 €; medio (2.700-6.500 km) 150 / 200 €; largo (más de 6.500 km)
  500 / 700 €. Los límites están en un solo sitio.
- Días libres extra (`--dias-extra 1` o `2`, por defecto 0): las mismas dos opciones de vuelta, desplazadas
  1 o 2 días (martes noche / miércoles mañana; miércoles noche / jueves mañana). Cada resultado dice
  cuántos días libres hay que pedir y cuánto se ahorra frente a la mejor vuelta sin pedirlos. Cuesta
  2 consultas más a Ryanair por día extra; Wizz se vuelve a consultar una vez con el periodo más largo.
- Dos billetes de solo ida: se pueden mezclar aerolíneas.
- **Países nuevos:** la columna «País nuevo» marca con 🆕 los destinos cuyo país no está en `paises_visitados.txt` (cuenta el país de la ida; en «otro aeropuerto» avisa también si lo es el de la vuelta, sin descartar). `--nuevos` deja solo esos. Tras cada viaje, añade el país a mano en el archivo.
- El modo España (apagado por defecto) mira solo el destino de la ida: volver desde un aeropuerto español
  sí vale.
- Tarifa básica (solo bolso de mano), 1 adulto.
- Consultas despacio (3 s Ryanair, 4 s Wizz). Si Wizz bloquea, sigue solo con Ryanair y lo avisa.
- Primera búsqueda de un domingo: unas 40 consultas (~3 min). En el modo mes, Wizz se consulta una vez
  para todo el mes, y cada domingo más solo añade unas pocas consultas de Ryanair.
  Repetir en 24 horas: ninguna.

## Clave de SerpApi (para Vueling)

La clave es privada: no se pega en ningún chat. Se guarda en un archivo de esta carpeta que solo está en
tu PC. Pasos (una sola vez):

1. Entra en serpapi.com con tu cuenta y copia tu clave («Your Private API Key», en tu panel).
2. Abre la carpeta `C:\escapadas_flash`. Haz clic derecho en `.env.example` → Abrir con → Bloc de notas.
3. Cambia `pon_aqui_tu_clave_de_serpapi` por tu clave (pégala justo detrás del `=`, sin espacios ni comillas).
4. Archivo → Guardar como… En «Tipo» elige «Todos los archivos (\*.\*)» y como nombre escribe `.env`
   (con el punto delante, sin nada más). Guarda en `C:\escapadas_flash`.
5. Comprueba que funciona: `.venv\Scripts\python.exe config.py` debe decir «SERPAPI_KEY encontrada»
   (no enseña la clave). Si se te guardó como `.env.txt`, también vale.

`config.py` (versión 1.0) lee la clave y, si falta, explica qué hacer. El `.env` está excluido de git
(`.gitignore`).

### Botón «Buscar también Vueling» (servidor local)

- Doble clic en `abrir_escapadas.bat`: arranca el servidor y abre la demo en http://localhost:8793/. Deja la
  ventana negra abierta mientras la usas.
- Arriba de la demo: **contador** («SerpApi: quedan 62 de 250 · se renuevan el 11 de noviembre»; la fecha la da
  la propia cuenta de SerpApi y consultarla no gasta) y tres botones:
  - **Actualizar este domingo / todos los domingos (gratis)**: vuelve a mirar Ryanair y Wizz; ~3 min por domingo
    (la caché de Ryanair y Wizz es ahora de 24 h: repetir dentro de ese plazo es casi instantáneo).
  - **Buscar también Vueling: solo el domingo elegido / los N domingos**: primero CALCULA cuántas búsquedas
    costará (sin gastar) y pregunta «Esto gastará unas 12 búsquedas. Te quedan 140. ¿Sigo?». Solo gasta si
    pulsas «Sí». El tope de esa ejecución es lo confirmado + 3 y nunca pasa del freno del mes (`LIMITE_MES`).
  - Sin créditos (o con el freno alcanzado) el botón sale en gris con el motivo y la fecha de renovación.
- **Los precios de Vueling se guardan con su fecha** (`vueling.guardar_tramos`, en la caché, por domingo). Al
  actualizar sin Vueling siguen saliendo, marcados «precio de hace 4 días» y con un chip en la demo.
- Abierta como archivo (doble clic en `escapadas.html`) la demo no tiene botones: solo enseña lo calculado.
- `vueling.py --recuperar`: una sola vez, rescata de la caché los precios de Vueling ya pagados y los guarda
  con la fecha real de su búsqueda (sin llamar a SerpApi).

### Usar Vueling (gasta del límite de 250 búsquedas gratis al mes)

- `escapadas.py 2026-10-18 --kiwi`: añade Kiwi (no gasta SerpApi). La primera vez de un domingo tarda ~2 min
  (unas 25 consultas con pausa); repetido, ~5 s por la caché. Sus tramos salen con «precio orientativo (Kiwi)».
- `escapadas.py 2026-10-18 --vueling --simular-vueling`: no gasta nada; dice cuántas búsquedas gastaría.
- `escapadas.py 2026-10-18 --vueling`: lo hace de verdad, con un tope de 10 búsquedas nuevas
  (`--tope-busquedas N` para cambiarlo). Al llegar al tope se para y lo avisa.
- `.venv\Scripts\python.exe vueling.py`: dice cuántas búsquedas quedan este mes (no gasta).
- `.venv\Scripts\python.exe vueling.py --radar [--meses 6] [--destinos TRN,PMO]`: radar GRATIS de Vueling
  (`bestPrices`): el mejor vuelo directo de ida a cada destino, mes a mes. Guarda cada lectura con su fecha.
  Tarda ~1 min por mes (pausa de 5 s). `--historico` enseña por destino mínimo, típico y última lectura.
- `escapadas.py 2026-10-18 --verificar-wizz 5`: comprueba en Google Flights los tramos de Wizz de las 5
  mejores opciones de cada lista (precio exacto y llegada real; marca ✓). Gasta 1-2 búsquedas.
  También vale con `--simular-vueling` para solo contarlas.
- Las respuestas se guardan 12 h: repetir la misma búsqueda no gasta.
- El límite de SerpApi es de **250 búsquedas al mes**. Además hay un freno propio: `LIMITE_MES = 245` en
  `vueling.py` (consulta la cuota real, sin gastar) impide pasar de 245 usadas en el mes (subido de 190 el 12-10-2026). Se cambia a mano
  si hace falta.
- **Probado con búsquedas reales (11-10-2026):** Google solo acepta **10 aeropuertos por búsqueda**
  (con 12 o más no devuelve nada). Los precios, horas de salida/llegada y números de vuelo salen bien.
- Para no preguntar por sitios donde Vueling no vuela, `vueling.py` parte de una lista de destinos de BCN
  (`RED_INICIAL`) y guarda cada aeropuerto donde ve un vuelo de Vueling (90 días). Cada ejecución la
  afina sola.
- Coste medido, primer domingo (18-10-2026, red sin aprender): **19 búsquedas** (ida ~8 y vueltas del lunes
  y del martes ~11). Los domingos siguientes deberían gastar menos. Un mes entero, ~60-80: se programará
  aprovechando las búsquedas sin usar de cada semana. Solo salen aeropuertos con coordenadas en las listas
  de Ryanair/Wizz.

## Fuentes probadas (10-10-2026)

| Fuente | Estado |
|---|---|
| Ryanair `farfnd` (oneWayFares / roundTripFares, con filtro de hora) | Funciona. Precios comprobados en la web: coinciden al céntimo |
| Ryanair `booking/availability` (la de la página de reserva) | No: «Availability declined» |
| Wizz Air `asset/map` (rutas) y `search/timetableV2` (más barato del día, con horas) | Funciona (librería flywizz). Su web no carga en el navegador de Claude: precios sin comprobar a mano |
| Wizz Air `search/search` | No: bloqueo antibots (429) |
| Vueling, consulta de precios propia | No: ya no existe |
| Google Flights con fast-flights (Vueling) | No: se queda en la pantalla de cookies de Google |

## Fases

1. Ryanair, mismo aeropuerto, un domingo — hecha y validada.
2. Wizz Air, Vueling y mezcla de aerolíneas — hecha (Vueling vía SerpApi, con presupuesto de búsquedas).
3. Open-jaw con radio — hecha (sin cruzar el mar por defecto).
4. Todos los domingos de un mes — hecha.
5. Hotel, ejecución semanal y aviso al móvil — pendiente.
6. Traslados: leer la web pública de 12Go (sin saltar antibots ni captchas) y ordenar por duración —
   después de la fase 5. Por ahora, solo enlaces y tiempo aproximado.

## Países lejanos con escalas en el Radar (`radar_larga.py` 0.18, vuelta desde países vecinos y territorios: ver ESTADO.md)
Dar de alta un país = una línea en `PAISES_LARGOS` (código, nombre, escalas, topes opcionales). Se lee con Kiwi (gratis) desde BCN y desde MAD (tren Ouigo estimado sumado).
Si la mejor oferta sale de Madrid, la ficha de la casilla lo avisa arriba: «ORIGEN MADRID». Leer uno solo: `radar_larga.py --meses 12 --zona za --max 1` (con `--mes` el filtro `--zona` se ignora y lee todas las zonas).
