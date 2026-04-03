"""
Script para ejecutar el dashboard de Streamlit
"""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    dashboard_app = project_root / "dashboard" / "app.py"
    # Ejecutar streamlit
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_app)])
