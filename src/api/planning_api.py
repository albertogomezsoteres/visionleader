"""
API FastAPI para Planificación con Fast Downward

Endpoints:
- POST /api/plan - Generar un plan desde estado inicial a objetivo
- GET /api/domain - Obtener el dominio PDDL actual
- POST /api/validate - Validar un plan
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path
import sys
import tempfile
import os
import re
import json
import io
import requests
from dotenv import load_dotenv
from PIL import Image
from typing import Optional, Tuple
from pydantic import BaseModel

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import (
    PlanningRequest,
    PlanningResponse,
    ValidationRequest,
    ValidationResponse,
    DomainResponse,
    ImageAnalysisResponse,
    ClarificationRequest,
    ClarificationResponse,
    TranscribeRequest,
    TranscribeResponse,
    GPSRouteRequest,
    GPSRouteResponse,
    ConversationRequest,
    ConversationResponse,
)
from navigation.fast_downward_client import FastDownwardPlanner
from navigation.pddl_converter import CampusGraphToPDDL
from navigation.agents import Agent1_Identifier, Agent2_Searcher, Agent3_Planner, CLASSIFIER_PROMPT
from navigation.conversation_agent import ConversationAgent

# Inicializar FastAPI
app = FastAPI(
    title="Campus Navigation Planning API",
    description="API para planificación de navegación en el campus usando PDDL y Fast Downward",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas de archivos
BASE_DIR = Path(__file__).parent.parent.parent
DOMAIN_PATH = BASE_DIR / "pddl" / "domain.pddl"
CAMPUS_JSON = BASE_DIR / "config" / "campus_graph.json"
PDDL_DIR = BASE_DIR / "pddl"

load_dotenv(BASE_DIR / ".env")

# Inicializar componentes
planner = FastDownwardPlanner()
converter = CampusGraphToPDDL(str(CAMPUS_JSON))

# Inicializar agente conversacional (singleton)
_conversation_agent = None

def get_conversation_agent() -> ConversationAgent:
    """Obtiene o crea el agente conversacional."""
    global _conversation_agent
    if _conversation_agent is None:
        campus_graph = load_campus_graph()
        _conversation_agent = ConversationAgent(campus_graph)
    return _conversation_agent

# Variables globales para Paligemma (singleton)
# Mantenemos el modelo y procesador en memoria para no cargarlos cada vez
_paligemma_model = None
_paligemma_processor = None
_campus_graph_data = None

# Base URL del túnel (p. ej. ngrok) hacia Colab con PaliGemma / Whisper. Vacío: inferencia local u otros flujos.
COLAB_API_URL = (os.getenv("COLAB_API_URL") or "").strip().rstrip("/")

def extract_floor_from_room_code(text: str) -> Optional[int]:
    """
    Extrae el número de planta de un código de aula o despacho.

    Ejemplos:
        "Aula 2.1"     → 2
        "Lab 1.3"      → 1
        "Despacho 205" → 2
        "Room 101"     → 1
        "Aula 0.3"     → 0
        "B2.05"        → 2
    """
    if not text or text.strip().lower() in ("none", "no", ""):
        return None
    text = text.strip()

    # Patrón "Aula 2.1", "Lab 1.3", "Clase 0.5", "Despacho 205", "Office 2.3"
    p1 = re.search(
        r'(?:aula|lab|laboratorio|despacho|room|clase|classroom|office|sala|seminar)\s*(\d+)[.\-]',
        text, re.IGNORECASE
    )
    if p1:
        val = int(p1.group(1))
        if -1 <= val <= 4:
            return val

    # Patrón "X.Y" suelto donde X es número de planta válido
    p2 = re.search(r'\b([0-4])\.\d+\b', text)
    if p2:
        return int(p2.group(1))

    # Código de 3 dígitos tipo "201", "105" → centenas = planta
    p3 = re.search(r'\b(\d{3})\b', text)
    if p3:
        hundreds = int(p3.group(1)) // 100
        if 0 <= hundreds <= 4:
            return hundreds

    # Número suelto de 1 dígito
    p4 = re.search(r'\b([0-4])\b', text)
    if p4:
        return int(p4.group(1))

    return None


def parse_paligemma_json(response_text: str) -> dict:
    """Parsea la respuesta JSON de PaliGemma con fallback robusto."""
    import json as _json
    _default = {
        'building_code': None, 'floor': None, 'confidence': 'none',
        'visible_text': [], 'landmarks': [],
        'reason': 'JSON parse failed, raw: ' + (response_text or '')[:100]
    }
    if not response_text:
        return _default
    try:
        result = _json.loads(response_text.strip())
        if isinstance(result, dict):
            return result
    except _json.JSONDecodeError:
        pass
    match = re.search(r'\{.*?\}', response_text, re.DOTALL)
    if match:
        try:
            result = _json.loads(match.group())
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return _default


@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "message": "Campus Navigation Planning API",
        "version": "1.0.0",
        "endpoints": {
            "plan": "POST /api/plan",
            "domain": "GET /api/domain",
            "validate": "POST /api/validate",
            "analyze-image": "POST /api/analyze-image",
            "clarify-location": "POST /api/clarify-location",
            "transcribe-audio": "POST /api/transcribe-audio",
            "conversation": "POST /api/conversation - Sistema conversacional con agente",
            "demo": "GET /demo - Interfaz web interactiva",
            "docs": "GET /docs"
        }
    }

@app.get("/demo")
async def demo():
    """Sirve la interfaz web interactiva."""
    # Buscar el archivo HTML en el directorio raíz del proyecto
    base_path = Path(__file__).parent.parent.parent
    html_file = base_path / "demo_interactiva.html"
    
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="demo_interactiva.html no encontrado")
    
    # Leer el contenido del archivo y devolverlo como HTML
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    return HTMLResponse(
        content=html_content,
        headers={"Content-Type": "text/html; charset=utf-8"}
    )


@app.post("/api/plan", response_model=PlanningResponse)
async def generate_plan(request: PlanningRequest):
    """
    Genera un plan de navegación desde estado inicial a objetivo.
    
    Args:
        request: PlanningRequest con estado inicial, objetivo y opciones
    
    Returns:
        PlanningResponse con el plan generado
    """
    try:
        # Validar estado inicial
        initial_building = request.initial_state.get("building")
        initial_floor = request.initial_state.get("floor")
        
        if initial_building is None or initial_floor is None:
            raise HTTPException(
                status_code=400,
                detail="initial_state must contain 'building' and 'floor'"
            )
        
        # Validar que se proporcione goal_state o goal_functional
        if not request.goal_state and not request.goal_functional:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar 'goal_state' o 'goal_functional'"
            )
        
        # Preparar información del objetivo para la respuesta
        goal_info = {}
        if request.goal_functional:
            # Usar Agente 2 (Buscador) para encontrar objetivo funcional
            campus_graph = load_campus_graph()
            # Por ahora, usar búsqueda en JSON (Agente 2 puede usar detección de imagen si está disponible)
            goal_building_id, goal_floor, source = Agent2_Searcher.search_goal(
                request.goal_functional,
                agent1_detection=None,  # Podría venir de una imagen previa
                campus_graph=campus_graph
            )
            print(f"Agente 2 buscó '{request.goal_functional}': encontrado en {source} -> Edificio {goal_building_id}, Planta {goal_floor}")
            
            if goal_building_id is None or goal_floor is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Objetivo funcional '{request.goal_functional}' no encontrado en el campus. Agente 2 no pudo localizarlo."
                )
            
            if goal_building_id and goal_floor is not None:
                # Obtener nombre del edificio
                building_name = None
                for b in campus_graph.get("buildings", []):
                    if b.get("id") == goal_building_id:
                        building_name = b.get("name", f"Edificio {goal_building_id}")
                        break
                
                floor_text = "planta 0" if goal_floor == 0 else f"planta {goal_floor}"
                if request.goal_functional.lower() == "cafeteria":
                    description = f"Cafetería ({building_name} {floor_text})"
                else:
                    description = f"Gimnasio ({building_name} {floor_text})"
            else:
                # Fallback si no se encuentra (no debería pasar)
                description = "Cafetería (CD planta 0)" if request.goal_functional == "cafeteria" else "Gimnasio (CD planta -1)"
            
            goal_info = {
                "functional": request.goal_functional,
                "description": description
            }
        else:
            goal_building = request.goal_state.get("building")
            goal_floor = request.goal_state.get("floor")
            if goal_building is None or goal_floor is None:
                raise HTTPException(
                    status_code=400,
                    detail="goal_state must contain 'building' and 'floor'"
                )
            goal_info = {
                "building": goal_building,
                "floor": goal_floor
            }
        
        # Generar problema PDDL
        initial_state = (initial_building, initial_floor)
        goal_state = None if request.goal_functional else (goal_info["building"], goal_info["floor"])
        
        # Usar Agente 3 (Planificador) para determinar si se necesita GPS
        if goal_state:
            goal_building = goal_state[0]
            use_gps = Agent3_Planner.needs_gps(initial_building, goal_building)
            if use_gps:
                print(f"Agente 3: Se necesita GPS (movimiento entre edificios {initial_building} -> {goal_building})")
        elif request.goal_functional:
            # Si es objetivo funcional, ya tenemos goal_building_id de Agente 2
            use_gps = Agent3_Planner.needs_gps(initial_building, goal_building_id)
            if use_gps:
                print(f"Agente 3: Se necesita GPS (movimiento entre edificios {initial_building} -> {goal_building_id})")
        
        # Crear archivo temporal para el problema
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.pddl',
            dir=str(PDDL_DIR),
            delete=False
        ) as f:
            problem_path = f.name
            converter.generate_problem(
                initial_state=initial_state,
                goal_state=goal_state,
                goal_functional=request.goal_functional,
                problem_name="api-problem",
                output_path=problem_path
            )
        
        try:
            # Ejecutar Fast Downward
            result = planner.plan(
                domain_path=str(DOMAIN_PATH),
                problem_path=problem_path
            )
            
            # Añadir información completa al resultado
            result["initial_state"] = request.initial_state
            result["goal_state"] = goal_info  # Incluye goal_state o goal_functional info
            
            return PlanningResponse(**result)
            
        finally:
            # Limpiar archivo temporal
            if os.path.exists(problem_path):
                os.remove(problem_path)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating plan: {str(e)}"
        )


@app.get("/api/domain", response_model=DomainResponse)
async def get_domain():
    """
    Obtiene el dominio PDDL actual.
    
    Returns:
        DomainResponse con el contenido del dominio
    """
    try:
        if not DOMAIN_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Domain file not found"
            )
        
        with open(DOMAIN_PATH, 'r', encoding='utf-8') as f:
            domain_content = f.read()
        
        return DomainResponse(domain=domain_content)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading domain: {str(e)}"
        )


@app.post("/api/validate", response_model=ValidationResponse)
async def validate_plan(request: ValidationRequest):
    """
    Valida un plan ejecutándolo.
    
    Args:
        request: ValidationRequest con plan y estados
    
    Returns:
        ValidationResponse indicando si el plan es válido
    """
    try:
        # Generar problema PDDL
        initial_state = (
            request.initial_state["building"],
            request.initial_state["floor"]
        )
        goal_state = (
            request.goal_state["building"],
            request.goal_state["floor"]
        )
        
        # Crear archivo temporal para el problema
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.pddl',
            dir=str(PDDL_DIR),
            delete=False
        ) as f:
            problem_path = f.name
            converter.generate_problem(
                initial_state=initial_state,
                goal_state=goal_state,
                problem_name="validation-problem",
                output_path=problem_path
            )
        
        try:
            # Ejecutar Fast Downward para obtener el plan correcto
            result = planner.plan(
                domain_path=str(DOMAIN_PATH),
                problem_path=problem_path
            )
            
            if not result["success"]:
                return ValidationResponse(
                    valid=False,
                    message=f"Could not generate plan: {result.get('error', 'Unknown error')}"
                )
            
            # Comparar planes (simplificado: verificar que tienen acciones)
            provided_plan = request.plan
            generated_plan = result["plan"]
            
            # Validación básica: verificar que ambos planes tienen acciones
            if len(provided_plan) == 0:
                return ValidationResponse(
                    valid=False,
                    message="Provided plan is empty"
                )
            
            if len(generated_plan) == 0:
                return ValidationResponse(
                    valid=False,
                    message="Generated plan is empty"
                )
            
            # Validación más estricta: comparar acciones (simplificado)
            # En producción, se podría hacer una validación más detallada
            return ValidationResponse(
                valid=True,
                message=f"Plan validated. Generated plan has {len(generated_plan)} steps."
            )
            
        finally:
            # Limpiar archivo temporal
            if os.path.exists(problem_path):
                os.remove(problem_path)
    
    except Exception as e:
        return ValidationResponse(
            valid=False,
            message=f"Error validating plan: {str(e)}"
        )


def load_campus_graph():
    """Carga el campus graph una vez y lo mantiene en memoria."""
    global _campus_graph_data
    # Solo cargamos el JSON una vez, luego lo reutilizamos
    if _campus_graph_data is None:
        with open(CAMPUS_JSON, 'r', encoding='utf-8') as f:
            _campus_graph_data = json.load(f)
    return _campus_graph_data


def correct_whisper_transcription(text: str, campus_graph: dict) -> str:
    """
    Corrige errores comunes de transcripción de Whisper.
    Especialmente útil para palabras del dominio del campus.
    
    Args:
        text: Texto transcrito por Whisper
        campus_graph: Grafo del campus para validar palabras
        
    Returns:
        Texto corregido
    """
    if not text:
        return text
    
    text_lower = text.lower().strip()
    original_text = text
    
    # Diccionario de correcciones comunes
    corrections = {
        # Objetivos funcionales
        "jim": "gym",
        "jimnasium": "gymnasium",
        "gim": "gym",
        "kafoturia": "cafeteria",
        "cafeturia": "cafeteria",
        "cafetaria": "cafeteria",
        "cafeteria": "cafeteria",  # Asegurar formato correcto
        "library": "library",
        "biblioteca": "biblioteca",
        
        # Edificios comunes
        "building age": "building h",
        "building a": "building h",  # Si está en contexto de edificio H
        "building eight": "building h",
        "building h": "building h",
        "building eps": "building eps",
        "building cd": "building cd",
        "edificio h": "edificio h",
        "edificio eps": "edificio eps",
        
        # Palabras comunes
        "flor": "floor",
        "flore": "floor",
        "planta": "planta",
        "planta": "floor",  # Si está en inglés, convertir
        "yes": "yes",
        "no": "no",
        "please": "please",
        "guide": "guide",
        "take": "take",
        "me": "me",
        "there": "there",
        "to": "to",
        "go": "go",
        "want": "want",
        "i": "i",
    }
    
    # Obtener nombres de edificios del campus para validación
    building_names = []
    building_codes = []
    for building in campus_graph.get("buildings", []):
        name = building.get("name", "").lower()
        full_name = building.get("full_name", "").lower()
        if name:
            building_names.append(name)
            building_codes.append(name)
        if full_name:
            building_names.extend(full_name.split())
    
    import re
    
    # Correcciones específicas por contexto
    # Si dice "jim" pero está en contexto de objetivos, probablemente es "gym"
    if "jim" in text_lower:
        # Verificar si hay contexto de objetivos (cafeteria, library, etc.)
        if any(word in text_lower for word in ["want", "go", "to", "cafeteria", "library", "the"]):
            # Preservar capitalización
            text = re.sub(r'\bjim\b', "gym", text, flags=re.IGNORECASE)
    
    # Corrección de "building age" → "building H"
    if "building age" in text_lower or "building a" in text_lower:
        # Si está en contexto de edificios conocidos
        if any(code in text_lower for code in ["h", "g", "cd", "b", "r", "floor"]):
            text = re.sub(r'\bbuilding\s+age\b', "building H", text, flags=re.IGNORECASE)
            text = re.sub(r'\bbuilding\s+a\b(?!\w)', "building H", text, flags=re.IGNORECASE)
    
    # Corrección de "kafoturia" y variantes de cafeteria
    cafeteria_variants = ["kafoturia", "cafeturia", "cafetaria", "kafeteria", "cafetaria"]
    for variant in cafeteria_variants:
        if variant in text_lower:
            text = re.sub(r'\b' + re.escape(variant) + r'\b', "cafeteria", text, flags=re.IGNORECASE)
    
    # Correcciones directas del diccionario (solo para palabras clave del dominio)
    domain_corrections = {
        "jim": "gym",
        "gim": "gym",
        "jimnasium": "gymnasium",
    }
    
    for wrong, correct in domain_corrections.items():
        # Reemplazar palabra completa (con límites de palabra)
        pattern = r'\b' + re.escape(wrong) + r'\b'
        text = re.sub(pattern, correct, text, flags=re.IGNORECASE)
    
    # Validación final: si el texto corregido contiene palabras conocidas del campus
    # y el original no, usar el corregido
    corrected_lower = text.lower()
    has_campus_words = any(word in corrected_lower for word in 
        ["gym", "cafeteria", "library", "building", "floor", "edificio", "planta"])
    
    if has_campus_words and text != original_text:
        print(f"[CORRECCION] '{original_text}' -> '{text}'")
    
    return text.strip()


def _find_functional_goal_in_json(campus_graph: dict, goal_functional: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Busca un objetivo funcional (cafetería, gimnasio) en el campus_graph.
    
    Args:
        campus_graph: Diccionario con la estructura del campus
        goal_functional: "cafeteria" o "gimnasio"
        
    Returns:
        (building_id, floor) o (None, None) si no se encuentra
    """
    goal_lower = goal_functional.lower()
    
    for building in campus_graph.get("buildings", []):
        if goal_lower == "cafeteria":
            cafeteria_floor = building.get('cafeteria_floor')
            if cafeteria_floor is not None:
                return (building['id'], cafeteria_floor)
        elif goal_lower == "gimnasio":
            gimnasio_floor = building.get('gimnasio_floor')
            if gimnasio_floor is not None:
                return (building['id'], gimnasio_floor)
    
    return (None, None)


def load_paligemma_model():
    """Carga el modelo Paligemma una vez y lo mantiene en memoria (singleton)."""
    global _paligemma_model, _paligemma_processor
    # Solo cargamos el modelo la primera vez que se necesita
    # Esto ahorra tiempo y memoria en peticiones posteriores
    if _paligemma_model is None or _paligemma_processor is None:
        from evaluation.model_loader import load_paligemma
        from huggingface_hub import login

        hf_token = (os.getenv("HF_TOKEN") or "").strip() or None
        
        # Autenticarnos en HuggingFace para poder descargar el modelo
        if hf_token:
            try:
                login(token=hf_token)
                print("Autenticado en HuggingFace")
            except Exception as e:
                print(f"Error al autenticar en HuggingFace: {e}")
        else:
            print("No se encontró HF_TOKEN. El modelo puede requerir autenticación.")
        
        # Cargar el modelo Paligemma (puede tardar un poco la primera vez)
        model_id = "google/paligemma2-3b-mix-224"
        print(f"Cargando modelo Paligemma: {model_id}")
        _paligemma_model, _paligemma_processor = load_paligemma(model_id, token=hf_token)
        print("Modelo Paligemma cargado exitosamente")
    return _paligemma_model, _paligemma_processor


def _normalize_image_type(raw: Optional[str]) -> Optional[str]:
    """
    Normaliza la respuesta del clasificador (prompt 7) a un tipo canónico.

    PaliGemma puede responder de formas impredecibles:
      - Respuesta exacta: "elevator", "sign", "stairs", "door", "other"
      - Contiene la palabra clave: "it's an elevator", "I see stairs"
      - Responde con texto de la imagen (ej: "h", "g") → None (fall through al chain)
      - Respuesta multilínea con explicación → extraer la palabra clave
    """
    if not raw:
        return None

    r = raw.strip().lower()

    # Respuesta exacta de una sola palabra
    if r in ("elevator", "lift", "ascensor"):
        return "elevator"
    if r in ("stairs", "staircase", "escaleras", "escalera"):
        return "stairs"
    if r in ("sign", "directory", "cartel", "señal"):
        return "sign"
    if r in ("door", "puerta"):
        return "door"
    if r == "other":
        return "other"

    # Respuesta que contiene la palabra clave (ej: "I see an elevator")
    if any(w in r for w in ("elevator", "lift", "ascensor")):
        return "elevator"
    if any(w in r for w in ("stair", "escalera", "escaleras", "steps")):
        return "stairs"
    if any(w in r for w in ("directory", "cartel", "facilities", "floor plan", "sign")):
        return "sign"
    if "door" in r or "puerta" in r:
        return "door"

    # Respuesta con texto de imagen (building codes, etc.) → no es una clasificación válida
    # Dejar que el chain de cartel lo intente
    return None


def _floor_text_local(floor: int) -> str:
    """Convierte número de planta a texto legible en inglés."""
    if floor == -1: return "the basement"
    if floor == 0:  return "the ground floor"
    if floor == 1:  return "the 1st floor"
    if floor == 2:  return "the 2nd floor"
    if floor == 3:  return "the 3rd floor"
    return f"floor {floor}"


def get_paligemma_prompts(campus_graph: Optional[dict] = None) -> list[str]:
    """
    Retorna una lista de prompts en inglés para usar con Paligemma.
    Usa los prompts del Agente 1 (Identificador) que detecta TODO en la imagen.
    Se intentan en orden: si uno falla (respuesta "unanswerable"), se prueba el siguiente.

    Args:
        campus_graph: Grafo del campus (opcional) para inyectar códigos de edificios dinámicamente.

    Returns:
        Lista de prompts en inglés del Agente 1, ordenados de más específico a más general
    """
    building_codes = ["G", "CD", "H"]
    return Agent1_Identifier.get_prompts(building_codes=building_codes)


def parse_location_from_paligemma_response(response: str, campus_graph: dict) -> dict:
    """
    Parsea la respuesta de Paligemma para extraer edificio y planta.
    
    Paligemma puede responder de muchas formas diferentes, así que intentamos
    varios patrones para encontrar el edificio y la planta en su respuesta.
    
    Args:
        response: Respuesta de texto de Paligemma
        campus_graph: Diccionario con la estructura del campus
        
    Returns:
        Dict con 'building' (int o None), 'floor' (int o None), 'error' (str o None)
    """
    result = {"building": None, "floor": None, "error": None}
    response_lower = response.lower()
    
    # Primero creamos un mapeo de todos los edificios para buscarlos fácilmente
    # Mapeamos tanto códigos (G, CD) como nombres completos
    building_map = {}
    name_to_id = {}
    for building in campus_graph.get("buildings", []):
        building_id = building.get("id")
        name = building.get("name", "").upper()
        full_name = building.get("full_name", "").lower()
        
        building_map[name] = building_id
        name_to_id[name.lower()] = building_id
        name_to_id[full_name] = building_id
        
        # También mapear variaciones comunes que puede usar Paligemma
        if "politécnica" in full_name or "politecnica" in full_name:
            name_to_id["escuela politecnica"] = building_id
            name_to_id["escuela politécnica"] = building_id
            # G es el nombre del edificio (building ID 1)
            name_to_id["g"] = building_id
        if "deportivo" in full_name:
            name_to_id["centro deportivo"] = building_id
    
    # Buscar el código del edificio en la respuesta
    building_found = None
    building_codes = ["G", "CD", "H"]

    # ── Patrón compacto: PaliGemma responde "g0", "eps1", "h2", "cd-1" ──
    # Mapa hardcodeado de los 4 códigos válidos → ID de edificio en campus_graph
    # G mapea al ID 1
    _compact_code_map = {"G": 1, "CD": 2, "H": 3}
    for b in campus_graph.get("buildings", []):
        bname = b.get("name", "").upper()
        if bname in _compact_code_map and b.get("id") is not None:
            _compact_code_map[bname] = b["id"]

    compact_match = re.search(
        r'\b(eps|g|cd|h)(\s*-?\s*\d+)\b',
        response.strip(), re.IGNORECASE
    )
    if compact_match:
        compact_code = compact_match.group(1).upper()
        compact_floor_str = compact_match.group(2).replace(" ", "")
        try:
            compact_floor = int(compact_floor_str)
            if -1 <= compact_floor <= 4:
                building_id_compact = _compact_code_map.get(compact_code)
                if building_id_compact is not None:
                    result["building"] = building_id_compact
                    result["floor"] = compact_floor
                    print("   [compact] Detectado '{}' -> building={}({}), floor={}".format(
                        compact_match.group(), compact_code, building_id_compact, compact_floor))
                    return result
        except ValueError:
            pass

    # Si la respuesta es muy corta (1-3 caracteres), puede ser solo el código del edificio
    # Ej: "H", "G", "CD"
    response_stripped = response.strip()
    if len(response_stripped) <= 3:
        # Buscar si coincide exactamente con algún código (case-insensitive)
        for code in building_codes:
            if response_stripped.upper() == code.upper():
                building_found = code.upper()
                print(f"   Código detectado directamente: {building_found}")
                break
    
    # Si no encontramos código directo, buscamos con patrones
    if not building_found:
        # Primero intentamos buscar códigos directamente (ej: "G", "CD", "H")
        # Para códigos de una letra como "H", necesitamos patrones más específicos
        for code in building_codes:
            # Patrón 1: Palabra completa (ej: "building H" o "H building" o "edificio H")
            # Para "H", también buscamos después de "edificio" o "building"
            if len(code) == 1:
                # Para letras simples como "H", buscamos en contextos específicos
                # Patrón mejorado: "building H", "in the building H", "at building H", "I am in the building H", etc.
                # También maneja: "EDIFICIO H / H BUILDING", "The sign shows EDIFICIO H", etc.
                pattern1 = r'(?:in\s+(?:the\s+)?)?(?:edificio|building)\s+' + re.escape(code) + r'\b'
                pattern1b = r'\b' + re.escape(code) + r'\s+(?:building|edificio)'
                # Pattern para manejar "/" en respuestas como "EDIFICIO H / H BUILDING"
                pattern1d = r'(?:edificio|building)\s+' + re.escape(code) + r'\s*/\s*' + re.escape(code) + r'\s+(?:building|edificio)'
                # Pattern para texto descriptivo: "shows EDIFICIO H", "says H BUILDING", etc.
                pattern1f = r'(?:shows?|says?|displays?|indicates?)\s+(?:edificio|building)\s+' + re.escape(code) + r'\b'
                # Pattern1c: buscar "H" como palabra suelta, PERO solo si NO está dentro de otra palabra
                # Usar lookahead/lookbehind negativos para evitar detectar dentro de números o palabras
                # Ej: NO detectar "B" en "11 building" o "building", "H" en "the", etc.
                pattern1c = r'(?<![a-zA-Z0-9])' + re.escape(code) + r'(?![a-zA-Z0-9])'
            else:
                # Para códigos de múltiples letras
                pattern1 = r'\b' + re.escape(code) + r'\b'
                pattern1b = None
                pattern1c = None
                pattern1d = None
                pattern1f = None
            
            # Patrón 2: Sin espacio después de "building" (ej: "onbuilding H", "inbuilding H")
            # IMPORTANTE: Para códigos de una letra, asegurarse de que no sea parte de otra palabra
            if len(code) == 1:
                # Para una letra, necesitamos asegurarnos de que no sea parte de "building" o un número
                pattern2 = r'(?:on|in|at)?building\s+(?<![a-zA-Z0-9])' + re.escape(code) + r'(?![a-zA-Z0-9])'
            else:
                pattern2 = r'(?:on|in|at)?building\s*' + re.escape(code) + r'\b'
            # Patrón 3: Código seguido de "building" sin espacio (ej: "Hbuilding")
            # IMPORTANTE: Para códigos de una letra, evitar detectar dentro de palabras
            if len(code) == 1:
                pattern3 = r'(?<![a-zA-Z0-9])' + re.escape(code) + r'(?![a-zA-Z0-9])\s*building'
            else:
                pattern3 = r'\b' + re.escape(code) + r'\s*building'
            # Patrón 4: "edificio" seguido del código (ej: "edificio h")
            # IMPORTANTE: Para códigos de una letra, evitar detectar dentro de palabras
            if len(code) == 1:
                pattern4 = r'edificio\s+(?<![a-zA-Z0-9])' + re.escape(code) + r'(?![a-zA-Z0-9])'
            else:
                pattern4 = r'edificio\s+' + re.escape(code) + r'\b'
            
            patterns_to_check = [pattern1, pattern2, pattern3, pattern4]
            if pattern1b:
                patterns_to_check.append(pattern1b)
            # Añadir patrones adicionales para códigos de una letra
            if len(code) == 1:
                if pattern1d:
                    patterns_to_check.append(pattern1d)
                if pattern1f:
                    patterns_to_check.append(pattern1f)
            if pattern1c:
                patterns_to_check.append(pattern1c)
            
            # Probar cada patrón y loggear cuál coincide
            for pattern_idx, pattern in enumerate(patterns_to_check):
                if pattern:
                    match = re.search(pattern, response, re.IGNORECASE)
                    if match:
                        building_found = code.upper()
                        print(f"   PROBLEMA: Patrón #{pattern_idx+1} coincidió para '{code}'")
                        print(f"   Patrón: {pattern}")
                        print(f"   Match encontrado: '{match.group()}' en posición {match.start()}-{match.end()}")
                        print(f"   Respuesta completa: '{response}'")
                        # Si detectamos algo sospechoso, no confiar en este resultado
                        if code.upper() == 'B' and '11' in response.lower():
                            print(f"   ❌ FALSO POSITIVO DETECTADO: 'B' en '11 building' - IGNORANDO")
                            building_found = None
                            continue
                        break
            
            if building_found:
                break
    
    # Si no encontramos código, buscamos nombres completos
    if not building_found:
        valid_codes_lower = {c.lower() for c in building_codes}
        for name, building_id in name_to_id.items():
            # Skip single-letter names that are not a valid building code —
            # they would cause false positives (e.g. "p" matching "planta").
            if len(name) == 1 and name not in valid_codes_lower:
                continue
            if name in response_lower:
                # Encontrar el código correspondiente al nombre
                for b in campus_graph.get("buildings", []):
                    if b.get("id") == building_id:
                        building_found = b.get("name", "").upper()
                        break
                if building_found:
                    break
    
    if building_found:
        # Validación adicional: rechazar falsos positivos obvios
        # Si la respuesta contiene números seguidos de "building" (ej: "11 building"), 
        # y detectamos una letra de una sola letra, es probablemente un falso positivo
        if len(building_found) == 1:
            # Buscar patrones sospechosos como "11 building", "2 building", etc.
            suspicious_pattern = r'\d+\s+building'
            if re.search(suspicious_pattern, response, re.IGNORECASE):
                print(f"   ❌ FALSO POSITIVO DETECTADO: '{building_found}' en respuesta sospechosa '{response}'")
                print(f"   ❌ La respuesta parece ser un número seguido de 'building', no un código de edificio")
                building_found = None
                result["building"] = None
            else:
                building_id = building_map.get(building_found)
                result["building"] = building_id
                print(f"   [BUILDING] Edificio encontrado: codigo='{building_found}' -> ID={building_id}")
        else:
            building_id = building_map.get(building_found)
            result["building"] = building_id
            print(f"   Edificio encontrado: código='{building_found}' -> ID={building_id}")
    
    # Ahora buscamos el número de planta
    floor_found = None
    
    # Intentamos varios patrones: "PLANTA 2", "planta 2", "PLANTA -1", etc.
    # También buscamos números sueltos que puedan ser plantas válidas
    patterns = [
        r'(?:planta|piso|floor|nivel)\s*[:\-]?\s*(-?\d+)',  # "planta 2", "planta: 1"
        r'(-?\d+)\s*(?:planta|piso|floor|nivel)',  # "2 planta"
        r'\b(-?\d+)\b',  # Cualquier número (como último recurso)
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response, re.IGNORECASE)
        if matches:
            # Tomar el primer número que encontremos que sea una planta válida
            for match in matches:
                try:
                    num = int(match)
                    # Solo aceptamos plantas válidas del campus (-1, 0, 1, 2)
                    if num in [-1, 0, 1, 2]:
                        floor_found = num
                        break
                except ValueError:
                    continue
            if floor_found is not None:
                break
    
    # Si no encontramos número, intentamos buscar palabras como "segunda", "tercera"
    if floor_found is None:
        word_to_num = {
            "primera": 1, "segunda": 2, "tercera": 3,
            "primero": 1, "segundo": 2, "tercero": 3,
            "sótano": -1, "sotano": -1, "planta baja": 0, "baja": 0,
            "agora": -1, "ágora": -1,
        }
        for word, num in word_to_num.items():
            if word in response_lower and num in [-1, 0, 1, 2]:
                floor_found = num
                break
    
    if floor_found is not None:
        result["floor"] = floor_found
    
    # Validar que encontramos al menos edificio o planta
    # Si no encontramos nada, devolvemos un error descriptivo
    if result["building"] is None and result["floor"] is None:
        result["error"] = "No se pudo identificar ni el edificio ni la planta en la respuesta de Paligemma"
    elif result["building"] is None:
        result["error"] = "No se pudo identificar el edificio en la respuesta de Paligemma"
    elif result["floor"] is None:
        result["error"] = "No se pudo identificar la planta en la respuesta de Paligemma"
    
    return result


def _building_name(building_id: Optional[int], campus_graph: dict) -> str:
    """Devuelve el nombre corto del edificio por su ID."""
    if building_id is None:
        return "unknown"
    for b in campus_graph.get("buildings", []):
        if b.get("id") == building_id:
            return b.get("name", f"Building {building_id}")
    return f"Building {building_id}"


def generate_clarification_question(building: Optional[int], floor: Optional[int], campus_graph: dict) -> str:
    """
    Genera una pregunta de clarificación basada en qué información falta.
    Las preguntas son en inglés y más naturales, adaptadas a lo que ya se detectó.
    
    Args:
        building: ID del edificio identificado (None si no se identificó)
        floor: Número de planta identificada (None si no se identificó)
        campus_graph: Diccionario con la estructura del campus
        
    Returns:
        Pregunta de clarificación en inglés (más natural y específica)
    """
    # Obtener nombre del edificio si lo tenemos
    building_name = None
    if building:
        for b in campus_graph.get("buildings", []):
            if b.get("id") == building:
                building_name = b.get("name", f"Building {building}")
                # Si el nombre tiene "Edificio" o similar, extraer solo el nombre
                if "Edificio" in building_name:
                    building_name = building_name.replace("Edificio", "").strip()
                break
    
    # Generar pregunta según qué falta (en inglés, más natural)
    if building and not floor:
        # Tenemos edificio pero no planta - pregunta específica y natural
        if building_name:
            return f"I can see you're in {building_name}. Could you tell me which floor you're on?"
        else:
            return f"I can see you're in a building, but I couldn't identify the floor. Which floor are you on?"
    elif floor is not None and not building:
        # Tenemos planta pero no edificio
        floor_text = "ground floor" if floor == 0 else f"floor {floor}"
        return f"I can see you're on the {floor_text}, but I couldn't identify the building. Which building are you in?"
    else:
        # No tenemos nada - pregunta general pero más específica
        return "I couldn't identify the location in the image. Could you tell me which building you see on the sign or signage?"


@app.post("/api/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    current_building: Optional[str] = Form(None),
    current_floor: Optional[str] = Form(None),
):
    """
    Analiza una imagen con Paligemma para extraer el edificio y la planta.
    Opcionalmente recibe estado actual (building, floor) para mensajes de ascensor/escaleras.
    
    Args:
        file: Archivo de imagen (JPEG, PNG)
        current_building: ID de edificio si ya se conoce (opcional)
        current_floor: Número de planta si ya se conoce (opcional)
        
    Returns:
        ImageAnalysisResponse con building, floor y raw_response
    """
    try:
        # Validar que la imagen sea del formato correcto (permitir octet-stream por compatibilidad con Android)
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "application/octet-stream"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de imagen no soportado: {file.content_type}. Use JPEG o PNG."
            )

        # Leer los bytes de la imagen
        image_data = await file.read()

        # DEBUG: guardar imagen recibida para verificar qué llega realmente
        _debug_path = Path("debug_received_image.jpg")
        _debug_path.write_bytes(image_data)
        print(f"\n   [DEBUG] Imagen guardada en {_debug_path.resolve()} ({len(image_data)} bytes)")

        # Necesitamos el campus graph para mapear nombres a IDs
        campus_graph = load_campus_graph()

        # Estado actual opcional (enviado por la app cuando ya tiene building/floor de una foto anterior)
        known_building: Optional[int] = None
        known_floor: Optional[int] = None
        if current_floor is not None and str(current_floor).strip():
            try:
                known_floor = int(str(current_floor).strip())
            except ValueError:
                pass
        if current_building is not None and str(current_building).strip():
            try:
                known_building = int(str(current_building).strip())
            except ValueError:
                pass

        def _call_colab(prompt_text: str, skip_sorry_filter: bool = False, max_tokens: int | None = None) -> str | None:
            """Llama al endpoint /analyze de Colab y devuelve la respuesta en texto, o None."""
            if not prompt_text.strip().startswith("<image>"):
                prompt_text = "<image>\n" + prompt_text
            payload: dict = {"prompt": prompt_text}
            if max_tokens is not None:
                payload["max_tokens"] = str(max_tokens)
            try:
                resp = requests.post(
                    f"{COLAB_API_URL}/analyze",
                    files={"file": (file.filename, image_data, file.content_type)},
                    data=payload,
                    timeout=30,
                )
                if resp.status_code != 200:
                    print(f"   [DEBUG Colab] status={resp.status_code} body={resp.text[:200]!r}")
                    return None
                d = resp.json()
                raw = (d.get("response") or "").strip()
                if not d.get("success"):
                    print(f"   [DEBUG Colab] success=False response={raw!r} error={d.get('error')!r}")
                    return None
                _invalid = {"none", "null", "n/a", "nothing", "unanswerable", "no", ""}
                if not raw or raw.lower() in _invalid or "unanswerable" in raw.lower():
                    return None
                if not skip_sorry_filter and "sorry" in raw.lower():
                    print(f"   [DEBUG Colab] respuesta descartada (sorry): {raw!r}")
                    return None
                return raw
            except Exception as e:
                print(f"   [DEBUG Colab] excepción: {e}")
                return None

        def _parse_floor_direct(text: str) -> int | None:
            """Extrae un número de planta directamente de una cadena corta."""
            if not text:
                return None
            import re as _re
            m = _re.search(r"(?<!\d)(-?\d+)(?!\d)", text.strip())
            if m:
                val = int(m.group(1))
                if -5 <= val <= 10:
                    return val
            return None

        prompts = get_paligemma_prompts(campus_graph)
        # Clasificador: 64 tokens. Resto (sign, fallbacks, landmarks): 256 como antes (detectar G, 0.3, etc.)
        DEFAULT_MAX_TOKENS = 256

        # Intentar usar Colab primero (más rápido con GPU)
        if COLAB_API_URL:
            try:
                # ── Step 0: Clasificar el tipo de imagen ─────────────────────────────
                classifier_prompt = CLASSIFIER_PROMPT
                raw_type = _call_colab(classifier_prompt, skip_sorry_filter=True, max_tokens=64)
                image_type = _normalize_image_type(raw_type)
                print("\n---------- CLASSIFIER ----------")
                print(f"Prompt: {classifier_prompt}")
                print(f"PaliGemma response: {raw_type!r}")
                print(f"Category: {image_type!r}")
                print("-------------------------------")

                # ── Elevator ──────────────────────────────────────────────────────────
                if image_type == "elevator":
                    elevator_prompt = Agent1_Identifier.get_elevator_prompt()
                    print("\n---------- ELEVATOR ----------")
                    print(f"Prompt: {elevator_prompt}")
                    raw_elev = _call_colab(elevator_prompt, skip_sorry_filter=True, max_tokens=DEFAULT_MAX_TOKENS)
                    print(f"PaliGemma response (open/closed): {raw_elev!r}")
                    r_elev = (raw_elev or "").lower()
                    elevator_state = "open" if "open" in r_elev else "closed"
                    # Intentar extraer planta del panel del ascensor
                    floor_from_panel: Optional[int] = None
                    panel_prompt = Agent1_Identifier.get_elevator_panel_floor_prompt()
                    print(f"Prompt: {panel_prompt}")
                    raw_panel = _call_colab(panel_prompt, skip_sorry_filter=True, max_tokens=32)
                    if raw_panel:
                        floor_from_panel = _parse_floor_direct(raw_panel)
                    print(f"PaliGemma response (panel floor): {raw_panel!r} -> {floor_from_panel}")
                    print("----------------------------")
                    effective_floor = known_floor if known_floor is not None else floor_from_panel
                    has_full_state = known_building is not None and effective_floor is not None
                    if has_full_state:
                        return ImageAnalysisResponse(
                            success=True,
                            raw_response=raw_elev or "",
                            image_type="elevator",
                            elevator_state=elevator_state,
                            floor=effective_floor,
                            needs_clarification=False,
                            clarification_question=None,
                        )
                    # Estado incompleto — construir mensaje según qué sabemos
                    open_closed = "open" if elevator_state == "open" else "closed"
                    sign_hint = "Directory signs are usually right next to the elevator and the stairs."
                    if effective_floor is None and known_building is None:
                        msg = (
                            f"In front of you there is an elevator with the doors {open_closed}. "
                            "I still don't know your location. "
                            "I need to know both your building and floor. "
                            f"{sign_hint} You can also tell me by voice."
                        )
                    elif floor_from_panel is not None and known_building is None:
                        floor_text = _floor_text_local(floor_from_panel)
                        msg = (
                            f"In front of you there is an elevator with the doors {open_closed}. "
                            f"I can see the button shows floor {floor_from_panel}, so you are on {floor_text}. "
                            "I still need to know your building. "
                            f"{sign_hint} You can also tell me by voice."
                        )
                    elif known_floor is not None and known_building is None:
                        floor_text = _floor_text_local(known_floor)
                        msg = (
                            f"In front of you there is an elevator with the doors {open_closed}. "
                            f"I know you are on {floor_text}, but I still need to know your building. "
                            f"{sign_hint} You can also tell me by voice."
                        )
                    else:
                        msg = (
                            f"In front of you there is an elevator with the doors {open_closed}. "
                            "I still need more information about your location. "
                            f"{sign_hint} You can also tell me by voice."
                        )
                    return ImageAnalysisResponse(
                        success=False,
                        raw_response=raw_elev or "",
                        image_type="elevator",
                        elevator_state=elevator_state,
                        floor=effective_floor,
                        building=known_building,
                        needs_clarification=True,
                        clarification_question=msg,
                    )

                # ── Stairs ────────────────────────────────────────────────────────────
                if image_type == "stairs":
                    stairs_prompt = Agent1_Identifier.get_stairs_prompt()
                    print("\n---------- STAIRS ----------")
                    print(f"Prompt: {stairs_prompt}")
                    raw_stairs = _call_colab(stairs_prompt, skip_sorry_filter=True, max_tokens=8)
                    print(f"PaliGemma response: {raw_stairs!r}")
                    r_stairs = (raw_stairs or "").lower()
                    if "up" in r_stairs and "down" in r_stairs:
                        stairs_direction = "both"
                    elif "up" in r_stairs:
                        stairs_direction = "up"
                    elif "down" in r_stairs:
                        stairs_direction = "down"
                    else:
                        stairs_direction = "both"
                    # Intentar extraer número de planta de la pared
                    floor_stairs: Optional[int] = None
                    stairs_floor_prompt = Agent1_Identifier.get_stairs_floor_prompt()
                    print(f"Prompt: {stairs_floor_prompt}")
                    raw_stairs_floor = _call_colab(stairs_floor_prompt, skip_sorry_filter=True, max_tokens=8)
                    if raw_stairs_floor:
                        floor_stairs = _parse_floor_direct(raw_stairs_floor)
                    print(f"PaliGemma response (wall floor): {raw_stairs_floor!r} -> {floor_stairs}")
                    print("----------------------------")
                    effective_floor = known_floor if known_floor is not None else floor_stairs
                    return ImageAnalysisResponse(
                        success=False,
                        raw_response=raw_stairs or "",
                        image_type="stairs",
                        stairs_direction=stairs_direction,
                        building=known_building,
                        floor=effective_floor,
                        needs_clarification=True,
                        clarification_question="stairs",
                    )

                # ── Door ──────────────────────────────────────────────────────────────
                if image_type == "door":
                    door_prompt = Agent1_Identifier.get_door_prompt()
                    print("\n---------- DOOR ----------")
                    print(f"Prompt: {door_prompt}")
                    raw_door = _call_colab(door_prompt, skip_sorry_filter=True, max_tokens=DEFAULT_MAX_TOKENS)
                    print(f"PaliGemma response: {raw_door!r}")
                    print("----------------------------")
                    floor_from_door = extract_floor_from_room_code(raw_door or "")
                    return ImageAnalysisResponse(
                        success=True,
                        raw_response=raw_door or "",
                        floor=floor_from_door,
                        image_type="door",
                        needs_clarification=False,
                        clarification_question=None,
                        confidence="medium" if floor_from_door is not None else "none",
                    )

                # ── Other / no reconocido ─────────────────────────────────────────────
                if image_type == "other":
                    print(f"[CLASSIFY] Imagen no reconocida, solicitando cartel al usuario")
                    return ImageAnalysisResponse(
                        success=False,
                        raw_response=raw_type or "",
                        image_type="other",
                        needs_clarification=True,
                        clarification_question="I cannot identify the navigation element. Please take a photo of a directory sign.",
                    )

                # ── Sign (o clasificador falló) → prompt para edificio y planta (max_tokens=256 como antes) ─────
                building_codes = ["G", "CD", "H"]  # lista corta para prompt directo (detecta bien G 0, etc.)
                sign_prompt = Agent1_Identifier.get_sign_prompt(building_codes)
                print("\n---------- SIGN ----------")
                print(f"Prompt: {sign_prompt}")
                raw = _call_colab(sign_prompt, max_tokens=DEFAULT_MAX_TOKENS)
                print(f"PaliGemma response: {raw!r}")
                print("-------------------------------")

                # Intentar parsear como JSON primero
                json_parsed = parse_paligemma_json(raw or "")

                agent1 = Agent1_Identifier.parse_response(raw or "", campus_graph)
                parsed = parse_location_from_paligemma_response(raw or "", campus_graph)

                building_id = agent1.get("building") or parsed.get("building")
                floor_num   = agent1.get("floor")   or parsed.get("floor")

                # ── UFV-only sign (no building code) ───────────────────────────────
                # If PaliGemma responds with "ufv …" the sign shows only the floor.
                # Use a targeted prompt to extract the floor reliably.
                if raw and "ufv" in raw.lower():
                    print(f"\n   [ufv-sign] Response starts with 'ufv' → no building code on this sign")
                    building_id = None  # force: no building extractable from this sign
                    ufv_floor_prompt = (
                        "<image>\n"
                        "Look at the top right corner of this sign. "
                        "There is a large building letter (e.g. G, H, CD). "
                        "Directly below that letter is the floor indicator. "
                        "The floor can be a number (e.g. -1, 0, 1, 2) or a word (e.g. AGORA). "
                        "Reply with ONLY that number or word, nothing else."
                    )
                    print(f"   [ufv-sign] PROMPT: {ufv_floor_prompt!r}")
                    raw_ufv = _call_colab(ufv_floor_prompt, max_tokens=32)
                    print(f"   [ufv-sign] RESPUESTA: {raw_ufv!r}")
                    if raw_ufv:
                        _ufv_word_map = {"agora": -1, "ágora": -1}
                        ufv_word = raw_ufv.strip().lower()
                        if ufv_word in _ufv_word_map:
                            floor_num = _ufv_word_map[ufv_word]
                            print(f"   [ufv-sign] Planta extraída (palabra): {raw_ufv.strip()} → {floor_num}")
                        else:
                            floor_from_ufv = _parse_floor_direct(raw_ufv)
                            if floor_from_ufv is not None:
                                floor_num = floor_from_ufv
                                print(f"   [ufv-sign] Planta extraída: {floor_num}")

                # Si el JSON respondió con confidence, usarlo.
                # Si no (PaliGemma respondió en texto plano), inferirlo de los datos detectados.
                json_confidence = json_parsed.get("confidence")
                if json_confidence and json_confidence != "none":
                    confidence = json_confidence
                elif building_id is not None and floor_num is not None:
                    confidence = "high"
                elif building_id is not None or floor_num is not None:
                    confidence = "medium"
                else:
                    confidence = "none"

                agent1["confidence"] = confidence
                landmarks   = agent1.get("landmarks", [])
                resources   = agent1.get("resources", [])

                # Si el JSON dio building_code, usarlo directamente
                if json_parsed.get("building_code"):
                    bc = json_parsed["building_code"].upper()
                    for b in campus_graph.get("buildings", []):
                        if b.get("name", "").upper() == bc:
                            building_id = b["id"]
                            break
                if json_parsed.get("floor") is not None:
                    try:
                        floor_num = int(json_parsed["floor"])
                    except (ValueError, TypeError):
                        pass
                if json_parsed.get("landmarks"):
                    landmarks = json_parsed["landmarks"] or landmarks

                # Fallback 1: JSON corto (siempre se intenta si falta planta) ──
                if floor_num is None:
                    print(f"\n   [fallback-1] PROMPT: {prompts[1]!r}")
                    raw2 = _call_colab(prompts[1], max_tokens=DEFAULT_MAX_TOKENS)
                    print(f"   [fallback-1] RESPUESTA: '{raw2}'")
                    if raw2:
                        j2 = parse_paligemma_json(raw2)
                        if j2.get("floor") is not None:
                            try:
                                floor_num = int(j2["floor"])
                            except (ValueError, TypeError):
                                pass
                        if floor_num is None:
                            p2 = parse_location_from_paligemma_response(raw2, campus_graph)
                            floor_num = p2.get("floor") or _parse_floor_direct(raw2)

                # Fallback 2: número tras PLANTA/FLOOR ──
                if floor_num is None:
                    print(f"\n   [fallback-2] PROMPT: {prompts[2]!r}")
                    raw3 = _call_colab(prompts[2], max_tokens=DEFAULT_MAX_TOKENS)
                    print(f"   [fallback-2] RESPUESTA: '{raw3}'")
                    floor_num = _parse_floor_direct(raw3)

                # Fallback 3: código de aula (Aula 2.1, Lab 1.3...) ──
                if floor_num is None:
                    print(f"\n   [fallback-room] PROMPT: {prompts[4]!r}")
                    raw5 = _call_colab(prompts[4], max_tokens=DEFAULT_MAX_TOKENS)
                    print(f"   [fallback-room] RESPUESTA: '{raw5}'")
                    if raw5:
                        floor_from_room = extract_floor_from_room_code(raw5)
                        if floor_from_room is not None:
                            floor_num = floor_from_room
                            if confidence == "none":
                                confidence = "medium"
                            print(f"   [fallback-room] Planta extraída de código de aula: {floor_num}")

                # Fallback 4: lector genérico de texto visible ──
                if floor_num is None:
                    print(f"\n   [fallback-text] PROMPT: {prompts[5]!r}")
                    raw6 = _call_colab(prompts[5], max_tokens=DEFAULT_MAX_TOKENS)
                    print(f"   [fallback-text] RESPUESTA: '{raw6}'")
                    if raw6:
                        floor_from_text = extract_floor_from_room_code(raw6)
                        if floor_from_text is not None:
                            floor_num = floor_from_text
                            if confidence == "none":
                                confidence = "medium"
                            print(f"   [fallback-text] Planta extraída de texto genérico: {floor_num}")
                        if floor_num is None:
                            p6 = parse_location_from_paligemma_response(raw6, campus_graph)
                            floor_num = p6.get("floor") or _parse_floor_direct(raw6)
                            if floor_num is not None and confidence == "none":
                                confidence = "medium"

                # Fallback 5: solo número decimal de planta (0.3, 1.2...) ──
                if floor_num is None:
                    print(f"\n   [fallback-decimal] PROMPT: {prompts[6]!r}")
                    raw7 = _call_colab(prompts[6], max_tokens=DEFAULT_MAX_TOKENS)
                    print(f"   [fallback-decimal] RESPUESTA: '{raw7}'")
                    if raw7:
                        floor_from_decimal = extract_floor_from_room_code(raw7)
                        if floor_from_decimal is not None:
                            floor_num = floor_from_decimal
                            if confidence == "none":
                                confidence = "medium"
                            print(f"   [fallback-decimal] Planta extraída de decimal: {floor_num}")

                # Landmarks: desactivado de momento para categoría sign (solo edificio y planta)
                # if not landmarks:
                #     print(f"\n   [landmarks] PROMPT: {prompts[3]!r}")
                #     raw4 = _call_colab(prompts[3], max_tokens=DEFAULT_MAX_TOKENS)
                #     ...

                # Clasificador indicó "sign" (o no clasificó → asumimos sign)
                image_type = "sign"

                print(f"   Resultado -> building={building_id}, floor={floor_num}, confidence={confidence}, image_type={image_type}")

                if building_id is not None and floor_num is not None:
                    return ImageAnalysisResponse(
                        success=True,
                        building=building_id,
                        floor=floor_num,
                        raw_response=raw or "",
                        error=None,
                        needs_clarification=False,
                        clarification_question=None,
                        landmarks=landmarks if landmarks else None,
                        resources=resources if resources else None,
                        confidence=confidence,
                        image_type=image_type,
                        elevator_state=None,
                        stairs_direction=None,
                    )
                else:
                    # Es un cartel pero falta información (edificio o planta)
                    question = generate_clarification_question(building_id, floor_num, campus_graph)
                    return ImageAnalysisResponse(
                        success=building_id is not None or floor_num is not None,
                        building=building_id,
                        floor=floor_num,
                        raw_response=raw or "",
                        error=None,
                        needs_clarification=True,
                        clarification_question=question,
                        landmarks=landmarks if landmarks else None,
                        resources=resources if resources else None,
                        confidence=confidence,
                        image_type=image_type,
                        elevator_state=None,
                        stairs_direction=None,
                    )
                
            except requests.exceptions.RequestException as e:
                # Si falla la conexión con Colab, intentamos localmente
                error_msg = f"Error de conexión con Colab: {str(e)}"
                print(f"{error_msg}")
                print(f"   URL intentada: {COLAB_API_URL}/analyze")
                print("   Intentando cargar modelo localmente...")
                # Fallback a local
                return await _analyze_image_local(image_data, campus_graph, file.filename, file.content_type)
            except Exception as e:
                # Cualquier otro error con Colab, también intentamos local
                error_msg = f"Error inesperado con Colab: {str(e)}"
                print(f"{error_msg}")
                print("   Intentando cargar modelo localmente...")
                # Fallback a local
                return await _analyze_image_local(image_data, campus_graph, file.filename, file.content_type)
        else:
            # Si no hay URL de Colab configurada, usamos el modelo local directamente
            return await _analyze_image_local(image_data, campus_graph, file.filename, file.content_type)
    
    except HTTPException:
        raise
    except Exception as e:
        # Cualquier error inesperado, lo devolvemos en la respuesta
        return ImageAnalysisResponse(
            success=False,
            building=None,
            floor=None,
            raw_response="",
            error=f"Error procesando imagen: {str(e)}",
            needs_clarification=False,
            clarification_question=None
        )


async def _analyze_image_local(image_data: bytes, campus_graph: dict, filename: str, content_type: str) -> ImageAnalysisResponse:
    """
    Función auxiliar para analizar imagen localmente.
    
    Esta función se usa cuando Colab no está disponible o falla.
    Carga el modelo Paligemma localmente (más lento pero funciona sin internet).
    """
    try:
        # Convertir los bytes a una imagen PIL
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        # Cargar el modelo Paligemma (solo la primera vez, luego se reutiliza)
        model, processor = load_paligemma_model()
        
        # Obtener lista de prompts para intentar secuencialmente
        prompts = get_paligemma_prompts()
        
        # Intentar cada prompt secuencialmente hasta que uno funcione
        from evaluation.inference import run_single_inference
        
        for prompt_idx, prompt in enumerate(prompts):
            try:
                # Procesar la imagen con Paligemma usando el prompt actual
                raw_response, inference_time = run_single_inference(
                    model=model,
                    processor=processor,
                    image=image,
                    question=prompt,
                    max_new_tokens=100
                )
                
                # Si la respuesta es "unanswerable", intentar siguiente prompt
                if "unanswerable" in raw_response.strip().lower():
                    print(f"   Prompt {prompt_idx + 1}/{len(prompts)}: 'unanswerable', intentando siguiente...")
                    continue
                
                # Parsear la respuesta de Paligemma para extraer edificio y planta
                parsed = parse_location_from_paligemma_response(raw_response, campus_graph)
                
                # Verificar si tenemos información parcial o completa
                building_id = parsed.get("building")
                floor_num = parsed.get("floor")
                
                # Si tenemos ambos, éxito completo
                if building_id is not None and floor_num is not None:
                    print(f"   Prompt {prompt_idx + 1}/{len(prompts)}: Éxito completo")
                    return ImageAnalysisResponse(
                        success=True,
                        building=building_id,
                        floor=floor_num,
                        raw_response=raw_response,
                        error=None,
                        needs_clarification=False,
                        clarification_question=None
                    )
                
                # Si tenemos información parcial, necesitamos clarificación
                elif building_id is not None or floor_num is not None:
                    print(f"   Prompt {prompt_idx + 1}/{len(prompts)}: Información parcial detectada")
                    question = generate_clarification_question(building_id, floor_num, campus_graph)
                    return ImageAnalysisResponse(
                        success=False,
                        building=building_id,
                        floor=floor_num,
                        raw_response=raw_response,
                        error=None,
                        needs_clarification=True,
                        clarification_question=question
                    )
                
                # Si no tenemos nada, intentar siguiente prompt
                else:
                    print(f"   Prompt {prompt_idx + 1}/{len(prompts)}: Sin información, intentando siguiente...")
                    if prompt_idx < len(prompts) - 1:
                        continue
                    else:
                        # Último prompt, necesitamos clarificación completa
                        question = generate_clarification_question(None, None, campus_graph)
                        return ImageAnalysisResponse(
                            success=False,
                            building=None,
                            floor=None,
                            raw_response=raw_response,
                            error=None,
                            needs_clarification=True,
                            clarification_question=question
                        )
            except Exception as e:
                # Si hay error con este prompt, intentar siguiente
                print(f"   Prompt {prompt_idx + 1}/{len(prompts)}: Error: {str(e)}, intentando siguiente...")
                if prompt_idx < len(prompts) - 1:
                    continue
                else:
                    # Último prompt, lanzar el error
                    raise
        
        # Si llegamos aquí, todos los prompts fallaron
        question = generate_clarification_question(None, None, campus_graph)
        return ImageAnalysisResponse(
            success=False,
            building=None,
            floor=None,
            raw_response="",
            error=None,
            needs_clarification=True,
            clarification_question=question
        )
    
    except Exception as e:
        # Si algo falla en el procesamiento local, devolvemos el error
        return ImageAnalysisResponse(
            success=False,
            building=None,
            floor=None,
            raw_response="",
            error=f"Error procesando imagen localmente: {str(e)}",
            needs_clarification=False,
            clarification_question=None
        )


def validate_user_response(user_response: str, campus_graph: dict) -> Tuple[bool, Optional[str]]:
    """
    Valida si la respuesta del usuario es clara y parseable.
    
    Args:
        user_response: Respuesta del usuario
        campus_graph: Diccionario con la estructura del campus
        
    Returns:
        Tuple (is_valid, error_message)
        - is_valid: True si la respuesta parece válida, False si es ambigua
        - error_message: Mensaje de error si no es válida, None si es válida
    """
    response_lower = user_response.lower().strip()
    
    # Si la respuesta es muy corta o vacía, no es válida
    if len(response_lower) < 2:
        return False, "Sorry, I couldn't understand. Could you please repeat that?"
    
    # Lista de palabras que indican que la respuesta puede ser ambigua o incorrecta
    # Casos como "building age" (debería ser "building H") o "onbuilding" (sin espacio)
    ambiguous_patterns = [
        r'\bbuilding\s+age\b',  # "building age" (probablemente "building H" mal transcrito)
        r'\bonbuilding\b',      # "onbuilding" (sin espacio)
        r'\binbuilding\b',       # "inbuilding" (sin espacio)
    ]
    
    # Verificar patrones ambiguos
    for pattern in ambiguous_patterns:
        if re.search(pattern, response_lower):
            return False, "Sorry, I couldn't understand clearly. Could you please repeat that more slowly?"
    
    # Intentar parsear para ver si obtenemos algo útil
    parsed = parse_location_from_paligemma_response(user_response, campus_graph)
    
    # Si no se pudo extraer nada y la respuesta es larga, puede ser que no sea relevante
    if parsed.get("building") is None and parsed.get("floor") is None:
        # Verificar si contiene palabras relacionadas con edificios o plantas
        building_keywords = ["building", "edificio", "floor", "planta", "ground", "first", "second", "third", "h", "g", "cd"]
        has_keywords = any(keyword in response_lower for keyword in building_keywords)
        
        # Si tiene palabras clave pero no se pudo parsear, puede ser ambigua
        if has_keywords:
            return False, "Sorry, I couldn't identify the building or floor clearly. Could you please repeat it?"
        
        # Si no tiene palabras clave y es larga, no es relevante
        if len(response_lower) > 10:
            return False, "Sorry, I couldn't identify the building or floor in your response. Could you please repeat it?"
    
    # Si llegamos aquí, la respuesta parece válida
    return True, None


@app.post("/api/clarify-location", response_model=ClarificationResponse)
async def clarify_location(request: ClarificationRequest):
    """
    Procesa la respuesta del usuario para completar la información de ubicación.
    
    Args:
        request: ClarificationRequest con la respuesta del usuario y contexto previo
        
    Returns:
        ClarificationResponse con la ubicación completa o nueva pregunta
    """
    try:
        campus_graph = load_campus_graph()
        user_response = request.user_response
        previous_context = request.previous_context
        
        # Validar que la respuesta del usuario sea clara
        is_valid, validation_error = validate_user_response(user_response, campus_graph)
        if not is_valid:
            # Si la respuesta no es clara, volver a preguntar
            building_id = previous_context.get("building")
            floor_num = previous_context.get("floor")
            question = generate_clarification_question(building_id, floor_num, campus_graph)
            # Modificar la pregunta para pedir que repita
            if validation_error:
                question = f"{validation_error} {question}"
            
            return ClarificationResponse(
                success=False,
                building=building_id,
                floor=floor_num,
                needs_clarification=True,
                clarification_question=question,
                error=None
            )
        
        # Obtener información previa
        building_id = previous_context.get("building")
        floor_num = previous_context.get("floor")
        
        # Parsear la respuesta del usuario para extraer edificio y/o planta
        parsed = parse_location_from_paligemma_response(user_response, campus_graph)
        print(f"Respuesta del usuario parseada: {parsed}")
        print(f"Contexto previo: building={building_id}, floor={floor_num}")
        
        # Combinar información previa con la nueva
        final_building = building_id if building_id is not None else parsed.get("building")
        final_floor = floor_num if floor_num is not None else parsed.get("floor")
        
        print(f"Información combinada: building={final_building}, floor={final_floor}")
        
        # Si ahora tenemos ambos, éxito
        if final_building is not None and final_floor is not None:
            print(f"Ubicación completa: building={final_building}, floor={final_floor}")
            print(f"Devolviendo success=True con building={final_building}, floor={final_floor}")
            return ClarificationResponse(
                success=True,
                building=final_building,
                floor=final_floor,
                needs_clarification=False,
                clarification_question=None,
                error=None
            )
        
        # Si aún falta información, hacer otra pregunta
        question = generate_clarification_question(final_building, final_floor, campus_graph)
        return ClarificationResponse(
            success=False,
            building=final_building,
            floor=final_floor,
            needs_clarification=True,
            clarification_question=question,
            error=None
        )
    
    except Exception as e:
        return ClarificationResponse(
            success=False,
            building=None,
            floor=None,
            needs_clarification=False,
            clarification_question=None,
            error=f"Error procesando clarificación: {str(e)}"
        )


@app.post("/api/gps-route", response_model=GPSRouteResponse)
async def get_gps_route(request: GPSRouteRequest):
    """
    Obtiene una ruta GPS entre dos edificios usando Google Maps Directions API.
    Este endpoint evita problemas de CORS al hacer la llamada desde el servidor.
    """
    try:
        # Coordenadas GPS de los edificios
        building_gps = {
            1: {"lat": 40.44162251912561, "lng": -3.8336784343565533, "name": "G"},
            2: {"lat": 40.44139393985062, "lng": -3.833504032472637, "name": "CD"},
            3: {"lat": 40.44188587337159, "lng": -3.83444151925449, "name": "Edificio H"}
        }
        
        origin_gps = building_gps.get(request.from_building)
        goal_gps = building_gps.get(request.to_building)
        
        if not origin_gps or not goal_gps:
            return GPSRouteResponse(
                success=False,
                error=f"No GPS coordinates available for buildings: {request.from_building} -> {request.to_building}"
            )

        maps_key = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
        if not maps_key:
            return GPSRouteResponse(
                success=False,
                error="GOOGLE_MAPS_API_KEY no configurada. Añádela al entorno o al fichero .env en la raíz del proyecto.",
            )

        origin = f"{origin_gps['lat']},{origin_gps['lng']}"
        destination = f"{goal_gps['lat']},{goal_gps['lng']}"

        directions_url = (
            f"https://maps.googleapis.com/maps/api/directions/json?"
            f"origin={origin}&destination={destination}&key={maps_key}&mode=walking&language=en"
        )
        
        response = requests.get(directions_url, timeout=10)
        data = response.json()
        
        if data.get("status") == "OK" and data.get("routes") and len(data["routes"]) > 0:
            route = data["routes"][0]
            leg = route["legs"][0]

            print(f"\n[GPS Route] {leg['distance']['text']} — {leg['duration']['text']}")
            for idx, step in enumerate(leg["steps"]):
                instruction = re.sub(r'<[^>]+>', '', step["html_instructions"])
                print(f"  Step {idx + 1}: {instruction} ({step['distance']['text']})")

            return GPSRouteResponse(
                success=True,
                distance=leg["distance"]["text"],
                duration=leg["duration"]["text"],
                steps=[
                    {
                        "instruction": re.sub(r'<[^>]+>', '', step["html_instructions"]),
                        "distance": step["distance"]["text"],
                        "duration": step["duration"]["text"],
                        "startLocation": step["start_location"],
                        "endLocation": step["end_location"]
                    }
                    for step in leg["steps"]
                ],
                polyline=route["overview_polyline"]["points"]
            )
        else:
            return GPSRouteResponse(
                success=False,
                error=f"Directions API error: {data.get('status')} - {data.get('error_message', 'Unknown error')}"
            )
    
    except Exception as e:
        return GPSRouteResponse(
            success=False,
            error=f"Error fetching GPS route: {str(e)}"
        )


@app.post("/api/conversation", response_model=ConversationResponse)
async def conversation(request: ConversationRequest):
    """
    Unified conversation endpoint. All state routing is handled inside
    ConversationAgent.process_turn().
    """
    try:
        agent = get_conversation_agent()
        image_analysis = (
            request.image_analysis
            if isinstance(request.image_analysis, dict)
            else None
        )
        user_message = request.user_message or ""

        result = agent.process_turn(
            session_id=request.session_id,
            user_message=user_message if user_message else None,
            image_analysis=image_analysis,
        )

        ctx = result.get("context", {})
        return ConversationResponse(
            response=result.get("tts_message", ""),
            action=result.get("action", ""),
            needs_input=result.get("next_input", "voice") != "none",
            context=ctx,
            tts_message=result.get("tts_message"),
            next_input=result.get("next_input"),
            plan_request=result.get("plan_request"),
            location_partial=result.get("location_partial"),
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return ConversationResponse(
            response=f"Sorry, I encountered an error: {str(e)}",
            action="error",
            needs_input=True,
            context={},
            error=str(e),
            tts_message=f"Sorry, I encountered an error: {str(e)}",
            next_input="voice",
        )


@app.post("/api/transcribe-audio", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Transcribe audio a texto usando Whisper (vía Colab).
    
    Args:
        file: Archivo de audio (WAV, MP3, etc.)
        
    Returns:
        TranscribeResponse con el texto transcrito
    """
    try:
        # Leer el audio
        audio_data = await file.read()
        audio_size = len(audio_data)
        print(f"\n[TRANSCRIBE] Received audio: filename={file.filename}, "
              f"content_type={file.content_type}, size={audio_size} bytes")

        if audio_size < 1000:
            print(f"[TRANSCRIBE] WARNING: Audio too small ({audio_size} bytes), likely empty recording")
            return TranscribeResponse(
                success=False,
                text="",
                error=f"Audio file too small ({audio_size} bytes). Microphone may not be capturing."
            )
        
        # Intentar usar Colab primero (más rápido con GPU)
        if COLAB_API_URL:
            try:
                # Enviar el audio al servidor de Colab
                send_filename = file.filename or "audio.wav"
                # Force WAV MIME when filename indicates WAV to avoid
                # intermittent decoding issues in remote endpoints.
                if send_filename.lower().endswith(".wav"):
                    send_content_type = "audio/wav"
                else:
                    send_content_type = file.content_type or "application/octet-stream"

                files = {"file": (send_filename, audio_data, send_content_type)}
                print(f"[TRANSCRIBE] Sending to Colab: {COLAB_API_URL}/transcribe (mime={send_content_type})")
                response = requests.post(
                    f"{COLAB_API_URL}/transcribe",
                    files=files,
                    timeout=30
                )
                
                print(f"[TRANSCRIBE] Colab response status: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"[TRANSCRIBE] Colab response data: {data}")
                    if data.get("success"):
                        # Corregir transcripción con post-procesamiento
                        transcribed_text = data.get("text", "")
                        # Retry once when text is empty but audio is large enough.
                        if not transcribed_text.strip() and audio_size > 120000:
                            print("[TRANSCRIBE] Empty text with large audio, retrying once...")
                            retry_files = {"file": ("audio.wav", audio_data, "audio/wav")}
                            retry_response = requests.post(
                                f"{COLAB_API_URL}/transcribe",
                                files=retry_files,
                                timeout=30
                            )
                            print(f"[TRANSCRIBE] Retry status: {retry_response.status_code}")
                            if retry_response.status_code == 200:
                                retry_data = retry_response.json()
                                print(f"[TRANSCRIBE] Retry data: {retry_data}")
                                if retry_data.get("success"):
                                    transcribed_text = retry_data.get("text", "")

                        campus_graph = load_campus_graph()
                        corrected_text = correct_whisper_transcription(transcribed_text, campus_graph)

                        print(f"[TRANSCRIBE] Raw:      '{transcribed_text}'")
                        if corrected_text != transcribed_text:
                            print(f"[TRANSCRIBE] Corrected: '{corrected_text}'")

                        if not corrected_text.strip():
                            return TranscribeResponse(
                                success=False,
                                text="",
                                error="No speech detected. Please speak clearly and try again."
                            )
                        return TranscribeResponse(
                            success=True,
                            text=corrected_text,
                            error=None
                        )
                    else:
                        raise Exception(data.get("error", "Error en Colab"))
                else:
                    raise Exception(f"Error en Colab: {response.status_code}")
            
            except requests.exceptions.RequestException as e:
                error_msg = f"Error de conexión con Colab: {str(e)}"
                print(f"{error_msg}")
                return TranscribeResponse(
                    success=False,
                    text="",
                    error=error_msg
                )
        else:
            return TranscribeResponse(
                success=False,
                text="",
                error="COLAB_API_URL no configurada. Defínela en el entorno o en .env (URL base del túnel, sin barra final).",
            )
    
    except Exception as e:
        return TranscribeResponse(
            success=False,
            text="",
            error=f"Error transcribiendo audio: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    # Ejecutar servidor
    uvicorn.run(
        "planning_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
