# Sistema de Navegación con PDDL y Fast Downward

Sistema de planificación de navegación basado en PDDL (Planning Domain Definition Language) usando Fast Downward como planificador.

## Arquitectura

```
campus_graph.json → PDDL Domain/Problem → Fast Downward (Docker) → Plan de Acciones
```

## Componentes

### 1. Conversor PDDL (`pddl_converter.py`)

Convierte el grafo del campus desde JSON a archivos PDDL:
- **Domain**: Define tipos, predicados y acciones (`pddl/domain.pddl`)
- **Problem**: Define objetos, estado inicial y objetivo (generado dinámicamente)

### 2. Cliente Fast Downward (`fast_downward_client.py`)

Ejecuta Fast Downward en un contenedor Docker para generar planes:
- Crea archivos PDDL temporales
- Ejecuta Fast Downward en Docker
- Parsea el plan resultante

## Uso Básico

### Ejemplo 1: Generar un Plan

```python
from navigation.pddl_converter import CampusGraphToPDDL
from navigation.fast_downward_client import FastDownwardPlanner

# Inicializar componentes
converter = CampusGraphToPDDL("config/campus_graph.json")
planner = FastDownwardPlanner()

# Generar problema PDDL
problem = converter.generate_problem(
    initial_state=(1, 0),  # Edificio 1, Planta 0
    goal_state=(2, 0)       # Edificio 2, Planta 0
)

# Guardar problema temporalmente
with open("problem.pddl", "w") as f:
    f.write(problem)

# Generar plan
result = planner.plan("pddl/domain.pddl", "problem.pddl")

if result["success"]:
    print("Plan encontrado:")
    for action in result["plan"]:
        print(f"  {action}")
else:
    print(f"Error: {result.get('error')}")
```

### Ejemplo 2: Objetivos Funcionales

```python
# Ir a la cafetería (CD planta 0)
result = converter.generate_problem(
    initial_state=(1, 0),
    goal_functional="cafeteria"
)

# Ir al gimnasio (CD planta -1)
result = converter.generate_problem(
    initial_state=(1, 0),
    goal_functional="gimnasio"
)
```

## Estructura del Dominio PDDL

El dominio define:

- **Tipos**: `robot`, `edificio`, `planta`, `tipo_conexion`
- **Predicados**: 
  - `en(robot, edificio, planta)` - Ubicación del robot
  - `hay_ascensor(edificio, planta)` - Recursos disponibles
  - `hay_escalera(edificio, planta)`
  - `hay_cafeteria(edificio, planta)`
  - `hay_gimnasio(edificio, planta)`
  - `conectado(edificio1, planta1, edificio2, planta2, tipo)` - Conexiones
  - `ascensor_disponible(edificio, planta)` - Estado de ascensores
  - `humano_disponible()` - Disponibilidad de ayuda humana
  - `escaleras_preparadas(edificio, planta)` - Preparación de escaleras

- **Acciones**:
  - `mover_edificio` - Moverse entre edificios (misma planta)
  - `pedir_ayuda_ascensor` - Solicitar ayuda para usar ascensor
  - `usar_ascensor` - Usar ascensor para cambiar de planta
  - `preparar_escaleras` - Preparar escaleras (paso adicional)
  - `subir_escaleras` - Subir escaleras
  - `bajar_escaleras` - Bajar escaleras

## Preferencias de Costo

El sistema está diseñado para preferir **ascensores sobre escaleras** (más seguro para personas con baja visibilidad):

- **Ascensor**: 2 pasos (pedir ayuda + usar)
- **Escaleras**: 2 pasos (preparar + usar), pero menos preferible

## API REST

El sistema expone una API FastAPI en `src/api/planning_api.py`:

```bash
# Iniciar API
python run_api.py

# Generar plan (POST /api/plan)
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "initial_state": {"building": 1, "floor": 0},
    "goal_state": {"building": 2, "floor": 0},
    "humano_disponible": true
  }'
```

## Interfaz Web

Abre `demo_interactiva.html` en el navegador para una interfaz interactiva que permite:
- Seleccionar estado inicial y objetivo
- Elegir objetivos funcionales (cafetería, gimnasio)
- Ver el plan generado

## Estructura del Campus

El archivo `config/campus_graph.json` define:
- **Edificios**: ID, nombre, plantas, ascensores, escaleras
- **Conexiones**: Entre edificios y plantas
- **Recursos especiales**: Cafetería (CD planta 0), Gimnasio (CD planta -1)

## Requisitos

- Docker (para ejecutar Fast Downward)
- Python 3.8+
- FastAPI (para la API REST)

## Notas

- Fast Downward se ejecuta en un contenedor Docker
- Los archivos PDDL se generan dinámicamente para cada problema
- El sistema minimiza el número de pasos, prefiriendo ascensores sobre escaleras
