# Dockerfile para Fast Downward Planner
# Fast Downward se compila desde código fuente

FROM ubuntu:22.04

# Evitar prompts interactivos durante la instalación
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias necesarias para compilar Fast Downward
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    g++ \
    make \
    python3 \
    python3-pip \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /fast-downward

# Clonar Fast Downward desde el repositorio oficial
RUN git clone https://github.com/aibasel/downward.git .

# Compilar Fast Downward (esto puede tardar varios minutos)
RUN ./build.py

# Crear directorio para archivos PDDL
RUN mkdir -p /pddl

# Copiar script de entrada
COPY entrypoint.sh /fast-downward/entrypoint.sh
RUN chmod +x /fast-downward/entrypoint.sh

# Configurar PATH para acceder a los binarios
ENV PATH="/fast-downward:$PATH"

# Punto de entrada
ENTRYPOINT ["/fast-downward/entrypoint.sh"]
