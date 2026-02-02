# Fast Downward Docker Setup

Este directorio contiene los archivos necesarios para ejecutar Fast Downward en Docker.

## Instrucciones Paso a Paso

### Paso 1: Verificar que Docker está instalado

Abre una terminal y ejecuta:
```bash
docker --version
```

Si no está instalado, instálalo desde: https://www.docker.com/get-started

### Paso 2: Construir la imagen Docker

Desde la raíz del proyecto (donde está el directorio `docker/`), ejecuta:

```bash
cd docker/fast-downward
docker build -t fast-downward:latest .
```

**Nota**: La compilación de Fast Downward puede tardar 5-10 minutos. Ten paciencia.

### Paso 3: Verificar que la imagen se construyó correctamente

```bash
docker images | grep fast-downward
```

Deberías ver algo como:
```
fast-downward   latest   abc123def456   2 minutes ago   1.2GB
```

### Paso 4: Probar Fast Downward

Ejecuta el test Python desde la raíz del proyecto:

```bash
# Desde la raíz del proyecto
python test_fast_downward_docker.py
```

O prueba directamente con tu dominio:

```bash
# Desde la raíz del proyecto
docker run --rm -v "$(pwd)/pddl:/pddl" fast-downward:latest domain.pddl problem_ejemplo.pddl
```

### Paso 5: Verificar el resultado

Si todo funciona correctamente, deberías ver:
- Información sobre la búsqueda
- Un plan de acciones (ej: `move obj1 loc1 loc2`, `move obj1 loc2 loc3`)
- Mensaje de éxito

## Uso General

Para usar Fast Downward con tus propios archivos PDDL:

1. Coloca tus archivos `domain.pddl` y `problem.pddl` en un directorio (ej: `pddl/`)
2. Ejecuta:
   ```bash
   docker run --rm -v /ruta/a/tus/archivos:/pddl fast-downward:latest domain.pddl problem.pddl
   ```

## Solución de Problemas

### Error: "Cannot connect to the Docker daemon"
- Asegúrate de que Docker Desktop esté ejecutándose
- En Windows/Mac, abre Docker Desktop

### Error: "No such file or directory"
- Verifica que los archivos PDDL estén en el directorio montado
- Usa rutas absolutas si es necesario

### Error durante la compilación
- Verifica que tienes suficiente espacio en disco (necesitas ~2GB)
- Asegúrate de tener conexión a Internet (descarga código desde GitHub)

## Próximos Pasos

Una vez que Fast Downward funcione correctamente:
1. Crear el dominio PDDL para el campus (basado en `campus_graph.json`)
2. Crear problemas PDDL dinámicamente desde estados inicial/final
3. Integrar con la API FastAPI
