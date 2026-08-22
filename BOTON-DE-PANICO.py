import os
import subprocess
import winsound


def kill_all_processes():
    print("==================================================")
    print("      LIMPIADOR DE PROCESOS (CERRAR TODO)         ")
    print("==================================================")
    print("Cerrando todos los descargadores y monitores activos...\n")

    # Lista de ejecutables a finalizar de raíz
    targets = ["yt-dlp.exe", "python.exe", "pythonw.exe"]

    for target in targets:
        try:
            # Taskkill fuerzo (/F) la terminación de todos los procesos coincidentes (/IM)
            subprocess.run(
                ["taskkill", "/F", "/IM", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[✓] Procesos de {target} finalizados.")
        except Exception as e:
            print(f"[!] Error al intentar cerrar {target}: {e}")

    # Emitir un sonido agudo de confirmación
    winsound.Beep(2000, 200)

    print("\n==================================================")
    print("       ¡SISTEMA LIMPIADO CORRECTAMENTE!           ")
    print("==================================================")


if __name__ == "__main__":
    kill_all_processes()