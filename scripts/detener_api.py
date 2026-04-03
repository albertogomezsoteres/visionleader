"""
Script para detener la API si está corriendo en el puerto 8000
"""

import subprocess
import sys

def find_process_on_port(port):
    """Encuentra el PID del proceso usando el puerto."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True
        )
        
        for line in result.stdout.split('\n'):
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    return pid
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def kill_process(pid):
    """Mata un proceso por su PID."""
    try:
        subprocess.run(["taskkill", "/F", "/PID", pid], check=True)
        return True
    except Exception as e:
        print(f"Error al detener proceso: {e}")
        return False

if __name__ == "__main__":
    port = 8000
    print(f"Buscando proceso en puerto {port}...")
    
    pid = find_process_on_port(port)
    
    if pid:
        print(f"Proceso encontrado: PID {pid}")
        respuesta = input("¿Detener este proceso? (s/n): ")
        if respuesta.lower() == 's':
            if kill_process(pid):
                print(f"[OK] Proceso {pid} detenido")
            else:
                print(f"[ERROR] No se pudo detener el proceso")
        else:
            print("Operación cancelada")
    else:
        print(f"No se encontró ningún proceso usando el puerto {port}")
