"""
Script para probar Fast Downward y ver el contenedor Docker corriendo

Este script ejecuta Fast Downward y muestra cómo ver el contenedor en Docker.
"""

import subprocess
import time
from pathlib import Path

def test_fast_downward_visible():
    """Ejecuta Fast Downward sin --rm para ver el contenedor."""
    print("=" * 60)
    print("PRUEBA: Fast Downward con contenedor visible")
    print("=" * 60)
    print()
    
    # Rutas
    pddl_dir = Path("pddl").absolute()
    domain_file = "domain.pddl"
    problem_file = "problem_ejemplo.pddl"
    container_name = "fast-downward-test"
    
    print(f"1. Limpiando contenedor anterior (si existe)...")
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True
    )
    print("   [OK]")
    print()
    
    print(f"2. Ejecutando Fast Downward en contenedor: {container_name}")
    print(f"   Domain: {domain_file}")
    print(f"   Problem: {problem_file}")
    print()
    
    # Ejecutar en segundo plano para poder ver el contenedor
    cmd = [
        "docker", "run",
        "--name", container_name,
        "-v", f"{pddl_dir}:/pddl",
        "fast-downward:latest",
        domain_file,
        problem_file
    ]
    
    print("   Ejecutando comando:")
    print(f"   {' '.join(cmd)}")
    print()
    
    # Ejecutar
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print("3. Contenedor iniciado. Esperando 2 segundos...")
    time.sleep(2)
    print()
    
    print("4. Verificando contenedor en Docker:")
    print("   Ejecuta en otra terminal: docker ps")
    print("   O: docker ps -a")
    print()
    
    # Verificar que el contenedor existe
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True,
        text=True
    )
    
    if container_name in result.stdout:
        print(f"   [OK] Contenedor '{container_name}' encontrado:")
        print(f"   {result.stdout.strip()}")
    else:
        print(f"   [INFO] Contenedor puede haber terminado ya")
    print()
    
    print("5. Esperando a que termine la ejecución...")
    stdout, stderr = process.communicate()
    
    print("6. Salida de Fast Downward:")
    print("-" * 60)
    output = stdout + stderr
    
    # Buscar el plan en la salida
    if "Solution found" in output:
        print("[OK] Plan encontrado!")
        # Extraer líneas del plan
        lines = output.split('\n')
        in_plan = False
        for line in lines:
            if "Solution found" in line or "Actual search time" in line:
                in_plan = True
            if in_plan and line.strip() and not line.strip().startswith('[t='):
                if "Plan length" in line or "Plan cost" in line:
                    print(f"  {line.strip()}")
                elif not line.strip().startswith('INFO') and '(' in line:
                    print(f"  {line.strip()}")
    else:
        print(output[-500:])  # Últimas 500 caracteres
    
    print("-" * 60)
    print()
    
    print("7. Verificando contenedor después de ejecutar:")
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True,
        text=True
    )
    
    if container_name in result.stdout:
        print(f"   Contenedor todavía existe:")
        print(f"   {result.stdout.strip()}")
        print()
        print("   Para ver los logs del contenedor:")
        print(f"   docker logs {container_name}")
        print()
        print("   Para eliminar el contenedor:")
        print(f"   docker rm {container_name}")
    else:
        print("   Contenedor ya fue eliminado automáticamente")
    
    print()
    print("=" * 60)
    print("PRUEBA COMPLETADA")
    print("=" * 60)
    print()
    print("Comandos útiles:")
    print("  docker ps              - Ver contenedores corriendo")
    print("  docker ps -a           - Ver todos los contenedores (incluidos detenidos)")
    print(f"  docker logs {container_name}  - Ver logs del contenedor")
    print(f"  docker rm {container_name}    - Eliminar el contenedor")
    print()

if __name__ == "__main__":
    test_fast_downward_visible()
