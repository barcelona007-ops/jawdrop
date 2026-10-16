# CLAUDE.md — Jawdrop

Proyecto para encontrar escapadas baratas en avión (Ryanair, Wizz, Kiwi) y puntuarlas con un semáforo.

Al empezar cada sesión:
1. Lee `ESTADO.md` (estado, reglas, siguiente paso) y `README.md` (uso y piezas).
2. Explica los cambios en castellano sencillo, en 2-3 frases, y entrega archivos completos.

Reglas:
- Nunca pidas claves por chat ni leas/muestres `.env`. Comprobar la clave: `python config.py`.
- Sin saltar antibots ni captchas. Consultas despacio y siempre por la caché (`cache.py`).
- SerpApi tiene cupo mensual limitado: avisa antes de gastarlo.
- Una pieza por aerolínea (`ryanair.py`, `wizz.py`, `vueling.py`). Cada archivo tiene `VERSION`: súbela al cambiarlo y actualiza `README.md` y `ESTADO.md`.
- Al terminar: prueba lo cambiado, actualiza `ESTADO.md`, commit en castellano y `git push`.
