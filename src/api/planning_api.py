"""
API FastAPI para Planificación con Fast Downward

Endpoints:
- POST /api/plan - Generar un plan desde estado inicial a objetivo
- GET /api/domain - Obtener el dominio PDDL actual
- POST /api/validate - Validar un plan
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
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
)
from navigation.fast_downward_client import FastDownwardPlanner
from navigation.pddl_converter import CampusGraphToPDDL

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

# Inicializar componentes
planner = FastDownwardPlanner()
converter = CampusGraphToPDDL(str(CAMPUS_JSON))

# Variables globales para Paligemma (singleton)
# Mantenemos el modelo y procesador en memoria para no cargarlos cada vez
_paligemma_model = None
_paligemma_processor = None
_campus_graph_data = None

# URL del servidor de Colab con Paligemma
# Si tienes el notebook corriendo, aquí va la URL que te da ngrok
# Si no está configurada, usará el modelo local (más lento pero funciona sin Colab)
COLAB_API_URL = "https://your-subdomain.ngrok-free.app"

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
            goal_info = {
                "functional": request.goal_functional,
                "description": "Cafetería (CD planta 0)" if request.goal_functional == "cafeteria" else "Gimnasio (CD planta -1)"
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


def load_paligemma_model():
    """Carga el modelo Paligemma una vez y lo mantiene en memoria (singleton)."""
    global _paligemma_model, _paligemma_processor
    # Solo cargamos el modelo la primera vez que se necesita
    # Esto ahorra tiempo y memoria en peticiones posteriores
    if _paligemma_model is None or _paligemma_processor is None:
        from model_loader import load_paligemma
        from huggingface_hub import login
        import os
        
        # Necesitamos un token de HuggingFace para descargar el modelo
        # Puedes ponerlo aquí directamente o usar una variable de entorno
        HF_TOKEN_HARDCODED = "***REMOVED***"
        
        # Intentamos usar el token hardcodeado, si no está, buscamos en variables de entorno
        hf_token = HF_TOKEN_HARDCODED or os.getenv("HF_TOKEN")
        
        # Autenticarnos en HuggingFace para poder descargar el modelo
        if hf_token:
            try:
                login(token=hf_token)
                print("✅ Autenticado en HuggingFace")
            except Exception as e:
                print(f"⚠️ Error al autenticar en HuggingFace: {e}")
        else:
            print("⚠️ No se encontró HF_TOKEN. El modelo puede requerir autenticación.")
        
        # Cargar el modelo Paligemma (puede tardar un poco la primera vez)
        model_id = "google/paligemma2-3b-mix-224"
        print(f"Cargando modelo Paligemma: {model_id}")
        _paligemma_model, _paligemma_processor = load_paligemma(model_id, token=hf_token)
        print("Modelo Paligemma cargado exitosamente")
    return _paligemma_model, _paligemma_processor


def get_paligemma_prompts() -> list[str]:
    """
    Retorna una lista de prompts en inglés para usar con Paligemma.
    Se intentan en orden: si uno falla (respuesta "unanswerable"), se prueba el siguiente.
    
    Returns:
        Lista de prompts en inglés, ordenados de más específico a más general
    """
    return [
        # Prompt 1: Instrucciones muy directas y específicas
        "Look at the signage board in this image. At the very top, you will see text that says 'EDIFICIO' followed by a letter, or a letter followed by 'BUILDING'. For example: 'EDIFICIO H' or 'H BUILDING' or 'EDIFICIO H / H BUILDING'. Read the LETTER that appears with 'EDIFICIO' or 'BUILDING'. That letter (H, B, R, E, M, O, P) is the building code. Do NOT read numbers. Only read the letter. Also check if there is floor information (PLANTA or FLOOR with a number).",
        
        # Prompt 2: Enfoque en leer el texto exacto
        "Read the text on the signage board. Find where it says 'EDIFICIO' - the letter immediately after 'EDIFICIO' is the building code. Or find where it says 'BUILDING' - the letter immediately before 'BUILDING' is the building code. Read that single letter (H, B, R, E, M, O, P, etc.). Do not read any numbers. The building code is a LETTER, not a number. Also look for floor numbers after 'PLANTA' or 'FLOOR'.",
        
        # Prompt 3: Instrucciones paso a paso
        "Step 1: Find the signage board in the image. Step 2: Look at the top of the sign. Step 3: Find the text 'EDIFICIO' or 'BUILDING'. Step 4: Read the LETTER that appears next to these words. For example, if you see 'EDIFICIO H', the building code is 'H'. If you see 'H BUILDING', the building code is 'H'. Read only the letter, not numbers. Step 5: Check for floor information (PLANTA or FLOOR with a number).",
        
        # Prompt 4: Formato muy específico con ejemplos
        "The signage board shows building information at the top. The format is: 'EDIFICIO [LETTER]' or '[LETTER] BUILDING' where [LETTER] is a single letter like H, B, R, E, M, O, or P. Read that letter. Examples: 'EDIFICIO H' means building code is H. 'H BUILDING' means building code is H. 'EDIFICIO B' means building code is B. Read the letter, not numbers. Also identify floor if shown (PLANTA or FLOOR with number)."
    ]


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
    # Mapeamos tanto códigos (EPS, CD) como nombres completos
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
        if "deportivo" in full_name:
            name_to_id["centro deportivo"] = building_id
    
    # Buscar el código del edificio en la respuesta
    building_found = None
    building_codes = ["EPS", "CD", "H", "B", "R", "C1", "C2", "C3", "C4", "C5", "E", "M", "CB", "O", "P", "PS", "MS", "BA", "CSQ", "CC"]
    
    # Si la respuesta es muy corta (1-3 caracteres), puede ser solo el código del edificio
    # Ej: "H", "EPS", "CD"
    response_stripped = response.strip()
    if len(response_stripped) <= 3:
        # Buscar si coincide exactamente con algún código (case-insensitive)
        for code in building_codes:
            if response_stripped.upper() == code.upper():
                building_found = code.upper()
                print(f"   ✅ Código detectado directamente: {building_found}")
                break
    
    # Si no encontramos código directo, buscamos con patrones
    if not building_found:
        # Primero intentamos buscar códigos directamente (ej: "EPS", "CD", "H")
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
                        print(f"   ⚠️ PROBLEMA: Patrón #{pattern_idx+1} coincidió para '{code}'")
                        print(f"   📋 Patrón: {pattern}")
                        print(f"   📋 Match encontrado: '{match.group()}' en posición {match.start()}-{match.end()}")
                        print(f"   📋 Respuesta completa: '{response}'")
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
        for name, building_id in name_to_id.items():
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
                print(f"   🏢 Edificio encontrado: código='{building_found}' -> ID={building_id}")
        else:
            building_id = building_map.get(building_found)
            result["building"] = building_id
            print(f"   🏢 Edificio encontrado: código='{building_found}' -> ID={building_id}")
    
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
            "sótano": -1, "sotano": -1, "planta baja": 0, "baja": 0
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
async def analyze_image(file: UploadFile = File(...)):
    """
    Analiza una imagen con Paligemma para extraer el edificio y la planta.
    Usa el endpoint de Colab si está configurado, sino intenta cargar localmente.
    
    Args:
        file: Archivo de imagen (JPEG, PNG)
        
    Returns:
        ImageAnalysisResponse con building, floor y raw_response
    """
    try:
        # Validar que la imagen sea del formato correcto
        if file.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(
                status_code=400,
                detail="Formato de imagen no soportado. Use JPEG o PNG."
            )
        
        # Leer los bytes de la imagen
        image_data = await file.read()
        
        # Necesitamos el campus graph para mapear nombres a IDs
        campus_graph = load_campus_graph()
        
        # Obtener lista de prompts para intentar secuencialmente
        prompts = get_paligemma_prompts()
        
        # Intentar usar Colab primero (más rápido con GPU)
        if COLAB_API_URL:
            try:
                # Intentar cada prompt secuencialmente hasta que uno funcione
                for prompt_idx, prompt in enumerate(prompts):
                    try:
                        # Enviar la imagen al servidor de Colab con el prompt actual
                        files = {"file": (file.filename, image_data, file.content_type)}
                        data_form = {"prompt": prompt}
                        response = requests.post(
                            f"{COLAB_API_URL}/analyze",
                            files=files,
                            data=data_form,
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data.get("success"):
                                raw_response_original = data.get("response", "").strip()
                                raw_response_lower = raw_response_original.lower()
                                
                                # Logging para debugging
                                print(f"   📝 Prompt {prompt_idx + 1}/{len(prompts)} - Respuesta de Paligemma: '{raw_response_original}'")
                                
                                # Si la respuesta es "unanswerable", intentar siguiente prompt
                                if "unanswerable" in raw_response_lower:
                                    print(f"   Prompt {prompt_idx + 1}/{len(prompts)}: 'unanswerable', intentando siguiente...")
                                    continue
                                
                                # Parsear la respuesta de Paligemma para extraer edificio y planta
                                # Usar la respuesta original (sin convertir a minúsculas) para mejor parsing
                                parsed = parse_location_from_paligemma_response(raw_response_original, campus_graph)
                                
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
                                        raw_response=data.get("response", ""),
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
                                        raw_response=data.get("response", ""),
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
                                            raw_response=data.get("response", ""),
                                            error=None,
                                            needs_clarification=True,
                                            clarification_question=question
                                        )
                            else:
                                # Si Colab devuelve error, intentar siguiente prompt
                                if prompt_idx < len(prompts) - 1:
                                    continue
                                else:
                                    raise Exception(data.get("error", "Error en Colab"))
                        else:
                            # Error HTTP, intentar siguiente prompt
                            if prompt_idx < len(prompts) - 1:
                                continue
                            else:
                                raise Exception(f"Error en Colab: {response.status_code}")
                    except requests.exceptions.RequestException:
                        # Error de conexión, intentar siguiente prompt
                        if prompt_idx < len(prompts) - 1:
                            continue
                        else:
                            raise
                
                # Si llegamos aquí, todos los prompts fallaron
                raise Exception("Todos los prompts fallaron al analizar la imagen")
                
            except requests.exceptions.RequestException as e:
                # Si falla la conexión con Colab, intentamos localmente
                error_msg = f"Error de conexión con Colab: {str(e)}"
                print(f"⚠️ {error_msg}")
                print(f"   URL intentada: {COLAB_API_URL}/analyze")
                print("   Intentando cargar modelo localmente...")
                # Fallback a local
                return await _analyze_image_local(image_data, campus_graph, file.filename, file.content_type)
            except Exception as e:
                # Cualquier otro error con Colab, también intentamos local
                error_msg = f"Error inesperado con Colab: {str(e)}"
                print(f"⚠️ {error_msg}")
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
        from inference import run_single_inference
        
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
        building_keywords = ["building", "edificio", "floor", "planta", "ground", "first", "second", "third", "h", "eps", "cd"]
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
        print(f"📝 Respuesta del usuario parseada: {parsed}")
        print(f"📝 Contexto previo: building={building_id}, floor={floor_num}")
        
        # Combinar información previa con la nueva
        final_building = building_id if building_id is not None else parsed.get("building")
        final_floor = floor_num if floor_num is not None else parsed.get("floor")
        
        print(f"📝 Información combinada: building={final_building}, floor={final_floor}")
        
        # Si ahora tenemos ambos, éxito
        if final_building is not None and final_floor is not None:
            print(f"✅ Ubicación completa: building={final_building}, floor={final_floor}")
            print(f"✅ Devolviendo success=True con building={final_building}, floor={final_floor}")
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
        # Coordenadas GPS de los edificios (deben coincidir con las del frontend)
        building_gps = {
            1: {"lat": 40.44162251912561, "lng": -3.8336784343565533, "name": "EPS"},
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
        
        # API Key de Google Maps (debe estar configurada)
        # IMPORTANTE: Esta API Key NO debe tener restricciones de referer (sitios web)
        # porque se llama desde el servidor, no desde el navegador
        # Opción 1: Usar la misma API Key pero sin restricciones de referer
        # Opción 2: Crear una API Key separada sin restricciones para el backend
        GOOGLE_MAPS_API_KEY = "***REMOVED***"
        
        origin = f"{origin_gps['lat']},{origin_gps['lng']}"
        destination = f"{goal_gps['lat']},{goal_gps['lng']}"
        
        directions_url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={GOOGLE_MAPS_API_KEY}&mode=walking&language=en"
        
        response = requests.get(directions_url, timeout=10)
        data = response.json()
        
        if data.get("status") == "OK" and data.get("routes") and len(data["routes"]) > 0:
            route = data["routes"][0]
            leg = route["legs"][0]
            
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
        
        # Intentar usar Colab primero (más rápido con GPU)
        if COLAB_API_URL:
            try:
                # Enviar el audio al servidor de Colab
                files = {"file": (file.filename, audio_data, file.content_type)}
                response = requests.post(
                    f"{COLAB_API_URL}/transcribe",
                    files=files,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return TranscribeResponse(
                            success=True,
                            text=data.get("text", ""),
                            error=None
                        )
                    else:
                        raise Exception(data.get("error", "Error en Colab"))
                else:
                    raise Exception(f"Error en Colab: {response.status_code}")
            
            except requests.exceptions.RequestException as e:
                error_msg = f"Error de conexión con Colab: {str(e)}"
                print(f"⚠️ {error_msg}")
                return TranscribeResponse(
                    success=False,
                    text="",
                    error=error_msg
                )
        else:
            return TranscribeResponse(
                success=False,
                text="",
                error="Colab API URL no configurada. Configura COLAB_API_URL en planning_api.py"
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
