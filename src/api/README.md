# API de Planificación del Campus

API REST para generar planes de navegación usando PDDL y Fast Downward.

## Instalación

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Asegurarse de que Fast Downward está disponible en Docker:
```bash
docker images | grep fast-downward
```

## Ejecutar la API

```bash
python scripts/run_api.py
```

La API estará disponible en:
- **API**: http://localhost:8000
- **Documentación interactiva**: http://localhost:8000/docs
- **Documentación alternativa**: http://localhost:8000/redoc

## Endpoints

### POST /api/plan

Genera un plan de navegación desde un estado inicial a un objetivo.

**Request:**
```json
{
  "initial_state": {
    "building": 1,
    "floor": 0
  },
  "goal_state": {
    "building": 1,
    "floor": 2
  },
  "humano_disponible": true
}
```

**Response:**
```json
{
  "success": true,
  "plan": [
    "pedir_ayuda_ascensor edificio_1 planta_0 elevator",
    "usar_ascensor robot1 edificio_1 planta_0 planta_1 elevator",
    "usar_ascensor robot1 edificio_1 planta_1 planta_2 elevator"
  ],
  "steps": 3,
  "cost": 3,
  "initial_state": {"building": 1, "floor": 0},
  "goal_state": {"building": 1, "floor": 2}
}
```

### GET /api/domain

Obtiene el dominio PDDL actual.

**Response:**
```json
{
  "domain": "(define (domain campus-navigation)..."
}
```

### POST /api/validate

Valida un plan.

**Request:**
```json
{
  "plan": ["usar_ascensor robot1 edificio_1 planta_0 planta_1 elevator"],
  "initial_state": {"building": 1, "floor": 0},
  "goal_state": {"building": 1, "floor": 1}
}
```

**Response:**
```json
{
  "valid": true,
  "message": "Plan validated. Generated plan has 1 steps."
}
```

## Ejemplos de Uso

### Usando curl

```bash
# Generar un plan
curl -X POST "http://localhost:8000/api/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "initial_state": {"building": 1, "floor": 0},
    "goal_state": {"building": 1, "floor": 2}
  }'

# Obtener el dominio
curl "http://localhost:8000/api/domain"
```

### Usando Python

```python
import requests

# Generar un plan
response = requests.post(
    "http://localhost:8000/api/plan",
    json={
        "initial_state": {"building": 1, "floor": 0},
        "goal_state": {"building": 1, "floor": 2}
    }
)

result = response.json()
if result["success"]:
    print(f"Plan encontrado con {result['steps']} pasos:")
    for action in result["plan"]:
        print(f"  - {action}")
else:
    print(f"Error: {result.get('error')}")
```

## Estructura de Edificios

- **Edificio 1 (EPS)**: Plantas -1, 0, 1, 2 (con ascensor y escaleras)
- **Edificio 2 (CD)**: Plantas -1, 0, 1, 2 (solo escaleras, cafetería en planta 0)
- **Edificio 3 (H)**: Plantas 0, 1, 2 (con ascensor y escaleras)

## Notas

- Los planes se generan dinámicamente desde el estado inicial/final
- Los archivos PDDL temporales se crean y eliminan automáticamente
- La API requiere que Docker esté ejecutándose con la imagen `fast-downward:latest`
