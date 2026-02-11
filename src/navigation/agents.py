"""
Sistema de Agentes Estructurados para Navegación en Campus

Este módulo implementa un sistema de agentes con roles específicos:
- Agente 1 (Identifier): Detecta landmarks y ubicación en imágenes
- Agente 2 (Searcher): Busca objetivos funcionales en JSON o detecciones
- Agente 3 (Planner): Genera planes con integración GPS
"""

from typing import Dict, List, Optional, Tuple, Any
import json
from pathlib import Path


class Agent1_Identifier:
    """
    Agente 1: Identificador/Detective
    Rol: Detectar TODOS los landmarks visibles en una imagen de cartel/señalización
    
    Detecta:
    - Edificio y planta (ubicación actual)
    - Landmarks visibles (cafetería, biblioteca, salas, despachos, etc.)
    - Recursos disponibles (ascensores, escaleras, etc.)
    """
    
    @staticmethod
    def get_prompts() -> List[str]:
        """
        Retorna prompts específicos para el Agente 1 (Identificador).
        Estos prompts están diseñados para detectar TODO lo visible en la imagen.
        
        Returns:
            Lista de prompts en inglés, ordenados de más específico a más general
        """
        return [
            # Prompt 0: Prompt específico del plan (en español, como se especifica)
            """Lee el cartel de señalización en esta imagen del campus. Identifica el nombre del edificio y el número de planta que aparecen en el cartel. Busca las palabras 'EDIFICIO' o 'PLANTA' y el texto asociado.""",
            
            # Prompt 1: Detección completa y estructurada (en inglés, más detallado)
            """You are an expert at reading building signage and identifying landmarks. 
Look at this image carefully and identify ALL visible information:

1. BUILDING INFORMATION:
   - Find the building code (letter after "EDIFICIO" or before "BUILDING")
   - Find the floor number (after "PLANTA" or "FLOOR")
   - Examples: "EDIFICIO H", "H BUILDING", "PLANTA 2", "FLOOR 2"

2. LANDMARKS AND LOCATIONS (if visible on the sign):
   - Cafeteria / Cafetería
   - Library / Biblioteca
   - Gym / Gimnasio
   - Classrooms / Aulas (with room numbers if shown)
   - Meeting rooms / Salas de reuniones
   - Offices / Despachos
   - Tutoring rooms / Salas de tutorías
   - Any other locations mentioned on the sign

3. RESOURCES (if visible):
   - Elevator / Ascensor
   - Stairs / Escaleras
   - Accessibility features

Format your response as:
"Building: [LETTER], Floor: [NUMBER], Landmarks: [list of visible landmarks], Resources: [elevator/stairs if visible]"

If you cannot identify something, say "unknown" for that field.""",

            # Prompt 2: Enfoque en lectura detallada del cartel
            """Read this building signage board completely. Identify:

BUILDING: The letter code (H, B, R, E, M, O, P, EPS, CD, etc.)
FLOOR: The floor number (can be negative like -1, or positive like 0, 1, 2)

Then, scan the entire sign for any mentions of:
- Cafeteria, Library, Gym, Classrooms, Offices, Meeting rooms
- Any room numbers or location names
- Elevator or stairs indicators

Respond with: "Building: X, Floor: Y, Visible landmarks: [list], Resources: [list]"
If a landmark is not visible, don't include it.""",

            # Prompt 3: Instrucciones paso a paso
            """Step-by-step analysis of this building sign:

STEP 1: Find building identification
- Look for "EDIFICIO [LETTER]" or "[LETTER] BUILDING"
- Extract the LETTER (this is the building code)

STEP 2: Find floor information
- Look for "PLANTA [NUMBER]" or "FLOOR [NUMBER]"
- Extract the NUMBER (can be negative)

STEP 3: Scan for landmarks
- Read all text on the sign
- Identify any mentions of: cafeteria, library, gym, classrooms, offices, meeting rooms, tutoring rooms
- Note any room numbers (e.g., "Aula 2.1", "Sala 2.1")

STEP 4: Identify resources
- Look for elevator icons or text
- Look for stairs indicators

Respond with all findings in this format:
"Building: [code], Floor: [number], Landmarks: [comma-separated list], Resources: [elevator/stairs/none]"
""",

            # Prompt 4: Formato muy específico con ejemplos
            """This is a building signage board. Extract ALL information:

EXAMPLES of what to find:
- "EDIFICIO H / H BUILDING" → Building: H
- "PLANTA 2 / FLOOR 2" → Floor: 2
- "Aula 2.1 / Classroom 2.1" → Landmark: Classroom 2.1
- "Cafetería / Cafeteria" → Landmark: Cafeteria
- "Salas de reuniones 2.1 - 2.2" → Landmark: Meeting rooms 2.1-2.2

Your task:
1. Identify building code (single letter or code like EPS, CD)
2. Identify floor number
3. List ALL landmarks/locations mentioned on the sign
4. Note if elevator or stairs are indicated

Response format:
"Building: [X], Floor: [Y], Landmarks: [landmark1, landmark2, ...], Resources: [elevator/stairs/none]"
"""
        ]
    
    @staticmethod
    def parse_response(response: str, campus_graph: Dict) -> Dict[str, Any]:
        """
        Parsea la respuesta del Agente 1 para extraer información estructurada.
        
        Args:
            response: Respuesta de Paligemma
            campus_graph: Grafo del campus para validar edificios
            
        Returns:
            Dict con:
            - building: ID del edificio (int o None)
            - floor: Número de planta (int o None)
            - landmarks: Lista de landmarks detectados (list)
            - resources: Lista de recursos detectados (list)
        """
        result = {
            "building": None,
            "floor": None,
            "landmarks": [],
            "resources": []
        }
        
        response_lower = response.lower()
        
        # Buscar edificio
        building_match = None
        for building in campus_graph.get("buildings", []):
            building_name = building.get("name", "").upper()
            full_name = building.get("full_name", "").upper()
            
            # Buscar por código (H, B, EPS, CD, etc.)
            if f"building: {building_name}" in response_lower or \
               f"building:{building_name}" in response_lower or \
               building_name in response_lower:
                building_match = building["id"]
                break
            
            # Buscar por nombre completo
            if full_name and any(word in response_lower for word in full_name.split() if len(word) > 2):
                building_match = building["id"]
                break
        
        result["building"] = building_match
        
        # Buscar planta (puede ser negativa)
        import re
        floor_patterns = [
            r"floor:\s*(-?\d+)",
            r"floor\s*(-?\d+)",
            r"planta:\s*(-?\d+)",
            r"planta\s*(-?\d+)"
        ]
        
        for pattern in floor_patterns:
            match = re.search(pattern, response_lower)
            if match:
                try:
                    result["floor"] = int(match.group(1))
                    break
                except ValueError:
                    continue
        
        # Buscar landmarks
        landmark_keywords = [
            "cafeteria", "cafetería", "library", "biblioteca", "gym", "gimnasio",
            "classroom", "aula", "office", "despacho", "meeting room", "sala de reuniones",
            "tutoring", "tutoría", "mentor", "mentoría"
        ]
        
        landmarks_found = []
        for keyword in landmark_keywords:
            if keyword in response_lower:
                # Intentar extraer el contexto completo
                # Por ejemplo: "Aula 2.1" o "Cafetería"
                pattern = rf"{keyword}[^\n,]*"
                matches = re.findall(pattern, response_lower, re.IGNORECASE)
                landmarks_found.extend(matches)
        
        result["landmarks"] = list(set(landmarks_found))  # Eliminar duplicados
        
        # Buscar recursos
        if "elevator" in response_lower or "ascensor" in response_lower:
            result["resources"].append("elevator")
        if "stairs" in response_lower or "escalera" in response_lower:
            result["resources"].append("stairs")
        
        return result


class Agent2_Searcher:
    """
    Agente 2: Buscador
    Rol: Buscar objetivos funcionales (cafetería, gimnasio, etc.) en:
    - Lo detectado por Agente 1 (si está en la imagen)
    - La base de datos JSON (campus_graph.json)
    
    Prioriza: Detección visual > Base de datos
    """
    
    @staticmethod
    def search_goal(goal_name: str, 
                   agent1_detection: Optional[Dict[str, Any]] = None,
                   campus_graph: Optional[Dict] = None) -> Tuple[Optional[int], Optional[int], str]:
        """
        Busca un objetivo funcional usando Agente 1 y/o base de datos.
        
        Args:
            goal_name: Nombre del objetivo ("cafeteria", "gimnasio", "biblioteca", etc.)
            agent1_detection: Resultado del Agente 1 (si está disponible)
            campus_graph: Grafo del campus (si está disponible)
            
        Returns:
            (building_id, floor, source) donde source es "image", "database", o "not_found"
        """
        goal_lower = goal_name.lower()
        
        # Prioridad 1: Buscar en detección del Agente 1 (imagen)
        if agent1_detection:
            landmarks = agent1_detection.get("landmarks", [])
            for landmark in landmarks:
                landmark_lower = landmark.lower()
                
                # Mapeo de objetivos a keywords
                goal_keywords = {
                    "cafeteria": ["cafeteria", "cafetería"],
                    "gimnasio": ["gym", "gimnasio"],
                    "biblioteca": ["library", "biblioteca"],
                    "aula": ["classroom", "aula"],
                    "despacho": ["office", "despacho"],
                    "sala": ["meeting room", "sala", "reuniones"]
                }
                
                keywords = goal_keywords.get(goal_lower, [goal_lower])
                
                if any(keyword in landmark_lower for keyword in keywords):
                    # Objetivo encontrado en la imagen
                    building_id = agent1_detection.get("building")
                    floor = agent1_detection.get("floor")
                    return (building_id, floor, "image")
        
        # Prioridad 2: Buscar en base de datos JSON
        if campus_graph:
            # Buscar objetivos funcionales conocidos
            for building in campus_graph.get("buildings", []):
                if goal_lower == "cafeteria":
                    cafeteria_floor = building.get('cafeteria_floor')
                    if cafeteria_floor is not None:
                        return (building['id'], cafeteria_floor, "database")
                elif goal_lower == "gimnasio":
                    gimnasio_floor = building.get('gimnasio_floor')
                    if gimnasio_floor is not None:
                        return (building['id'], gimnasio_floor, "database")
                elif goal_lower == "biblioteca":
                    # Buscar edificio con nombre "Biblioteca" o "B"
                    building_name = building.get("name", "").upper()
                    if building_name == "B" or "biblioteca" in building.get("full_name", "").lower():
                        # Asumir planta 0 por defecto (puedes ajustar según tu JSON)
                        return (building['id'], 0, "database")
        
        # No encontrado
        return (None, None, "not_found")
    
    @staticmethod
    def get_search_prompt(goal_name: str, agent1_info: Optional[str] = None) -> str:
        """
        Genera un prompt para buscar un objetivo específico.
        (Puede usarse con una IA adicional si se necesita búsqueda más compleja)
        
        Args:
            goal_name: Nombre del objetivo a buscar
            agent1_info: Información del Agente 1 (opcional)
            
        Returns:
            Prompt para búsqueda
        """
        if agent1_info:
            return f"""Based on the following information detected from an image:
{agent1_info}

The user wants to go to: {goal_name}

If {goal_name} is mentioned in the detected information, provide its location (building and floor).
If not found, respond with "not_found_in_image"."""
        else:
            return f"""The user wants to go to: {goal_name}

Search for this location in the campus database and provide building ID and floor number.
If not found, respond with "not_found_in_database"."""


class Agent3_Planner:
    """
    Agente 3: Planificador
    Rol: Generar planes de navegación con integración GPS cuando hay movimiento entre edificios
    
    Decide:
    - Cuándo usar GPS (movimiento entre edificios)
    - Cuándo usar navegación interior (dentro del mismo edificio)
    - Cómo combinar ambos (plan híbrido)
    """
    
    @staticmethod
    def needs_gps(initial_building: int, goal_building: int) -> bool:
        """
        Determina si se necesita GPS para el movimiento.
        
        Args:
            initial_building: ID del edificio inicial
            goal_building: ID del edificio objetivo
            
        Returns:
            True si se necesita GPS (diferentes edificios), False si es interior
        """
        return initial_building != goal_building
    
    @staticmethod
    def get_planning_prompt(initial_state: Tuple[int, int],
                           goal_state: Tuple[int, int],
                           use_gps: bool = False) -> str:
        """
        Genera un prompt para el planificador (puede usarse con IA adicional).
        
        Args:
            initial_state: (building_id, floor) estado inicial
            goal_state: (building_id, floor) estado objetivo
            use_gps: Si se necesita GPS
            
        Returns:
            Prompt para planificación
        """
        init_building, init_floor = initial_state
        goal_building, goal_floor = goal_state
        
        if use_gps:
            return f"""Generate a hybrid navigation plan:
- Start: Building {init_building}, Floor {init_floor}
- Goal: Building {goal_building}, Floor {goal_floor}
- Use GPS navigation for movement between buildings
- Use interior navigation (elevators/stairs) for floor changes within buildings
- Combine both types of navigation in the final plan"""
        else:
            return f"""Generate an interior navigation plan:
- Start: Building {init_building}, Floor {init_floor}
- Goal: Building {goal_building}, Floor {goal_floor}
- Use only interior navigation (elevators/stairs/hallways)
- No GPS needed (same building)"""


def create_agent_system() -> Dict[str, Any]:
    """
    Crea y retorna el sistema de agentes completo.
    
    Returns:
        Dict con los agentes inicializados
    """
    return {
        "agent1": Agent1_Identifier(),
        "agent2": Agent2_Searcher(),
        "agent3": Agent3_Planner()
    }
