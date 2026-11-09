"""
utils/settings.py
====================================================================
Persistencia de preferencias en JSON:

    %APPDATA%/MarkOS_Downloader/config.json

Escritura atomica (tmp + replace) y recuperacion automatica si el
archivo se corrompe. Guarda la calidad, la geometria, los perfiles por
sitio, las preferencias de bandeja y el estado del actualizador.
====================================================================
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from utils.paths import archivo_config
from utils.urls import normalizar_dominio

_log = logging.getLogger("markos.settings")

CALIDADES_VALIDAS = ("mp3", "480p", "720p", "1080p", "max")

_CLAVES_BOOL = (
    "primera_ejecucion",
    "usar_perfiles",
    "cerrar_a_bandeja",
    "iniciar_minimizado",
    "iniciar_con_windows",
    "auto_buscar_actualizaciones",
    "protocolo_registrado",
)


class Configuracion:
    """Configuracion sencilla tipo clave/valor con guardado inmediato."""

    POR_DEFECTO: dict[str, Any] = {
        "calidad": "max",
        "geometria": "",
        "pestana": 0,
        "primera_ejecucion": True,
        # Perfiles por dominio: {"youtube.com": "1080p", ...}
        "perfiles": {},
        "usar_perfiles": True,
        # Bandeja / segundo plano
        "cerrar_a_bandeja": False,
        "iniciar_minimizado": False,
        "iniciar_con_windows": False,
        # Actualizaciones de la aplicacion
        "auto_buscar_actualizaciones": True,
        "ultima_busqueda_actualizacion": "",
        "version_ignorada": "",
        # Protocolo markos:// (se registra en HKCU al arrancar el EXE)
        "protocolo_registrado": True,
    }

    def __init__(self, ruta: Path | None = None) -> None:
        self.ruta = ruta or archivo_config()
        self.datos: dict[str, Any] = dict(self.POR_DEFECTO)
        self.cargar()

    # ------------------------------------------------------------------
    def cargar(self) -> None:
        """Carga el JSON; si falla, conserva los valores por defecto."""
        if not self.ruta.is_file():
            return
        try:
            with self.ruta.open("r", encoding="utf-8") as f:
                cargado = json.load(f)
            if isinstance(cargado, dict):
                # Solo aceptamos claves conocidas y tipos correctos.
                for clave, defecto in self.POR_DEFECTO.items():
                    if clave not in cargado:
                        continue
                    valor = cargado[clave]
                    if isinstance(defecto, bool):
                        if isinstance(valor, bool):
                            self.datos[clave] = valor
                    elif isinstance(valor, type(defecto)):
                        self.datos[clave] = valor
                self._sanear()
        except (OSError, ValueError, TypeError) as exc:
            _log.warning("Configuracion ilegible (%s); se usan valores por defecto", exc)
            self._respaldar_corrupto()

    def _sanear(self) -> None:
        """Normaliza tipos y limpia valores invalidos sin perder el resto."""
        if self.datos.get("calidad") not in CALIDADES_VALIDAS:
            self.datos["calidad"] = "max"

        try:
            pestana = int(self.datos.get("pestana", 0) or 0)
        except (TypeError, ValueError):
            pestana = 0
        self.datos["pestana"] = max(0, min(2, pestana))

        for clave in _CLAVES_BOOL:
            if not isinstance(self.datos.get(clave), bool):
                self.datos[clave] = bool(self.POR_DEFECTO[clave])

        perfiles = self.datos.get("perfiles")
        limpios: dict[str, str] = {}
        if isinstance(perfiles, dict):
            for dominio, calidad in perfiles.items():
                if not isinstance(dominio, str) or not isinstance(calidad, str):
                    continue
                clave = normalizar_dominio(dominio)
                if clave and calidad in CALIDADES_VALIDAS:
                    limpios[clave] = calidad
        self.datos["perfiles"] = limpios

        for clave in (
            "geometria",
            "ultima_busqueda_actualizacion",
            "version_ignorada",
        ):
            if not isinstance(self.datos.get(clave), str):
                self.datos[clave] = str(self.POR_DEFECTO[clave])

    def _respaldar_corrupto(self) -> None:
        """Renombra el JSON invalido para no perder informacion del usuario."""
        try:
            if self.ruta.exists():
                self.ruta.replace(self.ruta.with_suffix(".json.bak"))
        except OSError:
            pass

    # ------------------------------------------------------------------
    def get(self, clave: str, defecto: Any = None) -> Any:
        return self.datos.get(clave, self.POR_DEFECTO.get(clave, defecto))

    def set(self, clave: str, valor: Any) -> None:
        self.datos[clave] = valor
        self.guardar()

    def actualizar(self, valores: dict[str, Any]) -> None:
        """Guarda varias claves con una sola escritura atomica."""
        self.datos.update(valores)
        self.guardar()

    # ------------------------------------------------------------------
    def guardar(self) -> None:
        """Escritura atomica para evitar JSON a medias si se corta la luz."""
        tmp = self.ruta.with_suffix(".json.tmp")
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self.datos, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.ruta)
        except OSError as exc:
            _log.error("No se pudo guardar la configuracion: %s", exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
