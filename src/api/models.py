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
