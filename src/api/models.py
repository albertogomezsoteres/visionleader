"""
Modelos Pydantic para la API de Planificación
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Union


class PlanningRequest(BaseModel):
    """Request para generar un plan."""
    initial_state: Dict[str, int] = Field(
        ...,
        description="Estado inicial: {'building': int, 'floor': int}",
        example={"building": 1, "floor": 0}
    )
    goal_state: Optional[Dict[str, int]] = Field(
        None,
        description="Estado objetivo: {'building': int, 'floor': int}. Usar goal_functional si no se especifica.",
        example={"building": 1, "floor": 2}
    )
    goal_functional: Optional[str] = Field(
        None,
        description="Objetivo funcional: 'cafeteria' o 'gimnasio'. Se usa si goal_state no se especifica.",
        example="cafeteria"
    )
    humano_disponible: bool = Field(
        True,
        description="Si hay humano disponible para ayudar con ascensores"
    )


class PlanningResponse(BaseModel):
    """Response con el plan generado."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    success: bool = Field(..., description="Si se encontró un plan")
    plan: List[str] = Field(default_factory=list, description="Lista de acciones del plan")
    steps: int = Field(0, description="Número de pasos del plan")
    cost: int = Field(0, description="Costo del plan")
    initial_state: Optional[Dict[str, int]] = Field(None, description="Estado inicial usado")
    goal_state: Optional[Any] = Field(None, description="Estado objetivo usado (puede ser específico {'building': int, 'floor': int} o funcional {'functional': str, 'description': str})")
    error: Optional[str] = Field(None, description="Mensaje de error si falla")
    output: Optional[str] = Field(None, description="Salida completa de Fast Downward")


class ValidationRequest(BaseModel):
    """Request para validar un plan."""
    plan: List[str] = Field(..., description="Lista de acciones del plan a validar")
    initial_state: Dict[str, int] = Field(..., description="Estado inicial")
    goal_state: Dict[str, int] = Field(..., description="Estado objetivo")


class ValidationResponse(BaseModel):
    """Response de validación."""
    valid: bool = Field(..., description="Si el plan es válido")
    message: str = Field(..., description="Mensaje de validación")


class DomainResponse(BaseModel):
    """Response con el dominio PDDL."""
    domain: str = Field(..., description="Contenido del dominio PDDL")


class ImageAnalysisResponse(BaseModel):
    """Response del análisis de imagen con Paligemma."""
    success: bool = Field(..., description="Si se pudo extraer la ubicación correctamente")
    building: Optional[int] = Field(None, description="ID del edificio identificado")
    floor: Optional[int] = Field(None, description="Número de planta identificada")
    raw_response: str = Field(..., description="Respuesta completa de Paligemma")
    error: Optional[str] = Field(None, description="Mensaje de error si falla")
    needs_clarification: bool = Field(False, description="Si el sistema necesita más información del usuario")
    clarification_question: Optional[str] = Field(None, description="Pregunta que hace el sistema para clarificar")
    landmarks: Optional[List[str]] = Field(None, description="Landmarks detectados en la imagen (Agente 1)")
    resources: Optional[List[str]] = Field(None, description="Recursos detectados (elevator, stairs, etc.)")


class ClarificationRequest(BaseModel):
    """Request para clarificar ubicación cuando falta información."""
    user_response: str = Field(..., description="Respuesta del usuario (texto o transcripción de voz)")
    previous_context: Dict[str, Any] = Field(..., description="Contexto previo: building, floor, raw_response, etc.")


class ClarificationResponse(BaseModel):
    """Response de la clarificación."""
    success: bool = Field(..., description="Si se completó la información correctamente")
    building: Optional[int] = Field(None, description="ID del edificio identificado")
    floor: Optional[int] = Field(None, description="Número de planta identificada")
    needs_clarification: bool = Field(False, description="Si aún necesita más información")
    clarification_question: Optional[str] = Field(None, description="Nueva pregunta si aún falta información")
    error: Optional[str] = Field(None, description="Mensaje de error si falla")


class TranscribeRequest(BaseModel):
    """Request para transcribir audio con Whisper."""
    audio_data: bytes = Field(..., description="Datos de audio en formato WAV o similar")


class TranscribeResponse(BaseModel):
    """Response de la transcripción."""
    success: bool = Field(..., description="Si la transcripción fue exitosa")
    text: str = Field(..., description="Texto transcrito del audio")
    error: Optional[str] = Field(None, description="Mensaje de error si falla")


class GPSRouteRequest(BaseModel):
    """Request para obtener ruta GPS entre edificios."""
    from_building: int = Field(..., description="ID del edificio origen")
    to_building: int = Field(..., description="ID del edificio destino")


class GPSRouteResponse(BaseModel):
    """Response con la ruta GPS."""
    success: bool = Field(..., description="Si se obtuvo la ruta correctamente")
    distance: Optional[str] = Field(None, description="Distancia de la ruta")
    duration: Optional[str] = Field(None, description="Duración estimada")
    steps: Optional[List[Dict[str, Any]]] = Field(None, description="Lista de pasos de la ruta")
    polyline: Optional[str] = Field(None, description="Polilínea de la ruta")
    error: Optional[str] = Field(None, description="Mensaje de error si falla")


class ConversationRequest(BaseModel):
    """Request para conversación con el agente."""
    session_id: str = Field(..., description="ID de la sesión de conversación")
    user_message: str = Field(..., description="Mensaje del usuario")
    image_analysis: Optional[Dict[str, Any]] = Field(None, description="Resultado del análisis de imagen (opcional)")


class ConversationResponse(BaseModel):
    """Response de la conversación."""
    response: str = Field(..., description="Respuesta del sistema")
    action: str = Field(..., description="Acción a tomar (ask_location, ask_goal, search_goal, generate_plan, etc.)")
    needs_input: bool = Field(..., description="Si necesita más información del usuario")
    context: Dict[str, Any] = Field(..., description="Contexto de la conversación actualizado")
    goal_location: Optional[Dict[str, int]] = Field(None, description="Ubicación del objetivo encontrado (si aplica)")
    plan_request: Optional[Dict[str, Any]] = Field(None, description="Request para generar plan (si action=generate_plan)")
    error: Optional[str] = Field(None, description="Mensaje de error si falla")
