# 🗺️ Dashboard de Mapas Geográficos

Sistema automatizado de generación de mapas temáticos usando Dash, Geopandas y Rasterio.

## 🚀 Quick Start

### Local (Codespace)
```bash
cd app
pip install -r requirements.txt
python app.py
```
Accede a: http://localhost:8051

### Docker
```bash
docker-compose up -d
```

## 📊 Características

- ✅ Mapa de ubicación geográfica
- ✅ Mapa de geomorfología
- ✅ Clasificación climática
- ✅ Mapa de pendientes
- ✅ Red de vías
- ✅ Centros poblados
- ✅ Geología

## 🏗️ Estructura

```
.
├── app/                    # Código Python
├── docker/                 # Dockerfile
├── config/                 # Nginx config
├── .github/workflows/      # GitHub Actions
└── docker-compose.yml      # Orquestación
```

## 📋 Requisitos

- Docker & Docker Compose
- GitHub (para CI/CD)
- VPS con Ubuntu (para producción)

## 🔧 Deploy

1. Push a main
2. GitHub Actions construye imagen
3. Sube a GHCR
4. Deploy automático a VPS

## 📧 Soporte

Por problemas, revisar logs:
```bash
docker logs dashboard
```
