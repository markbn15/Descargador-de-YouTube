"""
utils/urls.py
====================================================================
Utilidades de URLs compartidas por la GUI, el descargador y el
protocolo markos://.

- extraer_urls: obtiene enlaces http(s) de un texto o archivo.
- normalizar_dominio / dominio_de_url: claves de los perfiles por sitio.
- calidad_para_url: resuelve la calidad de cada enlace (perfil del
  dominio > calidad global).
- parsear_markos: interpreta los argumentos de markos:// y --minimized.
====================================================================
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

# Regex tolerante: corta en espacios, comillas y signos de cierre tipicos.
_RE_URL = re.compile(r"https?://[^\s<>'\"\[\]{}]+", re.IGNORECASE)
_RE_DOMINIO = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")


def limpiar_url(url: str) -> str:
    """Recorta espacios y puntuacion final que suele colarse al copiar."""
    limpia = (url or "").strip().strip("'\"<>")
    while limpia and limpia[-1] in ").,;:!?":
        # Solo recorta si el caracter de cierre no forma parte de la URL.
        if limpia[-1] == ")" and limpia.count("(") >= limpia.count(")"):
            break
        limpia = limpia[:-1]
    return limpia


def extraer_urls(texto: str) -> list[str]:
    """Devuelve todas las URLs http(s) encontradas en un texto."""
    if not texto:
        return []
    encontradas: list[str] = []
    for coincidencia in _RE_URL.finditer(texto):
        url = limpiar_url(coincidencia.group(0))
        if url and url not in encontradas:
            encontradas.append(url)
    return encontradas


def leer_urls_de_archivo(ruta: Path) -> list[str]:
    """Lee un .txt/.csv/.list y devuelve sus URLs (sin duplicados)."""
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return extraer_urls(texto)


def normalizar_dominio(valor: str) -> str:
    """
    Convierte 'https://www.YouTube.com/watch?v=...' en 'youtube.com'.

    Tambien acepta 'youtube.com', '  YouTube.COM  ' o 'www.youtube.com'.
    """
    texto = (valor or "").strip().lower()
    if not texto:
        return ""
    if "://" not in texto:
        texto = "//" + texto
    try:
        partes = urlsplit(texto)
        dominio = (partes.hostname or "").strip().lower().rstrip(".")
    except ValueError:
        dominio = ""
    if not dominio:
        # Ultimo recurso: primera parte de una posible URL mal formada.
        dominio = texto.split("/")[2] if "//" in texto else texto
        dominio = dominio.split(":")[0].strip().lower()
    if dominio.startswith("www."):
        dominio = dominio[4:]
    return dominio


def dominio_de_url(url: str) -> str:
    return normalizar_dominio(url)


def calidad_para_url(
    url: str,
    perfiles: dict[str, str] | None,
    calidad_global: str = "max",
    override: dict[str, str] | None = None,
) -> str:
    """
    Resuelve la calidad de una URL.

    Prioridad:
      1. override exacto (reintentos desde el historial).
      2. perfil del dominio mas especifico (sub.dominio > dominio).
      3. calidad global.
    """
    if override:
        elegida = override.get(url)
        if elegida:
            return elegida

    dominio = dominio_de_url(url)
    if perfiles and dominio:
        mejor_clave = ""
        mejor_calidad = ""
        for clave, calidad in perfiles.items():
            normalizada = normalizar_dominio(clave)
            if not normalizada:
                continue
            if dominio == normalizada or dominio.endswith("." + normalizada):
                if len(normalizada) > len(mejor_clave):
                    mejor_clave = normalizada
                    mejor_calidad = calidad
        if mejor_calidad:
            return mejor_calidad

    return calidad_global or "max"


def _url_valida(url: str) -> bool:
    limpia = limpiar_url(url)
    return limpia.lower().startswith(("http://", "https://"))


def parsear_markos(argumentos: list[str]) -> dict[str, object]:
    """
    Interpreta los argumentos de linea de comandos.

    Formatos admitidos:
        markos://add?url=https%3A%2F%2F...
        markos://download?url=...
        markos://capture
        markos://https://example.com/video
        --minimized / --tray
        --capture
    """
    resultado: dict[str, object] = {
        "urls": [],
        "capturar": False,
        "descargar": False,
        "minimizado": False,
    }
    urls: list[str] = resultado["urls"]  # type: ignore[assignment]

    i = 0
    while i < len(argumentos):
        arg = (argumentos[i] or "").strip()
        bajo = arg.lower()
        if bajo in ("--minimized", "--tray", "--oculto"):
            resultado["minimizado"] = True
        elif bajo in ("--capture", "--capturar"):
            resultado["capturar"] = True
        elif bajo in ("--download", "--descargar"):
            resultado["descargar"] = True
        elif bajo == "--add" and i + 1 < len(argumentos):
            i += 1
            candidata = limpiar_url(argumentos[i])
            if _url_valida(candidata):
                urls.append(candidata)
        elif bajo.startswith("markos://"):
            accion, url = _parsear_uri_markos(arg)
            if accion == "capture":
                resultado["capturar"] = True
            elif accion == "download":
                resultado["descargar"] = True
            if url and _url_valida(url) and url not in urls:
                urls.append(url)
        elif _url_valida(arg):
            candidata = limpiar_url(arg)
            if candidata not in urls:
                urls.append(candidata)
        i += 1

    return resultado


def _parsear_uri_markos(uri: str) -> tuple[str, str]:
    """Devuelve (accion, url) de una URI markos://."""
    resto = uri[len("markos://"):]
    if not resto:
        return "", ""

    # markos://https://sitio/video  (sin accion explicita)
    if resto.lower().startswith(("http://", "https://")):
        return "", limpiar_url(unquote(resto))

    try:
        partes = urlsplit(uri)
    except ValueError:
        return "", ""

    accion = (partes.netloc or "").strip().lower()
    if accion and "." in accion:
        # El "netloc" es en realidad un dominio: markos://youtube.com/...
        posible = unquote(uri[len("markos://"):])
        return "", limpiar_url(posible)

    parametros = parse_qs(partes.query or "")
    url = ""
    for clave in ("url", "u", "link", "enlace"):
        valores = parametros.get(clave)
        if valores:
            url = unquote(valores[0]).strip()
            break

    if not url and partes.path:
        posible = unquote(partes.path).lstrip("/")
        if posible.lower().startswith(("http://", "https://")):
            url = posible
        elif "." in posible and "/" not in posible:
            url = "https://" + posible

    if accion not in ("add", "download", "capture", "capturar", "descargar"):
        accion = "add" if url else accion

    return accion, limpiar_url(url)


__all__ = [
    "calidad_para_url",
    "dominio_de_url",
    "extraer_urls",
    "leer_urls_de_archivo",
    "limpiar_url",
    "normalizar_dominio",
    "parsear_markos",
]
