# MarkOS Downloader Suite

Aplicación de escritorio para Windows 10/11 que unifica en una sola GUI
(PySide6/Qt6) el interceptor de portapapeles, el descargador de yt-dlp y
un historial persistente de descargas.

- Interfaz rojo/negro (`#E50914`, `#C1121F`, `#0D0D0D`, `#1A1A1A`, `#2B2B2B`, `#F5F5F5`).
- **Asistente de 3 pasos** sin panel lateral: Interceptor → Descargador →
  Historial, con stepper superior y botones **Atrás / Siguiente paso**.
- **Historial SQLite** con búsqueda, filtros, estadísticas, reintentos y
  apertura de archivos/carpetas.
- **Cola con pausa y reintento**; cada enlace conserva su calidad original.
- **Perfiles de calidad por sitio/dominio** (YouTube, Instagram, TikTok…).
- **Bandeja del sistema**, cierre a segundo plano, inicio con Windows y
  protocolo `markos://`.
- **Arrastrar y soltar** URLs o archivos `.txt`.
- **Actualizador de dependencias** integrado (yt-dlp y FFmpeg) sin
  recompilar el EXE.
- **Actualizaciones de la app** vinculadas a las releases de GitHub.
- **Limpiar enlaces** desde la página del interceptor.
- Hilos Qt independientes para portapapeles y descargas: la ventana nunca se congela.
- Flujo guiado: al detener la captura puedes **elegir la calidad y descargar al instante**; al terminar, la app **pregunta si quieres abrir la carpeta**.
- Un solo `.exe` (`--onefile --windowed`) con yt-dlp embebido.
- Rutas idénticas a los scripts originales:
  - `Desktop\Descargador casero\enlaces.txt`
  - `Desktop\Descargador casero\DESCARGAS`

**Versión actual: V1.7.**

### Novedades V1.7

- **Historial persistente** en `%APPDATA%\MarkOS_Downloader\historial.db`,
  con reintento usando la calidad original de cada fila.
- **Cola pausable** (`Ctrl+Espacio`) y restauración de pendientes al arrancar.
- **Perfiles por dominio** y preferencias de bandeja/arranque/protocolo.
- **`markos://`** (`add`, `download`, `capture`) y `--minimized`.
- **Drag & drop** de enlaces y archivos de texto.
- **Comprobación automática de releases en cada arranque**, con aviso para
  descargar la nueva versión dentro de la propia app.
- **Se retiró el botón de pánico**: la app ya no necesita matar procesos
  externos para recuperarse; el Historial ocupa su lugar en el asistente.

---

## 1. Estructura

```
MarkOS-Downloader-Suite/
├─ main.py                     # Punto de entrada
├─ core/
│  ├─ __init__.py
│  ├─ interceptor.py           # QThread + pyperclip + keyboard
│  ├─ downloader.py            # QThread + yt-dlp (subprocess)
│  ├─ history.py               # SQLite: cola, estados y estadísticas
│  ├─ updates.py               # releases de GitHub + instalador del EXE
│  ├─ updater.py               # QThread: descarga yt-dlp / FFmpeg
├─ ui/
│  ├─ __init__.py
│  ├─ main_window.py           # Stepper, stack, navegación, atajos, bandeja
│  ├─ pages.py                 # Interceptor / Descargador
│  ├─ history_page.py          # Tabla, filtros y acciones del historial
│  ├─ profiles_dialog.py       # Perfiles de calidad por dominio
│  ├─ preferences_dialog.py    # Bandeja, arranque, protocolo y updates
│  ├─ update_dialog.py         # Releases, notas y descarga del EXE
│  ├─ dialogs.py               # Confirmación, calidad post-captura,
│  │                           # resultado con "Abrir carpeta", etc.
│  ├─ updater_dialog.py        # Progreso y registro del actualizador
│  └─ theme.py                 # Paleta y QSS
├─ utils/
│  ├─ __init__.py
│  ├─ paths.py                 # Rutas y sys._MEIPASS
│  ├─ urls.py                  # Extracción, dominios y markos://
│  ├─ integration.py           # HKCU: markos:// e inicio con Windows
│  ├─ settings.py              # config.json atómico
│  ├─ logger.py                # app.log rotativo
│  ├─ resources.py             # banner/instrucciones/icono
│  ├─ assets_embedded.py       # GENERADO: assets en base64/texto
│  └─ sound.py                 # winsound.Beep seguro
├─ assets/
│  ├─ banner.txt
│  ├─ instrucciones.txt
│  ├─ icon.ico                 # generado
│  └─ icon.png                 # generado
├─ bin/                        # yt-dlp.exe, ffmpeg.exe, ffprobe.exe
├─ tools/
│  ├─ make_icon.py             # .ico/.png sin Pillow
│  ├─ build_assets.py          # incrusta assets en Python
│  └─ descargar_binarios.py    # descarga yt-dlp/ffmpeg oficiales
├─ tests/
│  ├─ smoke_test.py            # GUI, rutas, interceptor, persistencia
│  └─ download_test.py         # descarga real contra un servidor local
├─ MarkOS_Downloader.spec      # PyInstaller onefile
├─ build.bat
├─ requirements.txt
├─ README.md
├─ LICENSE                     # MIT
└─ .gitignore
```

---

## 2. Requisitos

- **Windows 10/11 (64 bits).**
- **Python 3.11 o 3.12** (no 3.13: PyInstaller puede fallar).
- Conexión a Internet solo para compilar (descarga de dependencias y binarios).
- El EXE final no requiere Python, yt-dlp ni FFmpeg instalados.

Dependencias fijadas (`requirements.txt`):

```text
PySide6==6.12.0
pyperclip==1.11.0
keyboard==0.13.5
yt-dlp==2026.10.26
pyinstaller==6.22.3
```

---

## 3. Ejecutar desde el código fuente

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python tools\descargar_binarios.py
python tools\make_icon.py
python tools\build_assets.py
python main.py
```

Si `bin\yt-dlp.exe` no existe, `utils.paths.get_ytdlp_path()` usa
`yt-dlp` del PATH **solo en desarrollo**. En el EXE congelado se aceptan,
por este orden:

1. `%APPDATA%\MarkOS_Downloader\bin\yt-dlp.exe` (actualizador integrado),
2. `sys._MEIPASS\bin\yt-dlp.exe` (incluido en el EXE),
3. PATH **solo en desarrollo**.

Lo mismo se aplica a `ffmpeg.exe` y `ffprobe.exe`.

---

## 4. Compilar el EXE

```bat
build.bat
```

Hace todo:

1. Detecta Python 3.11/3.12 y crea `.venv`.
2. Instala `requirements.txt`.
3. Descarga `bin\yt-dlp.exe` y FFmpeg essentials (`ffmpeg.exe` + `ffprobe.exe`).
4. Genera icono y assets incrustados.
5. Ejecuta PyInstaller con el `.spec` (`--onefile`, sin consola).

Resultado:

```text
dist\MarkOS Downloader Suite.exe
```

Para un EXE más pequeño, sin FFmpeg (no habrá MP3 ni fusión MP4):

```bat
build.bat noffmpeg
```

El `.spec` respeta la variable `MARKOS_SIN_FFMPEG=1` y no empaqueta
`ffmpeg.exe`/`ffprobe.exe` aunque existan en `bin`.

### Tamaño medido

Compilado con PyInstaller 6.22.3 en Windows 11 (Python 3.12.0):

| Build | Tamaño real |
|---|---|
| Sin FFmpeg (`build.bat noffmpeg`) | **49,1 MB** (51.529.940 bytes) |
| Con FFmpeg + ffprobe (`build.bat`) | **122,9 MB** (128.873.954 bytes) |

El `.spec` filtra DLLs y plugins de Qt que el hook de PySide6 arrastra
aunque no se usen (`Qt6Network`, `Qt6Quick`, `opengl32sw`, traducciones,
plugins de imagen…), lo que ahorra ~20 MB. También se excluyen
`tkinter`, `tests`, `numpy`, `matplotlib`, `PIL`, etc.
`INCLUIR_MODULO_YT_DLP = False` evita duplicar el motor (el binario ya
viaja en `bin/yt-dlp.exe`). Si activas esa opción en el `.spec`, el EXE
crece ~15 MB.

### Pruebas

Con el entorno virtual activo:

```bat
.venv\Scripts\python.exe tests\smoke_test.py
.venv\Scripts\python.exe tests\download_test.py
```

- `smoke_test.py`: valida argumentos de yt-dlp, las 3 páginas,
  navegación Atrás/Siguiente, persistencia de calidad,
  captura/deduplicado con una carpeta temporal, prioridad de los binarios
  actualizados, botón de limpiar enlaces, diálogo del actualizador,
  historial SQLite, perfiles por dominio, protocolo `markos://`,
  comparación de versiones, maquetación estable en 720p,
  icono/instrucciones y cierre limpio.
  **No descarga ni mata procesos.**
- `download_test.py`: genera un MP4 local, lo sirve por HTTP y ejecuta un
  `DownloadThread` real con `bin\yt-dlp.exe`; comprueba progreso, archivo
  final y log. Tarda unos segundos y no usa Internet.

---

## 5. Uso

### Navegación

La app funciona como un asistente de tres pasos:

- **Stepper superior** con las pestañas Interceptor / Descargador / Historial.
- **Línea de progreso** que avanza con el paso actual.
- Botones **← Atrás** y **Siguiente paso →** abajo (en el último paso, el
  botón se desactiva y muestra "Último paso").
- Atajos `Ctrl+←` y `Ctrl+→`.
- Menú **⋯** para perfiles, preferencias, actualizaciones, instrucciones,
  Acerca de, abrir la carpeta de datos y salir.
- La ventana admite desde **900×640**. Si la pantalla es más baja, cada
  página se desplaza en vertical en lugar de comprimir o solapar tarjetas.
- Se pueden **arrastrar URLs o archivos `.txt`** sobre la ventana.

### Interceptor

1. Pestaña **Interceptor** → **Iniciar captura** (`Ctrl+I`).
2. Copia URLs `http://` o `https://`. Cada una se añade a `enlaces.txt`
   y suena un beep.
3. Pulsa **Detener captura** (o **ESC** global).

Al detenerse aparece el diálogo **Captura finalizada**:

- muestra cuántos enlaces se capturaron;
- permite elegir **MP3, 480p, 720p, 1080p o Máxima**;
- con **Descargar ahora** salta a la pestaña Descargador y comienza la
  descarga con la calidad elegida;
- con **Ahora no**, los enlaces quedan guardados en `enlaces.txt`;
- **Abrir** abre la carpeta de trabajo. ESC también la abre, igual que
  el comportamiento original.

> Igual que el script original, al iniciar se **vacía** `enlaces.txt`.
> La app pide confirmación si había enlaces en cola.
>
> Solo se evitan duplicados consecutivos (`last_url`), comportamiento
> idéntico al original.

El botón **Limpiar enlaces** vacía `enlaces.txt` y reinicia los contadores
de la sesión. Pide confirmación y se bloquea mientras el interceptor está
activo.

### Actualizador de dependencias

El botón **↻ Actualizar** de la barra superior abre un diálogo donde
puedes marcar:

- **yt-dlp.exe** (recomendado, descarga pequeña);
- **FFmpeg + ffprobe** (necesario para MP3 y fusión MP4, ~100 MB).

La descarga corre en segundo plano (`UpdaterThread`) y se puede cancelar
cerrando el diálogo. Los binarios se guardan en
`%APPDATA%\MarkOS_Downloader\bin` y tienen prioridad sobre los incluidos
en el EXE, así que la actualización se aplica sin recompilar ni reinstalar.

**Restaurar incluidos** elimina esa copia y vuelve a los binarios
empaquetados.

### Descargador

1. Pestaña **Descargador**.
2. Elige MP3, 480p, 720p, 1080p o Máxima (`Ctrl+D` para descargar).
3. El log muestra `[download] %` y los errores de yt-dlp en vivo.
4. Al terminar, notificación de Windows, resumen en la barra de estado y
   el diálogo **Descargas completadas**, que pregunta de forma explícita
   si quieres **abrir la carpeta DESCARGAS**.

Los argumentos de calidad son los del script original, más flags
técnicos (`--newline`, `--no-colors`, `--encoding utf-8`) y
`--ffmpeg-location` cuando FFmpeg viaja dentro del EXE.

### Historial

1. Pestaña **Historial** (`Ctrl+H`).
2. Cada enlace genera una fila con estado, calidad, título/archivo, tamaño
   y URL. Los datos viven en
   `%APPDATA%\MarkOS_Downloader\historial.db`.
3. Buscador y filtro por estado (`pendiente`, `descargando`, `completada`,
   `error`, `cancelada`).
4. **Reintentar** relanza las filas seleccionadas con su calidad original;
   **Eliminar** borra entradas sin tocar los archivos del disco.
5. **Abrir archivo** y **Abrir carpeta** localizan la descarga.
6. Si la app se cierra a medias, los pendientes se vuelven a escribir en
   `enlaces.txt` al arrancar (sin diálogos).

### Perfiles y preferencias

- **Perfiles por sitio** (`⋯ → Perfiles por sitio` o botón **Perfiles**):
  asigna una calidad a cada dominio (`youtube.com → 1080p`,
  `music.youtube.com → mp3`…). El subdominio hereda el perfil más
  específico; si no hay coincidencia se usa la calidad global.
- **Preferencias** (`Ctrl+,`):
  - cerrar la ventana a la bandeja y seguir capturando en segundo plano;
  - iniciar con Windows, opcionalmente minimizado;
  - registrar `markos://` (enlaces desde el navegador);
  - activar/desactivar perfiles;
  - comprobar actualizaciones automáticamente en cada arranque.

### Actualizaciones de la app

`⋯ → Buscar actualizaciones…` (`Ctrl+U`) consulta la última release de
GitHub del repositorio. Si hay una versión nueva:

- con asset `.exe`, lo descarga con progreso y, al cerrar, lo instala y
  reinicia MarkOS;
- sin asset `.exe`, abre la página de la release para descargarla a mano;
- **Ignorar esta versión** evita avisos futuros de esa etiqueta.

### Atajos

| Atajo | Acción |
|---|---|
| `Ctrl+I` | Iniciar/detener interceptor |
| `Ctrl+D` | Descargar |
| `Ctrl+Espacio` | Pausar/reanudar la cola |
| `Ctrl+H` | Historial |
| `Ctrl+,` | Preferencias |
| `Ctrl+U` | Buscar actualizaciones |
| `Ctrl+←` / `Ctrl+→` | Paso anterior / siguiente |
| `Ctrl+Q` | Salir |

---

## 6. Arquitectura y señales

```
main.py
  └─ VentanaPrincipal (ui/main_window.py)
       ├─ InterceptorThread (QThread)
       │    enlace_capturado(str,int)
       │    estado_cambiado(bool,str)
       │    aviso(str) / error(str)
       │    solicitud_abrir_carpeta()
       │    finalizado()
       ├─ DownloadThread (QThread)
       │    log(str)
       │    progreso(int)          # 0..100 global
       │    item_actual(int,int,str)
       │    item_resultado(dict)
       │    pausado(bool)
       │    finalizado(bool,str)
       ├─ Historial (SQLite)
       │    anadir_pendientes / actualizar / listar / estadisticas
       ├─ UpdaterThread (QThread)
       │    progreso(int,str)
       │    log(str)
       │    finalizado(bool,str)
       └─ ComprobacionThread (QThread)
            resultado(ResultadoActualizacion)
```

- El interceptor se detiene con `threading.Event` + `keyboard.unhook_all()`.
- El descargador cancela con `taskkill /F /T /PID` para matar también
  los procesos ffmpeg hijos.
- La pausa se aplica entre enlaces: el actual termina antes de detener la cola.
- La UI solo se actualiza mediante señales Qt (conexiones en cola entre
  hilos), nunca desde el hilo de trabajo.
- `DialogoPostCaptura` recibe la cantidad de enlaces y la última calidad;
  `DialogoDescargaFinalizada` devuelve `Accepted` cuando el usuario quiere
  abrir `DESCARGAS`. Ambos son modales y se abren desde el hilo de la GUI.
- `main.py` interpreta `markos://` y `--minimized`, y sincroniza el
  protocolo y el inicio con Windows en `HKCU`.

---

## 7. Persistencia, log y notificaciones

- Configuración: `%APPDATA%\MarkOS_Downloader\config.json`
  - última calidad, geometría, pestaña activa, perfiles, preferencias,
    versión ignorada y fecha de la última comprobación.
- Historial: `%APPDATA%\MarkOS_Downloader\historial.db`
  - una fila por enlace con estado, archivo, tamaño y fechas.
- Actualizaciones: `%APPDATA%\MarkOS_Downloader\updates\`
  - EXE descargado y script temporal de instalación.
- Log rotativo: `%APPDATA%\MarkOS_Downloader\app.log`
  - 1 MB × 3 archivos.
- Instrucciones: `%APPDATA%\MarkOS_Downloader\Instrucciones.txt`
  (se abre desde la app y desde el diálogo de dependencias).
- Notificaciones: `QSystemTrayIcon.showMessage()` al terminar descargas.
- Diálogo final: resumen, ruta de `DESCARGAS` y botón **Abrir carpeta**.

---

## 8. Manejo de errores

- Portapapeles bloqueado → aviso en la UI como máximo cada 15 s y reintento.
- `keyboard` sin permisos → aviso; el botón Detener sigue funcionando.
- yt-dlp ausente → diálogo con instrucciones al arrancar.
- FFmpeg ausente → aviso + confirmación antes de descargar.
- Fallo de yt-dlp → código de salida y últimas líneas `ERROR` en el log.
- Excepciones globales → `sys.excepthook` + `threading.excepthook`
  escriben en `app.log`; al usuario se le muestra un mensaje sin traceback.
- Todos los `subprocess` usan `CREATE_NO_WINDOW`.

---

## 9. Notas de empaquetado

- `binaries=[('bin/yt-dlp.exe','bin'), ...]` → accesibles como
  `Path(sys._MEIPASS)/"bin"` en el EXE.
- `utils.paths.get_ytdlp_path()` centraliza la resolución y **nunca**
  usa el PATH cuando `sys.frozen` es verdadero.
- `datas=[]`: banner, instrucciones e icono PNG están incrustados en
  `utils/assets_embedded.py`; `assets/icon.ico` solo se usa en tiempo de
  compilación para el icono del EXE.
- `console=False`, `upx=False`, `disable_windowed_traceback=True`.
- Se excluyen módulos pesados y Qt no usados (ver `.spec`).

---

## 10. Solución de problemas

| Problema | Solución |
|---|---|
| ESC no responde | Ejecuta como administrador (hook global de Windows). |
| Portapapeles no se lee | Cierra apps que lo bloqueen (gestores de contraseñas). |
| MP3/MP4 sin audio | Falta FFmpeg: recompila sin `noffmpeg` o instala `winget install Gyan.FFmpeg`. |
| SmartScreen bloquea | EXE sin firmar: *Más información → Ejecutar de todas formas*. |
| Antivirus falso positivo | Excluye `dist\`; no se usa UPX para reducir este riesgo. |
| yt-dlp falla en un sitio | Actualiza `bin\yt-dlp.exe` o usa cookies (`Get cookies.txt LOCALLY`). |
| PyInstaller falla | Usa Python 3.11/3.12, borra `build\` y `.venv`, reintenta. |
| El EXE no abre | Revisa `%APPDATA%\MarkOS_Downloader\app.log`. |

---

## 11. Diferencias conscientes con los scripts originales

1. **ESC ya no cierra la app** (`os._exit`), solo detiene el interceptor y
   abre la carpeta, tal como exige la GUI (iniciar/detener sin cerrar).
2. **Se retiró el botón de pánico.** La app ya no mata procesos externos
   con `taskkill /F /IM`: el Historial ocupa ese paso del asistente y el
   descargador cancela solo sus propios procesos. `taskkill` se sigue
   usando internamente con `/F /T /PID` para el enlace en curso.
3. **Se añaden flags técnicos** a yt-dlp para progreso legible y ruta
   explícita a FFmpeg; la selección de calidad no cambia.
4. **Se vacía `enlaces.txt` al iniciar el interceptor**, igual que el
   original, pero con confirmación previa si había enlaces.
5. **Flujo guiado nuevo**: al detener la captura se ofrece elegir calidad
   y descargar; al terminar se pregunta si abrir la carpeta. No cambia
   ningún argumento de descarga ni el formato de `enlaces.txt`.
6. **Ruta del Escritorio**: se usa `~/Desktop` y, solo si no existe, el
   `Desktop` de OneDrive (equipos Windows 11 con cuenta Microsoft).

---

## 12. Licencia

MIT © 2026 Markbn115. Consulta el archivo [`LICENSE`](LICENSE).

Este proyecto reutiliza la lógica de los scripts originales de MarkOS
(`interceptor_links.py` y `Descargador_yt.py`). El antiguo botón de pánico
se retiró de la interfaz.
