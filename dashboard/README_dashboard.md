# PaliGemma Evaluation Dashboard

Dashboard interactivo profesional para visualizar los resultados del experimento de evaluación de modelos PaliGemma.

## Instalación

1. Instalar dependencias:
```bash
pip install -r dashboard/requirements.txt
```

## Uso

Ejecutar el dashboard:
```bash
streamlit run dashboard/app.py
```

El dashboard se abrirá automáticamente en tu navegador (normalmente en `http://localhost:8501`).

## Características

- **🏠 Overview**: Resumen ejecutivo del experimento
- **📊 Comparación**: Tabla interactiva con filtros y ordenamiento
- **📈 Visualizaciones**: Gráficos comparativos (barras, scatter, radar)
- **🎯 Confusion Matrices**: Visualizador de matrices de confusión
- **🔍 Modelo Individual**: Análisis detallado por modelo
- **⚡ Rendimiento**: Análisis de throughput, VRAM y tiempo
- **📋 Por Categoría**: Métricas desglosadas por categoría
- **📥 Descargas**: Exportación de datos y métricas

## Estructura de Datos

El dashboard espera encontrar los resultados en:
```
results/ufv_experiment_YYYYMMDD/
├── comparison/
│   ├── comparison_expanded/
│   └── comparison_reduced/
├── confusion_matrices/
├── metrics/
├── results/
└── environment/
```

## Notas

- El dashboard carga los datos automáticamente desde la carpeta de resultados
- Todas las visualizaciones son interactivas (zoom, pan, hover)
- Los filtros se aplican globalmente a todas las secciones
- Se pueden descargar los datos filtrados en formato CSV
