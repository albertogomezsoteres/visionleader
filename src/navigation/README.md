# Navegación simbólica (PDDL + Fast Downward)

Este módulo implementa la capa de planificación macro del sistema:

`campus_graph.json` (connections) → problema PDDL → Fast Downward → acciones.

## Componentes

- `pddl_converter.py`  
  Convierte el grafo JSON a un problema PDDL temporal.
- `fast_downward_client.py`  
  Ejecuta Fast Downward en Docker (`fast-downward:latest`) y parsea el plan.
- `conversation_agent.py`  
  Interpreta acciones PDDL y las transforma en pasos de navegación para la app.

## Nivel de abstracción

- **PDDL (macro):** edificio + planta y tipos de conexión (`elevator`, `stairs_up`,
  `stairs_down`, `hallway`).
- **Grafo local (micro):** instrucciones dentro de una misma planta desde
  `local_connections` (incluye encadenado BFS cuando no hay arista directa).

## Modelo actual del dominio

- Ascensor con validación autónoma: `verificar_ascensor` + `usar_ascensor`.
- Escaleras en modo accesible: `validar_escaleras` + `subir/bajar_escaleras`.
- Escaleras en modo rápido: `subir/bajar_escaleras_rapido`.
- Movimiento entre edificios: `mover_edificio`.

## Notas operativas

- Rutas entre distintas plantas o edificios dependen de Fast Downward.
- Si Docker o la imagen no están disponibles, no se genera ruta macro.
- Costes de planificación definidos en `pddl/domain.pddl` (`:action-costs`).
