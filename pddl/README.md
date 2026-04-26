# PDDL del campus

## Dominio

`pddl/domain_indoor.pddl` (`campus-navigation`) — dominio único que cubre toda la navegación del campus: intra-edificio al nivel de sala (`location`) y cruces entre edificios vía la acción `outdoor_walk`.

## Acciones y costes

Costes en segundos de esfuerzo:

- `walk`: `(distance u1 u2)` metros
- `verify_elevator`: 5
- `use_elevator`: 15
- `validate_stairs`: 5
- `climb_stairs_accessible`: 30 — requiere `(not hurry_mode)`
- `descend_stairs_accessible`: 25 — requiere `(not hurry_mode)`
- `climb_stairs_fast`: 12 — requiere `(hurry_mode)`
- `descend_stairs_fast`: 8 — requiere `(hurry_mode)`
- `outdoor_walk`: 60 — hop exterior entre entradas de edificios distintos

Todas las variantes de escalera exigen `(stairs_verified u)` como precondición, de modo que el check con VLM (`validate_stairs`) es obligatorio en ambos modos.

## Predicados clave

- `(at ?p ?u)` — posición del usuario
- `(open ?u)` — disponibilidad dinámica (clausura)
- `(is_elevator ?u)` / `(is_stairs ?u)` — tipo de nodo
- `(elevator_verified ?u)` / `(stairs_verified ?u)` — confirmación por VLM
- `(hurry_mode)` — flag 0-ario
- Aristas: `(hallway_connected …)`, `(elevator_connected …)`, `(stairs_up_connected …)`, `(stairs_down_connected …)`, `(outdoor_connected …)`

## Generación de problemas

`src/navigation/hierarchical_pddl_converter.py::HierarchicalPDDLConverter` construye cada problema dinámicamente en cada petición, leyendo:

- `config/campus_topology.json` — edificios, plantas, salas, aristas `local_connections`, aristas exteriores `connections`
- `config/closed_rooms.json` — estado de clausuras (releído en cada planning)

Cuando origen y destino están en edificios distintos, el problema incluye las salas de ambos edificios y las aristas `outdoor_connected` entre sus entradas para que un solo plan resuelva la ruta completa.

Los IDs de sala que se repiten entre edificios (`elevator`, `stairs`, `bathroom`) se prefijan con el nombre del edificio (en minúscula) y el piso en PDDL: `elevator_g_f0`, `stairs_cd_fm1`. Los IDs únicos (`classroom_g_1_4`, `ai_lab`, `entrance_2`) se mantienen tal cual. El objeto `user` (de tipo `person`) representa al único usuario.

## Ejemplos en `problems/`

- `problem_g_intra_demo.pddl` — intra-G: entrance_2 → classroom_g_1_4
- `problem_g_to_cd_demo.pddl` — cross-building: classroom_g_1_4 (G) → gym (CD)

Son ejemplos ilustrativos; en runtime el planner nunca los lee — se escriben tempfiles por petición.

## Probar manualmente

```bash
docker run --rm -v "$(pwd)/pddl:/pddl" fast-downward:latest \
  domain_indoor.pddl problems/problem_g_intra_demo.pddl
```
