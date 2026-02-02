# Archivos PDDL del Campus

Este directorio contiene los archivos PDDL (Planning Domain Definition Language) para la planificación de navegación en el campus UFV.

## Archivos

- `domain.pddl` - Dominio PDDL con predicados y acciones del campus
- `problem_template.pddl` - Template para generar problemas dinámicamente
- `problem_*.pddl` - Problemas PDDL específicos (generados automáticamente)

## Dominio PDDL

### Tipos
- `robot` - El robot/cobot que se mueve
- `edificio` - Edificios del campus (EPS=1, CD=2, H=3)
- `planta` - Plantas de los edificios (-1, 0, 1, 2)
- `tipo_conexion` - Tipos de conexión (elevator, stairs_up, stairs_down, hallway)

### Predicados

#### Ubicación
- `(en ?r - robot ?b - edificio ?p - planta)` - El robot está en un edificio y planta específicos

#### Recursos
- `(hay_ascensor ?b - edificio ?p - planta)` - Hay ascensor en esa ubicación
- `(hay_escalera ?b - edificio ?p - planta)` - Hay escalera en esa ubicación
- `(hay_cafeteria ?b - edificio ?p - planta)` - Hay cafetería en esa ubicación

#### Conexiones (Relaciones Binarias)
- `(conectado ?b1 - edificio ?p1 - planta ?b2 - edificio ?p2 - planta ?tipo - tipo_conexion)` - Dos ubicaciones están conectadas

#### Estado de Ascensores (Cobots)
- `(ascensor_disponible ?b - edificio ?p - planta)` - El ascensor está disponible para usar
- `(humano_disponible)` - Hay un humano disponible para ayudar

### Acciones

1. **mover_edificio** - Moverse entre edificios en la misma planta (usando hallway)
2. **pedir_ayuda_ascensor** - Pedir ayuda al humano para usar el ascensor
3. **usar_ascensor** - Usar el ascensor (requiere que esté disponible)
4. **subir_escaleras** - Subir escaleras dentro del mismo edificio
5. **bajar_escaleras** - Bajar escaleras dentro del mismo edificio

## Uso

### Generar un problema PDDL

Los problemas PDDL se generan dinámicamente desde estados inicial/final usando el conversor (`src/navigation/pddl_converter.py`).

### Ejecutar con Fast Downward

```bash
docker run --rm -v $(pwd):/pddl fast-downward:latest domain.pddl problem.pddl
```

## Ejemplo de Problema

```pddl
(define (problem ejemplo)
  (:domain campus-navigation)
  
  (:objects
    robot1 - robot
    eps cd h - edificio
    planta_m1 planta_0 planta_1 planta_2 - planta
    elevator stairs_up stairs_down hallway - tipo_conexion
  )
  
  (:init
    (en robot1 eps planta_0)
    (hay_ascensor eps planta_0)
    (conectado eps planta_0 eps planta_1 elevator)
    ...
  )
  
  (:goal
    (en robot1 eps planta_2)
  )
)
```
