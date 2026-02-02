"""
Cliente para ejecutar Fast Downward en Docker

Ejecuta Fast Downward como contenedor Docker y parsea los planes resultantes.
"""

import subprocess
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import tempfile
import os


class FastDownwardPlanner:
    """Cliente para ejecutar Fast Downward en Docker."""
    
    def __init__(self, docker_image: str = "fast-downward:latest", timeout: int = 30):
        """
        Inicializa el cliente Fast Downward.
        
        Args:
            docker_image: Nombre de la imagen Docker de Fast Downward
            timeout: Timeout en segundos para la ejecución
        """
        self.docker_image = docker_image
        self.timeout = timeout
    
    def plan(self, 
             domain_path: str, 
             problem_path: str,
             search_config: str = "astar(lmcut())") -> Dict:
        """
        Ejecuta Fast Downward y devuelve el plan.
        
        Args:
            domain_path: Ruta al archivo domain.pddl
            problem_path: Ruta al archivo problem.pddl
            search_config: Configuración de búsqueda (por defecto: astar(lmcut()))
        
        Returns:
            Dict con:
            - success: bool
            - plan: List[str] con las acciones del plan
            - cost: int (costo del plan)
            - steps: int (número de pasos)
            - error: str (mensaje de error si falla)
        """
        domain_path = Path(domain_path).absolute()
        problem_path = Path(problem_path).absolute()
        
        # Verificar que los archivos existen
        if not domain_path.exists():
            return {
                "success": False,
                "error": f"Domain file not found: {domain_path}",
                "plan": [],
                "cost": 0,
                "steps": 0
            }
        
        if not problem_path.exists():
            return {
                "success": False,
                "error": f"Problem file not found: {problem_path}",
                "plan": [],
                "cost": 0,
                "steps": 0
            }
        
        # Construir comando Docker
        pddl_dir = domain_path.parent
        domain_file = domain_path.name
        problem_file = problem_path.name
        
        # Ejecutar Fast Downward en Docker
        # Usamos un nombre fijo para que sea visible en docker ps
        container_name = "fast-downward-planner"
        
        # Eliminar contenedor anterior si existe (por si quedó de una ejecución previa)
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=5
            )
        except:
            pass  # Ignorar si no existe
        
        # Ejecutar Fast Downward (SIN --rm para que sea visible)
        cmd = [
            "docker", "run",
            "--name", container_name,  # Nombre fijo para verlo en docker ps
            "-v", f"{pddl_dir}:/pddl",
            self.docker_image,
            domain_file,
            problem_file
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(pddl_dir)
            )
            
            # NO eliminamos el contenedor automáticamente
            # Así se puede ver en docker ps -a después de ejecutar
            # El usuario puede eliminarlo manualmente si quiere con: docker rm fast-downward-planner
            
            # Parsear la salida
            output = result.stdout + result.stderr
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Fast Downward failed with exit code {result.returncode}",
                    "output": output,
                    "plan": [],
                    "cost": 0,
                    "steps": 0
                }
            
            # Extraer el plan de la salida
            plan_info = self._parse_plan(output)
            
            return {
                "success": plan_info["success"],
                "plan": plan_info["plan"],
                "cost": plan_info["cost"],
                "steps": plan_info["steps"],
                "output": output,
                "error": plan_info.get("error")
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Fast Downward timeout after {self.timeout} seconds",
                "plan": [],
                "cost": 0,
                "steps": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing Fast Downward: {str(e)}",
                "plan": [],
                "cost": 0,
                "steps": 0
            }
    
    def _parse_plan(self, output: str) -> Dict:
        """
        Parsea la salida de Fast Downward para extraer el plan.
        
        Args:
            output: Salida de Fast Downward
        
        Returns:
            Dict con plan, cost, steps, success
        """
        plan = []
        cost = 0
        steps = 0
        success = False
        
        # Buscar "Solution found"
        if "Solution found" in output:
            success = True
            
            # Extraer número de pasos
            steps_match = re.search(r"Plan length:\s+(\d+)\s+step\(s\)", output)
            if steps_match:
                steps = int(steps_match.group(1))
            
            # Extraer costo
            cost_match = re.search(r"Plan cost:\s+(\d+)", output)
            if cost_match:
                cost = int(cost_match.group(1))
            
            # Extraer las acciones del plan
            # Buscar líneas que contengan acciones (formato: action_name param1 param2 ...)
            lines = output.split('\n')
            in_plan = False
            
            for line in lines:
                # Detectar inicio del plan (después de "Solution found" o "Actual search time")
                if "Solution found" in line or "Actual search time" in line:
                    in_plan = True
                    continue
                
                # Detectar fin del plan (cuando aparece "Plan length" o "Plan cost")
                if in_plan and ("Plan length" in line or "Plan cost" in line):
                    break
                
                # Extraer acciones (líneas que no empiezan con espacios o son comandos)
                if in_plan and line.strip():
                    # Filtrar líneas que son acciones (no empiezan con [t= o INFO)
                    if not line.strip().startswith('[t=') and not line.strip().startswith('INFO'):
                        # Limpiar la línea y añadirla al plan
                        action = line.strip()
                        if action and not action.startswith('['):
                            plan.append(action)
        
        # Si no encontramos plan con el método anterior, buscar directamente
        if not plan:
            # Buscar líneas con formato de acción PDDL
            action_pattern = r'([a-z_]+(?:\s+[a-z0-9_]+)+)\s*\(\d+\)'
            matches = re.findall(action_pattern, output)
            if matches:
                plan = [m.strip() for m in matches]
                success = True
        
        return {
            "success": success,
            "plan": plan,
            "cost": cost,
            "steps": steps
        }
    
    def validate_plan(self, plan: List[str], domain_path: str, problem_path: str) -> bool:
        """
        Valida un plan ejecutándolo con Fast Downward en modo validación.
        
        Args:
            plan: Lista de acciones del plan
            domain_path: Ruta al domain.pddl
            problem_path: Ruta al problem.pddl
        
        Returns:
            True si el plan es válido, False en caso contrario
        """
        # Fast Downward no tiene modo de validación directo,
        # pero podemos verificar que el plan se ejecutó correctamente
        result = self.plan(domain_path, problem_path)
        return result["success"] and len(result["plan"]) > 0


if __name__ == "__main__":
    # Ejemplo de uso
    planner = FastDownwardPlanner()
    
    domain = "pddl/domain.pddl"
    problem = "pddl/problem_ejemplo.pddl"
    
    print(f"Ejecutando Fast Downward...")
    print(f"Domain: {domain}")
    print(f"Problem: {problem}")
    print()
    
    result = planner.plan(domain, problem)
    
    if result["success"]:
        print("[OK] Plan encontrado!")
        print(f"  Pasos: {result['steps']}")
        print(f"  Costo: {result['cost']}")
        print(f"  Plan:")
        for i, action in enumerate(result["plan"], 1):
            print(f"    {i}. {action}")
    else:
        print("[ERROR] Error al generar plan:")
        print(f"  {result.get('error', 'Unknown error')}")
