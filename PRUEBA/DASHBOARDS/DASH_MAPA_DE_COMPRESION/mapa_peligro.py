# -*- coding: utf-8 -*-
"""
🎯 SCRIPT INTEGRADO: MAPA DE PELIGRO CON 5 PARÁMETROS + CENTROS POBLADOS
- Genera automáticamente el shapefile de distancia a ríos desde el DEM
- Calcula el mapa de peligro combinando: Pendiente + Geomorfología + PP Máxima + Distancia a Ríos + Geología
- Muestra centros poblados con etiquetas FUERA de la zona de estudio
- Líneas blancas gruesas y separación automática entre etiquetas
- ARCHIVOS DE RÍOS SE GUARDAN EN CARPETA DEL USUARIO
"""

import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
from matplotlib_scalebar.scalebar import ScaleBar
import os
import numpy as np
import matplotlib.patheffects as path_effects
from shapely.geometry import box, mapping
from shapely.ops import unary_union
import pyproj
import unicodedata
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Polygon, Rectangle, Patch
from matplotlib.lines import Line2D
import datetime
import pandas as pd

# Importaciones para procesamiento hidrológico
try:
    import rasterio
    from rasterio.mask import mask as rasterio_mask
    from rasterio.enums import Resampling
    from rasterio.transform import Affine
    from whitebox import WhiteboxTools
    HYDRO_AVAILABLE = True
except ImportError:
    HYDRO_AVAILABLE = False
    print("⚠️ WhiteboxTools o rasterio no disponibles. Instalando...")

# --- CONFIGURACIÓN GLOBAL ---
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"
AMARILLO_CLARO = "#FFEE58"

# MAPEO DE DEMS POR DEPARTAMENTO (cada departamento tiene su propio DEM)
DEMS_POR_DEPARTAMENTO = {
    'PIURA': f"{ruta_base}/DATA/PELIGRO/INUNDACION_PLUVIAL/PIURA_DEPARTAMENTO/DATOS_GENERALES/DISTANCIA_RIO/Piura_DEM_30m_MAX_RESOLUCION.tif",
    'CUSCO': f"{ruta_base}/DATA/PELIGRO/INUNDACION_PLUVIAL/CUSCO_DEPARTAMENTO/DATOS_GENERALES/DISTANCIA_RIO/DEM.tif",
}

# RUTAS BASE DE LAS CAPAS DE PELIGRO (por defecto CUSCO, serán sobrescritas dinámicamente)
RUTA_BASE_PENDIENTE = f"{ruta_base}/DATA/PELIGRO/PENDIENTE"
RUTA_BASE_GEOMORFOLOGIA = f"{ruta_base}/DATA/PELIGRO/INUNDACION_PLUVIAL/CUSCO_DEPARTAMENTO/ANTA_PROVINCIA/GEOMORFOLOGIA"
RUTA_BASE_PPMAX = f"{ruta_base}/DATA/PELIGRO/INUNDACION_PLUVIAL/CUSCO_DEPARTAMENTO/DATOS_GENERALES/PP_MAX"
RUTA_BASE_GEOLOGIA = f"{ruta_base}/DATA/PELIGRO/INUNDACION_PLUVIAL/CUSCO_DEPARTAMENTO/ANTA_PROVINCIA/GEOLOGIA"
RUTA_DEM = f"{ruta_base}/DATA/PELIGRO/INUNDACION_PLUVIAL/CUSCO_DEPARTAMENTO/DATOS_GENERALES/DISTANCIA_RIO/DEM.tif"
RUTA_CENTROS_POBLADOS = f"{ruta_base}/DATA/CENTROS_POBLADOS/Centros_Poblados_INEI_geogpsperu_SuyoPomalia.shp"


def get_rutas_peligro(departamento_sel, provincia_sel):
    """Construye rutas base para capas de peligro según departamento y provincia.

    Si el departamento no tiene una estructura especial, se devuelven
    las rutas por defecto ya definidas globalmente.
    """
    dpto = (departamento_sel or "").strip().upper()
    prov = (provincia_sel or "").strip().upper()

    # Obtener DEM del departamento desde el mapeo
    ruta_dem_dpto = DEMS_POR_DEPARTAMENTO.get(dpto, RUTA_DEM)

    # Ruta por defecto (las ya configuradas para CUSCO/ANTA)
    rutas = {
        'RUTA_BASE_PENDIENTE': RUTA_BASE_PENDIENTE,
        'RUTA_BASE_GEOMORFOLOGIA': RUTA_BASE_GEOMORFOLOGIA,
        'RUTA_BASE_PPMAX': RUTA_BASE_PPMAX,
        'RUTA_BASE_GEOLOGIA': RUTA_BASE_GEOLOGIA,
        'RUTA_DEM': ruta_dem_dpto  # Usar DEM específico del departamento
    }

    # Excepciones/estructura de carpetas conocida para PIURA
    if dpto == 'PIURA':
        base = os.path.join(ruta_base, 'DATA', 'PELIGRO', 'INUNDACION_PLUVIAL', 'PIURA_DEPARTAMENTO')

        # Buscar dentro del directorio del departamento (recursivo) — así encontraremos archivos
        # aunque las carpetas de provincia usen UPPER/Title case (PIURA_PROVINCIA / PIURA_Provincia)
        rutas['RUTA_BASE_GEOMORFOLOGIA'] = base
        rutas['RUTA_BASE_GEOLOGIA'] = base
        rutas['RUTA_BASE_PPMAX'] = os.path.join(base, 'DATOS_GENERALES', 'PP_MAX')
        rutas['RUTA_BASE_PENDIENTE'] = os.path.join(base, 'DATOS_GENERALES', 'PENDIENTE')
        rutas['RUTA_DEM'] = ruta_dem_dpto  # Usar DEM específico de PIURA

    return rutas


def downsample_dem(dem_in, dem_out, factor=4):
    """Crear un DEM con resolución reducida (factor entero > 1).

    Usa Resampling.average para disminuir tamaño y crear un DEM temporal que
    acelera el procesamiento hidrológico.
    """
    if not os.path.exists(dem_in):
        return None
    try:
        os.makedirs(os.path.dirname(dem_out), exist_ok=True)
        with rasterio.open(dem_in) as src:
            new_width = max(1, int(src.width / factor))
            new_height = max(1, int(src.height / factor))
            if new_width == src.width and new_height == src.height:
                # nothing to do
                return dem_in

            data = src.read(
                out_shape=(src.count, new_height, new_width),
                resampling=Resampling.average
            )

            # Adjust transform: scale by factor
            scale_x = src.width / new_width
            scale_y = src.height / new_height
            new_transform = src.transform * Affine.scale(scale_x, scale_y)

            kwargs = src.meta.copy()
            kwargs.update({
                'height': new_height,
                'width': new_width,
                'transform': new_transform
            })

            with rasterio.open(dem_out, 'w', **kwargs) as dst:
                dst.write(data)

            return dem_out
    except Exception as e:
        print(f"      ⚠️ Error al crear DEM reducido: {e}")
        return None

# CONFIGURACIÓN DE GENERACIÓN DE RÍOS
INTENSIDAD_RIOS = "muy_baja"  # Opciones: "muy_alta", "alta", "media", "baja", "muy_baja"
UMBRALES_RIOS = {"muy_alta": 50, "alta": 200, "media": 500, "baja": 1000, "muy_baja": 1500}

# CONFIGURACIÓN DE BUFFERS CON PESOS
BUFFERS_CONFIG = [
    {"name": "0-50m", "inner": 0, "outer": 50, "peso": 5},
    {"name": "50-100m", "inner": 50, "outer": 100, "peso": 4},
    {"name": "100-150m", "inner": 100, "outer": 150, "peso": 3},
    {"name": "150-200m", "inner": 150, "outer": 200, "peso": 2},
    {"name": ">200m", "inner": 200, "outer": None, "peso": 1}
]

# PALETA DE COLORES PARA NIVELES DE PELIGRO
COLORES_PELIGRO = ['#00FF00', '#FFFF00', '#FFA500', '#FF0000']
ETIQUETAS_PELIGRO = ['Baja', 'Media', 'Alta', 'Muy Alta']
RANGOS_PELIGRO = [1.00, 2.00, 3.00, 4.00, 5.00]

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIONES DE ETIQUETADO DE CENTROS POBLADOS (MEJORADAS)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def agregar_etiquetas_ordenadas_circularmente(gdf_distritos, gdf_centros_poblados, ax, radio_offset=0.12):
    """
    Agrega etiquetas de centros poblados FUERA del límite distrital de manera ordenada.
    Las etiquetas salen bien lejos del límite y se distribuyen evitando solapamiento.
    
    Parámetros:
    -----------
    gdf_distritos : GeoDataFrame
        GeoDataFrame con los polígonos de distritos
    gdf_centros_poblados : GeoDataFrame
        GeoDataFrame con los puntos de centros poblados
    ax : matplotlib.axes.Axes
        Eje de matplotlib donde dibujar
    radio_offset : float
        Distancia de separación de la etiqueta del límite (aumentado a 0.12)
    """
    
    if gdf_centros_poblados is None or len(gdf_centros_poblados) == 0:
        return
    
    # Obtener el límite del distrito como línea
    distrito_boundary = gdf_distritos.boundary.unary_union
    
    # Calcular centroide del distrito
    try:
        distrito_merged = gdf_distritos.unary_union
        centroide = distrito_merged.centroid
    except:
        centroide = gdf_distritos.geometry.centroid.iloc[0]
    
    # Obtener límites del distrito para calcular escala
    minx, miny, maxx, maxy = gdf_distritos.total_bounds
    ancho_distrito = maxx - minx
    alto_distrito = maxy - miny
    escala = max(ancho_distrito, alto_distrito)
    
    # Distancia perpendicular del límite (MÁS LEJOS)
    offset_perpendicular = escala * radio_offset
    
    # Lista para almacenar posiciones de etiquetas y evitar solapamiento
    posiciones_etiquetas = []
    distancia_minima_entre_etiquetas = escala * 0.04  # Separación mínima entre etiquetas
    
    for idx, (i, row) in enumerate(gdf_centros_poblados.iterrows()):
        try:
            punto = row.geometry
            
            # Buscar nombre en diferentes columnas posibles
            nombre = None
            for col in ['NOMB_CCPP', 'NOMBRE', 'NOMBCCPP', 'CCPP', 'NAME', 'nombre']:
                if col in row.index and pd.notna(row[col]):
                    nombre = str(row[col]).strip()
                    if nombre:
                        break
            
            if not nombre:
                nombre = f'Centro {idx}'
            
            # Coordenadas del punto original
            x_orig, y_orig = punto.x, punto.y
            
            # Encontrar el punto más cercano en el límite del distrito
            punto_limite = distrito_boundary.interpolate(
                distrito_boundary.project(punto)
            )
            
            # Calcular vector desde el centroide al punto
            dx = x_orig - centroide.x
            dy = y_orig - centroide.y
            dist_vec = np.sqrt(dx**2 + dy**2)
            
            if dist_vec > 0:
                # Normalizar vector
                dx_norm = dx / dist_vec
                dy_norm = dy / dist_vec
            else:
                dx_norm, dy_norm = 1, 0
            
            # Calcular posición INICIAL de la etiqueta FUERA del límite
            x_label = punto_limite.x + dx_norm * offset_perpendicular
            y_label = punto_limite.y + dy_norm * offset_perpendicular
            
            # 🆕 VERIFICAR SI HAY SOLAPAMIENTO CON ETIQUETAS ANTERIORES
            intentos_reubicacion = 0
            max_intentos = 12
            offset_adicional = 0
            
            while intentos_reubicacion < max_intentos:
                # Verificar distancia con todas las etiquetas ya colocadas
                muy_cerca = False
                for pos_anterior in posiciones_etiquetas:
                    dist = np.sqrt((x_label - pos_anterior[0])**2 + (y_label - pos_anterior[1])**2)
                    if dist < distancia_minima_entre_etiquetas:
                        muy_cerca = True
                        break
                
                if not muy_cerca:
                    # Posición válida encontrada
                    break
                else:
                    # Reubicar: alejar más la etiqueta progresivamente
                    intentos_reubicacion += 1
                    offset_adicional = escala * 0.02 * intentos_reubicacion
                    x_label = punto_limite.x + dx_norm * (offset_perpendicular + offset_adicional)
                    y_label = punto_limite.y + dy_norm * (offset_perpendicular + offset_adicional)
            
            # Guardar la posición final de esta etiqueta
            posiciones_etiquetas.append((x_label, y_label))
            
            # Intentar ubicar la etiqueta DENTRO del polígono si el punto está bien ubicado
            etiqueta_colocada_dentro = False
            try:
                if distrito_merged.contains(punto):
                    # Colocar etiqueta ligeramente desplazada respecto al punto (dentro)
                    shift = escala * 0.01
                    x_label_in = x_orig + dx_norm * shift
                    y_label_in = y_orig + dy_norm * shift
                    # Verificar solapamiento con etiquetas previas
                    collision = any(np.sqrt((x_label_in - px)**2 + (y_label_in - py)**2) < distancia_minima_entre_etiquetas for px, py in posiciones_etiquetas)
                    if not collision:
                        posiciones_etiquetas.append((x_label_in, y_label_in))
                        ax.plot(x_orig, y_orig, 'o', color='#006400', markersize=3.5, zorder=6)
                        ax.text(
                            x_label_in, y_label_in, nombre,
                            fontsize=6.0, fontweight='bold', ha='left', va='center',
                            bbox=dict(boxstyle='round,pad=0.25', facecolor='white', edgecolor='black', alpha=0.85, linewidth=0.5),
                            zorder=8
                        )
                        etiqueta_colocada_dentro = True
            except Exception:
                etiqueta_colocada_dentro = False

            if not etiqueta_colocada_dentro:
                # Dibujar línea fina y más corta desde el punto hasta la etiqueta externa
                # Reducir grosor y longitud para evitar exceso de cruces
                short_factor = 0.7
                x_label_short = punto_limite.x + dx_norm * (offset_perpendicular * short_factor)
                y_label_short = punto_limite.y + dy_norm * (offset_perpendicular * short_factor)

                ax.plot([x_orig, x_label_short], [y_orig, y_label_short], color='white', linewidth=0.5, alpha=0.9, zorder=5)
                ax.plot(x_orig, y_orig, 'o', color='#006400', markersize=3.5, zorder=6)
                posiciones_etiquetas.append((x_label_short, y_label_short))
                ax.text(
                    x_label_short, y_label_short, nombre,
                    fontsize=6.0, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.25', facecolor='white', edgecolor='black', alpha=0.85, linewidth=0.5),
                    zorder=8
                )
        except Exception as e:
            continue

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# FUNCIONES PARA GENERAR RED DE RÍOS Y BUFFERS
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def generar_shapefile_rios_con_pesos(distrito_shapefile, output_folder, temp_folder="/tmp/hydro_temp", nombre_distrito="distrito"):
    """
    Genera el shapefile de buffers de distancia a ríos con pesos a partir del DEM.
    
    Parámetros:
    - distrito_shapefile: GeoDataFrame del distrito para recortar
    - output_folder: Carpeta donde se guardará el shapefile final
    - temp_folder: Carpeta temporal para archivos intermedios
    - nombre_distrito: Nombre del distrito para el archivo shapefile
    
    Retorna:
    - ruta del shapefile generado o None si falla
    """
    
    if not HYDRO_AVAILABLE:
        print("❌ WhiteboxTools no está disponible. No se puede generar el shapefile de ríos.")
        return None
    
    print("\n" + "="*80)
    print("🌊 GENERANDO SHAPEFILE DE DISTANCIA A RÍOS CON PESOS")
    print("="*80)
    
    # Crear carpetas
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(temp_folder, exist_ok=True)
    
    # Inicializar WhiteboxTools
    wbt = WhiteboxTools()
    wbt.set_working_dir(temp_folder)
    wbt.set_verbose_mode(True)
    wbt.set_max_procs(4)
    
    # Verificar que existe el DEM (acepta ruta personalizada mediante variable global opcional RUTA_DEM_USUARIO)
    dem_uso = globals().get('RUTA_DEM_USUARIO', None) or RUTA_DEM
    if not os.path.exists(dem_uso):
        print(f"❌ No se encontró el DEM en: {dem_uso}")
        return None
    
    print(f"[1/6] ✂️ Recortando DEM al distrito...")
    
    try:
        # Cargar límite del distrito
        limit = distrito_shapefile.copy()
        
        with rasterio.open(dem_uso) as dem:
            if limit.crs != dem.crs:
                limit_proj = limit.to_crs(dem.crs)
            else:
                limit_proj = limit.copy()
            
            # Mostrar información del DEM original
            print(f"      📊 Info DEM original:")
            print(f"         - Dimensiones: {dem.width} x {dem.height} píxeles")
            print(f"         - Resolución: {dem.res[0]:.2f} x {dem.res[1]:.2f} metros")
            total_pixels = dem.width * dem.height
            print(f"         - Total píxeles: {total_pixels:,}")
        
        # Recortar DEM
        with rasterio.open(dem_uso) as src:
            geom = [mapping(limit_proj.geometry.unary_union)]
            out_image, out_transform = rasterio_mask(src, geom, crop=True)
            out_meta = src.meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
            
            # Mostrar información del DEM recortado
            recorte_pixels = out_image.shape[1] * out_image.shape[2]
            print(f"      📊 Info DEM recortado:")
            print(f"         - Dimensiones: {out_image.shape[2]} x {out_image.shape[1]} píxeles")
            print(f"         - Total píxeles: {recorte_pixels:,}")
            
            # Advertencia si el DEM es muy grande
            if recorte_pixels > 10_000_000:
                print(f"      ⚠️ ADVERTENCIA: DEM muy grande ({recorte_pixels:,} píxeles)")
                print(f"         El procesamiento puede tardar más de 10 minutos")
                print(f"         💡 Sugerencia: Considera usar un umbral más alto en INTENSIDAD_RIOS")
            elif recorte_pixels > 5_000_000:
                print(f"      ⏳ DEM mediano ({recorte_pixels:,} píxeles)")
                print(f"         Tiempo estimado: 5-10 minutos")
            else:
                print(f"      ✅ DEM pequeño ({recorte_pixels:,} píxeles)")
                print(f"         Tiempo estimado: 1-5 minutos")
            
            dem_clipped = os.path.join(temp_folder, "dem_distrito.tif")
            with rasterio.open(dem_clipped, "w", **out_meta) as dest:
                dest.write(out_image)
        
        print("      ✅ DEM recortado exitosamente")
        
    except Exception as e:
        print(f"❌ Error recortando DEM: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # [2/6] Procesar hidrología
    print(f"[2/6] 🌊 Procesando hidrología (intensidad: {INTENSIDAD_RIOS})...")
    print(f"      ⏳ Este proceso puede tardar varios minutos dependiendo del tamaño del DEM...")
    
    try:
        filled_dem = os.path.join(temp_folder, "filled.tif")
        flow_dir = os.path.join(temp_folder, "flow_dir.tif")
        flow_acc = os.path.join(temp_folder, "flow_acc.tif")
        streams_raster = os.path.join(temp_folder, "streams.tif")
        streams_vector = os.path.join(temp_folder, "streams.shp")
        
        # Verificar si ya existen archivos intermedios
        if os.path.exists(streams_vector):
            print(f"      ⚡ Archivos intermedios encontrados, saltando procesamiento hidrológico")
        else:
            print(f"      [2.1/4] Rellenando depresiones del DEM...")
            if not os.path.exists(filled_dem):
                wbt.fill_depressions(dem_clipped, filled_dem)
                print(f"      ✅ Depresiones rellenadas")
            else:
                print(f"      ⚡ Usando filled_dem existente")
            
            print(f"      [2.2/4] Calculando dirección de flujo (D8)...")
            if not os.path.exists(flow_dir):
                wbt.d8_pointer(filled_dem, flow_dir)
                print(f"      ✅ Dirección de flujo calculada")
            else:
                print(f"      ⚡ Usando flow_dir existente")
            
            print(f"      [2.3/4] Calculando acumulación de flujo (PUEDE TARDAR)...")
            if not os.path.exists(flow_acc):
                import time
                start_time = time.time()
                wbt.d8_flow_accumulation(filled_dem, flow_acc, out_type="cells")
                elapsed = time.time() - start_time
                print(f"      ✅ Acumulación de flujo calculada ({elapsed:.1f}s)")
            else:
                print(f"      ⚡ Usando flow_acc existente")
            
            threshold_default = int(UMBRALES_RIOS.get(INTENSIDAD_RIOS, 1500))
            print(f"      [2.4/4] Extrayendo red de ríos (umbral inicial: {threshold_default} celdas)...")

            # Intentar varios umbrales si la vectorización resulta vacía
            tried_thresholds = []
            success_vectorized = False
            candidate_thresholds = [threshold_default, max(int(threshold_default/2), 1), max(int(threshold_default/5), 1), 50, 10]

            for th in candidate_thresholds:
                if th in tried_thresholds:
                    continue
                tried_thresholds.append(th)
                try:
                    print(f"         → Probando umbral = {th} ...")
                    # extraer streams raster
                    if not os.path.exists(streams_raster):
                        wbt.extract_streams(flow_acc, streams_raster, th)
                    else:
                        # si ya existe, regenerarlo para este intento
                        try:
                            os.remove(streams_raster)
                        except Exception:
                            pass
                        wbt.extract_streams(flow_acc, streams_raster, th)

                    # vectorizar
                    if os.path.exists(streams_vector):
                        try:
                            os.remove(streams_vector)
                        except Exception:
                            pass

                    wbt.raster_streams_to_vector(streams_raster, flow_dir, streams_vector)

                    # verificar que el shapefile resultante exista y contenga registros
                    try:
                        import geopandas as _gpd
                        if os.path.exists(streams_vector):
                            rivers_try = _gpd.read_file(streams_vector)
                            if len(rivers_try) > 0:
                                print(f"      ✅ Red de ríos vectorizada (umbral {th}) — {len(rivers_try)} segmentos")
                                success_vectorized = True
                                break
                            else:
                                print(f"      ⚠️ Vector resultante vacío para umbral {th}")
                        else:
                            print(f"      ⚠️ No se creó el archivo vector para umbral {th}")
                    except Exception as e:
                        print(f"      ⚠️ Error leyendo vector generado: {e}")
                except Exception as e:
                    print(f"      ⚠️ Falló extracción/vectorización con umbral {th}: {e}")

            if not success_vectorized:
                print(f"      ❌ No se pudo obtener una red de ríos válida con los umbrales probados: {tried_thresholds}")
                # limpiar archivos intermedios si quedaron
                try:
                    if os.path.exists(streams_raster):
                        os.remove(streams_raster)
                except Exception:
                    pass

                # El fallback se maneja en [3/6], no aquí. Simplemente retornamos para que
                # el código continúe en la sección de carga de ríos donde existe limit_final
                print(f"      ℹ️ Se usará fallback en la siguiente etapa de carga de ríos")
                # Crear un archivo dummy para que el flujo continúe
                dummy_shp = os.path.join(temp_folder, "streams_dummy.shp")
                return None  # Retornar None para indicar que no hay streams reales
        
        print(f"      ✅ Procesamiento hidrológico completado")
        
    except Exception as e:
        print(f"❌ Error en procesamiento hidrológico: {e}")
        print(f"   💡 Sugerencias:")
        print(f"      - Verifica que el DEM sea válido")
        print(f"      - Prueba con INTENSIDAD_RIOS = 'baja' o 'muy_baja' (más rápido)")
        print(f"      - Los archivos temporales se guardan en: {temp_folder}")
        print(f"      - Puedes volver a ejecutar y continuará desde el último paso")
        import traceback
        traceback.print_exc()
        return None
    
    # [3/6] Cargar y recortar ríos
    print(f"[3/6] 🌀 Cargando red de ríos...")
    
    try:
        # Preparar limit_final (reproyectar a CRS del DEM si es necesario)
        if limit.crs != limit.crs:  # Si tienen CRS diferentes
            limit_final = limit.to_crs(limit.crs)
        else:
            limit_final = limit.copy()
        
        rivers = gpd.read_file(streams_vector)
        
        if rivers.crs is None:
            with rasterio.open(dem_clipped) as dem_src:
                rivers = rivers.set_crs(dem_src.crs)
        
        if rivers.crs != limit_final.crs:
            limit_final = limit_final.to_crs(rivers.crs)
        
        rivers_clip = gpd.clip(rivers, limit_final)
        print(f"      ✅ {len(rivers_clip)} segmentos de ríos")
        
    except Exception as e:
        print(f"❌ Error cargando ríos: {e}")
        print(f"   Activando fallback de ríos...")
        
        # Fallback: usar geometría del distrito directamente
        try:
            limit_final = limit.copy()
            geom_union = limit_final.geometry.unary_union
            area_km2 = geom_union.area / 1_000_000 if hasattr(geom_union, 'area') else 0
            
            rivers_clip = gpd.GeoDataFrame(
                {
                    'clase': ['no_rio_fallback'],
                    'dist_min_m': [999999],
                    'dist_max_m': [999999],
                    'area_km2': [round(area_km2, 4)],
                    'PESO_RIO': [1]
                },
                geometry=[geom_union],
                crs=limit_final.crs
            )
            print(f"      ✅ Fallback de ríos creado: {len(rivers_clip)} geometría(s) con PESO_RIO=1")
        except Exception as fb_e:
            print(f"      ⚠️ Falló la creación del fallback de ríos: {fb_e}")
            return None
    
    # [4/6] Generar buffers con pesos
    print(f"[4/6] 🎯 Generando buffers con pesos...")
    
    try:
        rivers_union = unary_union(rivers_clip.geometry)
        buffer_list = []
        
        for config in BUFFERS_CONFIG:
            name = config["name"]
            inner = config["inner"]
            outer = config["outer"]
            peso = config["peso"]
            
            if outer is None:
                outer_buffer = limit_final.geometry.union_all()
                inner_buffer = rivers_union.buffer(inner)
                buffer_ring = outer_buffer.difference(inner_buffer)
            else:
                outer_buffer = rivers_union.buffer(outer)
                inner_buffer = rivers_union.buffer(inner)
                buffer_ring = outer_buffer.difference(inner_buffer)
                buffer_ring = buffer_ring.intersection(limit_final.geometry.union_all())
            
            area_km2 = buffer_ring.area / 1_000_000
            
            gdf = gpd.GeoDataFrame(
                {
                    'clase': [name],
                    'dist_min_m': [inner],
                    'dist_max_m': [outer if outer else 999999],
                    'area_km2': [round(area_km2, 4)],
                    'PESO_RIO': [peso]
                },
                geometry=[buffer_ring],
                crs=rivers_clip.crs
            )
            
            buffer_list.append(gdf)
        
        buffers_gdf = gpd.GeoDataFrame(pd.concat(buffer_list, ignore_index=True))
        print(f"      ✅ {len(buffers_gdf)} clases de buffers generadas")
        
    except Exception as e:
        print(f"❌ Error generando buffers: {e}")
        return None
    
    # [5/6] Convertir a CRS 3857
    print(f"[5/6] 🔡 Convirtiendo a CRS 3857...")
    
    try:
        buffers_gdf = buffers_gdf.to_crs(epsg=3857)
        print(f"      ✅ CRS convertido")
    except Exception as e:
        print(f"❌ Error convirtiendo CRS: {e}")
        return None
    
    # [6/6] Guardar shapefile con nombre personalizado del distrito
    print(f"[6/6] 💾 Guardando shapefile...")
    
    try:
        # Limpiar nombre del distrito (quitar espacios y caracteres especiales)
        nombre_limpio = nombre_distrito.replace(' ', '_').replace('/', '_').replace('\\', '_')
        nombre_archivo = f"distancia_rio_{nombre_limpio}.shp"
        output_shp = os.path.join(output_folder, nombre_archivo)
        buffers_gdf.to_file(output_shp)
        
        print(f"      ✅ Shapefile guardado: {output_shp}")
        print(f"\n📊 Resumen:")
        print(f"   - Distrito: {nombre_distrito}")
        print(f"   - Segmentos de ríos: {len(rivers_clip)}")
        print(f"   - Clases de buffers: {len(buffers_gdf)}")
        print(f"   - Área total: {buffers_gdf['area_km2'].sum():.4f} km²")
        
        # Mostrar tabla de datos
        print(f"\n📋 DATOS DEL SHAPEFILE:")
        print("-" * 70)
        print(f"{'Clase':12} | {'Peso':5} | {'Dist Min':>9} | {'Dist Max':>9} | {'Área (km²)':>10}")
        print("-" * 70)
        for _, row in buffers_gdf.iterrows():
            print(f"{row['clase']:12} | {row['PESO_RIO']:5} | {row['dist_min_m']:9.0f} | {row['dist_max_m']:9.0f} | {row['area_km2']:10.4f}")
        print("-" * 70)
        
        print("\n" + "="*80)
        print("✅ SHAPEFILE DE RÍOS GENERADO EXITOSAMENTE")
        print("="*80 + "\n")
        
        return output_shp
        
    except Exception as e:
        print(f"❌ Error guardando shapefile: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES PARA MAPAS
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def add_north_arrow_blanco_completo(ax, xy_pos=(0.93, 0.08), size=0.06):
    x_pos, y_pos = xy_pos
    s = size / 2
    trans = ax.transAxes
    inv_trans = ax.transData.inverted()
    body_width = s * 0.15
    
    points_body = np.array([
        (x_pos - body_width / 2, y_pos + s * 0.5),
        (x_pos + body_width / 2, y_pos + s * 0.5),
        (x_pos + body_width / 2, y_pos - s * 0.5),
        (x_pos - body_width / 2, y_pos - s * 0.5)
    ])
    points_body_data = inv_trans.transform(trans.transform(points_body))
    
    points_head = np.array([
        (x_pos, y_pos + s * 1.5),
        (x_pos - s * 0.5, y_pos + s * 0.5),
        (x_pos + s * 0.5, y_pos + s * 0.5)
    ])
    points_head_data = inv_trans.transform(trans.transform(points_head))
    
    ax.add_patch(Polygon(points_body_data, facecolor='white', edgecolor='black', linewidth=1.5, zorder=11, transform=ax.transData))
    ax.add_patch(Polygon(points_head_data, facecolor='white', edgecolor='black', linewidth=1.5, zorder=11, transform=ax.transData))
    ax.text(x_pos, y_pos + s * 1.5 + 0.015, "N", transform=ax.transAxes, fontsize=16, fontweight='bold', 
            ha='center', va='center', color='white', 
            path_effects=[path_effects.withStroke(linewidth=3, foreground='black')])

def calculate_numeric_scale(ax, fig):
    xlim = ax.get_xlim()
    ground_width_m = xlim[1] - xlim[0]
    fig_width_in = fig.get_size_inches()[0]
    ax_pos = ax.get_position()
    ax_width_in = fig_width_in * ax_pos.width
    scale_denominator = ground_width_m / (ax_width_in * 0.0254)
    rounding = 5000 if scale_denominator > 100000 else 1000 if scale_denominator > 10000 else 500
    scale_rounded = int(round(scale_denominator / rounding) * rounding)
    return f"1:{scale_rounded:,}"

def add_membrete(ax, dpto, prov, dist, main_map_ax, fig_obj):
    escala_numerica = calculate_numeric_scale(main_map_ax, fig_obj)
    info = {
        "MAPA": f"MAPA DE SUSCEPTIBILIDAD: DISTRITO DE {dist.upper()}",
        "DPTO": dpto.upper(),
        "PROVINCIA": prov.upper(),
        "DISTRITO": dist.upper(),
        "MAPA_N": "003-2025",
        "ESCALA": escala_numerica,
        "FECHA": datetime.date.today().strftime("%d / %m / %Y")
    }
    
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis('off')
    
    ax.add_patch(Rectangle((0, 0), 10, 4, fill=False, edgecolor='black', lw=1.2))
    ax.plot([0, 10], [3, 3], color='black', lw=1.2)
    ax.plot([0, 7.5], [1.5, 1.5], color='black', lw=1.2)
    ax.plot([2.5, 2.5], [1.5, 3], color='black', lw=1.2)
    ax.plot([5, 5], [0, 3], color='black', lw=1.2)
    ax.plot([7.5, 7.5], [0, 3], color='black', lw=1.2)
    
    padding = 0.15
    ax.text(0 + padding, 3.5, "MAPA:", fontweight='bold', va='center', fontsize=8)
    ax.text(1.8 + padding, 3.5, info["MAPA"], va='center', fontsize=8)
    ax.text(0 + padding, 2.6, "DPTO:", fontweight='bold', va='center', fontsize=8)
    ax.text(0 + padding, 2.0, info["DPTO"], va='center', fontsize=8)
    ax.text(2.5 + padding, 2.6, "PROVINCIA:", fontweight='bold', va='center', fontsize=8)
    ax.text(2.5 + padding, 2.0, info["PROVINCIA"], va='center', fontsize=8)
    ax.text(5 + padding, 2.6, "DISTRITO:", fontweight='bold', va='center', fontsize=8)
    ax.text(5 + padding, 2.0, info["DISTRITO"], va='center', fontsize=8)
    ax.text(7.5 + padding, 2.5, "MAPA Nº", fontweight='bold', ha='left', va='center', fontsize=8)
    ax.text(7.5 + padding, 0.8, info["MAPA_N"], ha='left', va='center', fontsize=10)
    ax.text(0 + padding, 1.0, "ESCALA:", fontweight='bold', va='center', fontsize=8)
    ax.text(0 + padding, 0.5, info["ESCALA"], va='center', fontsize=8)
    ax.text(5 + padding, 1.0, "FECHA:", fontweight='bold', va='center', fontsize=8)
    ax.text(5 + padding, 0.5, info["FECHA"], va='center', fontsize=8)

def buscar_shapefile(nombre_busqueda):
    for root, _, files in os.walk(ruta_base):
        for file in files:
            if file.lower().endswith(".shp") and nombre_busqueda.lower() in file.lower():
                return os.path.join(root, file)
    return None

def cargar_shapefile(nombre, alias):
    path = buscar_shapefile(nombre)
    if not path:
        print(f"   No se encontró shapefile: {alias}")
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf.set_crs(epsg=4326, inplace=True)
        return gdf.to_crs(epsg=3857)
    except Exception as e:
        print(f"   Error cargando {alias}: {e}")
        return None

def grillado_utm_proyectado(ax, bbox, ndiv=8):
    x0, y0, x1, y1 = bbox
    
    for x in np.linspace(x0, x1, ndiv):
        ax.plot([x, x], [y0, y1], color="black", linestyle="-", linewidth=0.4, alpha=0.6, zorder=0)
    
    for y in np.linspace(y0, y1, ndiv):
        ax.plot([x0, x1], [y, y], color="black", linestyle="-", linewidth=0.4, alpha=0.6, zorder=0)
    
    def fmt_este(x, pos):
        return f"{int(x):06d}"[:3] + " " + f"{int(x):06d}"[3:] + " E"
    
    def fmt_norte(y, pos):
        return f"{int(y):07d}"[0] + " " + f"{int(y):07d}"[1:4] + " " + f"{int(y):07d}"[4:] + " N"
    
    ax.xaxis.set_major_formatter(FuncFormatter(fmt_este))
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_norte))
    ax.tick_params(axis='x', labelsize=7, width=0.5, length=3, direction="out", pad=2, 
                   top=False, bottom=True, labeltop=False, labelbottom=True)
    ax.tick_params(axis='y', labelsize=7, width=0.5, length=3, direction="out", pad=2, 
                   left=True, right=False, labelleft=True, labelright=False)
    
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontsize(7)
    
    for label in ax.get_yticklabels():
        label.set_rotation(90)
        label.set_verticalalignment('center')
        label.set_horizontalalignment('right')

def grillado_grados_mejorado(ax, bbox, ndiv=5, decimales=2):
    transformer = pyproj.Transformer.from_crs(3857, 4326, always_xy=True)
    x0, y0, x1, y1 = bbox
    lon_start, lat_start = transformer.transform(x0, y0)
    lon_end, lat_end = transformer.transform(x1, y1)
    
    for lon in np.linspace(lon_start, lon_end, ndiv):
        xs, ys = transformer.transform(np.full(2, lon), [lat_start, lat_end])
        ax.plot(xs, ys, color="gray", linestyle="--", linewidth=0.3, alpha=0.5, zorder=0)
    
    for lat in np.linspace(lat_start, lat_end, ndiv):
        xs, ys = transformer.transform([lon_start, lon_end], np.full(2, lat))
        ax.plot(xs, ys, color="gray", linestyle="--", linewidth=0.3, alpha=0.5, zorder=0)
    
    def fmt_lon(x, pos):
        lon, _ = transformer.transform(x, y0)
        return f"{abs(lon):.{decimales}f}°{'W' if lon < 0 else 'E'}"
    
    def fmt_lat(y, pos):
        _, lat = transformer.transform(x0, y)
        return f"{abs(lat):.{decimales}f}°{'S' if lat < 0 else 'N'}"
    
    ax.xaxis.set_major_formatter(FuncFormatter(fmt_lon))
    ax.yaxis.set_major_formatter(FuncFormatter(fmt_lat))
    ax.tick_params(labelsize=6, width=0.4, length=2, direction="out", pad=2, 
                   top=True, bottom=True, left=True, right=True, labeltop=True, labelright=False)
    
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontsize(6)
    
    for label in ax.get_yticklabels():
        label.set_rotation(90)
        label.set_verticalalignment('center')
        label.set_horizontalalignment('right')

def mapa_ubicacion(ax, gdf_base_map, gdf_context, gdf_focus, titulo, etiqueta, tipo_mapa, 
                   gdf_dpto_sel=None, gdf_prov_sel=None, col_prov=None, col_dpto=None, 
                   departamento_sel=None, provincia_sel=None, gdf_departamentos=None, 
                   gdf_provincias=None, gdf_oceano=None):
    
    is_focus_valid = not gdf_focus.empty and all(np.isfinite(gdf_focus.total_bounds))
    
    if tipo_mapa == "pais":
        bbox_geom = gdf_departamentos.total_bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.25, (bbox_geom[3] - bbox_geom[1]) * 0.25
    elif tipo_mapa == "provincia":
        bbox_geom = gdf_dpto_sel.total_bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.12, (bbox_geom[3] - bbox_geom[1]) * 0.12
    elif tipo_mapa == "distrito":
        provincia_seleccionada_geom = gdf_prov_sel.geometry.unary_union
        geoms_vecinas = [prov.geometry for _, prov in gdf_provincias.iterrows() 
                        if prov[col_prov] != provincia_sel and prov.geometry.touches(provincia_seleccionada_geom)]
        area_de_interes = gpd.GeoSeries([provincia_seleccionada_geom] + geoms_vecinas).unary_union
        bbox_geom = area_de_interes.bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.15, (bbox_geom[3] - bbox_geom[1]) * 0.15
    else:
        bbox_geom = gdf_departamentos.total_bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.25, (bbox_geom[3] - bbox_geom[1]) * 0.25
    
    x0, y0, x1, y1 = bbox_geom[0] - dx, bbox_geom[1] - dy, bbox_geom[2] + dx, bbox_geom[3] + dy
    S = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bbox = (cx - S / 2, cy - S / 2, cx + S / 2, cy + S / 2)
    
    # Proteger la creación del bbox y la operación de clip para evitar errores de LinearRing
    if gdf_oceano is not None:
        if all(np.isfinite(bbox)) and bbox[0] < bbox[2] and bbox[1] < bbox[3]:
            try:
                gdf_oceano.clip(box(*bbox)).plot(ax=ax, color="#A4D4FF", edgecolor="none", zorder=2)
            except Exception as e:
                print(f"      ⚠️ Error al graficar/oceano.clip(box): {e}")
        else:
            print("      ⚠️ BBox inválida para mapa de ubicación; se omitirá la capa de océano")
    
    if tipo_mapa == "pais":
        if gdf_base_map is not None:
            gdf_base_map.plot(ax=ax, color="#f0eee8", edgecolor="black", linewidth=0.4, zorder=1)
        if gdf_context is not None:
            gdf_context.plot(ax=ax, color=AMARILLO_CLARO, edgecolor="black", linewidth=0.7, zorder=3)
    elif tipo_mapa == "provincia":
        if gdf_base_map is not None:
            gdf_base_map.plot(ax=ax, color="#f0eee8", edgecolor="black", linewidth=0.4, zorder=1)
        if gdf_context is not None:
            gdf_context.plot(ax=ax, color=AMARILLO_CLARO, edgecolor="black", linewidth=0.7, zorder=3)
    elif tipo_mapa == "distrito":
        if gdf_provincias is not None:
            gdf_provincias[gdf_provincias[col_prov] != provincia_sel].plot(
                ax=ax, color='lightgray', edgecolor='darkgray', linewidth=0.4, zorder=2)
            gdf_prov_sel.plot(ax=ax, color=AMARILLO_CLARO, edgecolor='black', linewidth=0.7, zorder=3)
        if gdf_context is not None:
            gdf_context.plot(ax=ax, facecolor='none', edgecolor="gray", linewidth=0.4, zorder=4)
    
    if is_focus_valid:
        gdf_focus.plot(ax=ax, facecolor="red", edgecolor="red", linewidth=0.2, hatch='o', zorder=5)
    
    if all(np.isfinite(bbox)):
        grillado_grados_mejorado(ax, bbox, ndiv=5, decimales=1)
    
    ax.text(0.03, 0.05, titulo, transform=ax.transAxes, color="white", fontsize=8, 
            ha="left", va="bottom", zorder=8, 
            bbox=dict(facecolor="#4A90E2", edgecolor="black", boxstyle="round,pad=0.3", alpha=0.9))
    
    if is_focus_valid:
        ax.text(gdf_focus.geometry.centroid.iloc[0].x, gdf_focus.geometry.centroid.iloc[0].y, 
                etiqueta.upper(), color="white", fontsize=8, ha="center", va="center", zorder=9, 
                path_effects=[path_effects.withStroke(linewidth=3, foreground="black")])
    
    # Sólo ajustar límites si bbox es válido
    valid_bbox = all(np.isfinite(bbox)) and bbox[0] < bbox[2] and bbox[1] < bbox[3]
    if valid_bbox:
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])
    else:
        print("      ⚠️ BBox inválida: uso de autoscale para el subplot de ubicación")
        try:
            ax.autoscale()
        except Exception:
            pass

    ax.set_facecolor("#f0f8ff")
    ax.set_aspect('equal', adjustable='box')
    ax.axis('on')

def buscar_archivo_peligro(ruta_base, patron_busqueda, tipo_capa, provincia_sel=None):
    """Busca archivos de peligro de forma inteligente, priorizando por provincia si se especifica"""
    print(f"   🔍 Buscando {tipo_capa} en: {ruta_base}")
    
    archivos_encontrados = []
    archivos_provincia = []
    
    for root, dirs, files in os.walk(ruta_base):
        for file in files:
            if file.lower().endswith('.shp') and patron_busqueda.lower() in file.lower():
                ruta_completa = os.path.join(root, file)
                archivos_encontrados.append(ruta_completa)
                
                # Si se especifica provincia, priorizar archivos que la contengan en el nombre o ruta
                if provincia_sel:
                    provincia_norm = provincia_sel.lower().replace(' ', '_')
                    if provincia_norm in ruta_completa.lower() or provincia_norm in file.lower():
                        archivos_provincia.append(ruta_completa)
                        print(f"      ✅ Encontrado (provincia): {ruta_completa}")
                    else:
                        print(f"      ℹ️ Encontrado (otros): {ruta_completa}")
                else:
                    print(f"      ✅ Encontrado: {ruta_completa}")
    
    # Priorizar archivos de la provincia si existen
    if archivos_provincia:
        return archivos_provincia[0]
    
    if not archivos_encontrados:
        print(f"      ❌ No se encontraron archivos para {tipo_capa}")
        return None
    
    if len(archivos_encontrados) > 1:
        print(f"      ⚠️ Se encontraron {len(archivos_encontrados)} archivos, usando el primero")
    
    return archivos_encontrados[0]

def asignar_color_peligro(valor):
    """Asigna color según el nivel de peligro"""
    if 1.00 <= valor < 2.00:
        return COLORES_PELIGRO[0]  # Verde - BAJA
    elif 2.00 <= valor < 3.00:
        return COLORES_PELIGRO[1]  # Amarillo - MEDIA
    elif 3.00 <= valor < 4.00:
        return COLORES_PELIGRO[2]  # Naranja - ALTA
    elif 4.00 <= valor <= 5.00:
        return COLORES_PELIGRO[3]  # Rojo - MUY ALTA
    else:
        return COLORES_PELIGRO[0]

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIÓN PRINCIPAL CON 5 PARÁMETROS + CENTROS POBLADOS
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def generar_mapa_peligro(nombre_usuario, departamento_sel, provincia_sel, distrito_sel, fast_mode=False, downsample_factor=8, dry_run=False, auto_fast=True):
    print("\n" + "="*80)
    print("🗺️ INICIANDO PROCESO DE GENERACIÓN DE MAPA DE PELIGRO (5 PARÁMETROS)")
    print("="*80)
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")

    # CREAR CARPETA DE SALIDA
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "MAPA DE PELIGRO")
        carpeta_rios_usuario = os.path.join(carpeta_usuario, "DISTANCIA_RIOS")
        os.makedirs(carpeta_salida, exist_ok=True)
        os.makedirs(carpeta_rios_usuario, exist_ok=True)
        print(f"   - Carpeta de salida verificada: {carpeta_salida}")
        print(f"   - Carpeta de ríos del usuario: {carpeta_rios_usuario}")
    except Exception as e:
        print(f"❌ Error creando la estructura de carpetas para el usuario: {e}")
        return None

    print("\n📦 Cargando capas base...")
    gdf_departamentos = cargar_shapefile("departamento", "Departamentos")
    gdf_provincias = cargar_shapefile("provincia", "Provincias")
    gdf_distritos = cargar_shapefile("distrito", "Distritos del Perú")

    # CARGAR CENTROS POBLADOS
    print("   🏘️ Cargando centros poblados...")
    try:
        if os.path.exists(RUTA_CENTROS_POBLADOS):
            gdf_centros_pob = gpd.read_file(RUTA_CENTROS_POBLADOS)
            if gdf_centros_pob.crs is None or gdf_centros_pob.crs.to_epsg() != 4326:
                gdf_centros_pob.set_crs(epsg=4326, inplace=True)
            gdf_centros_pob = gdf_centros_pob.to_crs(epsg=3857)
            print(f"   ✅ Centros poblados cargados: {len(gdf_centros_pob)} puntos")
        else:
            print(f"   ⚠️ No se encontró el shapefile de centros poblados")
            gdf_centros_pob = None
    except Exception as e:
        print(f"   ⚠️ Error cargando centros poblados: {e}")
        gdf_centros_pob = None

    try:
        gdf_paises = gpd.read_file(f"{ruta_base}/DATA/MAPA_DE_UBICACION/PAISES_DE_SUDAMERICA/Sudamérica.shp").to_crs(3857)
        gdf_oceano = gpd.read_file(f"{ruta_base}/DATA/MAPA_DE_UBICACION/OCEANO/Océano.shp").to_crs(3857)
    except Exception as e:
        print(f"⚠️ Error cargando shapefiles de Países u Océano: {e}")
        gdf_paises = None
        gdf_oceano = None

    if gdf_departamentos is None or gdf_provincias is None or gdf_distritos is None:
        print("❌ Faltan capas base. Abortando.")
        return None

    col_dpto = next((c for c in ['NOMBDEP', 'DEPARTAMEN'] if c in gdf_departamentos.columns), None)
    col_prov = next((c for c in ['NOMBPROV', 'PROVINCIA'] if c in gdf_provincias.columns), None)
    col_distr = next((c for c in ['NOMBDIST', 'DISTRITO'] if c in gdf_distritos.columns), None)

    if not all([col_dpto, col_prov, col_distr]):
        print("❌ No se pudieron identificar las columnas de nombres")
        return None

    print("\n🔍 Filtrando datos del área seleccionada...")

    # Normalizadores para matching tolerante (mayúsculas, espacios, acentos)
    def normalize_str(s):
        if s is None:
            return ""
        s = str(s).strip()
        s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
        return s.upper()

    def select_by_name(gdf, col, name):
        """Intentar varias estrategias para localizar un área: exacto (normalizado), contains, startswith."""
        if name is None:
            return gdf.iloc[0:0]  # empty
        name_norm = normalize_str(name)
        # exact match (after normalize)
        mask = gdf[col].astype(str).apply(normalize_str) == name_norm
        if mask.any():
            return gdf[mask]
        # contains
        mask = gdf[col].astype(str).apply(normalize_str).str.contains(name_norm)
        if mask.any():
            return gdf[mask]
        # startswith
        mask = gdf[col].astype(str).apply(normalize_str).str.startswith(name_norm)
        if mask.any():
            return gdf[mask]
        return gdf.iloc[0:0]

    gdf_dpto_sel = select_by_name(gdf_departamentos, col_dpto, departamento_sel)
    gdf_prov_sel = select_by_name(gdf_provincias, col_prov, provincia_sel)
    # Para distrito necesitamos coincidir por provincia también. Primero filtrar provincia y luego distrito.
    if not gdf_prov_sel.empty:
        gdf_distritos_prov = gdf_distritos[gdf_distritos[col_prov].astype(str).apply(lambda x: normalize_str(x) in set(gdf_prov_sel[col_prov].astype(str).apply(normalize_str)) )]
    else:
        gdf_distritos_prov = gdf_distritos

    gdf_distrito = select_by_name(gdf_distritos_prov, col_distr, distrito_sel)
    gdf_distritos_en_provincia = gdf_distritos[gdf_distritos[col_prov] == provincia_sel]

    # Construir rutas específicas para el departamento/provincia (soporta PIURA)
    rutas_capa = get_rutas_peligro(departamento_sel, provincia_sel)
    ruta_base_geomorfo = rutas_capa['RUTA_BASE_GEOMORFOLOGIA']
    ruta_base_ppmax = rutas_capa['RUTA_BASE_PPMAX']
    ruta_base_geologia = rutas_capa['RUTA_BASE_GEOLOGIA']
    ruta_base_pendiente = rutas_capa['RUTA_BASE_PENDIENTE']
    ruta_dem_dir = rutas_capa['RUTA_DEM']

    if gdf_distrito.empty:
        # Intentar construir un polígono a partir de capas temáticas (p.ej geomorfología / geología)
        print(f"   ⚠️ No se encontró un distrito exacto para '{distrito_sel}'. Buscaré una capa de provincia para usar su polígono como área de interés...")
        # Buscar en geomorfología primero
        ruta_geom_prov = buscar_archivo_peligro(ruta_base_geomorfo, provincia_sel, "GEOMORFOLOGÍA")
        if not ruta_geom_prov:
            ruta_geom_prov = buscar_archivo_peligro(ruta_base_geomorfo, provincia_sel.lower(), "GEOMORFOLOGÍA")

        if ruta_geom_prov:
            try:
                gdf_temp = gpd.read_file(ruta_geom_prov)
                # Unir geometrías para obtener la extensión de la provincia
                union = gdf_temp.geometry.unary_union
                gdf_distrito = gpd.GeoDataFrame({col_distr: [provincia_sel], col_prov: [provincia_sel]}, geometry=[union], crs=gdf_temp.crs)
                print(f"      ✅ Usando geometría unida de {os.path.basename(ruta_geom_prov)} como área de interés (provincia)")
            except Exception as e:
                print(f"      ⚠️ No se pudo leer/usar {ruta_geom_prov}: {e}")

        # Si sigue vacío, intentar con geología
        if gdf_distrito.empty:
            ruta_geol_prov = buscar_archivo_peligro(ruta_base_geologia, provincia_sel, "GEOLOGÍA")
            if not ruta_geol_prov:
                ruta_geol_prov = buscar_archivo_peligro(ruta_base_geologia, provincia_sel.lower(), "GEOLOGÍA")

            if ruta_geol_prov:
                try:
                    gdf_temp = gpd.read_file(ruta_geol_prov)
                    union = gdf_temp.geometry.unary_union
                    gdf_distrito = gpd.GeoDataFrame({col_distr: [provincia_sel], col_prov: [provincia_sel]}, geometry=[union], crs=gdf_temp.crs)
                    print(f"      ✅ Usando geometría unida de {os.path.basename(ruta_geol_prov)} como área de interés (provincia)")
                except Exception as e:
                    print(f"      ⚠️ No se pudo leer/usar {ruta_geol_prov}: {e}")

        if gdf_distrito.empty:
            # Mensaje final: listar candidatos cercanos para ayudar al usuario
            posibles = gdf_distritos[col_distr].astype(str).unique()[:12]
            print(f"❌ Error: No se pudo encontrar la geometría para el distrito '{distrito_sel}'.")
            print("   👉 Algunos distritos disponibles (ejemplos):", list(posibles))
            return None

    print(f"   ✅ Distrito encontrado con geometría válida")

    # Construir rutas específicas para el departamento/provincia (soporta PIURA)
    rutas_capa = get_rutas_peligro(departamento_sel, provincia_sel)
    ruta_base_geomorfo = rutas_capa['RUTA_BASE_GEOMORFOLOGIA']
    ruta_base_ppmax = rutas_capa['RUTA_BASE_PPMAX']
    ruta_base_geologia = rutas_capa['RUTA_BASE_GEOLOGIA']
    ruta_base_pendiente = rutas_capa['RUTA_BASE_PENDIENTE']
    ruta_dem_dir = rutas_capa['RUTA_DEM']

    # 🆕 GENERAR SHAPEFILE DE RÍOS AUTOMÁTICAMENTE EN CARPETA DEL USUARIO
    print("\n" + "="*80)
    print("🌊 PASO 1: VERIFICANDO/GENERANDO SHAPEFILE DE DISTANCIA A RÍOS")
    print("="*80)
    
    # 🆕 PRIMERO: DETECTAR EL DEM CORRESPONDIENTE AL DISTRITO (para uso consistente)
    print(f"\n   🔍 Detectando DEM del distrito...")
    ruta_dem_candidate = None
    if os.path.isdir(ruta_dem_dir):
        for f in os.listdir(ruta_dem_dir):
            if f.lower().endswith('.tif'):
                ruta_dem_candidate = os.path.join(ruta_dem_dir, f)
                print(f"      ✅ DEM encontrado: {os.path.basename(ruta_dem_candidate)}")
                break
    elif os.path.isfile(ruta_dem_dir):
        ruta_dem_candidate = ruta_dem_dir
        print(f"      ✅ DEM encontrado: {os.path.basename(ruta_dem_candidate)}")
    
    if not ruta_dem_candidate:
        print(f"      ⚠️ No se encontró DEM en: {ruta_dem_dir}")
        print(f"      ℹ️ Se usará el DEM por defecto de CUSCO")
    
    # Limpiar nombre del distrito para el archivo
    nombre_distrito_limpio = distrito_sel.replace(' ', '_').replace('/', '_').replace('\\', '_')
    nombre_archivo_rio = f"distancia_rio_{nombre_distrito_limpio}.shp"
    ruta_rios = os.path.join(carpeta_rios_usuario, nombre_archivo_rio)
    
    print(f"\n   🔍 Verificando shapefile de ríos: {nombre_archivo_rio}")
    print(f"   📁 Carpeta del usuario: {carpeta_rios_usuario}")
    
    # 🆕 VERIFICAR SI YA EXISTE EL SHAPEFILE PARA EVITAR REGENERACIÓN INNECESARIA
    if os.path.exists(ruta_rios):
        print(f"   ✅ Shapefile encontrado en carpeta del usuario actual")
        print(f"   ⚡ Usando shapefile existente: {ruta_rios}")
        ruta_rios_ya_existe = True
    else:
        print(f"   ℹ️ No se encontró shapefile en la carpeta actual")
        ruta_rios_ya_existe = False
    
    # GENERACIÓN DE RÍOS CON WHITEBOX (SÓLO SI NO EXISTE EN CARPETA DEL USUARIO)
    if not ruta_rios_ya_existe:
        print(f"\n   🆕 Generando shapefile de ríos con Whitebox (consistente para todos los distritos)...")
        print(f"   ⏳ Este proceso puede tardar varios minutos...")
        
        if ruta_dem_candidate:
            # Auto-detect DEM size and enable fast mode if requested
            if auto_fast and rasterio is not None:
                try:
                    with rasterio.open(ruta_dem_candidate) as ds_check:
                        pixels = ds_check.width * ds_check.height
                    if pixels > 5_000_000 and not fast_mode:
                        print(f"   ⚡ DEM muy grande ({pixels:,} píxeles) — activando fast_mode automáticamente")
                        fast_mode = True
                except Exception as e:
                    print(f"   ⚠️ No se pudo determinar el tamaño del DEM: {e}")
            
            # Si se solicita fast_mode, crear DEM de menor resolución para acelerar
            if fast_mode and rasterio is not None and not dry_run:
                dem_down = os.path.join(carpeta_usuario, "temp_hydro", "dem_downsampled.tif")
                print(f"   ⚡ fast_mode activado — creando DEM reducido (factor={downsample_factor})...")
                down = downsample_dem(ruta_dem_candidate, dem_down, factor=downsample_factor)
                if down:
                    globals()['RUTA_DEM_USUARIO'] = down
                    print(f"   ✅ DEM reducido creado: {down}")
                else:
                    globals()['RUTA_DEM_USUARIO'] = ruta_dem_candidate
                    print(f"   ⚠️ No se creó DEM reducido — se usará DEM original")
            else:
                # Usar DEM original
                globals()['RUTA_DEM_USUARIO'] = ruta_dem_candidate
        
        if dry_run:
            print("   🧭 dry_run activado — NO se generará shapefile ahora")
            print(f"      - DEM: {ruta_dem_candidate}")
            print(f"      - Destino: {carpeta_rios_usuario}")
            return {
                'status': 'dry_run',
                'dem': ruta_dem_candidate,
                'carpeta_rios_usuario': carpeta_rios_usuario
            }
        
        ruta_rios = generar_shapefile_rios_con_pesos(
            gdf_distrito, 
            carpeta_rios_usuario,
            temp_folder=os.path.join(carpeta_usuario, "temp_hydro"),
            nombre_distrito=distrito_sel
        )
        
        if not ruta_rios:
            print("❌ Error generando shapefile de ríos")
            return None
        
        print(f"\n   ✅ Shapefile de ríos generado: {os.path.basename(ruta_rios)}")

    # 🆕 CARGAR LAS CINCO CAPAS DE PELIGRO
    print("\n" + "="*80)
    print("🌊 PASO 2: CARGANDO CAPAS DE PELIGRO (5 PARÁMETROS)")
    print("="*80)
    
    try:
        # 1️⃣ PENDIENTE
        print(f"\n   🔍 Buscando capa de PENDIENTE para {provincia_sel}...")
        ruta_pendiente = buscar_archivo_peligro(ruta_base_pendiente, provincia_sel, "PENDIENTE")
        if not ruta_pendiente:
            ruta_pendiente = buscar_archivo_peligro(ruta_base_pendiente, departamento_sel, "PENDIENTE")
        if not ruta_pendiente:
            ruta_pendiente = buscar_archivo_peligro(ruta_base_pendiente, "peso", "PENDIENTE")
        
        if not ruta_pendiente:
            raise FileNotFoundError(f"No se encontró archivo de PENDIENTE")
        
        gdf_pendiente = gpd.read_file(ruta_pendiente).to_crs(epsg=3857)
        print(f"      ✅ Pendiente cargada: {len(gdf_pendiente)} registros")
        
        # 2️⃣ GEOMORFOLOGÍA
        print(f"\n   🔍 Buscando capa de GEOMORFOLOGÍA...")
        ruta_geomorfo = buscar_archivo_peligro(ruta_base_geomorfo, departamento_sel.lower(), "GEOMORFOLOGÍA")
        if not ruta_geomorfo:
            ruta_geomorfo = buscar_archivo_peligro(ruta_base_geomorfo, "peso", "GEOMORFOLOGÍA")
        
        if not ruta_geomorfo:
            raise FileNotFoundError(f"No se encontró archivo de GEOMORFOLOGÍA")
        
        gdf_geomorfo = gpd.read_file(ruta_geomorfo).to_crs(epsg=3857)
        print(f"      ✅ Geomorfología cargada: {len(gdf_geomorfo)} registros")
        
        # 3️⃣ PP MÁXIMA
        print(f"\n   🔍 Buscando capa de PP MÁXIMA...")
        # Buscar con varios patrones comunes de archivos PP/Tr50 para cubrir nombres distintos
        ruta_ppmax = None
        pp_patterns = ["ppmax", "tr50", "pp", "clasif", "clasificacion", "peso"]
        for patt in pp_patterns:
            ruta_ppmax = buscar_archivo_peligro(ruta_base_ppmax, patt, "PP MÁXIMA")
            if ruta_ppmax:
                break
        
        if not ruta_ppmax:
            raise FileNotFoundError(f"No se encontró archivo de PP MÁXIMA")
        
        gdf_ppmax = gpd.read_file(ruta_ppmax).to_crs(epsg=3857)
        print(f"      ✅ PP Máxima cargada: {len(gdf_ppmax)} registros")
        
        # 4️⃣ 🆕 DISTANCIA A RÍOS (YA GENERADO EN PASO 1)
        print(f"\n   🔍 Cargando capa de DISTANCIA A RÍOS...")
        gdf_rios = None
        
        if os.path.exists(ruta_rios):
            try:
                gdf_rios = gpd.read_file(ruta_rios).to_crs(epsg=3857)
                print(f"      ✅ Distancia a Ríos cargada: {len(gdf_rios)} registros")
                
                # Asegurar columna PESO_RIO
                if 'PESO_RIO' not in gdf_rios.columns:
                    posibles = [c for c in gdf_rios.columns if 'PESO' in c.upper()]
                    if posibles:
                        chosen = posibles[0]
                        print(f"      ⚠️ No existe 'PESO_RIO' — usando columna encontrada '{chosen}' como PESO_RIO")
                        gdf_rios['PESO_RIO'] = gdf_rios[chosen]
                    else:
                        print("      ⚠️ No se encontró columna de peso en ríos; se creará 'PESO_RIO' con valor por defecto = 1")
                        gdf_rios['PESO_RIO'] = 1
                
                print(f"      📋 Columnas: {list(gdf_rios.columns)}")
            except Exception as e:
                print(f"      ⚠️ Error cargando ríos: {e}")
        else:
            print(f"      ⚠️ No se encontró el archivo de ríos: {ruta_rios}")
        
        # 5️⃣ 🆕 GEOLOGÍA
        print(f"\n   🔍 Cargando capa de GEOLOGÍA...")
        # Buscar automáticamente el shapefile de geología dentro de la ruta base
        # Priorizar por provincia para distritos en diferentes provincias
        ruta_geologia = buscar_archivo_peligro(ruta_base_geologia, "geol", "GEOLOGÍA", provincia_sel=provincia_sel)
        if not ruta_geologia:
            raise FileNotFoundError(f"No se encontró archivo de GEOLOGÍA en: {ruta_base_geologia}")
        gdf_geologia = gpd.read_file(ruta_geologia)
        
        # Convertir a EPSG:3857 si es necesario
        if gdf_geologia.crs is None or gdf_geologia.crs.to_epsg() != 3857:
            if gdf_geologia.crs is None:
                gdf_geologia.set_crs(epsg=4326, inplace=True)
            gdf_geologia = gdf_geologia.to_crs(epsg=3857)
        
        print(f"      ✅ Geología cargada: {len(gdf_geologia)} registros")
        print(f"      📋 Columnas: {list(gdf_geologia.columns)}")
        
        # VERIFICAR COLUMNAS / NORMALIZAR NOMBRES DE PESO
        # Algunos shapefiles usan nombres específicos ('PESO', 'Nivel', etc.) — buscar y renombrar si es posible
        def ensure_weight_column(gdf, expected_name, friendly_layer_name, priority_names=None):
            if expected_name in gdf.columns:
                return True

            if priority_names is None:
                priority_names = []

            # Buscar primero en lista de prioridades
            for prio_name in priority_names:
                if prio_name in gdf.columns:
                    print(f"      ⚠️ No existe '{expected_name}' en {friendly_layer_name} — usando columna encontrada '{prio_name}' como '{expected_name}'")
                    gdf[expected_name] = gdf[prio_name]
                    return True

            # Fallback: buscar columnas que contengan 'PESO' (insensible a mayúsculas)
            candidatos = [c for c in gdf.columns if 'PESO' in c.upper()]
            if candidatos:
                elegido = candidatos[0]
                print(f"      ⚠️ No existe '{expected_name}' en {friendly_layer_name} — usando columna encontrada '{elegido}' como '{expected_name}'")
                gdf[expected_name] = gdf[elegido]
                return True

            # no se encontró ninguna columna con 'PESO'
            return False

        # PENDIENTE: buscar 'PESO' con prioridad
        if not ensure_weight_column(gdf_pendiente, 'PESO', 'PENDIENTE', priority_names=['PESO']):
            raise ValueError(f"La columna de peso para PENDIENTE no existe. Columnas disponibles: {list(gdf_pendiente.columns)}")

        # GEOMORFOLOGÍA: buscar columnas de peso
        if not ensure_weight_column(gdf_geomorfo, 'PESO_GEOMO', 'GEOMORFOLOGÍA'):
            raise ValueError(f"La columna de peso para GEOMORFOLOGÍA no existe. Columnas disponibles: {list(gdf_geomorfo.columns)}")

        # PP MÁXIMA: buscar 'Nivel' con prioridad
        if not ensure_weight_column(gdf_ppmax, 'Nivel', 'PP MÁXIMA', priority_names=['Nivel']):
            # Si 'Nivel' no está, intentar extraer desde otras columnas categóricas comunes (Clase/Categoria)
            cat_candidates = [c for c in gdf_ppmax.columns if any(k in c.upper() for k in ['CLAS', 'CATEG', 'CAT', 'LEVEL', 'CLASS'])]
            if cat_candidates:
                cat_col = cat_candidates[0]
                vals = list(gdf_ppmax[cat_col].dropna().unique())
                # intentar convertir a números si es posible
                def try_num(x):
                    try:
                        return float(x)
                    except Exception:
                        return None

                numeric_vals = [try_num(v) for v in vals]
                if all(v is not None for v in numeric_vals) and len(numeric_vals) > 0:
                    # usar los valores numéricos como pesos
                    print(f"      ⚠️ Creando 'Nivel' a partir de columna numérica '{cat_col}'")
                    gdf_ppmax['Nivel'] = gdf_ppmax[cat_col].astype(float)
                else:
                    # mapear categorías ordenadas a 1..n
                    unique_sorted = sorted(vals, key=lambda x: str(x))
                    mapping = {v: i + 1 for i, v in enumerate(unique_sorted)}
                    print(f"      ⚠️ Creando 'Nivel' a partir de columna categórica '{cat_col}' con mapeo: {mapping}")
                    gdf_ppmax['Nivel'] = gdf_ppmax[cat_col].map(mapping).astype(float)
            else:
                raise ValueError(f"La columna de peso para PP MÁXIMA no existe. Columnas disponibles: {list(gdf_ppmax.columns)}")

        # PESO_RIO ya debe existir por la lógica anterior (se creó o detectó) — validar igualmente
        if gdf_rios is not None and 'PESO_RIO' not in gdf_rios.columns:
            if not ensure_weight_column(gdf_rios, 'PESO_RIO', 'DISTANCIA RÍOS'):
                # si aún no hay peso, crearlo por defecto
                print("      ⚠️ No se encontró columna de peso en ríos; se creará 'PESO_RIO' con valor por defecto = 1")
                gdf_rios['PESO_RIO'] = 1

        # GEOLOGÍA: buscar primero 'PESO_GEOL' (columna correcta), luego fallback a 'PESO_GEOMO'
        if not ensure_weight_column(gdf_geologia, 'PESO_GEOL', 'GEOLOGÍA', priority_names=['PESO_GEOL', 'PESO_GEOMO']):
            raise ValueError(f"La columna de peso para GEOLOGÍA no existe. Columnas disponibles: {list(gdf_geologia.columns)}")
        
        print(f"\n   ✅ Todas las 5 capas cargadas exitosamente")
        
    except Exception as e:
        print(f"\n❌ Error cargando capas de peligro: {e}")
        import traceback
        traceback.print_exc()
        return None

    # RECORTAR CAPAS DE PELIGRO AL DISTRITO
    print("\n✂️ Recortando capas de peligro al distrito...")
    try:
        # Reproyectar todas las capas al CRS del distrito para evitar clips vacíos por CRS mismatched
        target_crs = gdf_distrito.crs if gdf_distrito is not None and gdf_distrito.crs is not None else 'EPSG:4326'

        def ensure_crs_and_transform(gdf, name):
            if gdf is None:
                return None
            try:
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                if gdf.crs != target_crs:
                    gdf = gdf.to_crs(target_crs)
            except Exception as e:
                print(f"      ⚠️ No se pudo reproyectar {name} a {target_crs}: {e}")
            return gdf

        gdf_pendiente = ensure_crs_and_transform(gdf_pendiente, 'PENDIENTE')
        gdf_geomorfo = ensure_crs_and_transform(gdf_geomorfo, 'GEOMORFOLOGÍA')
        gdf_ppmax = ensure_crs_and_transform(gdf_ppmax, 'PP MÁXIMA')
        gdf_geologia = ensure_crs_and_transform(gdf_geologia, 'GEOLOGÍA')
        gdf_rios = ensure_crs_and_transform(gdf_rios, 'RÍOS')
        gdf_centros_pob = ensure_crs_and_transform(gdf_centros_pob, 'CENTROS_POB')

        # Ahora sí recortar
        gdf_pendiente_clip = gpd.clip(gdf_pendiente, gdf_distrito)
        gdf_geomorfo_clip = gpd.clip(gdf_geomorfo, gdf_distrito)
        gdf_ppmax_clip = gpd.clip(gdf_ppmax, gdf_distrito)
        gdf_geologia_clip = gpd.clip(gdf_geologia, gdf_distrito)
        if gdf_rios is not None:
            gdf_rios_clip = gpd.clip(gdf_rios, gdf_distrito)
        else:
            gdf_rios_clip = None
        
        print(f"   ✅ Capas recortadas exitosamente")
        print(f"      - Pendiente: {len(gdf_pendiente_clip)} registros")
        print(f"      - Geomorfología: {len(gdf_geomorfo_clip)} registros")
        print(f"      - PP Máxima: {len(gdf_ppmax_clip)} registros")
        if gdf_rios_clip is not None:
            print(f"      - Distancia a Ríos: {len(gdf_rios_clip)} registros")
        else:
            print(f"      - Distancia a Ríos: 0 (omitido)")
        print(f"      - Geología: {len(gdf_geologia_clip)} registros")
        
    except Exception as e:
        print(f"❌ Error recortando capas: {e}")
        import traceback
        traceback.print_exc()
        return None

    # 🆕 COMBINAR LAS CINCO CAPAS MEDIANTE INTERSECCIÓN
    print("\n🔀 Combinando capas de peligro (5 parámetros)...")
    try:
        # Antes de intersectar, garantizar que todas las capas tengan geometrías poligonales y válidas
        def filter_polygons(gdf, name):
            if gdf is None:
                return None
            try:
                gdf = gdf[gdf.geometry.notna()].copy()
                # Intentar corregir geometrías inválidas suavemente
                try:
                    invalid_mask = ~gdf.geometry.is_valid
                    if invalid_mask.any():
                        gdf.loc[invalid_mask, 'geometry'] = gdf.loc[invalid_mask, 'geometry'].buffer(0)
                except Exception:
                    pass
                # Filtrar por tipo geométrico
                poly_mask = gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])
                if not poly_mask.all():
                    before = len(gdf)
                    gdf = gdf[poly_mask].copy()
                    print(f"      ℹ️ Filtradas {before - len(gdf)} geometrías no poligonales en {name}")
                gdf = gdf.reset_index(drop=True)
            except Exception as e:
                print(f"      ⚠️ Error filtrando geometrías en {name}: {e}")
            return gdf

        gdf_pendiente_clip = filter_polygons(gdf_pendiente_clip, 'PENDIENTE')
        gdf_geomorfo_clip = filter_polygons(gdf_geomorfo_clip, 'GEOMORFOLOGÍA')
        gdf_ppmax_clip = filter_polygons(gdf_ppmax_clip, 'PP MÁXIMA')
        gdf_geologia_clip = filter_polygons(gdf_geologia_clip, 'GEOLOGÍA')
        if gdf_rios_clip is not None:
            gdf_rios_clip = filter_polygons(gdf_rios_clip, 'RÍOS')

        # Intersección dinámica de las capas disponibles (omite ríos si fue omitido)
        gdfs_to_intersect = [gdf_pendiente_clip, gdf_geomorfo_clip, gdf_ppmax_clip]
        if gdf_rios_clip is not None:
            gdfs_to_intersect.append(gdf_rios_clip)
        gdfs_to_intersect.append(gdf_geologia_clip)

        print(f"   🧩 Intersectando {len(gdfs_to_intersect)} capas disponibles...")
        gdf_inter = gdfs_to_intersect[0]
        for idx, next_gdf in enumerate(gdfs_to_intersect[1:], start=2):
            print(f"   [{idx}/{len(gdfs_to_intersect)}] Intersectando capa {idx} de {len(gdfs_to_intersect)}...")
            if next_gdf is None or len(next_gdf) == 0:
                print(f"      ⚠️ Capa {idx} vacía; saltando intersección con esta capa")
                continue
            gdf_inter = gpd.overlay(gdf_inter, next_gdf, how='intersection')

        gdf_peligro = gdf_inter
        
        # 🆕 VERIFICAR Y LIMPIAR NOMBRES DE COLUMNAS
        print("\n   📋 Verificando columnas después de intersección...")
        print(f"      Columnas disponibles: {list(gdf_peligro.columns)}")

        # Función auxiliar para localizar columnas por palabras clave (insensible a mayúsculas)
        def find_col_by_keywords(candidate_cols, keywords_all=None, keywords_any=None, exclude_keywords=None):
            keywords_all = [k.upper() for k in (keywords_all or [])]
            keywords_any = [k.upper() for k in (keywords_any or [])]
            exclude_keywords = [k.upper() for k in (exclude_keywords or [])]
            for c in candidate_cols:
                cu = c.upper()
                if any(ex in cu for ex in exclude_keywords):
                    continue
                ok_all = all(k in cu for k in keywords_all) if keywords_all else True
                ok_any = any(k in cu for k in keywords_any) if keywords_any else True
                if ok_all and ok_any:
                    return c
            return None

        cols_list = list(gdf_peligro.columns)

        # Buscar columnas por prioridad para evitar capturar la primera columna que contenga sólo 'PESO'
        col_geomo = find_col_by_keywords(cols_list, keywords_all=['PESO','GEOMO'], keywords_any=['GEOMO','PESO']) or find_col_by_keywords(cols_list, keywords_any=['GEOMO'])
        # Para Geología, buscar primero PESO_GEOL (la correcta), luego PESO_GEOMO como fallback
        col_geol  = find_col_by_keywords(cols_list, keywords_all=['PESO','GEOL'], keywords_any=['GEOL']) or find_col_by_keywords(cols_list, keywords_any=['GEOL','GEOMO'])
        col_rio   = find_col_by_keywords(cols_list, keywords_all=['PESO','RIO'],  keywords_any=['RIO','PESO']) or find_col_by_keywords(cols_list, keywords_any=['RIO'])
        col_ppmax = find_col_by_keywords(cols_list, keywords_any=['NIVEL','LEVEL','PP','TR50','PRECIP'])

        # Para pendiente buscamos una columna 'PESO' que no haya sido identificada como geomo/geol/rio
        excluded = []
        if col_geomo: excluded.append(col_geomo.upper())
        if col_geol:  excluded.append(col_geol.upper())
        if col_rio:   excluded.append(col_rio.upper())

        col_pendi = find_col_by_keywords(cols_list, keywords_any=['PESO'], exclude_keywords=excluded)

        print(f"\n   📊 Columnas identificadas:")
        detected = []
        if col_pendi:
            detected.append(("Pendiente", col_pendi))
        if col_geomo:
            detected.append(("Geomorfología", col_geomo))
        if col_ppmax:
            detected.append(("PP Máxima", col_ppmax))
        if col_rio:
            detected.append(("Distancia Ríos", col_rio))
        if col_geol:
            detected.append(("Geología", col_geol))

        if detected:
            for label, cname in detected:
                print(f"      - {label}: {cname}")
        else:
            print("      Ninguna columna de peso identificada (todas None)")
        
        # Verificar cuáles parámetros tenemos presentes y obtener sus columnas
        present_cols = {}
        weights_map = {
            'PENDI': 0.5,
            'GEOMO': 0.5,
            'PPMAX': 1.0,
            'RIO': 2.5,
            'GEOL': 0.5
        }

        if col_pendi:
            present_cols['PENDI'] = col_pendi
        if col_geomo:
            present_cols['GEOMO'] = col_geomo
        if col_ppmax:
            present_cols['PPMAX'] = col_ppmax
        if col_rio:
            present_cols['RIO'] = col_rio
        if col_geol:
            present_cols['GEOL'] = col_geol

        if not present_cols:
            raise ValueError("No se encontraron columnas de peso válidas tras la intersección")
        
        # 🆕 CALCULAR EL ÍNDICE DE PELIGRO (ponderación dinámica según parámetros disponibles)
        print("\n   [5/5] Calculando índice de peligro (ponderación dinámica)...")

        # Sumar los pesos disponibles
        peso_total = sum(weights_map[k] for k in present_cols.keys())
        if peso_total <= 0:
            raise ValueError("Peso total inválido (0) — no hay parámetros disponibles para calcular peligro")

        # Construir la suma ponderada de forma dinámica
        suma_expresion = None
        for key, colname in present_cols.items():
            w = weights_map.get(key, 1.0)
            if suma_expresion is None:
                suma_expresion = w * gdf_peligro[colname]
            else:
                suma_expresion = suma_expresion + w * gdf_peligro[colname]

        gdf_peligro['PELIGRO'] = suma_expresion / float(peso_total)

        # 🆕 MOSTRAR ESTADÍSTICAS PARA LOS PARÁMETROS DISPONIBLES
        print(f"\n   📊 Estadísticas ANTES del promedio (parámetros disponibles):")
        for key, colname in present_cols.items():
            try:
                print(f"      - {key}: min={gdf_peligro[colname].min():.2f}, max={gdf_peligro[colname].max():.2f}, media={gdf_peligro[colname].mean():.2f}")
            except Exception:
                print(f"      - {key}: (error leyendo estadísticas para columna {colname})")
        
        print(f"\n   📊 Estadísticas DESPUÉS del promedio (PELIGRO):")
        # Evitar errores con valores NaN o cuando no hay registros
        pel = gdf_peligro['PELIGRO'].dropna()
        if len(pel) > 0:
            print(f"      - Peligro Final: min={pel.min():.3f}, max={pel.max():.3f}, media={pel.mean():.3f}")
        else:
            print("      - Peligro Final: no hay valores válidos (todos NaN o dataset vacío)")
            # Si la intersección arrojó 0 polígonos, crear fallback agregado por distrito
            try:
                print("      ℹ️ Intersección vacía — creando polígono agregado a nivel distrital como fallback")

                def area_weighted_mean(gdf, col):
                    if gdf is None or len(gdf) == 0:
                        return None
                    try:
                        tmp = gdf.copy()
                        tmp['__area__'] = tmp.geometry.area
                        total_area = tmp['__area__'].sum()
                        if total_area <= 0:
                            return None
                        vals = tmp[col].astype(float).fillna(0)
                        return (vals * tmp['__area__']).sum() / total_area
                    except Exception:
                        return None

                # Calcular medias ponderadas por área para cada capa usando los GDF recortados
                fallback_vals = {}
                try:
                    if 'PESO' in gdf_pendiente_clip.columns:
                        v = area_weighted_mean(gdf_pendiente_clip, 'PESO')
                        if v is not None: fallback_vals['PENDI'] = v
                except Exception:
                    pass
                try:
                    if 'PESO_GEOMO' in gdf_geomorfo_clip.columns:
                        v = area_weighted_mean(gdf_geomorfo_clip, 'PESO_GEOMO')
                        if v is not None: fallback_vals['GEOMO'] = v
                except Exception:
                    pass
                try:
                    if 'Nivel' in gdf_ppmax_clip.columns:
                        v = area_weighted_mean(gdf_ppmax_clip, 'Nivel')
                        if v is not None: fallback_vals['PPMAX'] = v
                except Exception:
                    pass
                try:
                    if gdf_rios_clip is not None and 'PESO_RIO' in gdf_rios_clip.columns:
                        v = area_weighted_mean(gdf_rios_clip, 'PESO_RIO')
                        if v is not None: fallback_vals['RIO'] = v
                except Exception:
                    pass
                try:
                    if 'PESO_GEOL' in gdf_geologia_clip.columns:
                        v = area_weighted_mean(gdf_geologia_clip, 'PESO_GEOL')
                        if v is not None: fallback_vals['GEOL'] = v
                except Exception:
                    pass

                if not fallback_vals:
                    print("      ⚠️ No hay valores disponibles en las capas para crear el fallback agregado")
                else:
                    # Combinar según weights_map
                    peso_total_fb = sum(weights_map.get(k, 1.0) for k in fallback_vals.keys())
                    suma_fb = sum((weights_map.get(k, 1.0) * fallback_vals[k]) for k in fallback_vals.keys())
                    peligro_agg = suma_fb / float(peso_total_fb) if peso_total_fb > 0 else None

                    # Crear GeoDataFrame con la geometría del distrito (unión) y el valor agregado
                    geom_union = gdf_distrito.geometry.unary_union
                    gdf_peligro = gpd.GeoDataFrame(
                        {k: [v] for k, v in fallback_vals.items()},
                        geometry=[geom_union],
                        crs=gdf_distrito.crs
                    )
                    gdf_peligro['PELIGRO'] = peligro_agg
                    gdf_peligro['COLOR'] = gdf_peligro['PELIGRO'].apply(asignar_color_peligro)

                    print(f"      ✅ Fallback agregado calculado: PELIGRO={peligro_agg:.3f} basado en {list(fallback_vals.keys())}")
            except Exception as e:
                print(f"      ⚠️ Falló la creación del fallback agregado: {e}")

        # 🆕 MOSTRAR DISTRIBUCIÓN POR NIVEL DE PELIGRO
        print(f"\n   📊 Distribución por nivel de peligro:")
        # Utilizar sólo valores válidos de PELIGRO para la distribución
        pel_valid = pel
        nivel_baja = len(pel_valid[(pel_valid >= 1.0) & (pel_valid < 2.0)])
        nivel_media = len(pel_valid[(pel_valid >= 2.0) & (pel_valid < 3.0)])
        nivel_alta = len(pel_valid[(pel_valid >= 3.0) & (pel_valid < 4.0)])
        nivel_muy_alta = len(pel_valid[(pel_valid >= 4.0) & (pel_valid <= 5.0)])

        total = len(pel_valid)
        def pct(n):
            return (100.0 * n / total) if total > 0 else 0.0

        print(f"      - Baja (1.0-2.0):      {nivel_baja:5d} polígonos ({pct(nivel_baja):5.1f}%)")
        print(f"      - Media (2.0-3.0):     {nivel_media:5d} polígonos ({pct(nivel_media):5.1f}%)")
        print(f"      - Alta (3.0-4.0):      {nivel_alta:5d} polígonos ({pct(nivel_alta):5.1f}%)")
        print(f"      - Muy Alta (4.0-5.0):  {nivel_muy_alta:5d} polígonos ({pct(nivel_muy_alta):5.1f}%)")
        
        # Asignar colores según el nivel de peligro
        gdf_peligro['COLOR'] = gdf_peligro['PELIGRO'].apply(asignar_color_peligro)
        
        print(f"\n   ✅ Capas combinadas exitosamente: {len(gdf_peligro)} polígonos")
        
        # 🆕 GUARDAR SHAPEFILE CON RESULTADOS PARA DEBUG
        debug_shp = os.path.join(carpeta_salida, "peligro_debug_5param.shp")
        gdf_peligro.to_file(debug_shp)
        print(f"   💾 Shapefile de debug guardado: {debug_shp}")
        
    except Exception as e:
        print(f"❌ Error combinando capas: {e}")
        import traceback
        traceback.print_exc()
        return None

    print("\n🎨 Generando layout del mapa...")
    fig = plt.figure(figsize=(14, 9.9))
    grid = plt.GridSpec(1, 2, width_ratios=[3.0, 1], wspace=0.05)
    gs_izquierda = grid[0, 0].subgridspec(3, 1, height_ratios=[0.08, 3.5, 0.42], hspace=0.08)

    ax_titulo = fig.add_subplot(gs_izquierda[0])
    ax_titulo.text(0.5, 0.5, f"MAPA DE SUSCEPTIBILIDAD ANTE INUNDACIÓN - DISTRITO DE {distrito_sel.upper()}",
                   ha='center', va='center', fontsize=11, fontweight="normal",
                   bbox=dict(boxstyle='square,pad=0.5', facecolor='white', 
                            edgecolor='black', linewidth=1.5, alpha=0.95))
    ax_titulo.axis('off')

    ax_main = fig.add_subplot(gs_izquierda[1])

    # CÁLCULO DE BBOX
    minx, miny, maxx, maxy = gdf_distrito.total_bounds
    buffer_factor = 0.15
    buffer_x = (maxx - minx) * buffer_factor
    buffer_y = (maxy - miny) * buffer_factor
    bbox_temp = (minx - buffer_x, miny - buffer_y, maxx + buffer_x, maxy + buffer_y)
    
    # AJUSTE DE ASPECTO RATIO
    aspect_ratio_objetivo = 1.21
    cx, cy = (bbox_temp[0] + bbox_temp[2]) / 2, (bbox_temp[1] + bbox_temp[3]) / 2
    ancho_actual, alto_actual = bbox_temp[2] - bbox_temp[0], bbox_temp[3] - bbox_temp[1]
    
    if (ancho_actual / alto_actual) > aspect_ratio_objetivo:
        nuevo_alto = ancho_actual / aspect_ratio_objetivo
        bbox_main = (bbox_temp[0], cy - nuevo_alto/2, bbox_temp[2], cy + nuevo_alto/2)
    else:
        nuevo_ancho = alto_actual * aspect_ratio_objetivo
        bbox_main = (cx - nuevo_ancho/2, bbox_temp[1], cx + nuevo_ancho/2, bbox_temp[3])

    ax_main.set_xlim(bbox_main[0], bbox_main[2])
    ax_main.set_ylim(bbox_main[1], bbox_main[3])
    ax_main.set_aspect('equal', adjustable='box')

    print("   🛰️ Descargando imagen satelital...")
    try:
        ctx.add_basemap(ax_main, source=ctx.providers.Esri.WorldImagery, attribution=False, zoom='auto')
    except Exception as e:
        print(f"   ⚠️ No se pudo cargar el mapa base: {e}")
        ax_main.set_facecolor("#e8e8e8")

    # VISUALIZAR CAPA DE PELIGRO
    print("   🎨 Renderizando mapa de peligro...")
    gdf_peligro.plot(ax=ax_main, color=gdf_peligro['COLOR'], edgecolor='black', 
                     linewidth=0.2, alpha=0.7, zorder=4)
    
    # VISUALIZAR CENTROS POBLADOS
    if gdf_centros_pob is not None:
        print("   🏘️ Agregando centros poblados al mapa...")
        try:
            # Recortar centros poblados al área del mapa
            centros_en_mapa = gpd.clip(gdf_centros_pob, gdf_distrito)
            
            if len(centros_en_mapa) > 0:
                # Plotear puntos de centros poblados
                centros_en_mapa.plot(ax=ax_main, 
                                    color='#006400',  # Verde oscuro
                                    edgecolor='white', 
                                    markersize=40,
                                    marker='o',
                                    linewidth=1.0,
                                    alpha=0.95,
                                    zorder=10)
                
                # 🎯 AGREGAR ETIQUETAS PERPENDICULARES AL LÍMITE DISTRITAL (CON SEPARACIÓN)
                agregar_etiquetas_ordenadas_circularmente(gdf_distrito, centros_en_mapa, ax_main, radio_offset=0.12)
                
                print(f"      ✅ {len(centros_en_mapa)} centros poblados etiquetados")
            else:
                print(f"      ⚠️ No hay centros poblados en el área del distrito")
        except Exception as e:
            print(f"      ⚠️ Error agregando centros poblados: {e}")
    
    # LÍMITE DISTRITAL
    gdf_distrito.plot(ax=ax_main, facecolor="none", edgecolor="black", 
                     linewidth=1.5, linestyle='-', alpha=1.0, zorder=15)

    grillado_utm_proyectado(ax_main, bbox_main, ndiv=8)
    add_north_arrow_blanco_completo(ax_main, xy_pos=(0.93, 0.08), size=0.06)
    ax_main.add_artist(ScaleBar(1, units="m", location="lower left", 
                                box_alpha=0.6, border_pad=0.5, scale_loc='bottom'))

    # MEMBRETE Y LEYENDA
    gs_memb_ley = gs_izquierda[2].subgridspec(1, 2, wspace=0.1)
    ax_membrete = fig.add_subplot(gs_memb_ley[0])
    fig.canvas.draw()
    add_membrete(ax_membrete, departamento_sel, provincia_sel, distrito_sel, ax_main, fig)

    ax_leyenda = fig.add_subplot(gs_memb_ley[1])
    ax_leyenda.axis('off')

    legend_elements = [Patch(facecolor='white', edgecolor='white', label='SUSCEPTIBILIDAD:', linewidth=0)]
    
    legend_elements.extend([
        Patch(facecolor=COLORES_PELIGRO[3], edgecolor='black', label='Muy Alta'), 
        Patch(facecolor=COLORES_PELIGRO[2], edgecolor='black', label='Alta'),
        Patch(facecolor=COLORES_PELIGRO[1], edgecolor='black', label='Media'),
        Patch(facecolor=COLORES_PELIGRO[0], edgecolor='black', label='Baja')
    ])

    legend_elements.extend([
        Line2D([0], [0], color='black', lw=1.5, linestyle='-', label='Límite Distrital'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#006400',  # Verde oscuro
               markeredgecolor='white', markersize=7, linestyle='None', 
               label='Centro Poblado', markeredgewidth=1.0)
    ])

    leg = ax_leyenda.legend(handles=legend_elements, loc='center', ncol=1, frameon=True, fontsize=7,
                           title="LEYENDA", title_fontproperties={'size': 10, 'weight': 'bold'},
                           handletextpad=0.5, columnspacing=1.0, borderpad=0.7, handlelength=1.5)
    leg.get_title().set_ha('center')
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(1.2)

    print("   🗺️ Generando mapas de ubicación...")
    gs_ubicaciones = grid[0, 1].subgridspec(3, 1, height_ratios=[1, 1, 1], hspace=0.15)
    ax_depto = fig.add_subplot(gs_ubicaciones[0])
    ax_prov = fig.add_subplot(gs_ubicaciones[1])
    ax_dist = fig.add_subplot(gs_ubicaciones[2])

    mapa_ubicacion(ax_depto, gdf_paises, gdf_departamentos, gdf_dpto_sel,
                   f"DEPARTAMENTO DE\n{departamento_sel.upper()}", departamento_sel,
                   tipo_mapa="pais", gdf_departamentos=gdf_departamentos, gdf_oceano=gdf_oceano)

    mapa_ubicacion(ax_prov, gdf_departamentos, gdf_dpto_sel, gdf_prov_sel,
                   f"PROVINCIA DE\n{provincia_sel.upper()}", provincia_sel,
                   tipo_mapa="provincia", gdf_dpto_sel=gdf_dpto_sel, 
                   departamento_sel=departamento_sel, col_dpto=col_dpto, 
                   gdf_departamentos=gdf_departamentos, gdf_oceano=gdf_oceano)

    mapa_ubicacion(ax_dist, gdf_prov_sel, gdf_distritos_en_provincia, gdf_distrito,
                   f"DISTRITO DE\n{distrito_sel.upper()}", distrito_sel,
                   tipo_mapa="distrito", gdf_prov_sel=gdf_prov_sel, 
                   provincia_sel=provincia_sel, col_prov=col_prov, 
                   gdf_provincias=gdf_provincias, gdf_oceano=gdf_oceano)

    plt.subplots_adjust(top=0.98, bottom=0.02, left=0.02, right=0.98, hspace=0.2, wspace=0.05)

    rect_frame = fig.add_axes([0, 0, 1, 1], frameon=False)
    rect_frame.set_xticks([])
    rect_frame.set_yticks([])
    rect_frame.patch.set_visible(False)

    for spine in rect_frame.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(2)
        spine.set_color('black')

    print("\n💾 Guardando mapa final...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = f"MAPA_PELIGRO_5PARAM_{distrito_sel.replace(' ', '_')}_{timestamp}.png"
    ruta_guardado_final = os.path.join(carpeta_salida, nombre_base)

    try:
        plt.savefig(ruta_guardado_final, dpi=300, bbox_inches='tight', pad_inches=0.01)
        plt.close(fig)

        if os.path.exists(ruta_guardado_final):
            file_size = os.path.getsize(ruta_guardado_final) / (1024 * 1024)
            print(f"✅ Mapa de peligro guardado exitosamente")
            print(f"   📁 Ubicación: {ruta_guardado_final}")
            print(f"   📊 Tamaño: {file_size:.2f} MB")
            print(f"   🎯 Parámetros: 5 (Pendiente + Geomorfología + PP Máxima + Distancia a Ríos + Geología)")
            print(f"   🏘️ Centros poblados: Etiquetas FUERA de zona con líneas blancas gruesas")
            print(f"   ✨ Separación automática anti-solapamiento activada")
            print(f"   📂 Archivos de ríos guardados en: {carpeta_rios_usuario}")
            print("="*80 + "\n")
            return ruta_guardado_final
        else:
            print("❌ El archivo no se guardó correctamente")
            return None

    except Exception as e:
        print(f"❌ Error al guardar el archivo: {e}")
        import traceback
        traceback.print_exc()
        plt.close(fig)
        return None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🚀 EJECUCIÓN DEL SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # EJEMPLO DE USO
    generar_mapa_peligro(
        nombre_usuario="USUARIO_TEST21",
        departamento_sel="PIURA",
        provincia_sel="PIURA",
        distrito_sel="PIURA"
    )