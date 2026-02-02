#!/bin/bash
# Script de entrada para ejecutar Fast Downward

# Si no se pasan argumentos, mostrar ayuda
if [ $# -eq 0 ]; then
    echo "Fast Downward Planner"
    echo ""
    echo "Uso:"
    echo "  docker run --rm -v \$(pwd)/pddl:/pddl fast-downward:latest <domain.pddl> <problem.pddl> [opciones]"
    echo ""
    echo "Ejemplo:"
    echo "  docker run --rm -v \$(pwd)/pddl:/pddl fast-downward:latest domain.pddl problem.pddl"
    echo ""
    echo "O ejecutar directamente fast-downward:"
    /fast-downward/fast-downward.py --help
    exit 0
fi

# Si se pasan archivos PDDL, ejecutar Fast Downward
if [ $# -ge 2 ]; then
    DOMAIN_FILE="/pddl/$1"
    PROBLEM_FILE="/pddl/$2"
    
    # Verificar que los archivos existen
    if [ ! -f "$DOMAIN_FILE" ]; then
        echo "Error: No se encuentra el archivo de dominio: $DOMAIN_FILE"
        exit 1
    fi
    
    if [ ! -f "$PROBLEM_FILE" ]; then
        echo "Error: No se encuentra el archivo de problema: $PROBLEM_FILE"
        exit 1
    fi
    
    # Ejecutar Fast Downward
    echo "Ejecutando Fast Downward..."
    echo "Dominio: $DOMAIN_FILE"
    echo "Problema: $PROBLEM_FILE"
    echo ""
    
    # Ejecutar Fast Downward
    /fast-downward/fast-downward.py "$DOMAIN_FILE" "$PROBLEM_FILE" --search "astar(lmcut())"
    
    # Mantener el contenedor corriendo un poco más para que sea visible en docker ps
    # Esto permite ver el contenedor en estado "Up" (verde) en Docker Desktop
    echo ""
    echo "Fast Downward completado. Contenedor permanecerá activo por 5 segundos..."
    sleep 5
else
    # Ejecutar con los argumentos proporcionados
    /fast-downward/fast-downward.py "$@"
fi
