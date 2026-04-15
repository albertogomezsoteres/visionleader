# PDDL del campus

## Dominios

El sistema usa **dos dominios PDDL** separados que se cargan según el tipo de plan:

- **`domain_outdoor.pddl`** (`campus-outdoor`) — Navegación entre edificios del campus. Razona al nivel de `(edificio, planta)` sin entrar en habitaciones concretas. Tipos: `robot`, `edificio`, `planta`, `tipo_conexion`. Se usa cuando el origen y el destino están en edificios distintos.

- **`domain_indoor.pddl`** (`building-indoor`) — Navegación intra-edificio al nivel de sala (`ubicacion`). Compartido por los 14 edificios de UFV. Incluye distancias métricas en el fluente `(distancia ?u1 ?u2)` y cierres dinámicos vía el predicado `(abierto ?u)`. Edificio G usa distancias medidas reales; los demás usan una aproximación de 15 m por hop.

## Acciones y costes

Ambos dominios comparten el mismo esquema de acciones: `caminar`/`mover_edificio`, `verificar_ascensor`, `usar_ascensor`, `validar_escaleras`, `subir_escaleras`, `bajar_escaleras`, `subir_escaleras_rapido`, `bajar_escaleras_rapido`. Los costes de `domain_indoor` están en unidades de segundos de esfuerzo; los de `domain_outdoor` son arbitrarios pero internamente consistentes.

El flag `(modo_rapido)` cambia el modelo de costes: modo accesible preferirá ascensor frente a escaleras, modo rápido preferirá escaleras para distancias cortas.

## Generación de problemas

Los ficheros de problema se **generan dinámicamente** desde `config/campus_topology.json` y `config/campus_places.json`:

- `src/navigation/campus_graph_to_pddl.py::CampusGraphToPDDL` → outdoor
- `src/navigation/hierarchical_pddl_converter.py::HierarchicalPDDLConverter` → indoor

`pddl/problems/` contiene un problem file demo por edificio. Son ejemplos ilustrativos — el runtime nunca los lee, escribe tempfiles en cada petición.

## Flujo de ejecución

1. `ConversationAgent._compute_route` decide si el plan es intra o inter-edificio.
2. El converter adecuado genera un problem tempfile en `pddl/`.
3. `FastDownwardPlanner.plan()` ejecuta Fast Downward en Docker con `astar(lmcut())`.
4. El plan se parsea a acciones PDDL y se convierte a pasos TTS.

## Probar manualmente

```bash
docker run --rm -v "$(pwd):/pddl" fast-downward:latest \
  domain_indoor.pddl problems/problem_G_demo.pddl
```
