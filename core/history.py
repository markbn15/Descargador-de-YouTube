"""
core/history.py
====================================================================
Historial persistente de descargas en SQLite.

Base de datos:
    %APPDATA%\\MarkOS_Downloader\\historial.db

Se guarda una fila por enlace con su estado (pendiente, completada,
error o cancelada), la calidad usada, el archivo resultante, su tamano
y las fechas de inicio/fin. La cola pendiente sobrevive al cierre de la
aplicacion y puede reanudarse desde la pestana Historial.

SQLite viene incluido con Python: no se anade ninguna dependencia.
Cada operacion abre y cierra su propia conexion, por lo que el modulo
es seguro para usarse desde la GUI y desde DownloadThread.
====================================================================
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from utils.paths import archivo_historial

_log = logging.getLogger("markos.history")

ESTADOS = ("pendiente", "descargando", "completada", "error", "cancelada")
_ESTADOS_FINALES = ("completada", "error", "cancelada")
_CAMPOS_ACTUALIZABLES = {
    "url",
    "titulo",
    "canal",
    "calidad",
    "estado",
    "archivo",
    "tamano",
    "duracion",
    "error",
    "origen",
    "iniciado",
    "terminado",
}

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS descargas (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    url       TEXT    NOT NULL,
    titulo    TEXT    NOT NULL DEFAULT '',
    canal     TEXT    NOT NULL DEFAULT '',
    calidad   TEXT    NOT NULL DEFAULT 'max',
    estado    TEXT    NOT NULL DEFAULT 'pendiente',
    archivo   TEXT    NOT NULL DEFAULT '',
    tamano    INTEGER NOT NULL DEFAULT 0,
    duracion  REAL    NOT NULL DEFAULT 0,
    error     TEXT    NOT NULL DEFAULT '',
    origen    TEXT    NOT NULL DEFAULT 'enlaces',
    creado    TEXT    NOT NULL,
    iniciado  TEXT,
    terminado TEXT
);
CREATE INDEX IF NOT EXISTS idx_descargas_creado ON descargas(creado DESC);
CREATE INDEX IF NOT EXISTS idx_descargas_estado ON descargas(estado);
CREATE INDEX IF NOT EXISTS idx_descargas_url ON descargas(url);
"""


def _ahora() -> str:
    """Marca temporal local en ISO 8601 (legible y ordenable)."""
    return datetime.now().isoformat(timespec="seconds")


def _fila_a_dict(fila: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(fila) if fila is not None else None


class Historial:
    """Acceso de alto nivel al historial de descargas."""

    def __init__(self, ruta: Path | None = None) -> None:
        self.ruta = ruta or archivo_historial()
        self._cerrojo = threading.Lock()
        self._inicializado = False

    # ------------------------------------------------------------------
    # Conexion / esquema
    # ------------------------------------------------------------------
    def _conectar(self) -> sqlite3.Connection:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        conexion = sqlite3.connect(str(self.ruta), timeout=20)
        conexion.row_factory = sqlite3.Row
        try:
            conexion.execute("PRAGMA busy_timeout = 20000")
            conexion.execute("PRAGMA journal_mode = WAL")
            conexion.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.DatabaseError:
            pass
        return conexion

    def _asegurar_esquema(self, conexion: sqlite3.Connection) -> None:
        if self._inicializado:
            return
        with self._cerrojo:
            if self._inicializado:
                return
            conexion.executescript(_ESQUEMA)
            conexion.commit()
            self._inicializado = True

    # ------------------------------------------------------------------
    # Insercion / cola
    # ------------------------------------------------------------------
    def anadir_pendiente(
        self,
        url: str,
        calidad: str = "max",
        origen: str = "enlaces",
        titulo: str = "",
    ) -> int | None:
        """Crea una fila pendiente y devuelve su id (o None si falla)."""
        if not url:
            return None
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                cursor = conexion.execute(
                    "INSERT INTO descargas "
                    "(url, titulo, calidad, estado, origen, creado) "
                    "VALUES (?, ?, ?, 'pendiente', ?, ?)",
                    (url, titulo, calidad, origen, _ahora()),
                )
                conexion.commit()
                return int(cursor.lastrowid)
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudo guardar el pendiente %s: %s", url, exc)
            return None

    def anadir_pendientes(
        self,
        urls: Sequence[str],
        calidades: str | dict[str, str] = "max",
        origen: str = "enlaces",
    ) -> list[int | None]:
        """Inserta varios pendientes en una sola transaccion."""
        if not urls:
            return []
        ids: list[int | None] = []
        marca = _ahora()
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                for url in urls:
                    if isinstance(calidades, dict):
                        calidad = calidades.get(url, "max")
                    else:
                        calidad = calidades
                    cursor = conexion.execute(
                        "INSERT INTO descargas "
                        "(url, calidad, estado, origen, creado) "
                        "VALUES (?, ?, 'pendiente', ?, ?)",
                        (url, calidad or "max", origen, marca),
                    )
                    ids.append(int(cursor.lastrowid))
                conexion.commit()
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudieron guardar los pendientes: %s", exc)
            return [None] * len(urls)
        return ids

    # ------------------------------------------------------------------
    # Cambios de estado
    # ------------------------------------------------------------------
    def actualizar(self, id_descarga: int | None, **campos: Any) -> None:
        """Actualiza los campos permitidos de una fila."""
        if id_descarga is None:
            return
        limpios = {k: v for k, v in campos.items() if k in _CAMPOS_ACTUALIZABLES}
        if not limpios:
            return
        asignaciones = ", ".join(f"{campo} = ?" for campo in limpios)
        valores = list(limpios.values()) + [int(id_descarga)]
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                conexion.execute(
                    f"UPDATE descargas SET {asignaciones} WHERE id = ?",
                    valores,
                )
                conexion.commit()
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudo actualizar la descarga %s: %s", id_descarga, exc)

    def marcar_descargando(self, id_descarga: int | None) -> None:
        self.actualizar(
            id_descarga,
            estado="descargando",
            iniciado=_ahora(),
            error="",
        )

    def marcar_completada(
        self,
        id_descarga: int | None,
        archivo: str = "",
        tamano: int = 0,
        titulo: str = "",
        calidad: str | None = None,
    ) -> None:
        campos: dict[str, Any] = {
            "estado": "completada",
            "archivo": archivo,
            "tamano": max(0, int(tamano or 0)),
            "terminado": _ahora(),
            "error": "",
        }
        if titulo:
            campos["titulo"] = titulo
        if calidad:
            campos["calidad"] = calidad
        self.actualizar(id_descarga, **campos)

    def marcar_error(
        self,
        id_descarga: int | None,
        error: str = "",
        calidad: str | None = None,
    ) -> None:
        campos: dict[str, Any] = {
            "estado": "error",
            "error": (error or "Error desconocido")[:2000],
            "terminado": _ahora(),
        }
        if calidad:
            campos["calidad"] = calidad
        self.actualizar(id_descarga, **campos)

    def marcar_cancelada(self, id_descarga: int | None, motivo: str = "") -> None:
        self.actualizar(
            id_descarga,
            estado="cancelada",
            error=(motivo or "Cancelada por el usuario")[:2000],
            terminado=_ahora(),
        )

    def marcar_pendientes_canceladas(self, motivo: str = "") -> int:
        """Cierra las filas que quedaron pendientes tras un cierre inesperado."""
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                cursor = conexion.execute(
                    "UPDATE descargas SET estado = 'cancelada', error = ?, "
                    "terminado = ? WHERE estado IN ('pendiente', 'descargando')",
                    (motivo or "Interrumpida", _ahora()),
                )
                conexion.commit()
                return cursor.rowcount
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudieron cancelar los pendientes: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def obtener(self, id_descarga: int) -> dict[str, Any] | None:
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                fila = conexion.execute(
                    "SELECT * FROM descargas WHERE id = ?", (int(id_descarga),)
                ).fetchone()
                return _fila_a_dict(fila)
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudo leer la descarga %s: %s", id_descarga, exc)
            return None

    def listar(
        self,
        busqueda: str = "",
        estado: str = "",
        limite: int = 500,
    ) -> list[dict[str, Any]]:
        """Devuelve las filas mas recientes, con busqueda y filtro de estado."""
        sql = "SELECT * FROM descargas"
        condiciones: list[str] = []
        valores: list[Any] = []

        if busqueda.strip():
            patron = f"%{busqueda.strip()}%"
            condiciones.append(
                "(url LIKE ? OR titulo LIKE ? OR archivo LIKE ? OR canal LIKE ?)"
            )
            valores.extend([patron, patron, patron, patron])
        if estado and estado in ESTADOS:
            condiciones.append("estado = ?")
            valores.append(estado)
        if condiciones:
            sql += " WHERE " + " AND ".join(condiciones)
        sql += " ORDER BY creado DESC, id DESC LIMIT ?"
        valores.append(max(1, min(5000, int(limite))))

        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                filas = conexion.execute(sql, valores).fetchall()
                return [dict(fila) for fila in filas]
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudo listar el historial: %s", exc)
            return []

    def pendientes(self, limite: int = 2000) -> list[dict[str, Any]]:
        """Filas que aun no se han procesado (para reanudar la cola)."""
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                filas = conexion.execute(
                    "SELECT * FROM descargas WHERE estado IN "
                    "('pendiente', 'descargando') ORDER BY id ASC LIMIT ?",
                    (max(1, int(limite)),),
                ).fetchall()
                return [dict(fila) for fila in filas]
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudo leer la cola pendiente: %s", exc)
            return []

    def contar(self, estado: str = "") -> int:
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                if estado and estado in ESTADOS:
                    fila = conexion.execute(
                        "SELECT COUNT(*) AS n FROM descargas WHERE estado = ?",
                        (estado,),
                    ).fetchone()
                else:
                    fila = conexion.execute(
                        "SELECT COUNT(*) AS n FROM descargas"
                    ).fetchone()
                return int(fila["n"]) if fila else 0
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudo contar el historial: %s", exc)
            return 0

    def estadisticas(self) -> dict[str, Any]:
        """Resumen para las tarjetas de la pestana Historial."""
        vacio = {
            "total": 0,
            "completadas": 0,
            "errores": 0,
            "pendientes": 0,
            "canceladas": 0,
            "bytes": 0,
            "hoy": 0,
            "ultima": "",
        }
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                fila = conexion.execute(
                    "SELECT "
                    "COUNT(*) AS total, "
                    "COALESCE(SUM(estado = 'completada'), 0) AS completadas, "
                    "COALESCE(SUM(estado = 'error'), 0) AS errores, "
                    "COALESCE(SUM(estado IN ('pendiente', 'descargando')), 0) "
                    "AS pendientes, "
                    "COALESCE(SUM(estado = 'cancelada'), 0) AS canceladas, "
                    "COALESCE(SUM(CASE WHEN estado = 'completada' THEN tamano "
                    "ELSE 0 END), 0) AS bytes, "
                    "COALESCE(SUM(date(creado) = date('now', 'localtime')), 0) "
                    "AS hoy, "
                    "COALESCE(MAX(CASE WHEN estado = 'completada' THEN terminado "
                    "END), '') AS ultima "
                    "FROM descargas"
                ).fetchone()
                if fila is None:
                    return vacio
                datos = dict(fila)
                for clave in (
                    "total",
                    "completadas",
                    "errores",
                    "pendientes",
                    "canceladas",
                    "bytes",
                    "hoy",
                ):
                    datos[clave] = int(datos.get(clave) or 0)
                datos["ultima"] = str(datos.get("ultima") or "")
                return datos
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudieron calcular las estadisticas: %s", exc)
            return vacio

    # ------------------------------------------------------------------
    # Borrado
    # ------------------------------------------------------------------
    def eliminar(self, ids: Iterable[int]) -> int:
        lista = [int(i) for i in ids if str(i).strip().isdigit()]
        if not lista:
            return 0
        marcadores = ",".join("?" for _ in lista)
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                cursor = conexion.execute(
                    f"DELETE FROM descargas WHERE id IN ({marcadores})", lista
                )
                conexion.commit()
                return cursor.rowcount
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudieron eliminar filas del historial: %s", exc)
            return 0

    def limpiar(self, solo_terminadas: bool = True) -> int:
        """Borra el historial (por defecto conserva los pendientes)."""
        try:
            with self._conectar() as conexion:
                self._asegurar_esquema(conexion)
                if solo_terminadas:
                    cursor = conexion.execute(
                        "DELETE FROM descargas WHERE estado IN "
                        "('completada', 'error', 'cancelada')"
                    )
                else:
                    cursor = conexion.execute("DELETE FROM descargas")
                conexion.commit()
                return cursor.rowcount
        except sqlite3.DatabaseError as exc:
            _log.warning("No se pudo limpiar el historial: %s", exc)
            return 0

    def cerrar(self) -> None:
        """Compatibilidad: no hay conexion persistente que cerrar."""
        return None


def formatear_tamano(bytes_: int | float) -> str:
    """Tamano legible (B, KB, MB, GB)."""
    try:
        valor = float(bytes_)
    except (TypeError, ValueError):
        return "—"
    if valor <= 0:
        return "—"
    unidades = ("B", "KB", "MB", "GB", "TB")
    indice = 0
    while valor >= 1024 and indice < len(unidades) - 1:
        valor /= 1024.0
        indice += 1
    if indice == 0:
        return f"{int(valor)} {unidades[indice]}"
    return f"{valor:.1f} {unidades[indice]}"


__all__ = [
    "ESTADOS",
    "Historial",
    "formatear_tamano",
]
