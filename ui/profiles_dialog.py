"""
ui/profiles_dialog.py
====================================================================
Editor de perfiles de calidad por sitio.

Cada fila asocia un dominio (youtube.com, instagram.com…) con una
calidad. El descargador aplica el perfil mas especifico a cada enlace
y usa la calidad global cuando no hay coincidencia.
====================================================================
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.downloader import CALIDADES
from ui.theme import ROJO
from utils.paths import dir_appdata
from utils.urls import normalizar_dominio


class DialogoPerfiles(QDialog):
    """Tabla de dominios -> calidad con validacion al guardar."""

    def __init__(
        self,
        parent: QWidget | None,
        perfiles: dict[str, str] | None = None,
        activo: bool = True,
    ) -> None:
        super().__init__(parent)
        self._perfiles = dict(perfiles or {})
        self._resultado: dict[str, str] = {}

        self.setWindowTitle("Perfiles por sitio")
        self.setModal(True)
        self.setMinimumSize(660, 500)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(12)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(14)
        icono = QLabel("◎")
        icono.setFixedWidth(38)
        icono.setAlignment(Qt.AlignmentFlag.AlignTop)
        icono.setStyleSheet(
            f"color: {ROJO}; font-size: 32px; font-weight: 900; "
            "background: transparent;"
        )
        textos = QVBoxLayout()
        textos.setSpacing(5)
        titulo = QLabel("Perfiles por sitio")
        titulo.setObjectName("DialogTitle")
        mensaje = QLabel(
            "Asigna una calidad distinta a cada dominio. Si un enlace no "
            "coincide con ningún perfil se usará la calidad global del "
            "Descargador. Los subdominios heredan el perfil del dominio."
        )
        mensaje.setObjectName("DialogText")
        mensaje.setWordWrap(True)
        textos.addWidget(titulo)
        textos.addWidget(mensaje)
        cabecera.addWidget(icono)
        cabecera.addLayout(textos, 1)
        raiz.addLayout(cabecera)

        self.chk_activo = QCheckBox("Aplicar perfiles por sitio a las descargas")
        self.chk_activo.setChecked(bool(activo))
        self.chk_activo.setCursor(Qt.CursorShape.PointingHandCursor)
        raiz.addWidget(self.chk_activo)

        marco = QFrame()
        marco.setObjectName("Card")
        marco.setFrameShape(QFrame.Shape.NoFrame)
        mv = QVBoxLayout(marco)
        mv.setContentsMargins(14, 12, 14, 12)
        mv.setSpacing(8)

        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(("DOMINIO", "CALIDAD"))
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabla.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabla.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self.tabla.setColumnWidth(1, 190)
        mv.addWidget(self.tabla, 1)

        botones_tabla = QHBoxLayout()
        botones_tabla.setSpacing(8)
        self.boton_anadir = QPushButton("+ Añadir dominio")
        self.boton_anadir.setObjectName("Ghost")
        self.boton_anadir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_anadir.clicked.connect(lambda: self._anadir_fila("", "max"))
        self.boton_quitar = QPushButton("Quitar seleccionado")
        self.boton_quitar.setObjectName("Ghost")
        self.boton_quitar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_quitar.clicked.connect(self._quitar_fila)
        botones_tabla.addWidget(self.boton_anadir)
        botones_tabla.addWidget(self.boton_quitar)
        botones_tabla.addStretch(1)
        mv.addLayout(botones_tabla)

        raiz.addWidget(marco, 1)

        ayuda = QLabel(
            "Ejemplos: youtube.com → 1080p · music.youtube.com → mp3 · "
            "instagram.com → máx · tiktok.com → 720p.\n"
            f"Los perfiles se guardan en {dir_appdata() / 'config.json'}"
        )
        ayuda.setObjectName("Hint")
        ayuda.setWordWrap(True)
        raiz.addWidget(ayuda)

        pie = QHBoxLayout()
        pie.setSpacing(10)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.setObjectName("Ghost")
        boton_cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_cancelar.clicked.connect(self.reject)
        boton_guardar = QPushButton("Guardar perfiles")
        boton_guardar.setObjectName("Primary")
        boton_guardar.setMinimumWidth(170)
        boton_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_guardar.setDefault(True)
        boton_guardar.clicked.connect(self._guardar)
        pie.addStretch(1)
        pie.addWidget(boton_cancelar)
        pie.addWidget(boton_guardar)
        raiz.addLayout(pie)

        for dominio, calidad in sorted(self._perfiles.items()):
            self._anadir_fila(dominio, calidad)
        if not self._perfiles:
            self._anadir_fila("youtube.com", "1080p")
            self._anadir_fila("instagram.com", "max")

    # ------------------------------------------------------------------
    def _anadir_fila(self, dominio: str, calidad: str) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        item = QTableWidgetItem(dominio)
        item.setToolTip(
            "Escribe solo el dominio (youtube.com), no la URL completa."
        )
        self.tabla.setItem(fila, 0, item)

        combo = QComboBox()
        for clave, datos in CALIDADES.items():
            combo.addItem(datos["etiqueta"], clave)
        indice = combo.findData(calidad if calidad in CALIDADES else "max")
        combo.setCurrentIndex(max(0, indice))
        self.tabla.setCellWidget(fila, 1, combo)

    def _quitar_fila(self) -> None:
        fila = self.tabla.currentRow()
        if fila >= 0:
            self.tabla.removeRow(fila)

    def _guardar(self) -> None:
        resultado: dict[str, str] = {}
        errores: list[str] = []
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 0)
            combo = self.tabla.cellWidget(fila, 1)
            dominio_crudo = item.text().strip() if item is not None else ""
            if not dominio_crudo:
                continue
            dominio = normalizar_dominio(dominio_crudo)
            if not dominio or "." not in dominio:
                errores.append(f"Fila {fila + 1}: dominio no válido «{dominio_crudo}».")
                continue
            calidad = (
                str(combo.currentData()) if isinstance(combo, QComboBox) else "max"
            )
            if calidad not in CALIDADES:
                calidad = "max"
            if dominio in resultado:
                errores.append(f"Fila {fila + 1}: «{dominio}» está repetido.")
                continue
            resultado[dominio] = calidad

        if errores:
            QMessageBox.warning(
                self,
                "Revisa los perfiles",
                "\n".join(errores[:8])
                + ("\n…" if len(errores) > 8 else ""),
            )
            return

        self._resultado = resultado
        self.accept()

    # ------------------------------------------------------------------
    def perfiles(self) -> dict[str, str]:
        return dict(self._resultado)

    def activo(self) -> bool:
        return self.chk_activo.isChecked()


__all__ = ["DialogoPerfiles"]
