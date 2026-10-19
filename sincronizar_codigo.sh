#!/bin/bash
# Pone el CÓDIGO de esta carpeta igual que GitHub (origin/main). Nunca toca datos, lecturas, claves ni resultados.
# Lo que sustituye se copia antes a copias_antes_sync/AAAA-MM-DD_HHMM/. Con --seco solo cuenta. Lo lanza desplegar_pi.sh antes de cada subida.
cd "$(dirname "$0")"
git fetch -q origin main || { echo "$(date +%d-%m\ %H:%M) sin red: el código se queda como está"; exit 0; }
SECO=0; [ "$1" = "--seco" ] && SECO=1
COPIA="copias_antes_sync/$(date +%F_%H%M)"
N=0
PREV=$(cat .git/ultimo_sync 2>/dev/null)   # versión de GitHub de la última sincronización: lo que no coincida con ella lo tocó alguien a mano
while read -r modo tipo sha ruta; do
  case "$ruta" in datos/*|resultados/*|movil/*.json|.env*|*.tmp|*.lock|cache.sqlite*) continue;; esac
  if [ -f "$ruta" ] && [ "$(git hash-object "$ruta")" = "$sha" ]; then continue; fi
  N=$((N+1)); echo "cambia: $ruta"
  [ $SECO = 1 ] && continue
  if [ -f "$ruta" ] && [ -n "$PREV" ] && [ "$(git hash-object "$ruta")" != "$(git rev-parse -q --verify "$PREV:$ruta" 2>/dev/null)" ]; then
    echo "AVISO: $ruta tenía cambios locales que NO venían de GitHub (alguien lo tocó a mano en la Raspberry); se guarda copia en $COPIA/$ruta y se pone el de GitHub. Si el cambio era bueno, hay que subirlo a GitHub."
  fi
  if [ -f "$ruta" ]; then mkdir -p "$COPIA/$(dirname "$ruta")"; cp -p "$ruta" "$COPIA/$ruta"; fi
  mkdir -p "$(dirname "$ruta")"
  git show "origin/main:$ruta" > "$ruta.nuevo" && mv "$ruta.nuevo" "$ruta" || { rm -f "$ruta.nuevo"; echo "FALLO en $ruta"; exit 1; }
  [ "$modo" = "100755" ] && chmod +x "$ruta"
done < <(git ls-tree -r origin/main)
[ $SECO = 0 ] && git rev-parse origin/main > .git/ultimo_sync
echo "$(date +%d-%m\ %H:%M) código sincronizado con GitHub ($(git rev-parse --short origin/main)): $N archivos cambiados"
