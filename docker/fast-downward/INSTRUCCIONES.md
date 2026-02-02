# 🚀 Instrucciones: Instalar Fast Downward en Docker

## ✅ Paso a Paso (Windows)

### Paso 1: Abrir Docker Desktop

1. Abre **Docker Desktop** en Windows
2. Espera a que se inicie completamente (icono en la bandeja del sistema)
3. Verifica que dice "Docker Desktop is running"

### Paso 2: Abrir Terminal

Abre **PowerShell** o **CMD** y navega a la carpeta del proyecto:

```powershell
cd C:\path\to\visionleader\docker\fast-downward
```

### Paso 3: Construir la Imagen Docker

Ejecuta este comando (puede tardar 5-10 minutos):

```powershell
docker build -t fast-downward:latest .
```

**¿Qué hace esto?**
- Descarga Ubuntu 22.04
- Instala dependencias (compiladores, Python, etc.)
- Descarga el código fuente de Fast Downward desde GitHub
- Compila Fast Downward (esto es lo que más tarda)

**Espera a que termine.** Verás mensajes como:
```
Step 5/10 : RUN ./build.py
 ---> Running in abc123...
Building Fast Downward...
```

### Paso 4: Verificar que se Construyó

Ejecuta:
```powershell
docker images
```

Deberías ver una línea con `fast-downward` y `latest`.

### Paso 5: Probar Fast Downward

**Opción A: Usar el script automático (más fácil)**
```powershell
# Desde la raíz del proyecto:
python test_fast_downward_docker.py
```

**Opción B: Ejecutar manualmente**
```powershell
docker run --rm -v ${PWD}/pddl:/pddl fast-downward:latest domain.pddl problem_ejemplo.pddl
```

### Paso 6: Verificar el Resultado

Si todo funciona, deberías ver algo como:

```
Fast Downward
...
Plan length: 2 step(s)
Plan cost: 2
move obj1 loc1 loc2
move obj1 loc2 loc3
```

## ✅ Si Todo Funciona

¡Perfecto! Fast Downward está instalado y funcionando. Puedes continuar con el resto del plan.

## ❌ Si Hay Errores

### Error: "Cannot connect to Docker daemon"
- **Solución**: Abre Docker Desktop y espera a que se inicie

### Error: "No space left on device"
- **Solución**: Libera espacio en disco (necesitas ~2GB)

### Error durante la compilación
- **Solución**: 
  1. Verifica tu conexión a Internet
  2. Intenta de nuevo: `docker build -t fast-downward:latest .`
  3. Si falla, comparte el mensaje de error completo

### Error: "domain.pddl not found"
- **Solución**: Asegúrate de estar en el directorio `docker/fast-downward/`

## 📝 Comandos Útiles

```powershell
# Ver imágenes Docker
docker images

# Ver contenedores en ejecución
docker ps

# Limpiar imágenes no usadas (liberar espacio)
docker system prune -a

# Ver ayuda de Fast Downward
docker run --rm fast-downward:latest --help
```

## 🎯 Próximo Paso

Una vez que Fast Downward funcione, avísame y continuamos con:
1. Crear el dominio PDDL para el campus
2. Crear la API FastAPI
3. Integrar todo
