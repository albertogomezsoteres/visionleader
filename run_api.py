"""
Script para ejecutar la API de Planificación

Ejecutar: python run_api.py
"""

import uvicorn
from pathlib import Path
import sys

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from api.planning_api import app

if __name__ == "__main__":
    print("=" * 60)
    print("Campus Navigation Planning API")
    print("=" * 60)
    print("\nServidor iniciando en http://localhost:8000")
    print("Documentación disponible en http://localhost:8000/docs")
    print("\nPresiona Ctrl+C para detener el servidor\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False
    )
