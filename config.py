"""
config.py — Claves privadas de Jawdrop.

Las claves se guardan en el archivo .env de esta carpeta (C:\\escapadas_flash\\.env), que escribe el usuario
a mano y que nunca se comparte ni se sube a ningún sitio. Formato, una línea por clave:
    SERPAPI_KEY=la_clave_aquí
También vale una variable de entorno con el mismo nombre (tiene prioridad).
Este módulo nunca muestra el valor de una clave.
"""
import os
from pathlib import Path

VERSION = "1.2"
RUTA_ENV = Path(__file__).resolve().parent / ".env"


class FaltaClave(Exception):
    pass


def _archivo():
    """El .env; si el Bloc de notas lo guardó como .env.txt, también vale."""
    txt = RUTA_ENV.with_name(".env.txt")
    return RUTA_ENV if RUTA_ENV.exists() or not txt.exists() else txt


def _leer_env():
    valores = {}
    if _archivo().exists():
        for linea in _archivo().read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            nombre, valor = linea.split("=", 1)
            valores[nombre.strip()] = valor.strip().strip('"').strip("'")
    return valores


def clave(nombre):
    """Devuelve la clave `nombre` o lanza FaltaClave con instrucciones claras."""
    valor = os.environ.get(nombre) or _leer_env().get(nombre)
    if valor and not valor.startswith("pon_aqui"):
        return valor
    if not _archivo().exists():
        motivo = f"no existe el archivo {RUTA_ENV}"
    else:
        motivo = f"el archivo {_archivo()} no tiene la línea {nombre}= con una clave"
    raise FaltaClave(
        f"Falta la clave {nombre}: {motivo}.\n"
        f"Cómo arreglarlo: copia .env.example como .env en {RUTA_ENV.parent}, ábrelo con el Bloc de notas "
        f"y escribe tu clave detrás de {nombre}= (sin espacios ni comillas). Guarda y vuelve a lanzar."
    )


def serpapi_key():
    return clave("SERPAPI_KEY")


def liteapi_key():
    return clave("LITEAPI_KEY")


def dataforseo_auth():
    """(usuario, contraseña) de la API de DataForSEO. No son los del login de la web (panel «API Access»)."""
    return clave("DATAFORSEO_LOGIN"), clave("DATAFORSEO_PASSWORD")


if __name__ == "__main__":
    # Comprobación rápida: dice si las claves están, sin enseñarlas.
    for nombre in ("SERPAPI_KEY", "LITEAPI_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"):
        try:
            print(f"{nombre} encontrada ({len(clave(nombre))} caracteres). No se muestra por seguridad.")
        except FaltaClave as e:
            print(e)
