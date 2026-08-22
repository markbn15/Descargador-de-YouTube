import os
import subprocess
import sys

# Rutas dentro de 'Descargador casero'
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
folder_path = os.path.join(desktop_path, "Descargador casero")

links_file = os.path.join(folder_path, "enlaces.txt")
download_dir = os.path.join(folder_path, "DESCARGAS")

# Banner ASCII MarkOS
BANNER = r"""
  __  __            _       ____   _____ 
 |  \/  |          | |     / __ \ / ____|
 | \  / | __ _ r_ _| | __ | |  | | (___  
 | |\/| |/ _` | '__| |/ / | |  | |\___ \ 
 | |  | | (_| | |  |   <  | |__| |____) |
 |_|  |_|\__,_|_|  |_|\_\  \____/|_____/ 
"""


def select_quality():
    """Muestra el menú de calidad y retorna los parámetros correspondientes para yt-dlp."""
    print("Selecciona la calidad de descarga:")
    print("  1. MP3 (Solo audio)")
    print("  2. 480p (Calidad SD)")
    print("  3. 720p (Calidad HD)")
    print("  4. 1080p (Calidad Full HD)")
    print("  5. Máxima calidad posible (Defecto)")

    choice = input("\nIngresa una opción (1-5): ").strip()

    if choice == "1":
        return [
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
        ]  # Solo MP3
    elif choice == "2":
        return [
            "-f",
            "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "--merge-output-format",
            "mp4",
        ]
    elif choice == "3":
        return [
            "-f",
            "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "--merge-output-format",
            "mp4",
        ]
    elif choice == "4":
        return [
            "-f",
            "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "--merge-output-format",
            "mp4",
        ]
    else:
        # Opción 5 o cualquier entrada no válida usa el comando por defecto (máxima calidad disponible)
        return []


def run_yt_downloader():
    os.system("cls" if os.name == "nt" else "clear")
    print(BANNER)
    print("==================================================")
    print("             DESCARGADOR YOUTUBE                  ")
    print("==================================================")

    if not os.path.exists(links_file) or os.path.getsize(links_file) == 0:
        print("\n[!] No se encontró 'enlaces.txt' o está vacío.")
        print("Ejecuta primero el interceptor de links.")
        input("\nPresiona Enter para salir...")
        sys.exit()

    os.makedirs(download_dir, exist_ok=True)

    # Selección de calidad antes de iniciar el bucle
    quality_args = select_quality()

    # Leer enlaces del archivo txt
    with open(links_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"\n[+] Se encontraron {len(urls)} enlaces para descargar.\n")

    has_errors = False

    # Ejecutar yt-dlp para cada URL dentro de la carpeta DESCARGAS
    for index, url in enumerate(urls, 1):
        print(f"--------------------------------------------------")
        print(f"Descargando [{index}/{len(urls)}]: {url}")
        print(f"--------------------------------------------------")

        command = ["yt-dlp"] + quality_args + [url]

        try:
            # Captura si el proceso terminó con un código de error de retorno
            result = subprocess.run(command, cwd=download_dir)
            if result.returncode != 0:
                has_errors = True
        except Exception as e:
            print(f"[!] Error al procesar {url}: {e}")
            has_errors = True

    print("\n==================================================")
    if has_errors:
        print("  ¡OCURRIÓ UN ERROR EN ALGUNAS DESCARGAS! :(     ")
    else:
        print("  ¡DESCARGAS PROCESADAS CORRECTAMENTE! (creo xD)  ")
    print("==================================================")

    input("\nPresiona Enter para cerrar...")


if __name__ == "__main__":
    run_yt_downloader()