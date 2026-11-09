"""
utils/assets_embedded.py
====================================================================
ARCHIVO GENERADO AUTOMATICAMENTE por tools/build_assets.py.
No lo edites a mano: modifica assets/ y vuelve a ejecutar:
    python tools/build_assets.py
====================================================================
"""

# Banner ASCII de MarkOS (assets/banner.txt)
BANNER = "  __  __            _       ____   _____\n |  \\/  |          | |     / __ \\ / ____|\n | \\  / | __ _ _ __| | __ | |  | | (___\n | |\\/| |/ _` | '__| |/ / | |  | |\\___ \\\n | |  | | (_| | |  |   <  | |__| |____) |\n |_|  |_|\\__,_|_|  |_|\\_\\  \\____/|_____/\n\n        MarkOS Downloader Suite\n"

# Instrucciones que se copian a %APPDATA% (assets/instrucciones.txt)
INSTRUCCIONES = '====================================================================\n MarkOS Downloader Suite - Instrucciones\n====================================================================\n\nA) USO DE LA APLICACION YA COMPILADA (.exe)\n--------------------------------------------------------------------\n1. Ejecuta "MarkOS Downloader Suite.exe".\n2. La ventana se organiza como un asistente de 3 pasos. Arriba tienes\n   las pestanas Interceptor / Descargador / Historial y abajo los botones\n   "Atras" y "Siguiente paso" (o Ctrl+Izquierda / Ctrl+Derecha).\n3. Pestana Interceptor:\n   - Pulsa "Iniciar captura" (o Ctrl+I).\n   - Copia enlaces http:// o https:// desde el navegador.\n   - Cada enlace se guarda en:\n       Desktop\\Descargador casero\\enlaces.txt\n   - Pulsa ESC (global) o el boton "Detener" para terminar.\n     ESC abre ademas la carpeta de trabajo.\n   - Al detenerse aparece "Captura finalizada": elige MP3, 480p, 720p,\n     1080p o Maxima y pulsa "Descargar ahora" para empezar sin cambiar\n     de pestana. Con "Ahora no" los enlaces quedan guardados.\n   - Al iniciar una nueva captura el archivo enlaces.txt se vacia,\n     igual que en el script original. La app te avisa antes.\n   - "Limpiar enlaces" vacia enlaces.txt y reinicia los contadores.\n     Debe usarse con el interceptor detenido.\n   - Puedes arrastrar URLs o un archivo .txt a la ventana para anadirlos.\n4. Pestana Descargador:\n   - Elige la calidad (MP3, 480p, 720p, 1080p o Maxima).\n   - Pulsa "Descargar" (o Ctrl+D).\n   - "Pausar" (Ctrl+Espacio) detiene la cola al acabar el enlace actual.\n   - "Perfiles" asigna una calidad distinta a cada sitio (por dominio).\n   - Los archivos van a Desktop\\Descargador casero\\DESCARGAS.\n   - El log muestra el progreso y los errores en tiempo real.\n   - Al terminar, la app pregunta si quieres abrir la carpeta DESCARGAS.\n5. Pestana Historial:\n   - Guarda cada descarga en %APPDATA%\\MarkOS_Downloader\\historial.db.\n   - Busca, filtra por estado y consulta tamanos y errores.\n   - "Reintentar" vuelve a descargar con la calidad original de la fila.\n   - "Abrir archivo" y "Abrir carpeta" localizan lo descargado.\n   - Si la app se cierra a medias, la cola pendiente se restaura al\n     arrancar en enlaces.txt.\n6. Preferencias (menu ... > Preferencias o Ctrl+,):\n   - Cerrar a la bandeja y seguir capturando en segundo plano.\n   - Iniciar con Windows (minimizado si lo deseas).\n   - Registrar el protocolo markos:// para enviar enlaces desde el\n     navegador: markos://add?url=... / markos://capture.\n   - Buscar actualizaciones de MarkOS automaticamente en cada arranque.\n7. Actualizar dependencias (boton "Actualizar" de la barra superior):\n   - Descarga la ultima version de yt-dlp y, si lo marcas, FFmpeg.\n   - Se guarda en %APPDATA%\\MarkOS_Downloader\\bin y tiene prioridad\n     sobre los binarios incluidos en el EXE (no hay que recompilar).\n   - "Restaurar incluidos" borra esa copia y vuelve a los del EXE.\n8. Actualizaciones de MarkOS (menu ... > Buscar actualizaciones):\n   - Consulta las releases de GitHub del repositorio del proyecto.\n   - Si hay un .exe nuevo, lo descarga y lo instala al cerrar la app.\n   - Si la release no trae .exe, abre la pagina para descargarla a mano.\n   - "Ignorar esta version" evita avisos de esa etiqueta concreta.\n9. Atajos: Ctrl+I interceptor, Ctrl+D descargar, Ctrl+Espacio pausar,\n   Ctrl+H historial, Ctrl+, preferencias, Ctrl+U actualizaciones,\n   Ctrl+Izquierda/Derecha cambiar de paso, Ctrl+Q salir.\n\nB) REQUISITOS PARA EJECUTAR DESDE EL CODIGO FUENTE\n--------------------------------------------------------------------\nPython 3.11 o 3.12 (NO 3.13, por compatibilidad con PyInstaller).\n\n    pip install -r requirements.txt\n\nDependencias principales:\n  - yt-dlp      : motor de descargas (se incluye yt-dlp.exe en /bin)\n  - instaloader : opcional, util para Instagram desde otros scripts\n  - pyperclip   : lectura del portapapeles\n  - keyboard    : atajo global ESC\n  - PySide6     : interfaz grafica Qt6\n\nC) DEPENDENCIAS EXTERNAS RECOMENDADAS (una sola vez)\n--------------------------------------------------------------------\nFFmpeg (fusionar audio+video y convertir a MP3):\n\n    winget install Gyan.FFmpeg\n\nDeno (algunos sitios lo usan para resolver firmas de YouTube):\n\n    winget install Denoland.Deno\n\nExtractor de JavaScript @yt-dlp/ejs (requiere Node.js/npm):\n\n    npm install -g @yt-dlp/ejs\n\nActualizar yt-dlp cuando un sitio deje de funcionar:\n   - Lo mas rapido: boton "Actualizar" dentro de la app (yt-dlp).\n   - Desde el codigo fuente tambien puedes usar:\n       pip install --upgrade yt-dlp\n   - El actualizador nunca modifica el EXE: deja los binarios nuevos en\n     %APPDATA%\\MarkOS_Downloader\\bin.\n\nCookies para contenido con inicio de sesion:\n  - Extension recomendada: "Get cookies.txt LOCALLY".\n  - Sin cookies, algunos videos privados o con verificacion fallan.\n\nD) COMPILAR EL .EXE\n--------------------------------------------------------------------\n1. Ejecuta build.bat (crea .venv, instala dependencias y descarga\n   yt-dlp.exe / ffmpeg.exe / ffprobe.exe en bin\\).\n2. El resultado queda en:\n       dist\\MarkOS Downloader Suite.exe\n3. Para compilar sin FFmpeg (EXE mas pequeno):\n       build.bat noffmpeg\n\nE) SOLUCION DE PROBLEMAS\n--------------------------------------------------------------------\n- "No se pudo leer el portapapeles": otra app lo bloquea; se reintenta.\n- ESC no funciona: ejecuta la app con permisos de administrador.\n- Windows SmartScreen: el EXE no esta firmado; usa "Mas informacion >\n  Ejecutar de todas formas" solo si confias en el archivo.\n- Antivirus: los EXE onefile a veces dan falsos positivos. Agrega una\n  exclusion para la carpeta dist.\n- Descargas que fallan: actualiza yt-dlp y prueba con cookies.\n- Descarga lenta o bloqueada: usa Pausar/Reanudar en el Descargador.\n- Si el EXE no arranca, revisa app.log y prueba a lanzarlo de nuevo;\n  la app no depende del boton de panico ni de procesos externos.\n\nRuta de configuracion, historial y log:\n    %APPDATA%\\MarkOS_Downloader\\config.json\n    %APPDATA%\\MarkOS_Downloader\\historial.db\n    %APPDATA%\\MarkOS_Downloader\\app.log\n'

# Icono 256x256 en PNG codificado en base64 (assets/icon.png)
ICONO_PNG_B64 = (
    "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"
)
