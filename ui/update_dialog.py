"""
ui/update_dialog.py
====================================================================
Dialogo del sistema de actualizacion de la aplicacion.

Muestra la ultima release de GitHub, sus notas, los assets disponibles
y permite descargar el .exe e instalarlo al cerrar la app. Si la
release no trae ejecutable, ofrece abrir la pagina para descargarla a
mano. Tambien permite ignorar una version concreta.
====================================================================
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.updates import (
    DescargaActualizacionThread,
    ResultadoActualizacion,
    URL_RELEASES,
    puede_autoinstalar,
)
from ui.theme import ROJO, ROJO_CLARO, VERDE
from utils.paths import APP_NAME, APP_VERSION


class DialogoActualizacion(QDialog):
    """Resultado de la comprobacion + descarga/instalacion del EXE."""

    def __init__(
        self,
        parent: QWidget | None,
        resultado: ResultadoActualizacion,
        version_ignorada: str = "",
        auto_descargar: bool = False,
    ) -> None:
        super().__init__(parent)
        self.resultado = resultado
        self.version_ignorada = version_ignorada
        self.ignorada = False
        self.ruta_instalacion = ""
        self._auto_descargar = bool(auto_descargar)
        self._hilo: DescargaActualizacionThread | None = None

        self.setWindowTitle("Actualizaciones de MarkOS")
        self.setModal(True)
        self.setMinimumSize(700, 560)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(12)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(14)
        self.icono = QLabel("↻")
        self.icono.setFixedWidth(38)
        self.icono.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.icono.setStyleSheet(
            f"color: {ROJO}; font-size: 32px; font-weight: 900; "
            "background: transparent;"
        )
        textos = QVBoxLayout()
        textos.setSpacing(5)
        self.titulo = QLabel("Actualizaciones")
        self.titulo.setObjectName("DialogTitle")
        self.mensaje = QLabel("")
        self.mensaje.setObjectName("DialogText")
        self.mensaje.setWordWrap(True)
        textos.addWidget(self.titulo)
        textos.addWidget(self.mensaje)
        cabecera.addWidget(self.icono)
        cabecera.addLayout(textos, 1)
        raiz.addLayout(cabecera)

        # ----- Tarjeta de versiones -----
        marco = QFrame()
        marco.setObjectName("Card")
        marco.setFrameShape(QFrame.Shape.NoFrame)
        mv = QVBoxLayout(marco)
        mv.setContentsMargins(16, 12, 16, 12)
        mv.setSpacing(5)
        etiqueta = QLabel("VERSIONES")
        etiqueta.setObjectName("CardTitle")
        self.lbl_versiones = QLabel("")
        self.lbl_versiones.setObjectName("PathLabel")
        self.lbl_versiones.setWordWrap(True)
        self.lbl_versiones.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        mv.addWidget(etiqueta)
        mv.addWidget(self.lbl_versiones)
        raiz.addWidget(marco)

        # ----- Notas -----
        self.lbl_notas = QLabel("NOTAS DE LA RELEASE")
        self.lbl_notas.setObjectName("SectionLabel")
        raiz.addWidget(self.lbl_notas)

        self.notas = QPlainTextEdit()
        self.notas.setObjectName("Log")
        self.notas.setReadOnly(True)
        self.notas.setMaximumBlockCount(2000)
        self.notas.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.notas.setMinimumHeight(130)
        self.notas.setPlaceholderText("Esta release no incluye notas.")
        raiz.addWidget(self.notas, 1)

        # ----- Assets -----
        self.lbl_assets = QLabel("")
        self.lbl_assets.setObjectName("Hint")
        self.lbl_assets.setWordWrap(True)
        raiz.addWidget(self.lbl_assets)

        # ----- Progreso -----
        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setTextVisible(False)
        self.barra.setVisible(False)
        raiz.addWidget(self.barra)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setObjectName("Hint")
        self.lbl_estado.setWordWrap(True)
        raiz.addWidget(self.lbl_estado)

        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(80)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log.setMaximumHeight(78)
        self.log.setVisible(False)
        raiz.addWidget(self.log)

        # ----- Botones -----
        botones = QHBoxLayout()
        botones.setSpacing(10)
        self.boton_ignorar = QPushButton("Ignorar esta versión")
        self.boton_ignorar.setObjectName("Ghost")
        self.boton_ignorar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_ignorar.clicked.connect(self._ignorar)

        self.boton_pagina = QPushButton("Abrir página de la release")
        self.boton_pagina.setObjectName("Ghost")
        self.boton_pagina.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_pagina.clicked.connect(self._abrir_pagina)

        self.boton_cerrar = QPushButton("Cerrar")
        self.boton_cerrar.setObjectName("Ghost")
        self.boton_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_cerrar.clicked.connect(self.reject)

        self.boton_instalar = QPushButton("Descargar e instalar")
        self.boton_instalar.setObjectName("Primary")
        self.boton_instalar.setMinimumWidth(180)
        self.boton_instalar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_instalar.setDefault(True)
        self.boton_instalar.clicked.connect(self._iniciar_descarga)

        botones.addWidget(self.boton_ignorar)
        botones.addWidget(self.boton_pagina)
        botones.addStretch(1)
        botones.addWidget(self.boton_cerrar)
        botones.addWidget(self.boton_instalar)
        raiz.addLayout(botones)

        self._pintar_resultado()
        if self._auto_descargar and self.resultado.hay_nueva:
            if self.resultado.activo_exe is not None:
                QTimer.singleShot(0, self._iniciar_descarga)

    # ------------------------------------------------------------------
    def _pintar_resultado(self) -> None:
        resultado = self.resultado
        if not resultado.ok or resultado.release is None:
            self.titulo.setText("No se pudo comprobar")
            self.mensaje.setText(
                resultado.error
                or "No se pudo consultar la última release de GitHub."
            )
            self.lbl_versiones.setText(
                f"Versión instalada: {APP_VERSION}\n"
                f"Repositorio: {URL_RELEASES}"
            )
            self.lbl_notas.setVisible(False)
            self.notas.setVisible(False)
            self.boton_ignorar.setVisible(False)
            self.boton_instalar.setVisible(False)
            self.boton_pagina.setText("Abrir página de releases")
            return

        release = resultado.release
        activo = resultado.activo_exe
        ignorada = bool(
            self.version_ignorada
            and self.version_ignorada.strip().lower()
            == release.tag.strip().lower()
        )
        self.lbl_versiones.setText(
            f"Instalada: {APP_VERSION}\n"
            f"Última publicada: {release.tag or 'sin etiqueta'} "
            f"· {release.nombre}\n"
            f"Publicada: {self._fecha(release.publicado)}\n"
            f"Repositorio: {URL_RELEASES}"
        )
        self.notas.setPlainText(release.notas or "Esta release no incluye notas.")

        if release.assets:
            nombres = ", ".join(a.nombre for a in release.assets[:6])
            if len(release.assets) > 6:
                nombres += "…"
            self.lbl_assets.setText(f"Archivos publicados: {nombres}")
        else:
            self.lbl_assets.setText("Esta release no adjunta archivos.")

        if resultado.hay_nueva:
            self.titulo.setText("Hay una versión nueva disponible")
            if ignorada:
                self.mensaje.setText(
                    f"La versión {release.tag} está marcada como ignorada. "
                    "Puedes instalarla igualmente o dejar de ignorarla."
                )
                self.boton_ignorar.setText("Dejar de ignorar")
            else:
                self.mensaje.setText(
                    f"MarkOS {release.tag} ya está publicado. Estás usando "
                    f"la versión {APP_VERSION}."
                )
            self.boton_ignorar.setVisible(True)
            self.boton_instalar.setVisible(True)
            if activo is not None:
                if puede_autoinstalar():
                    self.boton_instalar.setText("Descargar e instalar")
                    self.boton_instalar.setToolTip(
                        "Descarga el nuevo EXE, lo instala al cerrar y vuelve a abrir MarkOS."
                    )
                else:
                    self.boton_instalar.setText("Descargar actualización")
                    self.boton_instalar.setToolTip(
                        "En modo desarrollo se descarga el EXE sin reemplazar la app."
                    )
                self.lbl_estado.setText(
                    f"Asset seleccionado: {activo.nombre}"
                )
            else:
                self.boton_instalar.setVisible(False)
                self.boton_pagina.setText("Abrir página y descargar")
                self.lbl_estado.setText(
                    "Esta release no incluye un archivo .exe. Ábrela en el "
                    "navegador para descargar el paquete manualmente."
                )
        else:
            self.titulo.setText("Estás al día")
            self.mensaje.setText(
                f"MarkOS {APP_VERSION} es la versión más reciente publicada "
                "en el repositorio."
            )
            self.boton_ignorar.setVisible(False)
            self.boton_instalar.setVisible(False)
            self.boton_pagina.setText("Abrir página de releases")

    @staticmethod
    def _fecha(iso: str) -> str:
        if not iso:
            return "fecha desconocida"
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime(
                "%d/%m/%Y %H:%M"
            )
        except ValueError:
            return iso[:16]

    # ------------------------------------------------------------------
    def _abrir_pagina(self) -> None:
        release = self.resultado.release
        url = release.pagina if release else URL_RELEASES
        QDesktopServices.openUrl(QUrl(url))

    def _ignorar(self) -> None:
        release = self.resultado.release
        if release is None:
            return
        if (
            self.version_ignorada
            and self.version_ignorada.strip().lower()
            == release.tag.strip().lower()
        ):
            self.version_ignorada = ""
            self.ignorada = False
            self.boton_ignorar.setText("Ignorar esta versión")
            self.mensaje.setText(
                f"La versión {release.tag} ya no está ignorada."
            )
            self.lbl_estado.setText("Se volverá a avisar de esta versión.")
            self.accept()
            return
        self.ignorada = True
        self.version_ignorada = release.tag
        self.accept()

    def _iniciar_descarga(self) -> None:
        activo = self.resultado.activo_exe
        if activo is None:
            self._abrir_pagina()
            return
        if self._hilo is not None and self._hilo.isRunning():
            return

        self.barra.setVisible(True)
        self.log.setVisible(True)
        self.barra.setValue(0)
        self.log.clear()
        self.lbl_estado.setStyleSheet("")
        self.lbl_estado.setText("Iniciando descarga…")
        self._habilitar(False)

        hilo = DescargaActualizacionThread(activo, self)
        hilo.progreso.connect(self._al_progreso)
        hilo.log.connect(self._al_log)
        hilo.finalizado.connect(self._al_finalizar)
        self._hilo = hilo
        hilo.start()

    def _habilitar(self, habilitado: bool) -> None:
        self.boton_instalar.setEnabled(habilitado)
        self.boton_pagina.setEnabled(habilitado)
        self.boton_ignorar.setEnabled(habilitado)
        self.boton_cerrar.setEnabled(habilitado)

    def _al_progreso(self, porcentaje: int, texto: str) -> None:
        self.barra.setValue(max(0, min(100, int(porcentaje))))
        if texto:
            self.lbl_estado.setText(texto)

    def _al_log(self, texto: str) -> None:
        self.log.appendPlainText(texto)
        barra = self.log.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _al_finalizar(self, exito: bool, ruta: str, error: str) -> None:
        hilo = self._hilo
        if hilo is not None:
            hilo.wait(1500)
        self._hilo = None
        self._habilitar(True)

        if not exito:
            self.barra.setVisible(False)
            self.lbl_estado.setStyleSheet(f"color: {ROJO_CLARO};")
            self.lbl_estado.setText(error or "No se pudo descargar la actualización.")
            return

        self.barra.setValue(100)
        self.lbl_estado.setStyleSheet(f"color: {VERDE};")
        if puede_autoinstalar():
            self.lbl_estado.setText(
                "Actualización descargada. MarkOS se cerrará, instalará la "
                "nueva versión y volverá a abrirse."
            )
            self.ruta_instalacion = ruta
            QMessageBox.information(
                self,
                "Actualización lista",
                "La nueva versión se descargó correctamente.\n\n"
                "Al cerrar este aviso, MarkOS se reiniciará para instalarla.",
            )
            self.accept()
        else:
            self.lbl_estado.setText(
                f"Descarga completada en:\n{ruta}\n\n"
                "La instalación automática solo está disponible en el EXE."
            )
            QMessageBox.information(
                self,
                "Actualización descargada",
                "El ejecutable se descargó correctamente:\n\n"
                f"{ruta}\n\n"
                "En modo desarrollo no se reemplaza la aplicación.",
            )

    # ------------------------------------------------------------------
    def reject(self) -> None:  # noqa: D401
        if self._hilo is not None and self._hilo.isRunning():
            respuesta = QMessageBox.question(
                self,
                "Descarga en curso",
                "La actualización se está descargando. ¿Quieres cancelarla?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return
            self._hilo.detener()
            self._hilo.wait(5000)
            self._hilo = None
        super().reject()

    def closeEvent(self, evento) -> None:  # noqa: N802
        if self._hilo is not None and self._hilo.isRunning():
            respuesta = QMessageBox.question(
                self,
                "Descarga en curso",
                "La actualización se está descargando. ¿Quieres cancelarla?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                evento.ignore()
                return
            self._hilo.detener()
            self._hilo.wait(5000)
            self._hilo = None
        evento.accept()


__all__ = ["DialogoActualizacion"]
