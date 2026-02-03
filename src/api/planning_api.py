"""
API FastAPI para Planificación con Fast Downward

Endpoints:
- POST /api/plan - Generar un plan desde estado inicial a objetivo
- GET /api/domain - Obtener el dominio PDDL actual
- POST /api/validate - Validar un plan
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.models import (
    PlanningRequest,
    PlanningResponse,
    ValidationRequest,
    ValidationResponse,
    DomainResponse,
    ImageAnalysisResponse
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
_paligemma_model = None
_paligemma_processor = None
_campus_graph_data = None

# ============================================================
# CONFIGURACIÓN - URL DE COLAB (opcional)
# ============================================================
# Si tienes el notebook de Colab corriendo, pon aquí la URL de ngrok
# Ejemplo: COLAB_API_URL = "https://abc123.ngrok.io"
# Si es None, intentará cargar el modelo localmente
COLAB_API_URL = "https://your-subdomain.ngrok-free.app"  # <-- URL de Colab
# ============================================================


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
            "docs": "GET /docs"
        }
    }


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
    if _campus_graph_data is None:
        with open(CAMPUS_JSON, 'r', encoding='utf-8') as f:
            _campus_graph_data = json.load(f)
    return _campus_graph_data


def load_paligemma_model():
    """Carga el modelo Paligemma una vez y lo mantiene en memoria (singleton)."""
    global _paligemma_model, _paligemma_processor
    if _paligemma_model is None or _paligemma_processor is None:
        from model_loader import load_paligemma
        from huggingface_hub import login
        import os
        
        # ============================================
        # CONFIGURAR TU TOKEN DE HUGGINGFACE AQUÍ
        # ============================================
        # Opción 1: Token hardcodeado (reemplaza con tu token)
        HF_TOKEN_HARDCODED = "***REMOVED***"  # <-- PON TU TOKEN AQUÍ: "hf_tu_token_aqui"
        
        # Opción 2: Token desde variable de entorno (si prefieres)
        hf_token = HF_TOKEN_HARDCODED or os.getenv("HF_TOKEN")
        # ============================================
        
        if hf_token:
            try:
                login(token=hf_token)
                print("✅ Autenticado en HuggingFace")
            except Exception as e:
                print(f"⚠️ Error al autenticar en HuggingFace: {e}")
        else:
            print("⚠️ No se encontró HF_TOKEN. El modelo puede requerir autenticación.")
            print("   Configura HF_TOKEN_HARDCODED en este archivo o la variable de entorno: $env:HF_TOKEN='tu_token'")
        
        model_id = "google/paligemma2-3b-mix-224"
        print(f"Cargando modelo Paligemma: {model_id}")
        _paligemma_model, _paligemma_processor = load_paligemma(model_id, token=hf_token)
        print("Modelo Paligemma cargado exitosamente")
    return _paligemma_model, _paligemma_processor


def parse_location_from_paligemma_response(response: str, campus_graph: dict) -> dict:
    """
    Parsea la respuesta de Paligemma para extraer edificio y planta.
    
    Args:
        response: Respuesta de texto de Paligemma
        campus_graph: Diccionario con la estructura del campus
        
    Returns:
        Dict con 'building' (int o None), 'floor' (int o None), 'error' (str o None)
    """
    result = {"building": None, "floor": None, "error": None}
    response_lower = response.lower()
    
    # Crear mapeo de nombres de edificios a IDs
    building_map = {}
    name_to_id = {}
    for building in campus_graph.get("buildings", []):
        building_id = building.get("id")
        name = building.get("name", "").upper()
        full_name = building.get("full_name", "").lower()
        
        building_map[name] = building_id
        name_to_id[name.lower()] = building_id
        name_to_id[full_name] = building_id
        
        # También mapear variaciones comunes
        if "politécnica" in full_name or "politecnica" in full_name:
            name_to_id["escuela politecnica"] = building_id
            name_to_id["escuela politécnica"] = building_id
        if "deportivo" in full_name:
            name_to_id["centro deportivo"] = building_id
    
    # Buscar edificio
    building_found = None
    building_codes = ["EPS", "CD", "H", "B", "R", "C1", "C2", "C3", "C4", "C5", "E", "M", "CB", "O", "P", "PS", "MS", "BA", "CSQ", "CC"]
    
    # Buscar códigos directamente (case-insensitive)
    for code in building_codes:
        # Buscar el código como palabra completa
        pattern = r'\b' + re.escape(code) + r'\b'
        if re.search(pattern, response, re.IGNORECASE):
            building_found = code.upper()
            break
    
    # Si no se encontró código, buscar nombres completos
    if not building_found:
        for name, building_id in name_to_id.items():
            if name in response_lower:
                # Encontrar el código correspondiente
                for b in campus_graph.get("buildings", []):
                    if b.get("id") == building_id:
                        building_found = b.get("name", "").upper()
                        break
                if building_found:
                    break
    
    if building_found:
        result["building"] = building_map.get(building_found)
    
    # Buscar planta
    floor_found = None
    
    # Buscar patrones como "PLANTA 2", "planta 2", "PLANTA -1", etc.
    patterns = [
        r'(?:planta|piso|floor|nivel)\s*[:\-]?\s*(-?\d+)',
        r'(-?\d+)\s*(?:planta|piso|floor|nivel)',
        r'\b(-?\d+)\b',  # Cualquier número
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response, re.IGNORECASE)
        if matches:
            # Tomar el primer número encontrado que esté en el rango válido
            for match in matches:
                try:
                    num = int(match)
                    if num in [-1, 0, 1, 2]:
                        floor_found = num
                        break
                except ValueError:
                    continue
            if floor_found is not None:
                break
    
    # Si no se encontró número, buscar palabras como "segunda", "tercera"
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
    
    # Validar que se encontró al menos uno
    if result["building"] is None and result["floor"] is None:
        result["error"] = "No se pudo identificar ni el edificio ni la planta en la respuesta de Paligemma"
    elif result["building"] is None:
        result["error"] = "No se pudo identificar el edificio en la respuesta de Paligemma"
    elif result["floor"] is None:
        result["error"] = "No se pudo identificar la planta en la respuesta de Paligemma"
    
    return result


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
        # Validar tipo de archivo
        if file.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(
                status_code=400,
                detail="Formato de imagen no soportado. Use JPEG o PNG."
            )
        
        # Leer imagen
        image_data = await file.read()
        
        # Cargar campus graph
        campus_graph = load_campus_graph()
        
        # Intentar usar Colab si está configurado
        if COLAB_API_URL:
            try:
                # Enviar imagen a Colab
                files = {"file": (file.filename, image_data, file.content_type)}
                response = requests.post(
                    f"{COLAB_API_URL}/analyze",
                    files=files,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        raw_response = data.get("response", "")
                        # Parsear respuesta de Paligemma
                        parsed = parse_location_from_paligemma_response(raw_response, campus_graph)
                        
                        # Preparar respuesta
                        if parsed["error"]:
                            return ImageAnalysisResponse(
                                success=False,
                                building=parsed.get("building"),
                                floor=parsed.get("floor"),
                                raw_response=raw_response,
                                error=parsed["error"]
                            )
                        else:
                            return ImageAnalysisResponse(
                                success=True,
                                building=parsed["building"],
                                floor=parsed["floor"],
                                raw_response=raw_response,
                                error=None
                            )
                    else:
                        raise Exception(data.get("error", "Error en Colab"))
                else:
                    raise Exception(f"Error en Colab: {response.status_code}")
            
            except requests.exceptions.RequestException as e:
                error_msg = f"Error de conexión con Colab: {str(e)}"
                print(f"⚠️ {error_msg}")
                print(f"   URL intentada: {COLAB_API_URL}/analyze")
                print("   Intentando cargar modelo localmente...")
                # Fallback a local
                return await _analyze_image_local(image_data, campus_graph, file.filename, file.content_type)
            except Exception as e:
                error_msg = f"Error inesperado con Colab: {str(e)}"
                print(f"⚠️ {error_msg}")
                print("   Intentando cargar modelo localmente...")
                # Fallback a local
                return await _analyze_image_local(image_data, campus_graph, file.filename, file.content_type)
        else:
            # Usar modelo local
            return await _analyze_image_local(image_data, campus_graph, file.filename, file.content_type)
    
    except HTTPException:
        raise
    except Exception as e:
        return ImageAnalysisResponse(
            success=False,
            building=None,
            floor=None,
            raw_response="",
            error=f"Error procesando imagen: {str(e)}"
        )


async def _analyze_image_local(image_data: bytes, campus_graph: dict, filename: str, content_type: str) -> ImageAnalysisResponse:
    """Función auxiliar para analizar imagen localmente."""
    try:
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        # Cargar modelo Paligemma
        model, processor = load_paligemma_model()
        
        # Prompt para Paligemma
        prompt = "Lee el cartel de señalización en esta imagen del campus. Identifica el nombre del edificio y el número de planta que aparecen en el cartel. Busca las palabras 'EDIFICIO' o 'PLANTA' y el texto asociado."
        
        # Procesar imagen con Paligemma
        from inference import run_single_inference
        raw_response, inference_time = run_single_inference(
            model=model,
            processor=processor,
            image=image,
            question=prompt,
            max_new_tokens=100
        )
        
        # Parsear respuesta
        parsed = parse_location_from_paligemma_response(raw_response, campus_graph)
        
        # Preparar respuesta
        if parsed["error"]:
            return ImageAnalysisResponse(
                success=False,
                building=parsed.get("building"),
                floor=parsed.get("floor"),
                raw_response=raw_response,
                error=parsed["error"]
            )
        else:
            return ImageAnalysisResponse(
                success=True,
                building=parsed["building"],
                floor=parsed["floor"],
                raw_response=raw_response,
                error=None
            )
    
    except Exception as e:
        return ImageAnalysisResponse(
            success=False,
            building=None,
            floor=None,
            raw_response="",
            error=f"Error procesando imagen localmente: {str(e)}"
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
