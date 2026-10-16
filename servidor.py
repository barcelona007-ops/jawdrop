"""servidor.py 0.20 — Servidor local de Jawdrop: la demo con botones que sí hacen cosas.

La demo (resultados\\escapadas.html) es una página estática: no puede lanzar búsquedas por sí sola. Este
servidor la sirve en http://localhost:8793/ y le da tres botones:
  - «Actualizar»: gratis (Ryanair, Wizz y Kiwi), un domingo o todos (Vueling se queda con lo guardado).
  - «Buscar también Vueling» (un domingo o todos): gasta búsquedas de SerpApi, PERO antes calcula cuántas
    serán (sin gastar) y pide confirmación. Respeta el tope por ejecución y el freno del mes de vueling.py.
  - «Un país concreto»: ida y vuelta a un país por aeropuertos distintos (pais.py), gratis.
  - Refresco automático: al abrir la demo (y cada 30 min con el servidor abierto), si los datos pasan de
    6 horas se actualizan solos en segundo plano (gratis; una vez por hora como mucho).
  - «Cuánto tardará» (`/api/estimar-pais`, estimar.py): consultas nuevas y minutos de una búsqueda por país,
    sin hacerla.
  - Contador de la cuenta de SerpApi (quedan, total y fecha de renovación; esa consulta no gasta).
Escucha en la red de casa (para abrir la pantalla del iPhone, `/movil/`), pero solo contesta a direcciones
privadas (localhost, 192.168.x.x, 10.x.x.x, 172.16-31.x.x): ni nombres de internet ni equipos de fuera. Sin
clave (decisión del usuario): las acciones que gastan siguen pidiendo confirmación y exigen una cabecera propia.
`--solo-local` lo deja como antes, solo en este ordenador (127.0.0.1).

Uso:  abrir_escapadas.bat   (o)   .venv\\Scripts\\python.exe servidor.py [--no-abrir]
"""
import ipaddress
import json
import socket
import sys
import threading
import time
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import escapadas
import explorar
import pais
import pasaporte
import historico
import movil_datos
import radar
import vueling
import ver_resultados

VERSION = "0.26"
PUERTO = 8793
ESTIMA_DOMINGO_NUEVO = 21   # búsquedas de un domingo sin Vueling guardado (medido el 11-10-2026: ~21)
MARGEN = 3                  # búsquedas de más que se dejan sobre lo confirmado
HORAS_FRESCO = 6            # los datos de más de tantas horas se refrescan solos (gratis) al abrir la demo
ESPERA_REINTENTO = 3600     # tras un intento automático (con éxito o no) no se repite antes de 1 h
REVISION = 1800             # con el servidor abierto, cada cuántos segundos se mira si toca refrescar

MOVIL = Path(__file__).resolve().parent / "movil"   # pantalla del iPhone: solo estos archivos se sirven
ARCHIVOS_MOVIL = {
    "flash.html": "text/html; charset=utf-8",
    "manifest.webmanifest": "application/manifest+json",
    "icono-180.png": "image/png",
    "icono-192.png": "image/png",
    "icono-512.png": "image/png",
    "mapa.json": "application/json; charset=utf-8",   # contornos del mapamundi (mapa_construir.py)
    "aeropuertos.json": "application/json; charset=utf-8",   # fichas de aeropuerto (a mano, con fuente y fecha)
}


def _privada(texto):
    """True si es localhost o una IP de red privada (la wifi de casa). Nombres de internet: no."""
    if texto == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        return False
    return ip.is_loopback or (ip.version == 4 and ip.is_private and not ip.is_link_local)


def ip_de_casa():
    """La IP del ordenador en la wifi (sin enviar nada: solo pregunta qué interfaz usaría). None si no hay red."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        return ip if _privada(ip) and not ip.startswith("127.") else None
    except OSError:
        return None


_cerrojo = threading.Lock()
_trabajo = None
_cuota = (0.0, None)
_ultimo_auto = 0.0
_cancelar = threading.Event()   # «Cancelar» de la búsqueda por país (lo hecho queda en la caché)


def domingos_con_datos():
    """Domingos con archivo en resultados\\ desde hoy en adelante."""
    hoy = date.today().isoformat()
    return sorted(p.stem for p in escapadas.RESULTADOS.glob("20??-??-??.md") if p.stem >= hoy)


def cuota():
    """Cuenta de SerpApi (con 30 s de memoria; consultarla no gasta)."""
    global _cuota
    t, c = _cuota
    if c is None or time.time() - t > 30:
        c = vueling.cuenta()
        c = dict(c, limite=vueling.LIMITE_MES, utiles=vueling.utiles(c))
        _cuota = (time.time(), c)
    return c


def _ultimo_visto():
    """{domingo: fecha más reciente de un precio de Vueling guardado} de los domingos con datos."""
    res = {}
    for d in domingos_con_datos():
        try:
            vistos = [t["visto"] for t in vueling.tramos_guardados(d) if t.get("visto")]
        except Exception:
            vistos = []
        res[d] = max(vistos) if vistos else None
    return res


def edad_datos():
    """Segundos desde la última actualización del domingo MÁS ANTIGUO con datos (o None si no hay)."""
    horas = []
    for d in domingos_con_datos():
        try:
            horas.append((escapadas.RESULTADOS / f"{d}.md").stat().st_mtime)
        except OSError:
            pass
    return time.time() - min(horas) if horas else None


def toca_refrescar():
    """True si los datos pasan de HORAS_FRESCO, no hay trabajo en marcha y no se intentó hace menos de 1 h."""
    global _ultimo_auto
    edad = edad_datos()
    if edad is None or edad < HORAS_FRESCO * 3600:
        return False
    if _trabajo and _trabajo["estado"] == "corriendo":
        return False
    return time.time() - _ultimo_auto > ESPERA_REINTENTO


def refrescar_si_toca():
    """Refresco automático en segundo plano (gratis: Ryanair, Wizz y Kiwi; Vueling se queda con lo guardado)."""
    global _ultimo_auto
    if not toca_refrescar():
        return
    t, _ = lanzar("actualizar", [], auto=True)
    if t:
        _ultimo_auto = time.time()


def _vigilante():
    while True:
        time.sleep(REVISION)
        try:
            refrescar_si_toca()
        except Exception:
            pass


def estado():
    try:
        c, error = cuota(), None
    except Exception as e:
        c, error = None, f"No se pudo consultar SerpApi: {str(e)[:100]}"
    edad = edad_datos()
    return {"cuota": c, "error": error, "vueling": _ultimo_visto(), "trabajo": _trabajo,
            "hoy": date.today().isoformat(), "edad_datos": edad, "horas_fresco": HORAS_FRESCO}


def _periodo(dom, todos):
    """Periodo de Wizz de un domingo: del primer al último domingo CON DATOS de su mismo mes (como `--mes`).
    Un periodo más largo (p. ej. 6 semanas seguidas) lo rechaza Wizz («InvalidTimeDateRange»)."""
    mes = [d for d in todos if d[:7] == dom[:7]]
    return (mes[0], mes[-1])


def _por_meses(domingos, todos):
    """[(periodo, [domingos])] agrupando por mes, en orden."""
    grupos = {}
    for d in sorted(domingos):
        grupos.setdefault(d[:7], []).append(d)
    return [(_periodo(g[0], todos), g) for g in grupos.values()]


def _correr_radar(t, accion, datos):
    """Radar de largo plazo: gratis (Ryanair, Wizz, Vueling bestPrices y Kiwi), no toca SerpApi."""
    progreso = lambda i, n, d: t.update(mensaje=f"Radar: {d} ({i}/{n})")
    try:
        dmin, dmax = radar._dias(datos.get("dias") or "6-8")
        if accion == "radar":
            lista, avisos = radar.radar_ida(datos["mes"], dmin, dmax, avisar=progreso)
            radar.guardar_mes(datos["mes"], lista, avisos, dmin, dmax)
        else:
            lista, avisos = radar.radar_vuelta(datos["destino"], datos["ida"], dmin, dmax, avisar=progreso)
            radar.guardar_vuelta(datos["destino"], datos["ida"], lista, avisos, dmin, dmax)
        t["mensaje"] = "Preparando la página…"
        ver_resultados.construir()
        t["avisos"] = list(dict.fromkeys(avisos))[:8]
        t["resultado"] = {}
        t["estado"] = "hecho"
        t["mensaje"] = "Listo"
    except Exception as e:
        t["estado"] = "error"
        t["mensaje"] = str(e)[:300]
    finally:
        t["fin"] = time.time()


def lanzar_radar(accion, datos):
    global _trabajo
    with _cerrojo:
        if _trabajo and _trabajo["estado"] == "corriendo":
            return None, "Ya hay un trabajo en marcha."
        t = {"accion": accion, "estado": "corriendo", "mensaje": "Empezando…", "domingos": [],
             "inicio": time.time()}
        _trabajo = t
    threading.Thread(target=_correr_radar, args=(t, accion, datos), daemon=True).start()
    return t, None


def _correr_historico(t, datos):
    """Toma lecturas nuevas del radar (6 meses, gratis) para el histórico de ofertas."""
    try:
        meses = max(1, min(12, int(datos.get("meses", 6))))
        historico.tomar(meses, avisar=lambda *a: t.update(mensaje=" ".join(str(x) for x in a)[:120]))
        t["mensaje"] = "Preparando la página…"
        ver_resultados.construir()
        t["resultado"] = {}
        t["estado"] = "hecho"
        t["mensaje"] = "Listo"
    except Exception as e:
        t["estado"] = "error"
        t["mensaje"] = str(e)[:300]
    finally:
        t["fin"] = time.time()


def lanzar_historico(datos):
    global _trabajo
    with _cerrojo:
        if _trabajo and _trabajo["estado"] == "corriendo":
            return None, "Ya hay un trabajo en marcha."
        t = {"accion": "historico", "estado": "corriendo", "mensaje": "Empezando…", "domingos": [],
             "inicio": time.time()}
        _trabajo = t
    threading.Thread(target=_correr_historico, args=(t, datos), daemon=True).start()
    return t, None


def _correr_explorar(t, datos):
    """Todos los países nuevos a la vez, con semáforo (explorar.py): gratis, no toca SerpApi."""
    progreso = lambda i, n, d: t.update(mensaje=f"Países nuevos: {d} ({i}/{n})")
    try:
        explorar.main(["--salida", datos["salida"], "--dias", datos["dias"],
                       "--meses-vista", str(datos["meses"])], avisar=progreso)
        t["mensaje"] = "Preparando la página…"
        ver_resultados.construir()
        t["resultado"] = {}
        t["estado"] = "hecho"
        t["mensaje"] = "Listo"
    except SystemExit as e:
        t["estado"] = "error"
        t["mensaje"] = str(e)[:300] or "No se pudo calcular"
    except Exception as e:
        t["estado"] = "error"
        t["mensaje"] = str(e)[:300]
    finally:
        t["fin"] = time.time()


def lanzar_explorar(datos):
    global _trabajo
    with _cerrojo:
        if _trabajo and _trabajo["estado"] == "corriendo":
            return None, "Ya hay un trabajo en marcha."
        t = {"accion": "explorar", "estado": "corriendo", "mensaje": "Empezando…", "domingos": [],
             "inicio": time.time()}
        _trabajo = t
    threading.Thread(target=_correr_explorar, args=(t, datos), daemon=True).start()
    return t, None


def _correr_pais(t, datos):
    """Búsqueda por país (pais.py): gratis (Kiwi, Ryanair y Wizz), no toca SerpApi."""
    def global_(p):
        # progreso de toda la búsqueda (todos los bloques): la página pinta la barra con esto
        t.update(progreso=p, mensaje=f"{p['fase']} ({p['pct']} %)")
    try:
        entrada, _ = pais.ejecutar(datos["pais"], meses=datos["mes"], desde=datos["desde"], hasta=datos["hasta"],
                                   salida=datos["salida"], dias=datos["dias"], progreso=global_, cancelar=_cancelar,
                                   vuelta=datos["vuelta"], maximo=datos["maximo"],
                                   solo=datos["solo"], sin=datos["sin"], radio=datos["radio"])
        pais.guardar(entrada)
        t["mensaje"] = "Preparando la página…"
        ver_resultados.construir()
        t["avisos"] = entrada["avisos"]
        t["resultado"] = {"clave": entrada["clave"]}
        t["estado"] = "hecho"
        t["mensaje"] = "Listo"
    except pais.Cancelado as c:
        t["estado"] = "cancelado"
        t["mensaje"] = "Cancelado. Lo ya consultado queda guardado: si buscas de nuevo, sale más rápido."
        if c.parcial:   # había bloques terminados: se guardan como resultado parcial
            try:
                pais.guardar(c.parcial)
                ver_resultados.construir()
                t["resultado"] = {"clave": c.parcial["clave"]}
                t["mensaje"] = "Cancelado. Te enseño lo que ya estaba terminado (resultado parcial)."
            except Exception:
                pass
    except ValueError as e:
        t["estado"] = "error"
        t["mensaje"] = str(e)[:300]
    except Exception as e:
        t["estado"] = "error"
        t["mensaje"] = str(e)[:300]
    finally:
        t["fin"] = time.time()


def datos_pais(cuerpo):
    """Lee y valida los campos del formulario «Un país concreto». Devuelve (datos, None) o (None, error)."""
    import re
    f = lambda k: str(cuerpo.get(k, "") if cuerpo.get(k) is not None else "").strip()
    mes_re = r"20\d\d-(0[1-9]|1[0-2])"
    dia_re = r"[a-záéíóúñ,]{3,40}"
    datos = {"pais": f("pais"), "mes": f("mes"), "desde": f("desde"), "hasta": f("hasta"),
             "dias": f("dias") or "4", "salida": f("salida") or "domingo", "vuelta": f("vuelta").lower(),
             "solo": f("solo"), "sin": f("sin"), "maximo": None, "radio": None}
    try:
        if f("maximo"):
            datos["maximo"] = float(f("maximo").replace(",", "."))
        if f("radio"):
            datos["radio"] = float(f("radio").replace(",", "."))
    except ValueError:
        return None, "El precio máximo y el radio son números."
    if (datos["maximo"] is not None and not 0 < datos["maximo"] < 100000) or \
            (datos["radio"] is not None and not 0 <= datos["radio"] < 20000):
        return None, "Precio máximo o radio fuera de rango."
    fecha_re = r"20\d\d-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
    con_rango = bool(datos["desde"] or datos["hasta"])
    ok = (0 < len(datos["pais"]) <= 40
          and ((not con_rango and re.fullmatch(mes_re + "(," + mes_re + "){0,5}", datos["mes"]))
               or (con_rango and re.fullmatch(fecha_re, datos["desde"]) and re.fullmatch(fecha_re, datos["hasta"])
                   and datos["desde"] <= datos["hasta"]))
          and re.fullmatch(r"\d{1,2}(-\d{1,2})?", datos["dias"])
          and re.fullmatch(dia_re, datos["salida"].lower())
          and (not datos["vuelta"] or re.fullmatch(dia_re, datos["vuelta"]))
          and len(datos["solo"]) <= 80 and len(datos["sin"]) <= 80
          and re.fullmatch(r"[\w ,.\-]*", datos["solo"] + datos["sin"]))
    if not ok:
        return None, "datos de la búsqueda por país no válidos"
    if con_rango:
        datos["mes"] = None
    else:
        datos["desde"] = datos["hasta"] = None
    return datos, None


def lanzar_pais(datos):
    global _trabajo
    with _cerrojo:
        if _trabajo and _trabajo["estado"] == "corriendo":
            return None, "Ya hay un trabajo en marcha."
        t = {"accion": "pais", "estado": "corriendo", "mensaje": "Empezando…", "domingos": [],
             "inicio": time.time()}
        _trabajo = t
    _cancelar.clear()
    threading.Thread(target=_correr_pais, args=(t, datos), daemon=True).start()
    return t, None


def _correr(t, accion, domingos, maximo):
    global _cuota
    avisos = []
    progreso = lambda m: t.update(mensaje=m)

    def recorrer(lista, **opciones):
        """actualizar_domingos mes a mes; el contador de búsquedas gastadas se mantiene entre meses."""
        costes = {}
        for i, (periodo, grupo) in enumerate(_por_meses(lista, todos)):
            costes.update(escapadas.actualizar_domingos(grupo, periodo, avisos=avisos, progreso=progreso,
                                                        reiniciar=(i == 0), **opciones))
        return costes

    try:
        todos = domingos_con_datos()
        if not todos:
            raise RuntimeError("No hay resultados: ejecuta antes escapadas.py")
        if accion == "estimar":
            costes = recorrer(domingos, con_vueling=True, simular=True)
            est = {}
            for d, n in costes.items():
                nuevo = not vueling.tramos_guardados(d)
                est[d] = max(n, ESTIMA_DOMINGO_NUEVO) if nuevo else n
            t["resultado"] = {"costes": est, "total": sum(est.values())}
        elif accion == "actualizar":
            # sin domingos = todos; con uno o varios, solo esos (los demás se quedan como están)
            recorrer(domingos or todos, extras=(0, 1, 2), con_kiwi=True)
            progreso("Preparando la página…")
            ver_resultados.construir()
            t["resultado"] = {}
        elif accion == "vueling":
            util = vueling.utiles(vueling.cuenta())
            tope = min(maximo + MARGEN, util)
            if tope <= 0:
                raise RuntimeError("No hay búsquedas disponibles (cuota o freno del mes).")
            costes = recorrer(domingos, con_vueling=True, tope=tope, extras=(0, 1, 2), con_kiwi=True)
            progreso("Preparando la página…")
            ver_resultados.construir()
            t["resultado"] = {"gastadas": sum(costes.values()), "costes": costes}
        t["avisos"] = list(dict.fromkeys(avisos))[:8]
        t["estado"] = "hecho"
        t["mensaje"] = "Listo"
    except Exception as e:
        t["estado"] = "error"
        t["mensaje"] = str(e)[:300]
    finally:
        _cuota = (0.0, None)
        t["fin"] = time.time()


def lanzar(accion, domingos, maximo=0, auto=False):
    """Pone en marcha un trabajo (solo uno a la vez). Devuelve (trabajo, error)."""
    global _trabajo
    validos = set(domingos_con_datos())
    if accion in ("estimar", "vueling", "actualizar"):
        domingos = [d for d in domingos if d in validos]
        if not domingos and accion != "actualizar":
            return None, "Ese domingo no tiene resultados."
    with _cerrojo:
        if _trabajo and _trabajo["estado"] == "corriendo":
            return None, "Ya hay un trabajo en marcha."
        t = {"accion": accion, "estado": "corriendo", "mensaje": "Empezando…", "domingos": domingos,
             "inicio": time.time(), "auto": auto}
        _trabajo = t
    threading.Thread(target=_correr, args=(t, accion, domingos, int(maximo)), daemon=True).start()
    return t, None


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _host_ok(self):
        # El nombre del servidor Y quien pregunta deben ser de la red de casa (frena el «DNS rebinding»)
        return _privada(self.headers.get("Host", "").rsplit(":", 1)[0]) and _privada(self.client_address[0])

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if not self._host_ok():
            return self._json({"error": "no permitido"}, 403)
        ruta = self.path.split("?")[0]
        if ruta in ("/movil", "/movil/") or ruta.startswith("/movil/"):
            nombre = ruta[len("/movil/"):] or "flash.html"
            if nombre == "flash.html":
                refrescar_si_toca()   # igual que la demo: si los datos son viejos, se refrescan en segundo plano
            tipo = ARCHIVOS_MOVIL.get(nombre)
            archivo = MOVIL / nombre
            if not tipo or not archivo.is_file():
                return self._json({"error": "no existe"}, 404)
            cuerpo = archivo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        if ruta == "/api/movil-flash":
            try:
                d = movil_datos.datos()
            except Exception as e:
                return self._json({"error": f"No se pudieron leer los resultados: {str(e)[:100]}"}, 500)
            d["edad_datos"] = edad_datos()
            return self._json(d)
        if ruta == "/api/movil-trabajo":   # ligero (sin SerpApi): lo pregunta el iPhone mientras actualiza
            return self._json({"trabajo": _trabajo})
        if ruta == "/api/movil-radar":
            try:
                return self._json(movil_datos.datos_radar())
            except Exception as e:
                return self._json({"error": f"No se pudo leer el radar: {str(e)[:100]}"}, 500)
        if ruta == "/api/movil-paises":
            try:
                return self._json(movil_datos.datos_paises())
            except Exception as e:
                return self._json({"error": f"No se pudo leer los países nuevos: {str(e)[:100]}"}, 500)
        if ruta == "/api/pasaporte":
            return self._json(pasaporte.datos())
        if ruta == "/api/estado":
            return self._json(estado())
        if ruta == "/api/historico-datos":
            return self._json(historico.guardar())
        if ruta == "/api/radar-datos":
            return self._json(radar.cargar())
        if ruta == "/api/pais-datos":
            return self._json(pais.cargar())
        if ruta == "/api/explorar-datos":
            return self._json(explorar.cargar())
        if ruta == "/explorar.html":
            archivo = explorar.CARPETA / "explorar.html"
            if not archivo.exists():
                return self._json({"error": "no existe"}, 404)
            cuerpo = archivo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        if ruta in ("/", "/escapadas.html"):
            refrescar_si_toca()   # al abrir la demo, si los datos son viejos se refrescan en segundo plano
            if not ver_resultados.SALIDA.exists():
                ver_resultados.construir()
            cuerpo = ver_resultados.SALIDA.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        self._json({"error": "no existe"}, 404)

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Escapadas") != "1":
            return self._json({"error": "no permitido"}, 403)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            cuerpo = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json({"error": "petición mal formada"}, 400)
        ruta = self.path.split("?")[0]
        if ruta in ("/api/radar", "/api/radar-vuelta"):
            import re
            f = lambda k: str(cuerpo.get(k, ""))
            if ruta == "/api/radar":
                ok = re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", f("mes"))
                datos = {"mes": f("mes"), "dias": f("dias") or "6-8"}
            else:
                ok = re.fullmatch(r"[A-Z]{3}", f("destino")) and re.fullmatch(r"20\d\d-\d\d-\d\d", f("ida"))
                datos = {"destino": f("destino"), "ida": f("ida"), "dias": f("dias") or "6-8"}
            if not ok or not re.fullmatch(r"\d{1,2}(-\d{1,2})?", datos["dias"]):
                return self._json({"error": "datos del radar no válidos"}, 400)
            t, error = lanzar_radar("radar" if ruta == "/api/radar" else "radar_vuelta", datos)
            if error:
                return self._json({"error": error}, 409)
            return self._json({"trabajo": t})
        if ruta == "/api/pasaporte":   # marcar/desmarcar un país: solo escribe paises_visitados.txt, no gasta nada
            try:
                return self._json(pasaporte.guardar(cuerpo.get("codigo", ""), cuerpo.get("visitado") is True,
                                                    cuerpo.get("anios", []), cuerpo.get("nota", ""),
                                                    medios=cuerpo.get("medios", [])))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if ruta == "/api/historico-tomar":
            t, error = lanzar_historico({"meses": cuerpo.get("meses", 6)})
            if error:
                return self._json({"error": error}, 409)
            return self._json({"trabajo": t})
        if ruta == "/api/estimar-pais":
            import estimar
            datos, error = datos_pais(cuerpo)
            if error:
                return self._json({"error": error}, 400)
            try:
                return self._json(estimar.estimar_pais(datos["pais"], meses=datos["mes"], desde=datos["desde"],
                                                       hasta=datos["hasta"], salida=datos["salida"], dias=datos["dias"],
                                                       vuelta=datos["vuelta"], solo=datos["solo"], sin=datos["sin"]))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if ruta == "/api/explorar":
            import re
            f = lambda k: str(cuerpo.get(k, "")).strip()
            datos = {"salida": f("salida") or "domingo", "dias": f("dias") or "3-4", "meses": f("meses") or "3"}
            ok = (re.fullmatch(r"[a-záéíóúñ,]{3,40}", datos["salida"].lower())
                  and re.fullmatch(r"\d{1,2}(-\d{1,2})?", datos["dias"]) and re.fullmatch(r"[1-6]", datos["meses"]))
            if not ok:
                return self._json({"error": "datos de la búsqueda de países nuevos no válidos"}, 400)
            t, error = lanzar_explorar(datos)
            if error:
                return self._json({"error": error}, 409)
            return self._json({"trabajo": t})
        if ruta == "/api/cancelar":
            if _trabajo and _trabajo["estado"] == "corriendo" and _trabajo["accion"] == "pais":
                _cancelar.set()
                _trabajo["mensaje"] = "Cancelando…"
            return self._json({"ok": True})
        if ruta == "/api/pais":
            datos, error = datos_pais(cuerpo)
            if error:
                return self._json({"error": error}, 400)
            t, error = lanzar_pais(datos)
            if error:
                return self._json({"error": error}, 409)
            return self._json({"trabajo": t})
        acciones = {"/api/estimar": "estimar", "/api/vueling": "vueling", "/api/actualizar": "actualizar"}
        accion = acciones.get(self.path.split("?")[0])
        if not accion:
            return self._json({"error": "no existe"}, 404)
        if accion in ("estimar", "vueling"):   # desde 13-10-2026 Vueling viene de Kiwi (gratis); SerpApi ya no se gasta aquí
            return self._json({"error": "Buscar Vueling con SerpApi está desactivado: Vueling viene de Kiwi (gratis). "
                                        "Para comprobar un vuelo suelto usa comprobar.py."}, 410)
        domingos = [d for d in cuerpo.get("domingos", []) if isinstance(d, str)]
        maximo = cuerpo.get("maximo", 0)
        if accion == "vueling" and not (isinstance(maximo, int) and maximo > 0 and cuerpo.get("confirmado") is True):
            return self._json({"error": "falta la confirmación del gasto"}, 400)
        t, error = lanzar(accion, domingos, maximo)
        if error:
            return self._json({"error": error}, 409)
        self._json({"trabajo": t})


class Servidor(ThreadingHTTPServer):
    # En Windows, con la opción por defecto dos servidores pueden compartir puerto y repartirse las peticiones
    allow_reuse_address = False


def main():
    solo_local = "--solo-local" in sys.argv
    try:
        srv = Servidor(("127.0.0.1" if solo_local else "0.0.0.0", PUERTO), Manejador)
    except OSError:
        sys.exit(f"El puerto {PUERTO} ya está en uso: seguramente Jawdrop ya está abierto "
                 f"(mira http://localhost:{PUERTO}/).")
    if not ver_resultados.SALIDA.exists():
        ver_resultados.construir()
    url = f"http://localhost:{PUERTO}/"
    print(f"Jawdrop (servidor {VERSION}) en {url}")
    ip = None if solo_local else ip_de_casa()
    if ip:
        print(f"En el iPhone (misma wifi), abre en Safari:  http://{ip}:{PUERTO}/movil/")
        print("Si el iPhone no conecta: Windows pregunta la primera vez si deja a Python usar la red; di que sí solo en red PRIVADA.")
    elif not solo_local:
        print("No encuentro la IP de la wifi: sin red no se puede abrir desde el iPhone.")
    print("Deja esta ventana abierta mientras usas la página. Para cerrar: Ctrl+C o cierra la ventana.")
    if "--no-abrir" not in sys.argv:
        webbrowser.open(url)
    threading.Thread(target=_vigilante, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Cerrado.")


if __name__ == "__main__":
    main()
