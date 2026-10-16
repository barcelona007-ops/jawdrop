# ¿Qué aerolíneas de El Prat se pueden leer como Ryanair y Wizz?

Investigación del 12-10-2026. Hecha desde la nube, que **no llega a ninguna web de aerolínea** (probado: Ryanair,
Wizz, easyJet, Vueling, Transavia, Volotea, Pegasus, Kiwi, AZair, Google y Aena devuelven «bloqueado» desde aquí).
Por eso cada cosa va marcada:

- **Visto**: lo he leído en una fuente concreta (enlace al final).
- **Deducido**: lo saco de pistas indirectas; hay que probarlo en tu PC antes de fiarse.

Nada de esto se ha probado contra la web real de la aerolínea. El primer paso, si quieres, es una «prueba de
puertas» en tu PC: una consulta por fuente, despacio, para ver cuáles abren.

---

## 1. Lo importante en 6 líneas

1. **Vueling tiene un calendario de precios público** (Visto): una consulta por ruta devuelve el precio más
   barato de cada día de los próximos 7-10 meses, con número de vuelo y **hora de salida** (sin hora de llegada).
   Si funciona desde tu casa, **Vueling pasa a ser gratis** y SerpApi queda libre para otras cosas.
   Ojo: el `ESTADO.md` dice «Vueling, consulta propia: ya no existe»; esto es otra puerta distinta.
2. **Con Ryanair + Wizz + ese calendario de Vueling, casi todos los países nuevos cercanos salen gratis**:
   Irlanda, Malta, Chipre, Islandia, Turquía (Estambul), Argelia, Túnez, Egipto, Senegal, Gambia y Cabo Verde.
3. **Kiwi.com** (el buscador) tiene una consulta pública sin clave que cubre **todas** las aerolíneas (Pegasus,
   Turkish, AJet, Icelandair, Air Algérie…) y admite «cualquier destino de un país» y rangos de fechas (Visto en
   código público de mayo de 2026). Sirve de **radar** para lo que no cubren Ryanair/Wizz/Vueling. Su precio puede
   diferir del de la aerolínea: se usa para encontrar, y se confirma aparte.
4. **easyJet, Volotea, Transavia, Norwegian, Eurowings, Jet2, Pegasus y SunExpress están detrás de antibots**
   (Akamai, Incapsula, Cloudflare, Radware). Quien las lee usa un Chrome «disfrazado»: eso es saltarse el antibot,
   **descartado** por tus reglas. Además, ninguna lleva desde BCN a un país que te falte, salvo Pegasus y SunExpress
   (Turquía), y Turquía ya la cubren Vueling y Kiwi.
5. **Icelandair, Aer Lingus, airBaltic, Air Arabia, Royal Air Maroc y Aegean** tienen calendarios de precios
   que otros leen sin disfraz (Deducido: lo dice el estado de un proyecto público, sin ver el código). De estas,
   solo **Icelandair** te abre un país nuevo que no cubra ya otra (Islandia en invierno; Vueling solo va en verano).
6. **Google Flights gratis** (librería `fli`) existe y funciona, pero **acepta la pantalla de cookies de Google
   por ti**: es justo lo que decidimos no saltar. Lo dejo como decisión tuya (ver punto 6).

---

## 2. Un domingo cualquiera: 11-oct-2026, salidas de 05:45 a 11:35 (muestra)

Tablero de salidas de FlightStats y Avionio (Visto). Solo veo la primera página de cada franja, así que es una
muestra, no la lista entera (ese día hubo unas 530 salidas contando códigos compartidos).

| Hora | Vuelo | Aerolínea | Destino |
|---|---|---|---|
| 05:45 | FR 1205 | Ryanair | Viena |
| 05:45 | FR 7539 | Ryanair | Milán Malpensa |
| 05:55 | FR 774 | Ryanair | Turín |
| 05:55 | FR 1342 | Ryanair | Palma |
| 05:55 | VY 7364 | Vueling | Tánger |
| 06:00 | FR 3182 | Ryanair | Málaga |
| 06:00 | TP 1041 | TAP | Lisboa |
| 06:00 | LX 1951 | Swiss | Zúrich |
| 06:05 | FR 3035 | Ryanair | Cracovia |
| 06:05 | FR 6881 | Ryanair | Menorca |
| 06:10 | AF 1449 | Air France | París CDG |
| 07:00 | VY (×8) | Vueling | Bilbao, Niza, Granada, San Sebastián, Palma, Palermo, Londres Gatwick, Oporto |
| 07:00 | IB 426 | Iberia | Madrid |
| 07:10 | EC 7105 | easyJet | Ginebra |
| 07:10 | VY (×7) | Vueling | Alicante, Stuttgart, Berlín, Málaga, Sevilla, Ibiza, Ámsterdam |
| 07:20 | IB 5628 | Iberia | Lisboa |
| 09:40 | W6 4462 | Wizz Air | Sofía |
| 10:45 | LY 394 | El Al | Tel Aviv |
| 10:50 | VY 8250 | Vueling | París CDG |
| 11:05 | U2 2002 | easyJet | Mánchester |
| 11:05 | EK 255 | Emirates | Ciudad de México |
| 11:15 | U2 8056 | easyJet | Londres Gatwick |
| 11:20 | U2 3102 | easyJet | Glasgow |
| 11:25 | FR 7959 | Ryanair | Cork |
| 11:25 | TP 1031 | TAP | Lisboa |
| 11:30 | CY 323 | Cyprus Airways | Lárnaca |
| 11:35 | J2 46 | Azerbaijan Airlines | Bakú |

Lo que se ve: entre las 6 y las 10 de la mañana de un domingo mandan **Ryanair y Vueling** con diferencia; luego
easyJet, alguna de bandera (TAP, Swiss, Air France, Iberia) y Wizz. Las «exóticas» (El Al, Cyprus Airways,
Azerbaijan Airlines) salen más tarde, a media mañana.

---

## 3. Todas las aerolíneas de El Prat (lista de Wikipedia, oct-2026) y sus países nuevos para ti

Marcado **🆕** = país que no está en `paises_visitados.txt`.

| Grupo | Aerolíneas | Destinos que te interesan |
|---|---|---|
| Low cost grandes | Ryanair, Vueling, Wizz Air, easyJet, Volotea, Transavia, Eurowings, Norwegian, Jet2 | Ryanair: Dublín/Cork 🆕, Malta 🆕. Vueling: Dublín 🆕, Malta 🆕, Estambul 🆕, Reikiavik 🆕 (verano), Argel/Orán 🆕, Túnez 🆕 (verano), El Cairo 🆕, Dakar 🆕, Banjul 🆕, Sal 🆕 (temporada). Wizz: Lárnaca 🆕 |
| Turquía | Pegasus (Estambul-SAW, Esmirna), AJet (Ankara), Turkish (Estambul), SunExpress (Esmirna, verano) | Turquía 🆕 |
| Islandia / Irlanda | Icelandair (Keflavík), Aer Lingus (Dublín) | Islandia 🆕, Irlanda 🆕 |
| Norte de África | Air Algérie, Tunisair, Nouvelair, Egyptair, Royal Air Maroc, Air Arabia Maroc | Argelia 🆕, Túnez 🆕, Egipto 🆕 (Marruecos ya lo tienes) |
| Mediterráneo oriental | Cyprus Airways (Lárnaca, temporada), El Al, Arkia, Bluebird, TUS (Tel Aviv), Royal Jordanian (Amán), Middle East Airlines (Beirut, temporada), Aegean, Sky Express | Chipre 🆕, Israel 🆕, Jordania 🆕, Líbano 🆕 |
| Este | Azerbaijan Airlines (Bakú), FlyOne, HiSky, SkyUp, Air Serbia, Bulgaria Air, Croatia Airlines, LOT, airBaltic, Dan Air | Azerbaiyán 🆕 (el resto ya lo tienes) |
| Raras | Atlantic Airways (Islas Feroe, verano), Azores Airlines | Feroe 🆕 (cuenta como Dinamarca según a quién preguntes) |
| Bandera y largo radio | Iberia, Air France, KLM, Lufthansa, Swiss, TAP, ITA, BA, Finnair, SAS, Qatar, Emirates, Etihad, Saudia, Kuwait, Level, americanas, asiáticas… | Golfo y largo radio: fuera del plan de escapadas |

---

## 4. Aerolínea por aerolínea

Semáforo: 🟢 se puede leer sin trampas (o ya se lee) · 🟡 hay puerta, falta probarla en tu PC · 🔴 antibot o cerrada.

| Aerolínea | Semáforo | Qué hay | Antibot | ¿Te abre país nuevo? | Veredicto |
|---|---|---|---|---|---|
| Ryanair | 🟢 | `farfnd` (ya en uso) | No en farfnd | Irlanda, Malta | Ya está |
| Wizz Air | 🟢 | `timetableV2` (ya en uso). La búsqueda fina, Kasada | Kasada en `search` | Chipre (Lárnaca) | Ya está. Lárnaca entra gratis |
| **Vueling** | 🟡 muy prometedor | Calendario JSON público por ruta (el que pinta el «calendario de precios» de vueling.com): precio mínimo por día, 7-10 meses, nº de vuelo y hora de salida; sin hora de llegada; una ruta por consulta (Visto en la ficha de un raspador de Apify) | No citan antibot; dicen que **desde servidores de nube se cuelga** y usan IP de casa. Tu PC es IP de casa | Irlanda, Malta, Turquía, Islandia, Argelia, Túnez, Egipto, Senegal, Gambia, Cabo Verde | **Probar lo primero.** Ahorra SerpApi y abre África |
| easyJet | 🔴/🟡 | Hubo una consulta pública de «tarifas más bajas» (`ejcms/nocache/api/lowestfares`, Visto en código antiguo) | Akamai; quien la lee hoy usa Chrome disfrazado (Visto) | No (Reino Unido, Suiza, Francia, Italia…) | Una prueba sin insistir; si da 403, olvidarla |
| Volotea | 🔴 | Caché de precios | Incapsula + Akamai (Visto) | No (Francia, Italia) | Descartada |
| Transavia | 🔴 | Tuvo API para programadores (developer.transavia.com), hoy dudosa | Cloudflare (Visto) | No (Países Bajos, París) | Descartada |
| Norwegian | 🔴 | Calendario de tarifas | Incapsula (Visto) | No (nórdicos) | Descartada |
| Eurowings | 🔴 | — | Cloudflare (Visto) | No | Descartada |
| Jet2 | 🔴 | — | Akamai (Visto) | No | Descartada |
| Pegasus | 🔴 | Calendario de tarifas; **da 403 desde ago-2025** (Visto, librería Pegasustan) | Akamai (Visto) | Turquía | Por Kiwi o SerpApi |
| SunExpress | 🔴 | — | Radware (Visto) | Turquía (Esmirna, verano) | Por Kiwi o SerpApi |
| AJet | ? | Nada público encontrado | ? | Turquía (Ankara) | Por Kiwi |
| Turkish Airlines | 🔴 | Portal oficial para empresas, con alta y aprobación | Akamai (Deducido) | Turquía | Por Kiwi o SerpApi |
| **Icelandair** | 🟡 | Calendario de tarifas + páginas de ofertas (Deducido) | No citado | Islandia (todo el año) | Probar |
| Aer Lingus | 🟡 | Calendario de tarifas (Deducido) | No citado | Irlanda | Poco útil: Ryanair ya cubre Dublín y Cork |
| airBaltic | 🟡 | API de su app: precio mínimo **por mes** (Visto) | No citado | No (Riga, Tallin) | Poco útil |
| Aegean | 🟡 | Calendario (Deducido) | No citado | No directo | Poco útil |
| Air Arabia Maroc / Royal Air Maroc | 🟡 | Calendario / API (Deducido) | No citado | No (Marruecos ya) | Poco útil |
| Cyprus Airways | ? | Nada encontrado | ? | Chipre | Wizz ya va a Lárnaca |
| Egyptair | 🔴 | Su reserva no responde a programas (Visto) | — | Egipto | Vueling va a El Cairo |
| Royal Jordanian | 🔴 | Roto (Visto) | — | Jordania | Por Kiwi o SerpApi |
| Air Algérie, Tunisair, Nouvelair, El Al, Arkia, MEA, Azerbaijan Airlines, Atlantic Airways | ? | Webs antiguas, nada público encontrado | ? | Sí, varias | Por Kiwi o SerpApi |
| De bandera europeas (TAP, SAS, Finnair, LOT…) | 🟡 | Varias tienen calendario | — | No | No interesan para esto |

---

## 5. Buscadores que juntan muchas aerolíneas

| Fuente | Qué da | Riesgo | Veredicto |
|---|---|---|---|
| **Kiwi.com** (consulta GraphQL pública `api.skypicker.com/umbrella/v2/graphql`, sin clave) | Todas las aerolíneas, solo ida o ida y vuelta, rango de fechas, destino «país entero», horas de salida y llegada, precio en euros (Visto en código de mayo-2026) | No oficial: pueden cerrarla. Precio de Kiwi, a veces algo distinto del de la aerolínea, y mete combinaciones raras (filtrar «solo directos») | **Probar.** Ideal para el radar de países nuevos (Turquía, Israel, Jordania, Azerbaiyán…) |
| AZair (azair.eu) | Buscador checo de low cost: «a cualquier sitio», fechas flexibles, días de estancia | Página web, no API. Hay que leer su HTML con calma y respetar sus normas | Plan B para easyJet (un raspador de Apify saca easyJet de ahí, Visto) |
| Google Flights con `fli` | Todo Google Flights gratis, con horas | Manda una cookie de «cookies aceptadas» para saltar la pantalla europea; avisos de bloqueo 429 en junio-2026 (Visto) | **Decisión tuya** |
| Skyscanner, Kayak, Momondo | — | PerimeterX y similares | Descartados |
| SerpApi (Google Flights) | Lo que ya usas | 250/mes | Reservarlo para confirmar, no para explorar |

---

## 6. Lo que yo haría (por orden)

1. **Prueba de puertas en tu PC** (gratis, 10 minutos, unas 10 consultas en total, despacio): Vueling (calendario),
   Kiwi, Icelandair y easyJet. Para cada una: ¿abre?, ¿qué devuelve?, ¿cuadra el precio con la web? Si una da
   403 o un reto antibot, se apunta y no se insiste.
2. **Si Vueling abre: `vueling.py` 2.0** leyendo el calendario gratis (precio por día y hora de salida) y
   SerpApi solo para confirmar la hora de llegada de los vuelos que de verdad encajan. Es lo que más te ahorra.
3. **Si Kiwi abre: `kiwi.py`** solo para el radar de países nuevos a 2-6 meses (una consulta por país y mes),
   marcando el precio como «según Kiwi».
4. **Icelandair**, solo si abre y Kiwi no la cubre bien.
5. El resto (easyJet, Volotea, Transavia, Norwegian, Eurowings, Jet2, Pegasus, SunExpress): no tocar.
   Lo que llevan a países nuevos ya entra por Vueling, Wizz o Kiwi.

Sobre Google Flights con `fli`: técnicamente no es un antibot, es la pantalla de «aceptar cookies» que Google
enseña en Europa; la librería la da por aceptada. En octubre decidimos no saltarla. Si Kiwi funciona, no hace falta.

---

## Fuentes

- Lista de aerolíneas de BCN: [Wikipedia, Aeropuerto de Barcelona-El Prat](https://en.wikipedia.org/wiki/Josep_Tarradellas_Barcelona–El_Prat_Airport)
- Salidas del 11-oct: [FlightStats BCN](https://www.flightstats.com/v2/flight-tracker/departures/BCN), [Avionio BCN](https://www.avionio.com/en/airport/bcn/departures)
- Vueling (calendario JSON, IP de casa): [Vueling Scraper, Apify](https://apify.com/studio-amba/vueling-scraper)
- Volotea (Incapsula + Akamai): [Volotea Scraper, Apify](https://apify.com/studio-amba/volotea-scraper)
- Transavia (Cloudflare): [Transavia Scraper, Apify](https://apify.com/studio-amba/transavia-scraper)
- Wizz (Kasada): [Wizz Air Scraper, Apify](https://apify.com/studio-amba/wizzair-scraper)
- Estado de ~100 conectores de aerolíneas con su antibot: [CONNECTOR_STATUS.md](https://github.com/iflow-mcp/boosted-chat-boostedtravel/blob/main/CONNECTOR_STATUS.md) (copia de LetsFG)
- Pegasus 403: [Pegasustan, issue 18](https://github.com/sirdx/Pegasustan/issues/18)
- easyJet (consulta antigua): [opayen/easyjet-api](https://github.com/opayen/easyjet-api/blob/master/routes.js); easyJet vía AZair: [easyJet Flight Scraper, Apify](https://apify.com/bakos_bence/easyjet-flights)
- airBaltic (API de la app, precio por mes): [airBaltic Scraper, Apify](https://apify.com/rl1987/airbaltic-api-scraper)
- Norwegian (calendario): [Norwegian Flights Scraper, Apify](https://apify.com/scrapers_lat/norwegian-flights-scraper)
- Kiwi GraphQL sin clave: [wolfiesch/flightfinder](https://github.com/wolfiesch/flightfinder)
- Google Flights con `fli`: [punitarani/fli](https://github.com/punitarani/fli), [issues](https://github.com/punitarani/fli/issues)
- AZair: [azair.eu](https://www.azair.eu/), [guía de uso](https://czechtheworld.com/how-to-search-flight-tickets-on-azair/)
