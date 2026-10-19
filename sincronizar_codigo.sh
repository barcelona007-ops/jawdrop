#!/bin/bash
# Pone el CÓDIGO de esta carpeta igual que GitHub (origin/main). Nunca toca datos, lecturas, claves ni resultados.
# Lo que sustituye se copia antes a copias_antes_sync/AAAA-MM-DD_HHMM/. Con --seco solo cuenta. Lo lanza desplegar_pi.sh antes de cada subida.
cd "$(dirname "$0")"
git fetch -q origin main || { echo "$(date +%d-%m\ %H:%M) sin red: el código se queda como está"; exit 0; }
SECO=0; [ "$1" = "--seco" ] && SECO=1
COPIA="copias_antes_sync/$(date +%F_%H%M)"
N=0
while read -r modo tipo sha ruta; do
  case "$ruta" in datos/*|resultados/*|movil/*.json|.env*|*.tmp|*.lock|cache.sqlite*) continue;; esac
  if [ -f "$ruta" ] && [ "$(git hash-object "$ruta")" = "$sha" ]; then continue; fi
  N=$((N+1)); echo "cambia: $ruta"
  [ $SECO = 1 ] && continue
  if [ -f "$ruta" ]; then mkdir -p "$COPIA/$(dirname "$ruta")"; cp -p "$ruta" "$COPIA/$ruta"; fi
  mkdir -p "$(dirname "$ruta")"
  git show "origin/main:$ruta" > "$ruta.nuevo" && mv "$ruta.nuevo" "$ruta" || { rm -f "$ruta.nuevo"; echo "FALLO en $ruta"; exit 1; }
  [ "$modo" = "100755" ] && chmod +x "$ruta"
done < <(git ls-tree -r origin/main)
echo "$(date +%d-%m\ %H:%M) código sincronizado con GitHub ($(git rev-parse --short origin/main)): $N archivos cambiados"
