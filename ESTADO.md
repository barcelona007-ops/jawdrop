# ESTADO — Jawdrop

Este es el estado público del proyecto. La bitácora detallada de trabajo es privada.

## Qué hay
- Búsqueda de vuelos de ida y vuelta (Ryanair, Wizz, Kiwi) con semáforo de precio, radar por país y mes, y página móvil (`movil/`).
- Cloudflare Pages + Worker (`functions/`, `cron/`) como escaparate; GitHub Actions (`.github/workflows/`) hace las lecturas pesadas.
- Detalle de cada pieza y su versión: ver `README.md`.

## Cómo usarlo por tu cuenta
1. Copia `.env.example` a `.env` y rellena tus claves (nunca las subas).
2. Edita `paises_visitados.txt` (países que ya conoces; no saldrán como «nuevos»), `vigilados.txt` (vuelos a seguir) y, si no sales de Barcelona, el aeropuerto de origen por defecto.
3. En `wrangler.toml` y `cron/wrangler.toml` sustituye `TU_ID_…` por los identificadores de tu cuenta de Cloudflare, y `TU-SUBDOMINIO` en `.github/workflows/diagnostico.yml`.
4. En GitHub → Settings → Secrets: `CLOUDFLARE_API_TOKEN` y `CLOUDFLARE_ACCOUNT_ID`.

## Siguiente paso
Hacer el aeropuerto de origen un ajuste de configuración (hoy BCN va por defecto en el código).
