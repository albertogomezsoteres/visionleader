# PDDL del campus

## Ficheros

- **`domain.pddl`** — Dominio fijo: predicados, acciones y costes (`:action-costs`). La abstracción es **edificio + planta** (no aulas sueltas en el PDDL).

- **Problemas (`.pddl`)** — Se **generan en tiempo de ejecución** desde `config/campus_graph.json` con `src/navigation/pddl_converter.py` (no hay `problem_template.pddl` en el repo). Fast Downward recibe un fichero temporal.

## Flujo

1. El grafo JSON aporta `connections` (topología macro) y `buildings`.
2. `CampusGraphToPDDL.generate_problem(...)` escribe init + goal + métrica.
3. `FastDownwardPlanner` (Docker, imagen `fast-downward:latest`) resuelve el problema.

## Documentación del dominio

Ver comentarios al inicio de `domain.pddl`: modo accesible vs `modo_rapido`, validación autónoma de ascensor/escaleras, y movimiento entre edificios.

## Ejemplo Docker

```bash
docker run --rm -v "%CD%:/pddl" fast-downward:latest domain.pddl <problem>.pddl
```

(En Linux/macOS sustituir el volumen por `$(pwd):/pddl`.)
