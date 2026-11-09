"""
ui/history_page.py
====================================================================
Pestana Historial: consulta las descargas guardadas en SQLite.

Incluye buscador, filtro por estado, estadisticas, reintento de
enlaces fallidos, apertura del archivo/carpeta y borrado de entradas.
La pagina solo presenta datos y emite senales; la ventana principal
decide cuando confirmar un borrado o lanzar una descarga.
====================================================================
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.history import ESTADOS, Historial, formatear_tamano
from ui.theme import ROJO, ROJO_CLARO, TEXTO_DIM, VERDE
from ui.pages import CabeceraPagina

_ETIQUETAS_ESTADO = {
    "pendiente": "… Pendiente",
    "descargando": "↓ Descargando",
    "completada": "✓ Completada",
    "error": "✕ Error",
    "cancelada": "— Cancelada",
}

_COLORES_ESTADO = {
    "pendiente": "#FFB020",
    "descargando": "#FFB020",
    "completada": VERDE,
    "error": "#FF6B6B",
    "cancelada": TEXTO_DIM,
}


class TarjetaResumen(QFrame):
    """Tarjeta compacta para las cifras del historial."""

    def __init__(self, titulo: str, destacada: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumHeight(74)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(1)

        etiqueta = QLabel(titulo.upper())
        etiqueta.setObjectName("CardTitle")
        self.valor = QLabel("0")
        self.valor.setObjectName("StatValueRed" if destacada else "StatValue")
        self.valor.setStyleSheet(
            (
                f"color: {ROJO};" if destacada else "color: #FFFFFF;"
            )
            + " font-size: 22px; font-weight: 800;"
        )
        self.detalle = QLabel("")
        self.detalle.setObjectName("Hint")
        layout.addWidget(etiqueta)
        layout.addWidget(self.valor)
        layout.addWidget(self.detalle)

    def set_valor(self, valor: str, detalle: str = "") -> None:
        self.valor.setText(str(valor))
        self.detalle.setText(detalle)


class PaginaHistorial(QWidget):
    """Historial persistente con busqueda, filtros y acciones."""

    reintentar_solicitado = Signal(list)  # [(url, calidad), ...]
    eliminar_solicitado = Signal(list)    # [id, ...]

    def __init__(self, historial: Historial, parent=None) -> None:
        super().__init__(parent)
        self.historial = historial
        self._filas: dict[int, dict] = {}
        self._temporizador = QTimer(self)
        self._temporizador.setSingleShot(True)
        self._temporizador.setInterval(250)
        self._temporizador.timeout.connect(self.refrescar)
        self._construir()
        self.refrescar()

    # ------------------------------------------------------------------
    def _construir(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 14, 26, 12)
        raiz.setSpacing(10)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(16)
        cabecera.addWidget(
            CabeceraPagina(
                "Historial",
                "Consulta todo lo descargado, reintenta enlaces fallidos y "
                "abre los archivos sin buscar manualmente en DESCARGAS.",
            ),
            1,
        )
        self.boton_actualizar = QPushButton("Actualizar")
        self.boton_actualizar.setObjectName("Ghost")
        self.boton_actualizar.setFixedSize(108, 36)
        self.boton_actualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_actualizar.clicked.connect(self.refrescar)
        cabecera.addWidget(
            self.boton_actualizar, 0, Qt.AlignmentFlag.AlignTop
        )
        raiz.addLayout(cabecera)

        # ----- Estadisticas -----
        resumen = QHBoxLayout()
        resumen.setSpacing(10)
        self.tarjeta_total = TarjetaResumen("Descargas", destacada=True)
        self.tarjeta_ok = TarjetaResumen("Completadas")
        self.tarjeta_error = TarjetaResumen("Errores")
        self.tarjeta_tamano = TarjetaResumen("Tamaño total")
        for tarjeta in (
            self.tarjeta_total,
            self.tarjeta_ok,
            self.tarjeta_error,
            self.tarjeta_tamano,
        ):
            resumen.addWidget(tarjeta)
        raiz.addLayout(resumen)

        # ----- Filtros -----
        filtros = QHBoxLayout()
        filtros.setSpacing(8)
        self.busqueda = QLineEdit()
        self.busqueda.setPlaceholderText(
            "Buscar por título, canal, archivo o URL…"
        )
        self.busqueda.setClearButtonEnabled(True)
        self.busqueda.textChanged.connect(
            lambda _texto: self._temporizador.start()
        )

        self.filtro_estado = QComboBox()
        self.filtro_estado.addItem("Todos los estados", "")
        for estado in ESTADOS:
            self.filtro_estado.addItem(_ETIQUETAS_ESTADO.get(estado, estado), estado)
        self.filtro_estado.currentIndexChanged.connect(self.refrescar)

        self.boton_reintentar = QPushButton("Reintentar")
        self.boton_reintentar.setObjectName("Primary")
        self.boton_reintentar.setFixedSize(112, 34)
        self.boton_reintentar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_reintentar.setToolTip(
            "Vuelve a descargar las filas seleccionadas con su calidad original."
        )
        self.boton_reintentar.clicked.connect(self._reintentar)

        self.boton_eliminar = QPushButton("Eliminar")
        self.boton_eliminar.setObjectName("Ghost")
        self.boton_eliminar.setFixedSize(100, 34)
        self.boton_eliminar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_eliminar.setToolTip("Borra las filas seleccionadas del historial.")
        self.boton_eliminar.clicked.connect(self._eliminar)

        filtros.addWidget(self.busqueda, 1)
        filtros.addWidget(self.filtro_estado)
        filtros.addWidget(self.boton_reintentar)
        filtros.addWidget(self.boton_eliminar)
        raiz.addLayout(filtros)

        # ----- Tabla -----
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ("FECHA", "ESTADO", "CALIDAD", "TÍTULO / ARCHIVO", "TAMAÑO", "URL")
        )
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabla.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.setWordWrap(False)
        self.tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabla.customContextMenuRequested.connect(self._menu_contextual)
        self.tabla.doubleClicked.connect(lambda _i: self._abrir_archivo())
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones)

        cabecera_tabla = self.tabla.horizontalHeader()
        cabecera_tabla.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        cabecera_tabla.setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        cabecera_tabla.setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )

        raiz.addWidget(self.tabla, 1)

        pie = QHBoxLayout()
        self.lbl_resumen = QLabel("Sin descargas registradas todavía.")
        self.lbl_resumen.setObjectName("Hint")
        self.lbl_resumen.setWordWrap(True)
        self.boton_abrir_archivo = QPushButton("Abrir archivo")
        self.boton_abrir_archivo.setObjectName("Ghost")
        self.boton_abrir_archivo.setFixedWidth(116)
        self.boton_abrir_archivo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_abrir_archivo.clicked.connect(self._abrir_archivo)
        self.boton_abrir_carpeta = QPushButton("Abrir carpeta")
        self.boton_abrir_carpeta.setObjectName("Ghost")
        self.boton_abrir_carpeta.setFixedWidth(120)
        self.boton_abrir_carpeta.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_abrir_carpeta.clicked.connect(self._abrir_carpeta)
        pie.addWidget(self.lbl_resumen, 1)
        pie.addWidget(self.boton_abrir_archivo)
        pie.addWidget(self.boton_abrir_carpeta)
        raiz.addLayout(pie)

        self._actualizar_botones()

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    def refrescar(self) -> None:
        busqueda = self.busqueda.text().strip()
        estado = str(self.filtro_estado.currentData() or "")
        filas = self.historial.listar(busqueda=busqueda, estado=estado, limite=500)
        self._filas = {int(fila["id"]): fila for fila in filas}
        self._llenar_tabla(filas)
        self._actualizar_estadisticas()
        self._actualizar_botones()

        stats = self.historial.estadisticas()
        if not stats["total"]:
            self.lbl_resumen.setText(
                "Sin descargas registradas todavía. Las próximas descargas "
                "aparecerán aquí automáticamente."
            )
        elif filas:
            self.lbl_resumen.setText(
                f"Mostrando {len(filas)} de {stats['total']} descarga(s)."
            )
        else:
            self.lbl_resumen.setText(
                "Ningún resultado coincide con el filtro actual."
            )

    def _llenar_tabla(self, filas: list[dict]) -> None:
        self.tabla.setUpdatesEnabled(False)
        self.tabla.setRowCount(0)
        self.tabla.setRowCount(len(filas))
        fuente_mono = QFont("Consolas")
        fuente_mono.setPointSize(9)

        for fila_idx, fila in enumerate(filas):
            id_descarga = int(fila.get("id") or 0)
            estado = str(fila.get("estado") or "pendiente")
            calidad = str(fila.get("calidad") or "max")
            titulo = str(fila.get("titulo") or "").strip()
            archivo = str(fila.get("archivo") or "").strip()
            url = str(fila.get("url") or "")
            tamano = int(fila.get("tamano") or 0)
            creado = str(fila.get("creado") or "")

            if not titulo and archivo:
                titulo = Path(archivo).stem
            if not titulo:
                titulo = "(pendiente de descarga)"

            valores = (
                self._formatear_fecha(creado),
                _ETIQUETAS_ESTADO.get(estado, estado.title()),
                calidad.upper(),
                titulo + (f"  ·  {Path(archivo).name}" if archivo else ""),
                formatear_tamano(tamano),
                url,
            )
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                item.setData(Qt.ItemDataRole.UserRole, id_descarga)
                if columna == 1:
                    item.setForeground(QColor(_COLORES_ESTADO.get(estado, "#F5F5F5")))
                if columna in (0, 2, 4):
                    item.setFont(fuente_mono)
                if columna == 5:
                    item.setToolTip(url)
                if columna == 3 and archivo:
                    item.setToolTip(archivo)
                self.tabla.setItem(fila_idx, columna, item)

        self.tabla.setUpdatesEnabled(True)

    def _actualizar_estadisticas(self) -> None:
        stats = self.historial.estadisticas()
        self.tarjeta_total.set_valor(
            str(stats["total"]), f"{stats['hoy']} hoy"
        )
        self.tarjeta_ok.set_valor(
            str(stats["completadas"]), "descargas correctas"
        )
        self.tarjeta_error.set_valor(
            str(stats["errores"]), f"{stats['pendientes']} pendientes"
        )
        self.tarjeta_tamano.set_valor(
            formatear_tamano(stats["bytes"]), "en disco"
        )

    @staticmethod
    def _formatear_fecha(iso: str) -> str:
        if not iso:
            return "—"
        try:
            fecha = datetime.fromisoformat(iso)
            return fecha.strftime("%d/%m/%y %H:%M")
        except ValueError:
            return iso[:16]

    # ------------------------------------------------------------------
    # Seleccion y acciones
    # ------------------------------------------------------------------
    def _ids_seleccionados(self) -> list[int]:
        ids: list[int] = []
        for indice in self.tabla.selectionModel().selectedRows():
            item = self.tabla.item(indice.row(), 0)
            if item is None:
                continue
            id_descarga = int(item.data(Qt.ItemDataRole.UserRole) or 0)
            if id_descarga and id_descarga not in ids:
                ids.append(id_descarga)
        return ids

    def _fila_seleccionada(self) -> dict | None:
        ids = self._ids_seleccionados()
        if not ids:
            return None
        return self._filas.get(ids[0])

    def _actualizar_botones(self) -> None:
        hay = bool(self._ids_seleccionados())
        self.boton_reintentar.setEnabled(hay)
        self.boton_eliminar.setEnabled(hay)
        self.boton_abrir_archivo.setEnabled(hay)
        self.boton_abrir_carpeta.setEnabled(hay)

    def _reintentar(self) -> None:
        ids = self._ids_seleccionados()
        if not ids:
            return
        datos: list[tuple[str, str]] = []
        for id_descarga in ids:
            fila = self._filas.get(id_descarga)
            if not fila:
                continue
            url = str(fila.get("url") or "").strip()
            if not url:
                continue
            calidad = str(fila.get("calidad") or "max")
            datos.append((url, calidad))
        if datos:
            self.reintentar_solicitado.emit(datos)

    def _eliminar(self) -> None:
        ids = self._ids_seleccionados()
        if ids:
            self.eliminar_solicitado.emit(ids)

    def _abrir_archivo(self) -> None:
        fila = self._fila_seleccionada()
        if not fila:
            return
        archivo = str(fila.get("archivo") or "").strip()
        if not archivo:
            QMessageBox.information(
                self,
                "Sin archivo",
                "Esta descarga no tiene un archivo asociado (pendiente, "
                "cancelada o fallida).",
            )
            return
        ruta = Path(archivo)
        if not ruta.is_file():
            QMessageBox.warning(
                self,
                "Archivo no encontrado",
                "El archivo ya no está en disco:\n\n"
                f"{ruta}\n\n"
                "Puedes reintentar la descarga o abrir la carpeta.",
            )
            return
        try:
            os.startfile(str(ruta))  # type: ignore[attr-defined]
        except OSError as exc:
            QMessageBox.warning(
                self,
                "No se pudo abrir",
                f"No se pudo abrir:\n{ruta}\n\n{exc}",
            )

    def _abrir_carpeta(self) -> None:
        fila = self._fila_seleccionada()
        if not fila:
            return
        archivo = str(fila.get("archivo") or "").strip()
        carpeta = None
        if archivo:
            ruta = Path(archivo)
            carpeta = ruta.parent if ruta.parent.is_dir() else None
        if carpeta is None:
            from utils.paths import dir_descargas

            carpeta = dir_descargas()
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            os.startfile(str(carpeta))  # type: ignore[attr-defined]
        except OSError as exc:
            QMessageBox.warning(
                self,
                "No se pudo abrir",
                f"No se pudo abrir:\n{carpeta}\n\n{exc}",
            )

    def _menu_contextual(self, posicion) -> None:
        if not self._ids_seleccionados():
            return
        menu = QMenu(self)
        accion_abrir = menu.addAction("Abrir archivo")
        accion_abrir.triggered.connect(self._abrir_archivo)
        accion_carpeta = menu.addAction("Abrir carpeta")
        accion_carpeta.triggered.connect(self._abrir_carpeta)
        menu.addSeparator()
        accion_reintentar = menu.addAction("Reintentar descarga")
        accion_reintentar.triggered.connect(self._reintentar)
        accion_eliminar = menu.addAction("Eliminar del historial")
        accion_eliminar.triggered.connect(self._eliminar)
        menu.exec(self.tabla.viewport().mapToGlobal(posicion))

    def seleccionar_por_estado(self, estado: str) -> None:
        """Utilidad para la ventana principal (errores / pendientes)."""
        indice = self.filtro_estado.findData(estado)
        if indice >= 0:
            self.filtro_estado.setCurrentIndex(indice)
            self.refrescar()


__all__ = ["PaginaHistorial"]
