# 🗺️ Dashboard de Comprensión de Riesgo

Sistema web interactivo para análisis de peligros naturales y elementos expuestos en el Perú.

![Dashboard Preview](https://via.placeholder.com/800x400?text=Dashboard+Preview)

## 🎯 Características

- ✅ **Análisis de Peligros:** Inundación pluvial, deslizamientos, heladas
- ✅ **Elementos Expuestos:** Infraestructura, centros poblados, instituciones educativas
- ✅ **Mapas Interactivos:** Visualización geoespacial avanzada
- ✅ **Procesamiento en Background:** Generación de mapas sin bloquear la UI
- ✅ **Descarga de Resultados:** Exportar mapas generados
- ✅ **Diseño Moderno:** Interfaz dark mode responsive

## 🚀 Demo

**URL:** https://tu-dominio.com  
**Usuario:** admin  
**Contraseña:** admin

## 📋 Requisitos

### Servidor VPS
- **RAM:** Mínimo 2GB (Recomendado 4GB)
- **CPU:** 2 cores o más
- **Disco:** 20GB libres
- **SO:** Ubuntu 20.04 LTS o superior

### Software
- Python 3.8+
- Nginx
- Gunicorn
- GDAL

## 🛠️ Instalación

### Método 1: Script Automático (Recomendado)
```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/dashboard-riesgo.git
cd dashboard-riesgo

# 2. Editar dominio
nano deploy.sh
# Cambiar: DOMAIN="tu-dominio.com"

# 3. Ejecutar script
chmod +x deploy.sh
sudo ./deploy.sh
```

### Método 2: Manual

Ver [GUIA_COMPLETA_DESPLIEGUE.md](./GUIA_COMPLETA_DESPLIEGUE.md)

## 📦 Estructura del Proyecto