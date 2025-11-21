FROM continuumio/miniconda3:latest

LABEL maintainer="tu-email@example.com"
LABEL description="Dashboard de Mapas - Automatización"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Variables de compilación
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal \
    LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH

# Copiar requirements
COPY app/requirements.txt .

# Instalar Python packages
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY app/ ./

# Crear carpetas
RUN mkdir -p /workspaces/AUTOMATIZACION_DASH/PRUEBA/USUARIOS && \
    mkdir -p /workspaces/AUTOMATIZACION_DASH/PRUEBA/DATA && \
    mkdir -p /app/logs && \
    chmod -R 755 /workspaces && \
    chmod -R 755 /app/logs

# Usuario no-root
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /workspaces

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8051/ || exit 1

EXPOSE 8051

CMD ["gunicorn", \
     "--bind", "0.0.0.0:8051", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:server"]
