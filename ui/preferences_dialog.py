"""
ui/preferences_dialog.py
====================================================================
Preferencias de segundo plano, integracion con Windows y
actualizaciones. Los cambios de registro se aplican en main_window
para poder avisar si Windows los rechaza.
====================================================================
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import ROJO, TEXTO_DIM
from utils.paths import APP_NAME, APP_VERSION, dir_appdata


class DialogoPreferencias(QDialog):
    """Casillas de bandeja, arranque, protocolo y actualizaciones."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        cerrar_a_bandeja: bool = False,
        iniciar_minimizado: bool = False,
        iniciar_con_windows: bool = False,
        protocolo_registrado: bool = True,
        auto_actualizaciones: bool = True,
        usar_perfiles: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferencias")
        self.setModal(True)
        self.setMinimumWidth(620)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(14)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(14)
        icono = QLabel("⚙")
        icono.setFixedWidth(38)
        icono.setAlignment(Qt.AlignmentFlag.AlignTop)
        icono.setStyleSheet(
            f"color: {ROJO}; font-size: 30px; font-weight: 900; "
            "background: transparent;"
        )
        textos = QVBoxLayout()
        textos.setSpacing(4)
        titulo = QLabel("Preferencias")
        titulo.setObjectName("DialogTitle")
        mensaje = QLabel(
            "Controla cómo se comporta la suite en segundo plano y cómo "
            "se integra con Windows."
        )
        mensaje.setObjectName("DialogText")
        mensaje.setWordWrap(True)
        textos.addWidget(titulo)
        textos.addWidget(mensaje)
        cabecera.addWidget(icono)
        cabecera.addLayout(textos, 1)
        raiz.addLayout(cabecera)

        # ----- Bandeja / arranque -----
        marco = QFrame()
        marco.setObjectName("Card")
        marco.setFrameShape(QFrame.Shape.NoFrame)
        mv = QVBoxLayout(marco)
        mv.setContentsMargins(16, 14, 16, 14)
        mv.setSpacing(10)
        etiqueta = QLabel("SEGUNDO PLANO")
        etiqueta.setObjectName("CardTitle")
        mv.addWidget(etiqueta)

        self.chk_bandeja = QCheckBox(
            "Cerrar la ventana a la bandeja y seguir capturando en segundo plano"
        )
        self.chk_bandeja.setChecked(bool(cerrar_a_bandeja))
        self.chk_bandeja.setCursor(Qt.CursorShape.PointingHandCursor)
        mv.addWidget(self.chk_bandeja)

        self.chk_minimizado = QCheckBox(
            "Al arrancar con Windows, iniciar minimizado en la bandeja"
        )
        self.chk_minimizado.setChecked(bool(iniciar_minimizado))
        self.chk_minimizado.setCursor(Qt.CursorShape.PointingHandCursor)
        mv.addWidget(self.chk_minimizado)

        self.chk_windows = QCheckBox("Iniciar MarkOS automáticamente con Windows")
        self.chk_windows.setChecked(bool(iniciar_con_windows))
        self.chk_windows.setCursor(Qt.CursorShape.PointingHandCursor)
        mv.addWidget(self.chk_windows)
        raiz.addWidget(marco)

        # ----- Integracion -----
        marco2 = QFrame()
        marco2.setObjectName("Card")
        marco2.setFrameShape(QFrame.Shape.NoFrame)
        mv2 = QVBoxLayout(marco2)
        mv2.setContentsMargins(16, 14, 16, 14)
        mv2.setSpacing(10)
        etiqueta2 = QLabel("INTEGRACIÓN")
        etiqueta2.setObjectName("CardTitle")
        mv2.addWidget(etiqueta2)

        self.chk_protocolo = QCheckBox(
            "Registrar enlaces markos:// (enviar URLs desde el navegador)"
        )
        self.chk_protocolo.setChecked(bool(protocolo_registrado))
        self.chk_protocolo.setCursor(Qt.CursorShape.PointingHandCursor)
        mv2.addWidget(self.chk_protocolo)

        self.chk_perfiles = QCheckBox(
            "Usar perfiles de calidad por sitio en las descargas"
        )
        self.chk_perfiles.setChecked(bool(usar_perfiles))
        self.chk_perfiles.setCursor(Qt.CursorShape.PointingHandCursor)
        mv2.addWidget(self.chk_perfiles)

        self.chk_actualizaciones = QCheckBox(
            "Buscar actualizaciones de MarkOS automáticamente (1 vez al día)"
        )
        self.chk_actualizaciones.setChecked(bool(auto_actualizaciones))
        self.chk_actualizaciones.setCursor(Qt.CursorShape.PointingHandCursor)
        mv2.addWidget(self.chk_actualizaciones)
        raiz.addWidget(marco2)

        ayuda = QLabel(
            f"{APP_NAME} v{APP_VERSION}\n"
            "El protocolo markos:// se registra en tu usuario de Windows "
            f"(HKCU), sin permisos de administrador.\nDatos: {dir_appdata()}"
        )
        ayuda.setObjectName("Hint")
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet(f"color: {TEXTO_DIM};")
        raiz.addWidget(ayuda)

        pie = QHBoxLayout()
        pie.setSpacing(10)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.setObjectName("Ghost")
        boton_cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_cancelar.clicked.connect(self.reject)
        boton_guardar = QPushButton("Guardar preferencias")
        boton_guardar.setObjectName("Primary")
        boton_guardar.setMinimumWidth(180)
        boton_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_guardar.setDefault(True)
        boton_guardar.clicked.connect(self.accept)
        pie.addStretch(1)
        pie.addWidget(boton_cancelar)
        pie.addWidget(boton_guardar)
        raiz.addLayout(pie)

    # ------------------------------------------------------------------
    def valores(self) -> dict[str, bool]:
        return {
            "cerrar_a_bandeja": self.chk_bandeja.isChecked(),
            "iniciar_minimizado": self.chk_minimizado.isChecked(),
            "iniciar_con_windows": self.chk_windows.isChecked(),
            "protocolo_registrado": self.chk_protocolo.isChecked(),
            "usar_perfiles": self.chk_perfiles.isChecked(),
            "auto_buscar_actualizaciones": self.chk_actualizaciones.isChecked(),
        }


__all__ = ["DialogoPreferencias"]
