import os
import sys
import time
import winsound
import keyboard
import pyperclip

# Rutas configuradas para la carpeta 'Descargador casero' en el Escritorio
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
folder_path = os.path.join(desktop_path, "Descargador casero")
txt_file = os.path.join(folder_path, "enlaces.txt")


def setup_environment():
    """Crea la carpeta si no existe y vacía enlaces.txt al iniciar."""
    os.makedirs(folder_path, exist_ok=True)
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write("")  # Vacía el archivo para iniciar desde cero


def finish_and_open_folder():
    """Cierra el interceptor y abre la carpeta Descargador casero."""
    winsound.Beep(1500, 200)
    print("\n[!] Captura finalizada por el usuario.")
    print(f"[+] Abriendo carpeta: {folder_path}")

    # Abrir el explorador de archivos en la carpeta de la herramienta
    os.startfile(folder_path)

    # Finalizar la ejecución del programa
    os._exit(0)


def monitor_clipboard():
    setup_environment()

    print("==================================================")
    print("      INTERCEPTOR DE ENLACES (MODO VISIBLE)       ")
    print("==================================================")
    print(f"Ruta de guardado: {txt_file}")
    print("Presiona [ESC] en cualquier momento para finalizar")
    print("y abrir la carpeta de trabajo.\n")
    print("Esperando que copies enlaces...\n")

    last_url = ""

    # Asignar la tecla Esc para cerrar y abrir la carpeta
    keyboard.add_hotkey("esc", finish_and_open_folder)

    while True:
        try:
            current_clip = pyperclip.paste().strip()

            # Captura cualquier enlace que empiece por http/https y no esté repetido
            if (
                current_clip != last_url
                and current_clip.startswith(("http://", "https://"))
            ):
                with open(txt_file, "a", encoding="utf-8") as f:
                    f.write(current_clip + "\n")

                winsound.Beep(1000, 150)  # Pitido de confirmación
                print(f"[✓] Capturado: {current_clip}")
                last_url = current_clip

            time.sleep(0.4)
        except Exception as e:
            time.sleep(1)


if __name__ == "__main__":
    monitor_clipboard()