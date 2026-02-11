"""
Sistema Conversacional Agente para Navegación

Este módulo implementa un sistema conversacional inteligente que:
- Mantiene contexto de la conversación
- Decide qué preguntar y cuándo
- Busca objetivos automáticamente
- Propone acciones al usuario
"""

from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class ConversationState(Enum):
    """Estados posibles de la conversación."""
    INITIAL = "initial"  # Inicio, esperando imagen o ubicación
    LOCATION_DETECTED = "location_detected"  # Ubicación detectada, esperando destino
    GOAL_PROVIDED = "goal_provided"  # Objetivo proporcionado, listo para planificar
    PLANNING = "planning"  # Generando plan
    NAVIGATING = "navigating"  # Navegando activamente
    COMPLETE = "complete"  # Navegación completada
    ASK_BUILDING = "ask_building"  # Preguntando por el edificio
    ASK_FLOOR = "ask_floor"  # Preguntando por la planta


class ConversationContext:
    """
    Mantiene el contexto de la conversación con el usuario.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = ConversationState.INITIAL
        self.current_location: Optional[Dict[str, Any]] = None  # {building, floor, landmarks, resources}
        self.goal: Optional[Dict[str, Any]] = None  # {type: "functional"|"location", value: str|dict}
        self.conversation_history: List[Dict[str, str]] = []  # [{role: "user"|"system", message: str}]
        self.agent1_detection: Optional[Dict[str, Any]] = None  # Detección del Agente 1
    
    def add_message(self, role: str, message: str):
        """Añade un mensaje al historial de conversación."""
        self.conversation_history.append({
            "role": role,
            "message": message
        })
    
    def update_location(self, building: int, floor: int, landmarks: Optional[List[str]] = None, 
                       resources: Optional[List[str]] = None):
        """Actualiza la ubicación actual."""
        self.current_location = {
            "building": building,
            "floor": floor,
            "landmarks": landmarks or [],
            "resources": resources or []
        }
        self.state = ConversationState.LOCATION_DETECTED
    
    def set_goal(self, goal_type: str, goal_value: Any):
        """Establece el objetivo de navegación."""
        self.goal = {
            "type": goal_type,  # "functional" o "location"
            "value": goal_value
        }
        self.state = ConversationState.GOAL_PROVIDED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el contexto a diccionario para serialización."""
        return {
            "session_id": self.session_id,
            "state": self.state.value if isinstance(self.state, ConversationState) else str(self.state),
            "current_location": self.current_location,
            "goal": self.goal,
            "conversation_history": self.conversation_history,
            "agent1_detection": self.agent1_detection
        }


class ConversationAgent:
    """
    Agente conversacional que decide qué hacer según el contexto.
    """
    
    def __init__(self, campus_graph: Dict):
        self.campus_graph = campus_graph
        self.contexts: Dict[str, ConversationContext] = {}  # session_id -> context
    
    def get_or_create_context(self, session_id: str) -> ConversationContext:
        """Obtiene o crea un contexto de conversación."""
        if session_id not in self.contexts:
            self.contexts[session_id] = ConversationContext(session_id)
        return self.contexts[session_id]
    
    def process_user_message(self, session_id: str, user_message: str, 
                           image_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Procesa un mensaje del usuario y decide qué hacer.
        """
        context = self.get_or_create_context(session_id)
        context.add_message("user", user_message)
        
        user_message_lower = user_message.lower().strip()
        
        # Si hay análisis de imagen, actualizar ubicación
        if image_analysis and isinstance(image_analysis, dict):
            if image_analysis.get("success"):
                building = image_analysis.get("building")
                floor = image_analysis.get("floor")
                landmarks = image_analysis.get("landmarks")
                resources = image_analysis.get("resources")
                
                # Actualizar ubicación parcial o completa
                if building is not None or floor is not None:
                    current_loc = context.current_location if isinstance(context.current_location, dict) else None
                    current_building = current_loc.get("building") if current_loc else None
                    current_floor = current_loc.get("floor") if current_loc else None
                    
                    final_building = building if building is not None else current_building
                    final_floor = floor if floor is not None else current_floor
                    
                    context.update_location(final_building, final_floor, landmarks, resources)
                    context.agent1_detection = {
                        "building": final_building,
                        "floor": final_floor,
                        "landmarks": landmarks or [],
                        "resources": resources or []
                    }
        
        # Estado INITIAL
        if context.state == ConversationState.INITIAL:
            current_loc = context.current_location if isinstance(context.current_location, dict) else None
            has_building = current_loc is not None and current_loc.get("building") is not None
            has_floor = current_loc is not None and current_loc.get("floor") is not None
            
            if has_building and has_floor and current_loc:
                building_name = self._get_building_name(current_loc["building"])
                floor_num = current_loc["floor"]
                floor_text = "ground floor" if floor_num == 0 else f"floor {floor_num}"
                context.state = ConversationState.LOCATION_DETECTED
                return {
                    "response": f"I can see you're in {building_name}, {floor_text}. Where would you like to go?",
                    "action": "ask_goal",
                    "needs_input": True,
                    "context": context.to_dict(),
                    "auto_fill": {"building": current_loc["building"], "floor": floor_num}
                }
            elif has_floor and not has_building and current_loc:
                floor_num = current_loc["floor"]
                floor_text = "ground floor" if floor_num == 0 else f"floor {floor_num}"
                context.state = ConversationState.ASK_BUILDING
                return {
                    "response": f"I can see you're on {floor_text}. Which building are you in?",
                    "action": "ask_building",
                    "needs_input": True,
                    "context": context.to_dict(),
                    "auto_fill": {"floor": floor_num}
                }
            elif has_building and not has_floor and current_loc:
                building_name = self._get_building_name(current_loc["building"])
                context.state = ConversationState.ASK_FLOOR
                return {
                    "response": f"I can see you're in {building_name}. Which floor are you on?",
                    "action": "ask_floor",
                    "needs_input": True,
                    "context": context.to_dict(),
                    "auto_fill": {"building": current_loc["building"]}
                }
            elif any(word in user_message_lower for word in ["where", "location", "estoy", "dónde"]):
                return {
                    "response": "I need to know your current location. Could you please upload an image of a building sign or tell me which building and floor you're on?",
                    "action": "ask_location",
                    "needs_input": True,
                    "context": context.to_dict()
                }
            elif any(word in user_message_lower for word in ["go", "want", "need", "quiero", "ir"]):
                return self._handle_goal_request(context, user_message)
            else:
                return {
                    "response": "Hello! I can help you navigate the campus. Where are you now, or where would you like to go?",
                    "action": "greet",
                    "needs_input": True,
                    "context": context.to_dict()
                }
        
        # Estado LOCATION_DETECTED
        elif context.state == ConversationState.LOCATION_DETECTED:
            if context.goal and any(word in user_message_lower for word in ["yes", "sí", "ok", "okay", "please", "guide"]):
                context.state = ConversationState.GOAL_PROVIDED
                return {
                    "response": "Perfect! I'm generating your navigation plan now. Please wait a moment...",
                    "action": "generate_plan",
                    "needs_input": False,
                    "context": context.to_dict()
                }
            return self._handle_goal_request(context, user_message)
        
        # Estado ASK_BUILDING
        elif context.state == ConversationState.ASK_BUILDING:
            from api.planning_api import parse_location_from_paligemma_response
            parsed = parse_location_from_paligemma_response(user_message, self.campus_graph)
            if parsed.get("building"):
                building_id = parsed.get("building")
                current_loc = context.current_location if isinstance(context.current_location, dict) else None
                floor = current_loc.get("floor") if current_loc else None
                context.update_location(building_id, floor)
                building_name = self._get_building_name(building_id)
                context.state = ConversationState.LOCATION_DETECTED
                return {
                    "response": f"Got it! You're in {building_name}, floor {floor if floor is not None else '?'}. Where would you like to go?",
                    "action": "ask_goal",
                    "needs_input": True,
                    "context": context.to_dict(),
                    "auto_fill": {"building": building_id, "floor": floor}
                }
            else:
                return {
                    "response": "I couldn't understand which building. Could you please specify the building name (e.g., EPS, CD, H)?",
                    "action": "ask_building",
                    "needs_input": True,
                    "context": context.to_dict()
                }
        
        # Estado ASK_FLOOR
        elif context.state == ConversationState.ASK_FLOOR:
            from api.planning_api import parse_location_from_paligemma_response
            parsed = parse_location_from_paligemma_response(user_message, self.campus_graph)
            if parsed.get("floor") is not None:
                floor = parsed.get("floor")
                current_loc = context.current_location if isinstance(context.current_location, dict) else None
                building_id = current_loc.get("building") if current_loc else None
                context.update_location(building_id, floor)
                building_name = self._get_building_name(building_id) if building_id else "Unknown"
                context.state = ConversationState.LOCATION_DETECTED
                return {
                    "response": f"Got it! You're in {building_name}, floor {floor}. Where would you like to go?",
                    "action": "ask_goal",
                    "needs_input": True,
                    "context": context.to_dict(),
                    "auto_fill": {"building": building_id, "floor": floor}
                }
            else:
                return {
                    "response": "I couldn't understand the floor number. Could you please specify the floor (e.g., 0, 1, 2, -1)?",
                    "action": "ask_floor",
                    "needs_input": True,
                    "context": context.to_dict()
                }
        
        # Estado GOAL_PROVIDED
        elif context.state == ConversationState.GOAL_PROVIDED:
            confirmation_keywords = ["yes", "sí", "ok", "okay", "start", "empezar", "vamos", 
                "please", "guide", "take", "lead", "show", "help", "go", "sure", "alright", "correct", "right", "yeah", "yep"]
            negation_keywords = ["no", "cancel", "cancelar", "stop", "don't", "dont", "not"]
            
            is_confirmation = any(keyword in user_message_lower for keyword in confirmation_keywords)
            is_negation = any(keyword in user_message_lower for keyword in negation_keywords)
            
            if is_confirmation and not is_negation:
                return {
                    "response": "Perfect! I'm generating your navigation plan now. Please wait a moment...",
                    "action": "generate_plan",
                    "needs_input": False,
                    "context": context.to_dict()
                }
            elif is_negation:
                context.goal = None
                context.state = ConversationState.LOCATION_DETECTED
                return {
                    "response": "Okay, let's start over. Where would you like to go?",
                    "action": "ask_goal",
                    "needs_input": True,
                    "context": context.to_dict()
                }
            else:
                goal_keywords_in_message = any(word in user_message_lower for word in 
                    ["cafeteria", "gym", "gimnasio", "library", "biblioteca", "building", "floor", "edificio", "planta"])
                
                if goal_keywords_in_message:
                    return self._handle_goal_request(context, user_message)
                else:
                    if len(user_message_lower.strip()) <= 20:
                        return {
                            "response": "Perfect! I'm generating your navigation plan now. Please wait a moment...",
                            "action": "generate_plan",
                            "needs_input": False,
                            "context": context.to_dict()
                        }
                    else:
                        return {
                            "response": "Would you like me to generate the navigation plan to your destination? Please say 'yes' to continue or 'no' to choose a different destination.",
                            "action": "confirm_plan",
                            "needs_input": True,
                            "context": context.to_dict()
                        }
        
        # Estado desconocido
        else:
            return {
                "response": "I'm ready to help. What would you like to do?",
                "action": "unknown",
                "needs_input": True,
                "context": context.to_dict()
            }
    
    def _handle_goal_request(self, context: ConversationContext, user_message: str) -> Dict[str, Any]:
        """
        Maneja una solicitud de objetivo del usuario.
        """
        from navigation.agents import Agent2_Searcher
        
        user_message_lower = user_message.lower()
        
        goal_keywords = {
            "cafeteria": ["cafeteria", "cafetería", "cafe"],
            "gimnasio": ["gym", "gimnasio", "gymnasium"],
            "biblioteca": ["library", "biblioteca", "lib"]
        }
        
        goal_type = None
        goal_name = None
        
        for goal, keywords in goal_keywords.items():
            if any(keyword in user_message_lower for keyword in keywords):
                goal_type = "functional"
                goal_name = goal
                break
        
        if goal_type == "functional" and goal_name:
            goal_building, goal_floor, source = Agent2_Searcher.search_goal(
                goal_name,
                agent1_detection=context.agent1_detection,
                campus_graph=self.campus_graph
            )
            
            if goal_building is not None and goal_floor is not None:
                context.set_goal("functional", goal_name)
                context.state = ConversationState.GOAL_PROVIDED
                
                building_name = "Unknown"
                for b in self.campus_graph.get("buildings", []):
                    if b.get("id") == goal_building:
                        building_name = b.get("name", f"Building {goal_building}")
                        break
                
                floor_text = "ground floor" if goal_floor == 0 else f"floor {goal_floor}"
                source_text = "the image you showed me" if source == "image" else "the campus database"
                
                context.add_message("system", f"Found {goal_name} at {building_name}, {floor_text} (from {source_text})")
                
                return {
                    "response": f"I found the {goal_name} at {building_name}, {floor_text}. Would you like me to guide you there?",
                    "action": "goal_found",
                    "needs_input": True,
                    "goal_location": {"building": goal_building, "floor": goal_floor},
                    "context": context.to_dict(),
                    "auto_fill_goal": {"building": goal_building, "floor": goal_floor, "functional": goal_name}
                }
            else:
                return {
                    "response": f"I couldn't find the {goal_name} in the campus. Could you please specify the building and floor?",
                    "action": "goal_not_found",
                    "needs_input": True,
                    "context": context.to_dict()
                }
        else:
            # Intentar parsear como ubicación
            from api.planning_api import parse_location_from_paligemma_response
            parsed = parse_location_from_paligemma_response(user_message, self.campus_graph)
            
            if parsed.get("building") and parsed.get("floor") is not None:
                goal_building = parsed.get("building")
                goal_floor = parsed.get("floor")
                context.set_goal("location", {"building": goal_building, "floor": goal_floor})
                
                building_name = "Unknown"
                for b in self.campus_graph.get("buildings", []):
                    if b.get("id") == goal_building:
                        building_name = b.get("name", f"Building {goal_building}")
                        break
                
                context.add_message("system", f"Destination: {building_name}, floor {goal_floor}")
                context.state = ConversationState.GOAL_PROVIDED
                
                return {
                    "response": f"Got it! You want to go to {building_name}, floor {goal_floor}. Should I generate the navigation plan?",
                    "action": "goal_found",
                    "needs_input": True,
                    "goal_location": {"building": goal_building, "floor": goal_floor},
                    "context": context.to_dict(),
                    "auto_fill_goal": {"building": goal_building, "floor": goal_floor}
                }
            else:
                return {
                    "response": "I couldn't understand where you want to go. Could you please specify a location (like 'cafeteria', 'gym', or 'Building H, floor 2')?",
                    "action": "ask_goal_clarification",
                    "needs_input": True,
                    "context": context.to_dict()
                }
    
    def _get_building_name(self, building_id: int) -> str:
        """Obtiene el nombre del edificio por su ID."""
        for b in self.campus_graph.get("buildings", []):
            if b.get("id") == building_id:
                return b.get("name", f"Building {building_id}")
        return f"Building {building_id}"
    
    def generate_plan_request(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Genera un request de planificación basado en el contexto actual.
        """
        context = self.get_or_create_context(session_id)
        
        current_loc = context.current_location if isinstance(context.current_location, dict) else None
        if not current_loc or not context.goal:
            return None
        
        request = {
            "initial_state": {
                "building": current_loc["building"],
                "floor": current_loc["floor"]
            },
            "humano_disponible": True
        }
        
        if context.goal["type"] == "functional":
            request["goal_functional"] = context.goal["value"]
        else:
            request["goal_state"] = context.goal["value"]
        
        return request
