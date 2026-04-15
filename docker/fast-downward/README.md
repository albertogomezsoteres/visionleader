# Fast Downward Docker

Imagen Docker que empaqueta Fast Downward para que el backend pueda invocar al planificador clásico desde Python sin tener que compilarlo en el host.

## Construir la imagen

Desde la raíz del proyecto:

```bash
cd docker/fast-downward
docker build -t fast-downward:latest .
```

La compilación tarda 5–10 minutos la primera vez. Requiere conexión a Internet (descarga el código fuente de Fast Downward).

## Verificar la imagen

```bash
docker images | grep fast-downward
```

Salida esperada:

```
fast-downward   latest   <id>   <fecha>   ~1.2GB
```

## Ejecución directa (debug)

Para invocar Fast Downward sobre un par `dominio + problema`:

```bash
docker run --rm -v "$(pwd)/pddl:/pddl" fast-downward:latest domain_indoor.pddl problems/problem_G_demo.pddl
```

El contenedor monta la carpeta `pddl/` del repo en `/pddl` dentro del contenedor. La salida muestra la búsqueda y, si tiene éxito, el plan línea a línea.

## Uso desde el backend

El backend nunca lanza Docker manualmente. `src/navigation/fast_downward_client.py` envuelve la llamada y limpia los tempfiles. La API de planificación (`/api/plan`) requiere que la imagen `fast-downward:latest` esté disponible localmente; si no lo está, la respuesta indica que no se puede generar ruta.

## Solución de problemas

- **`Cannot connect to the Docker daemon`** — Docker Desktop no está arrancado.
- **`No such file or directory`** dentro del contenedor — verifica que el `-v` apunta a una ruta absoluta correcta y que el archivo PDDL existe en esa carpeta.
- **Build falla** — comprueba espacio en disco (~2 GB) y que el host tiene salida a Internet.
