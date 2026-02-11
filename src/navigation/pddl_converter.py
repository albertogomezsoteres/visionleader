"""
Conversor de JSON del Campus a PDDL

Convierte:
- campus_graph.json → domain.pddl (estructura estática)
- Estados inicial/final → problem.pddl (dinámico)
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set


class CampusGraphToPDDL:
    """Convierte el grafo del campus desde JSON a proposiciones PDDL."""
    
    def __init__(self, json_path: str):
        """Carga el grafo del campus desde JSON."""
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
    
    def get_buildings(self) -> List[Dict]:
        """Obtiene la lista de edificios."""
        return self.data.get("buildings", [])
    
    def get_connections(self) -> List[Dict]:
        """Obtiene la lista de conexiones."""
        return self.data.get("connections", [])
    
    def _find_functional_goal(self, goal_functional: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Busca un objetivo funcional (cafetería, gimnasio) en el JSON.
        
        Args:
            goal_functional: "cafeteria" o "gimnasio"
            
        Returns:
            (building_id, floor) o (None, None) si no se encuentra
        """
        goal_lower = goal_functional.lower()
        
        for building in self.get_buildings():
            if goal_lower == "cafeteria":
                cafeteria_floor = building.get('cafeteria_floor')
                if cafeteria_floor is not None:
                    return (building['id'], cafeteria_floor)
            elif goal_lower == "gimnasio":
                gimnasio_floor = building.get('gimnasio_floor')
                if gimnasio_floor is not None:
                    return (building['id'], gimnasio_floor)
        
        return (None, None)
    
    def generate_problem_objects(self) -> Dict[str, List[str]]:
        """
        Genera los objetos PDDL desde el JSON.
        
        Returns:
            Dict con claves: 'robots', 'edificios', 'plantas', 'tipos_conexion'
        """
        objects = {
            'robots': ['robot1'],
            'edificios': [],
            'plantas': set(),
            'tipos_conexion': ['elevator', 'stairs_up', 'stairs_down', 'hallway']
        }
        
        # Obtener edificios
        for building in self.get_buildings():
            edificio_id = building['id']
            objects['edificios'].append(f"edificio_{edificio_id}")
            
            # Obtener plantas (usar 'm1' para -1, 'm2' para -2, etc.)
            for planta in building.get('floors', []):
                if planta < 0:
                    planta_str = f"planta_m{abs(planta)}"
                else:
                    planta_str = f"planta_{planta}"
                objects['plantas'].add(planta_str)
        
        objects['plantas'] = sorted(list(objects['plantas']))
        
        return objects
    
    def generate_problem_init(self, 
                             robot_location: Optional[Tuple[int, int]] = None,
                             humano_disponible: bool = True) -> List[str]:
        """
        Genera las proposiciones INIT desde el JSON.
        
        Args:
            robot_location: (edificio, planta) donde está el robot inicialmente
            humano_disponible: Si hay humano disponible para ayudar
        
        Returns:
            Lista de proposiciones PDDL para :init
        """
        init = []
        
        # Ubicación inicial del robot
        if robot_location:
            edificio, planta = robot_location
            planta_str = f"planta_m{abs(planta)}" if planta < 0 else f"planta_{planta}"
            init.append(f"    (en robot1 edificio_{edificio} {planta_str})")
        
        # Humano disponible
        if humano_disponible:
            init.append("    (humano_disponible)")
        
        # Recursos por edificio (ascensores, escaleras, cafeterías)
        for building in self.get_buildings():
            edificio_id = building['id']
            has_elevator = building.get('elevators', False)
            has_stairs = building.get('stairs', False)
            
            for planta in building.get('floors', []):
                if planta < 0:
                    planta_str = f"planta_m{abs(planta)}"
                else:
                    planta_str = f"planta_{planta}"
                
                if has_elevator:
                    init.append(f"    (hay_ascensor edificio_{edificio_id} {planta_str})")
                
                if has_stairs:
                    init.append(f"    (hay_escalera edificio_{edificio_id} {planta_str})")
                
                # Cafetería: leer del JSON en lugar de hardcodeado
                cafeteria_floor = building.get('cafeteria_floor')
                if cafeteria_floor is not None and planta == cafeteria_floor:
                    init.append(f"    (hay_cafeteria edificio_{edificio_id} {planta_str})")
                
                # Gimnasio: leer del JSON en lugar de hardcodeado
                gimnasio_floor = building.get('gimnasio_floor')
                if gimnasio_floor is not None and planta == gimnasio_floor:
                    init.append(f"    (hay_gimnasio edificio_{edificio_id} {planta_str})")
        
        # Conexiones
        for conn in self.get_connections():
            from_b = conn['from']['building']
            from_p = conn['from']['floor']
            to_b = conn['to']['building']
            to_p = conn['to']['floor']
            tipo = conn['type']
            
            # Formatear plantas (negativas como m1, m2, etc.)
            from_p_str = f"planta_m{abs(from_p)}" if from_p < 0 else f"planta_{from_p}"
            to_p_str = f"planta_m{abs(to_p)}" if to_p < 0 else f"planta_{to_p}"
            
            init.append(
                f"    (conectado edificio_{from_b} {from_p_str} "
                f"edificio_{to_b} {to_p_str} {tipo})"
            )
        
        return init
    
    def generate_problem(self,
                        initial_state: Tuple[int, int],
                        goal_state: Optional[Tuple[int, int]] = None,
                        goal_functional: Optional[str] = None,
                        problem_name: str = "campus-problem",
                        output_path: Optional[str] = None) -> str:
        """
        Genera un archivo problem.pddl completo.
        
        Args:
            initial_state: (edificio, planta) estado inicial
            goal_state: (edificio, planta) estado objetivo
            problem_name: Nombre del problema
            output_path: Ruta donde guardar el archivo (opcional)
        
        Returns:
            Contenido del archivo problem.pddl como string
        """
        objects = self.generate_problem_objects()
        init = self.generate_problem_init(robot_location=initial_state)
        
        # Goal
        if goal_functional:
            # Goal funcional: buscar en JSON en lugar de hardcodeado
            goal_building_id, goal_floor = self._find_functional_goal(goal_functional)
            if goal_building_id is None or goal_floor is None:
                raise ValueError(f"Goal funcional '{goal_functional}' no encontrado en campus_graph.json")
            
            goal_floor_str = f"planta_m{abs(goal_floor)}" if goal_floor < 0 else f"planta_{goal_floor}"
            
            if goal_functional.lower() == "cafeteria":
                goal = f"    (and\n      (en robot1 edificio_{goal_building_id} {goal_floor_str})\n      (hay_cafeteria edificio_{goal_building_id} {goal_floor_str})\n    )"
            elif goal_functional.lower() == "gimnasio":
                goal = f"    (and\n      (en robot1 edificio_{goal_building_id} {goal_floor_str})\n      (hay_gimnasio edificio_{goal_building_id} {goal_floor_str})\n    )"
            else:
                raise ValueError(f"Goal funcional desconocido: {goal_functional}. Usa 'cafeteria' o 'gimnasio'")
        elif goal_state:
            # Goal por ubicación
            goal_edificio, goal_planta = goal_state
            goal_planta_str = f"planta_m{abs(goal_planta)}" if goal_planta < 0 else f"planta_{goal_planta}"
            goal = f"    (en robot1 edificio_{goal_edificio} {goal_planta_str})"
        else:
            raise ValueError("Debe especificar goal_state o goal_functional")
        
        # Construir el archivo
        problem_content = f"""(define (problem {problem_name})
  (:domain campus-navigation)
  
  (:objects
    {' '.join(objects['robots'])} - robot
    {' '.join(objects['edificios'])} - edificio
    {' '.join(objects['plantas'])} - planta
    {' '.join(objects['tipos_conexion'])} - tipo_conexion
  )
  
  (:init
{chr(10).join(init)}
  )
  
  (:goal
    (and
      {goal}
    )
  )
)
"""
        
        # Guardar si se especifica ruta
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(problem_content)
        
        return problem_content


def create_problem_from_states(json_path: str,
                               initial_state: Tuple[int, int],
                               goal_state: Optional[Tuple[int, int]] = None,
                               goal_functional: Optional[str] = None,
                               output_path: str = None) -> str:
    """
    Función helper para crear un problema PDDL desde estados.
    
    Args:
        json_path: Ruta al campus_graph.json
        initial_state: (edificio, planta) inicial
        goal_state: (edificio, planta) objetivo
        output_path: Donde guardar el problem.pddl
    
    Returns:
        Ruta al archivo generado
    """
    converter = CampusGraphToPDDL(json_path)
    converter.generate_problem(
        initial_state=initial_state,
        goal_state=goal_state,
        goal_functional=goal_functional,
        output_path=output_path
    )
    return output_path


if __name__ == "__main__":
    # Ejemplo de uso
    json_path = "config/campus_graph.json"
    converter = CampusGraphToPDDL(json_path)
    
    # Generar problema de ejemplo: EPS planta 0 → EPS planta 2
    problem_content = converter.generate_problem(
        initial_state=(1, 0),  # EPS planta 0
        goal_state=(1, 2),      # EPS planta 2
        problem_name="ejemplo-eps-0-a-2",
        output_path="pddl/problem_ejemplo.pddl"
    )
    
    print("Problema generado en pddl/problem_ejemplo.pddl")
    print("\nContenido:")
    print(problem_content)
