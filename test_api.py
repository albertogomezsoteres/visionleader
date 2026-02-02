"""
Script para probar la API de Planificación
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_root():
    """Prueba el endpoint raíz."""
    print("=" * 60)
    print("1. Probando endpoint raíz (GET /)")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print()
        return True
    except requests.exceptions.ConnectionError:
        print("ERROR: No se puede conectar a la API. ¿Está ejecutándose?")
        print("Ejecuta: python run_api.py")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_domain():
    """Prueba obtener el dominio."""
    print("=" * 60)
    print("2. Probando obtener dominio (GET /api/domain)")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/domain", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            domain = data.get("domain", "")
            print(f"Dominio obtenido: {len(domain)} caracteres")
            print(f"Primeras líneas:")
            for line in domain.split('\n')[:5]:
                print(f"  {line}")
        else:
            print(f"Error: {response.text}")
        print()
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_plan():
    """Prueba generar un plan."""
    print("=" * 60)
    print("3. Probando generar plan (POST /api/plan)")
    print("=" * 60)
    print("Request: EPS planta 0 -> EPS planta 2")
    
    payload = {
        "initial_state": {"building": 1, "floor": 0},
        "goal_state": {"building": 1, "floor": 2},
        "humano_disponible": True
    }
    
    try:
        print(f"Enviando request a {BASE_URL}/api/plan...")
        response = requests.post(
            f"{BASE_URL}/api/plan",
            json=payload,
            timeout=30
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse:")
            print(f"  Success: {data.get('success')}")
            print(f"  Steps: {data.get('steps')}")
            print(f"  Cost: {data.get('cost')}")
            print(f"  Plan:")
            for i, action in enumerate(data.get('plan', []), 1):
                print(f"    {i}. {action}")
            
            if not data.get('success'):
                print(f"  Error: {data.get('error')}")
        else:
            print(f"Error: {response.text}")
        print()
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_plan_cross_building():
    """Prueba generar un plan entre edificios."""
    print("=" * 60)
    print("4. Probando plan entre edificios (POST /api/plan)")
    print("=" * 60)
    print("Request: EPS planta 0 -> CD planta 0")
    
    payload = {
        "initial_state": {"building": 1, "floor": 0},
        "goal_state": {"building": 2, "floor": 0},
        "humano_disponible": True
    }
    
    try:
        print(f"Enviando request a {BASE_URL}/api/plan...")
        response = requests.post(
            f"{BASE_URL}/api/plan",
            json=payload,
            timeout=30
        )
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse:")
            print(f"  Success: {data.get('success')}")
            print(f"  Steps: {data.get('steps')}")
            print(f"  Cost: {data.get('cost')}")
            print(f"  Plan:")
            for i, action in enumerate(data.get('plan', []), 1):
                print(f"    {i}. {action}")
            
            if not data.get('success'):
                print(f"  Error: {data.get('error')}")
        else:
            print(f"Error: {response.text}")
        print()
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("PRUEBAS DE LA API DE PLANIFICACIÓN")
    print("=" * 60)
    print()
    
    # Esperar un poco para que la API se inicie
    print("Esperando 3 segundos para que la API se inicie...")
    time.sleep(3)
    print()
    
    # Ejecutar pruebas
    results = []
    results.append(("Root endpoint", test_root()))
    
    if results[-1][1]:  # Si la primera prueba pasó
        results.append(("Get domain", test_domain()))
        results.append(("Generate plan (same building)", test_plan()))
        results.append(("Generate plan (cross building)", test_plan_cross_building()))
    
    # Resumen
    print("=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    for name, passed in results:
        status = "[OK]" if passed else "[FALLO]"
        print(f"  {name}: {status}")
    
    print()
    print("Para ver la documentación interactiva, abre:")
    print("  http://localhost:8000/docs")
    print()
