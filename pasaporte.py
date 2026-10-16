r"""
pasaporte.py — Mapa y pasaporte de países (Jawdrop).

Lee y escribe `paises_visitados.txt`, el mismo archivo que ya usan el semáforo de «país nuevo» y la
búsqueda de países nuevos. Cada línea: `Francia en inglés | años | nota | medios` (todo menos el país es opcional;
los años van separados por comas: `2019, 2022, 2024`; también vale AAAA-MM; cada viaje puede llevar cómo se entró: `2025:avion+tren`.
La 4.ª columna (medios por país) es del formato anterior: se sigue leyendo, pero ya no se escribe si algún viaje lleva los suyos).
Medios válidos: avion, coche, tren, barco, a_pie (salen como iconos en el sello). Las líneas antiguas, sin fecha, siguen valiendo tal cual. Los comentarios (#)
y las líneas que no se reconocen se conservan sin tocar.

Marcar un país que no está en la tabla de `paises.py` lo escribe con su código de 2 letras (vale igual).

Prueba: .venv\Scripts\python.exe pasaporte.py
"""
import os
import re
import tempfile
from pathlib import Path

import paises

VERSION = "0.4"
MEDIOS = ("avion", "coche", "tren", "barco", "a_pie")
_M = "|".join(MEDIOS)
FECHA = re.compile(r"(19\d\d|20\d\d)(-(0[1-9]|1[0-2]))?(:(%s)(\+(%s))*)?" % (_M, _M))   # «2025» o «2025:avion+tren» (cómo se entró en ese viaje)
MAX_VISITAS = 40
MAX_NOTA = 120
_NOMBRE = {}                     # código -> nombre en inglés (el primero de la tabla de paises.py)
for _n, _c in paises.CODIGOS.items():
    _NOMBRE.setdefault(_c, _n.title())
_NOMBRE.update({"GB": "United Kingdom", "US": "United States", "CZ": "Czechia", "AE": "United Arab Emirates"})


def _anios(texto):
    """Lista ordenada de visitas ('2019', '2022-05'…) a partir de «2019, 2022»."""
    if isinstance(texto, (list, tuple)):
        texto = ",".join(str(x) for x in texto)
    return sorted(x for x in re.split(r"[,;\s]+", str(texto or "").strip()) if x)


def _medios(texto):
    """Lista de medios válidos, sin repetir y en el orden fijo de MEDIOS (los desconocidos se ignoran)."""
    if isinstance(texto, (list, tuple)):
        texto = ",".join(str(x) for x in texto)
    pedidos = {x.strip().lower() for x in re.split(r"[,;\s]+", str(texto or "")) if x.strip()}
    return [m for m in MEDIOS if m in pedidos]


def _partir(linea):
    """(texto del país, años, nota, medios) de una línea del archivo."""
    trozos = [x.strip() for x in linea.split("|")]
    trozos += [""] * (4 - len(trozos))
    return trozos[0], trozos[1], trozos[2], trozos[3]


def _codigo(texto):
    c = paises.CODIGOS.get(texto.lower())
    if c is None and len(texto) == 2 and texto.isalpha():
        c = texto.upper()
    return c


def leer(ruta=paises.ARCHIVO):
    """{código: {"anios": [...], "nota": ..., "medios": [...]}} de los países visitados reconocidos."""
    out = {}
    p = Path(ruta)
    if not p.exists():
        return out
    for linea in p.read_text(encoding="utf-8").splitlines():
        if not linea.strip() or linea.strip().startswith("#"):
            continue
        texto, anios, nota, medios = _partir(linea)
        c = _codigo(texto)
        if c:
            out.setdefault(c, {"anios": _anios(anios), "nota": nota, "medios": _medios(medios)})
    return out


def guardar(codigo, visitado, anios=(), nota="", ruta=paises.ARCHIVO, medios=()):
    """Marca o desmarca un país. Devuelve el estado nuevo de ese país. ValueError si algo no es válido."""
    codigo = str(codigo).upper()
    anios, nota, medios = _anios(anios), " ".join(str(nota or "").replace("|", "/").split()), _medios(medios)
    if not re.fullmatch(r"[A-Z]{2}", codigo):
        raise ValueError("Código de país no válido.")
    if any(not FECHA.fullmatch(a) for a in anios):
        raise ValueError("Cada visita debe ser un año (por ejemplo 2019 o 2019:avion+tren).")
    if len(anios) > MAX_VISITAS:
        raise ValueError("Demasiadas visitas.")
    if any(":" in a for a in anios):
        medios = []                          # cada viaje lleva los suyos: la columna antigua por país se vacía
    fecha, via = ", ".join(anios), ", ".join(medios)
    if len(nota) > MAX_NOTA:
        raise ValueError(f"La nota es demasiado larga (máximo {MAX_NOTA} letras).")
    p = Path(ruta)
    lineas = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    nuevas, puesto = [], False
    nombre = _NOMBRE.get(codigo, codigo)
    for linea in lineas:
        t = linea.strip()
        if t and not t.startswith("#"):
            texto = _partir(linea)[0]
            if _codigo(texto) == codigo:
                if visitado and not puesto:      # se reescribe la primera; las repetidas se descartan
                    nuevas.append(" | ".join([texto, fecha, nota, via]).rstrip(" |"))
                    puesto = True
                continue
        nuevas.append(linea)
    if visitado and not puesto:
        nuevas.append(" | ".join([nombre, fecha, nota, via]).rstrip(" |"))
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".paises_", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(nuevas) + "\n")
    os.replace(tmp, p)
    if Path(ruta) == paises.ARCHIVO:
        paises._VISITADOS = None                 # que el semáforo vea el cambio sin reiniciar
    return {"codigo": codigo, "visitado": bool(visitado), "anios": anios if visitado else [],
            "nota": nota if visitado else "", "medios": medios if visitado else []}


def datos():
    return {"visitados": leer(), "version": VERSION}


if __name__ == "__main__":
    import shutil
    carpeta = Path(tempfile.mkdtemp())
    t = carpeta / "v.txt"
    shutil.copy(paises.ARCHIVO, t)
    n0 = len(leer(t))
    print(f"pasaporte.py {VERSION}: {n0} países leídos del archivo real.")
    guardar("PE", True, ["2024", "2019"], "Machu Picchu", t)
    guardar("FR", True, "2019, 2022, 2024", "", t)
    guardar("XK", False, ruta=t)
    r = leer(t)
    assert r["PE"] == {"anios": ["2019", "2024"], "nota": "Machu Picchu", "medios": []} and r["FR"]["anios"] == ["2019", "2022", "2024"] and "XK" not in r
    guardar("PE", False, ruta=t)
    guardar("XK", True, ruta=t)
    guardar("ZW", True, "", "", t)
    r = leer(t)
    assert "PE" not in r and "XK" in r and "ZW" in r and len(r) == n0 + 1, len(r)
    assert paises.cargar(t)[1] == [], paises.cargar(t)[1]
    for malo in (("PE", True, "ayer"), ("1", True, ""), ("PE", True, [], "x" * 200), ("PE", True, "1850")):
        try:
            guardar(*malo, ruta=t)
            raise SystemExit("debía fallar: %r" % (malo,))
        except ValueError:
            pass
    guardar("EE", True, "2025", "", t, medios=["coche", "tren", "tren", "cohete"])
    guardar("JP", True, "2007, 2017", "Con Marta", t, ["avion"])
    r = leer(t)
    assert r["EE"] == {"anios": ["2025"], "nota": "", "medios": ["coche", "tren"]}, r["EE"]
    assert r["JP"]["nota"] == "Con Marta" and r["JP"]["medios"] == ["avion"] and r["FR"]["medios"] == []
    assert paises.cargar(t)[1] == []
    guardar("PE", True, "2019:tren+avion, 2024:barco", "", t, medios=["coche"])
    assert leer(t)["PE"] == {"anios": ["2019:tren+avion", "2024:barco"], "nota": "", "medios": []}, leer(t)["PE"]
    try:
        guardar("PE", True, "2019:cohete", ruta=t)
        raise SystemExit("debía fallar")
    except ValueError:
        pass
    print("  OK: marcar, desmarcar, fecha, nota, validación y compatibilidad con paises.cargar.")
    shutil.rmtree(carpeta)
