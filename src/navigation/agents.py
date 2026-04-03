"""
Sistema de Agentes Estructurados para Navegación en Campus

Este módulo implementa un sistema de agentes con roles específicos:
- Agente 1 (Identifier): Detecta landmarks y ubicación en imágenes
- Agente 2 (Searcher): Busca objetivos funcionales en JSON o detecciones
- Agente 3 (Planner): Genera planes con integración GPS
"""

from typing import Dict, List, Optional, Tuple, Any
import json
import re
from pathlib import Path


# Prompt para clasificar el tipo de imagen. Siempre es el primer paso.
# Formato <image>\n + instrucción. Uso de "detect" para redacción formal (memoria).
CLASSIFIER_PROMPT = (
    "<image>\n"
    "Detect the navigation element visible in this image. "
    "Reply with exactly one word: sign, door, elevator, stairs, or other."
)


class Agent1_Identifier:
    """
    Agente 1: Identificador/Detective
    Rol: Detectar TODOS los landmarks visibles en una imagen de cartel/señalización

    Detecta:
    - Edificio y planta (ubicación actual)
    - Landmarks visibles (cafetería, biblioteca, salas, despachos, etc.)
    - Recursos disponibles (ascensores, escaleras, etc.)
    - Nivel de confianza en la detección
    """

    @staticmethod
    def get_classifier_prompt() -> str:
        """Prompt para clasificar el tipo de imagen. Siempre es el primer paso."""
        return CLASSIFIER_PROMPT

    @staticmethod
    def get_sign_prompt(building_codes: Optional[List[str]] = None) -> str:
        """Prompt para categoría sign: detectar edificio y planta en el cartel."""
        return "<image> What building and floor is on the sign? Examples: G 0, CD 1, H -1, G 2, G 1, G AGORA."

    @staticmethod
    def get_door_prompt() -> str:
        """Prompt para categoría door: detectar número de aula/oficina en la puerta (para inferir planta)."""
        return (
            "<image> What room number, classroom code, or office number is written on this door? "
            "Write ONLY the code you see, for example: 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, "
            "1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, "
            "2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9. "
            "If you cannot see a room number, write: none."
        )

    @staticmethod
    def get_elevator_prompt() -> str:
        """Prompt para categoría elevator: detectar si la puerta está abierta o cerrada."""
        return (
            "<image> Is the elevator door in this image open or closed? "
            "Answer with ONE word only: open or closed."
        )

    @staticmethod
    def get_elevator_panel_floor_prompt() -> str:
        """Prompt para extraer número de planta visible en el panel del ascensor (botón iluminado, etc.)."""
        return (
            "<image> Detect floor number on elevator panel. target: numeric digit. "
            "output: single integer. if not visible: none."
        )

    @staticmethod
    def get_stairs_prompt() -> str:
        """Prompt para categoría stairs: dirección de las escaleras desde la perspectiva del usuario."""
        return (
            "<image>\n"
            "Looking at these stairs from the viewer's perspective: "
            "can the person go up, go down, or both? "
            "Reply with exactly one word: up, down, or both."
        )

    @staticmethod
    def get_stairs_floor_prompt() -> str:
        """Prompt para extraer número de planta visible en la pared de las escaleras."""
        return (
            "<image>\n"
            "Look for a floor number displayed on the wall of this staircase. "
            "It is usually a large digit painted or printed on the wall, "
            "such as 0, 1, 2, or -1. "
            "Reply with only that number. "
            "If no floor number is visible, reply: none."
        )

    @staticmethod
    def get_prompts(building_codes: Optional[List[str]] = None) -> List[str]:
        """
        Retorna prompts específicos para el Agente 1 (Identificador).
        Estos prompts están diseñados para detectar TODO lo visible en la imagen.

        Args:
            building_codes: Lista opcional de códigos de edificios válidos para incluir
                            dinámicamente en el prompt (e.g. ["G", "CD", "H"]).

        Returns:
            Lista de prompts en inglés, ordenados de más específico a más general
        """
        codes_str = ", ".join(building_codes) if building_codes else "G, CD, H"

        return [
            # Prompt 0: JSON estructurado con campo de confianza
            (
                f"You are analyzing a campus building directory sign. "
                f"Valid building codes are: {codes_str}. "
                f"Respond ONLY with a JSON object in this exact format (no extra text):\n"
                f'{{"building_code": "G"|"CD"|"H"|null, '
                f'"floor": -1|0|1|2|null, '
                f'"confidence": "high"|"medium"|"low"|"none", '
                f'"visible_text": ["..."], '
                f'"landmarks": ["..."], '
                f'"reason": "brief explanation"}}'
            ),

            # Prompt 1: Fallback corto también en JSON
            (
                f"Look at this building sign. Valid codes: {codes_str}. "
                f'Reply ONLY with JSON: {{"building_code": null|"CODE", "floor": null|NUMBER, '
                f'"confidence": "high"|"medium"|"low"|"none", "visible_text": [], '
                f'"landmarks": [], "reason": ""}}'
            ),

            # Prompt 2: Fallback muy corto orientado a planta
            "What number is shown after PLANTA or FLOOR in the top right corner of this sign? "
            "Answer with ONLY the number (e.g. -1, 0, 1, 2).",

            # Prompt 3: Solo landmarks
            "List the facilities shown on this building sign (cafeteria, library, classrooms, "
            "laboratories, meeting rooms). Answer as a comma-separated list only.",

            # Prompt 4: Room number / classroom code detection
            "Look at this image. Do you see a room number, classroom label, or office code? "
            "For example: Aula 2.1, Lab 1.3, Despacho 205, or similar. "
            "Write ONLY the room or office code you see, nothing else. "
            "If you see nothing like that, write: none.",

            # Prompt 5: Generic text reader — works for door signs, plaques, any label
            "Read all text and numbers visible in this image. "
            "Write exactly what you see, word by word. "
            "Include any numbers, letters, abbreviations, or labels you can read.",

            # Prompt 6: Simple decimal room number (e.g. 0.3, 1.2, 2.5 on door signs)
            "Is there a number with a decimal point visible in this image? "
            "For example: 0.3, 1.2, 2.5, or similar door/room numbers. "
            "Write ONLY that number. If you do not see one, write: none.",

            # Prompt 7: Image classifier — primer prompt que se envía siempre
            "<image> Detect what you see in this image. Reply with one word: sign, door, elevator, stairs, other",

            # Prompt 8: Elevator door state (only called when classifier says elevator)
            "Is the elevator door in this image open or closed? "
            "Answer with ONE word only: open or closed.",

            # Prompt 9: Room number extraction (only called when classifier says door)
            "What room number, classroom code, or office number is written on this door? "
            "Write ONLY the code you see, for example: 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, "
            "1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, "
            "2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9. "
            "If you cannot see a room number, write: none.",
        ]

    @staticmethod
    def _try_parse_json(response_text: str) -> Optional[Dict[str, Any]]:
        """
        Intenta parsear la respuesta como JSON.
        Primero intenta directamente, luego extrae el primer objeto JSON con regex.

        Args:
            response_text: Texto de respuesta de PaliGemma

        Returns:
            Diccionario parseado o None si no se puede parsear
        """
        if not response_text:
            return None

        # Intento 1: parseo directo
        try:
            result = json.loads(response_text.strip())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        # Intento 2: extraer el primer bloque {...} con regex
        match = re.search(r'\{.*?\}', response_text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    @staticmethod
    def parse_response(response: str, campus_graph: Dict) -> Dict[str, Any]:
        """
        Parsea la respuesta del Agente 1 para extraer información estructurada.
        Intenta parsear JSON primero; si falla, usa la lógica regex original.

        Args:
            response: Respuesta de PaliGemma
            campus_graph: Grafo del campus para validar edificios

        Returns:
            Dict con:
            - building: ID del edificio (int o None)
            - floor: Número de planta (int o None)
            - landmarks: Lista de landmarks detectados (list)
            - resources: Lista de recursos detectados (list)
            - confidence: Nivel de confianza ("high"/"medium"/"low"/"none")
        """
        result: Dict[str, Any] = {
            "building": None,
            "floor": None,
            "landmarks": [],
            "resources": [],
            "confidence": "none",
        }

        # --- Intento JSON ---
        parsed_json = Agent1_Identifier._try_parse_json(response)
        if parsed_json is not None:
            confidence = parsed_json.get("confidence", "none")
            result["confidence"] = confidence if confidence in ("high", "medium", "low", "none") else "none"

            # Resolver building_code → building_id
            building_code = parsed_json.get("building_code")
            if building_code:
                building_code_upper = str(building_code).upper()
                for building in campus_graph.get("buildings", []):
                    if building.get("name", "").upper() == building_code_upper:
                        result["building"] = building["id"]
                        break

            # Floor
            floor_val = parsed_json.get("floor")
            if floor_val is not None:
                try:
                    result["floor"] = int(floor_val)
                except (ValueError, TypeError):
                    pass

            # Landmarks
            landmarks = parsed_json.get("landmarks", [])
            if isinstance(landmarks, list):
                result["landmarks"] = [str(l) for l in landmarks if l]

            # Visible text puede contener recursos
            visible_text = parsed_json.get("visible_text", [])
            all_text = " ".join(
                (landmarks if isinstance(landmarks, list) else []) +
                (visible_text if isinstance(visible_text, list) else [])
            ).lower()

            if "elevator" in all_text or "ascensor" in all_text:
                result["resources"].append("elevator")
            if "stairs" in all_text or "escalera" in all_text:
                result["resources"].append("stairs")

            return result

        # --- Fallback: lógica regex original ---
        response_lower = response.lower()

        # Buscar edificio
        building_match = None
        for building in campus_graph.get("buildings", []):
            building_name = building.get("name", "").upper()
            full_name = building.get("full_name", "").upper()

            if (
                f"building: {building_name.lower()}" in response_lower
                or f"building:{building_name.lower()}" in response_lower
                or building_name.lower() in response_lower
            ):
                building_match = building["id"]
                break

            if full_name and any(
                word in response_lower for word in full_name.lower().split() if len(word) > 2
            ):
                building_match = building["id"]
                break

        result["building"] = building_match

        # Buscar planta
        floor_patterns = [
            r"floor:\s*(-?\d+)",
            r"floor\s*(-?\d+)",
            r"planta:\s*(-?\d+)",
            r"planta\s*(-?\d+)",
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
            "tutoring", "tutoría", "mentor", "mentoría",
        ]
        landmarks_found = []
        for keyword in landmark_keywords:
            if keyword in response_lower:
                pat = rf"{keyword}[^\n,]*"
                matches = re.findall(pat, response_lower, re.IGNORECASE)
                landmarks_found.extend(matches)
        result["landmarks"] = list(set(landmarks_found))

        # Buscar recursos
        if "elevator" in response_lower or "ascensor" in response_lower:
            result["resources"].append("elevator")
        if "stairs" in response_lower or "escalera" in response_lower:
            result["resources"].append("stairs")

        # En modo fallback no tenemos confianza fiable, usar "low"
        if result["building"] is not None or result["floor"] is not None:
            result["confidence"] = "low"

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
    def search_goal(
        goal_name: str,
        agent1_detection: Optional[Dict[str, Any]] = None,
        campus_graph: Optional[Dict] = None,
    ) -> Tuple[Optional[int], Optional[int], str]:
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

                goal_keywords = {
                    "cafeteria": ["cafeteria", "cafetería"],
                    "gimnasio": ["gym", "gimnasio"],
                    "biblioteca": ["library", "biblioteca"],
                    "aula": ["classroom", "aula"],
                    "despacho": ["office", "despacho"],
                    "sala": ["meeting room", "sala", "reuniones"],
                }

                keywords = goal_keywords.get(goal_lower, [goal_lower])

                if any(keyword in landmark_lower for keyword in keywords):
                    building_id = agent1_detection.get("building")
                    floor = agent1_detection.get("floor")
                    return (building_id, floor, "image")

        # Prioridad 2: Buscar en base de datos JSON
        if campus_graph:
            for building in campus_graph.get("buildings", []):
                if goal_lower == "cafeteria":
                    cafeteria_floor = building.get("cafeteria_floor")
                    if cafeteria_floor is not None:
                        return (building["id"], cafeteria_floor, "database")
                elif goal_lower == "gimnasio":
                    gimnasio_floor = building.get("gimnasio_floor")
                    if gimnasio_floor is not None:
                        return (building["id"], gimnasio_floor, "database")
                elif goal_lower == "biblioteca":
                    building_name = building.get("name", "").upper()
                    if building_name == "B" or "biblioteca" in building.get("full_name", "").lower():
                        return (building["id"], 0, "database")

        return (None, None, "not_found")

    @staticmethod
    def get_search_prompt(goal_name: str, agent1_info: Optional[str] = None) -> str:
        """
        Genera un prompt para buscar un objetivo específico.

        Args:
            goal_name: Nombre del objetivo a buscar
            agent1_info: Información del Agente 1 (opcional)

        Returns:
            Prompt para búsqueda
        """
        if agent1_info:
            return (
                f"Based on the following information detected from an image:\n{agent1_info}\n\n"
                f"The user wants to go to: {goal_name}\n\n"
                f"If {goal_name} is mentioned in the detected information, provide its location "
                f"(building and floor).\nIf not found, respond with \"not_found_in_image\"."
            )
        else:
            return (
                f"The user wants to go to: {goal_name}\n\n"
                f"Search for this location in the campus database and provide building ID and floor number.\n"
                f"If not found, respond with \"not_found_in_database\"."
            )


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
    def get_planning_prompt(
        initial_state: Tuple[int, int],
        goal_state: Tuple[int, int],
        use_gps: bool = False,
    ) -> str:
        """
        Genera un prompt para el planificador.

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
            return (
                f"Generate a hybrid navigation plan:\n"
                f"- Start: Building {init_building}, Floor {init_floor}\n"
                f"- Goal: Building {goal_building}, Floor {goal_floor}\n"
                f"- Use GPS navigation for movement between buildings\n"
                f"- Use interior navigation (elevators/stairs) for floor changes within buildings\n"
                f"- Combine both types of navigation in the final plan"
            )
        else:
            return (
                f"Generate an interior navigation plan:\n"
                f"- Start: Building {init_building}, Floor {init_floor}\n"
                f"- Goal: Building {goal_building}, Floor {goal_floor}\n"
                f"- Use only interior navigation (elevators/stairs/hallways)\n"
                f"- No GPS needed (same building)"
            )


def create_agent_system() -> Dict[str, Any]:
    """
    Crea y retorna el sistema de agentes completo.

    Returns:
        Dict con los agentes inicializados
    """
    return {
        "agent1": Agent1_Identifier(),
        "agent2": Agent2_Searcher(),
        "agent3": Agent3_Planner(),
    }
