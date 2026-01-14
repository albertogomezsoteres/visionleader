"""
Script para ejecutar el dashboard de Streamlit
"""
import subprocess
import sys

if __name__ == "__main__":
    # Ejecutar streamlit
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard/app.py"])
