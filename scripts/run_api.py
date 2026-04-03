"""
Script para ejecutar la API de Planificación

Ejecutar: python scripts/run_api.py
"""

import uvicorn
from pathlib import Path
import sys

from dotenv import load_dotenv

# Añadir src al path
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root / "src"))

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
