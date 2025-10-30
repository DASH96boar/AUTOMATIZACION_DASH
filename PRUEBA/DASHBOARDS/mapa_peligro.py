# -*- coding: utf-8 -*-
"""
🎯 SCRIPT INTEGRADO: MAPA DE PELIGRO CON 5 PARÁMETROS + CENTROS POBLADOS
- Genera automáticamente el shapefile de distancia a ríos desde el DEM
- Calcula el mapa de peligro combinando: Pendiente + Geomorfología + PP Máxima + Distancia a Ríos + Geología
- Muestra centros poblados como referencia
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
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Polygon, Rectangle, Patch
from matplotlib.lines import Line2D
import datetime
import pandas as pd

# Importaciones para procesamiento hidrológico
try:
    import rasterio
    from rasterio.mask import mask as rasterio_mask
    from whitebox import WhiteboxTools
    HYDRO_AVAILABLE = True
except ImportError:
    HYDRO_AVAILABLE = False
    print("⚠️ WhiteboxTools o rasterio no disponibles. Instalando...")

# --- CONFIGURACIÓN GLOBAL ---
ruta_base = "/workspaces/SIG-AUTOMATIZACION/PRUEBA"
AMARILLO_CLARO = "#FFEE58"

# RUTAS BASE DE LAS CAPAS DE PELIGRO
RUTA_BASE_PENDIENTE = f"{ruta_base}/DATA/PELIGRO/PENDIENTE"
RUTA_BASE_GEOMORFOLOGIA = f"{ruta_base}/DATA/PELIGRO/GEOMORFOLOGIA"
RUTA_BASE_PPMAX = f"{ruta_base}/DATA/PELIGRO/PP_MAX"
RUTA_BASE_RIOS = f"{ruta_base}/DATA/PELIGRO/DISTANCIA_RIO"
RUTA_BASE_GEOLOGIA = f"{ruta_base}/DATA/PELIGRO/GEOLOGIA"
RUTA_DEM = f"{RUTA_BASE_RIOS}/DEM.tif"
RUTA_CENTROS_POBLADOS = f"{ruta_base}/DATA/CENTROS POBLADOS/Centros_Poblados_INEI_geogpsperu_SuyoPomalia.shp"

# CONFIGURACIÓN DE GENERACIÓN DE RÍOS
INTENSIDAD_RIOS = "muy_baja"  # Opciones: "muy_alta", "alta", "media", "baja", "muy_baja"
UMBRALES_RIOS = {"muy_alta": 50, "alta": 200, "media": 500, "baja": 1000, "muy_baja": 2000}

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

# ═══════════════════════════════════════════════════════════════════════════
# 🌊 FUNCIONES PARA GENERAR RED DE RÍOS Y BUFFERS
# ═══════════════════════════════════════════════════════════════════════════

def generar_shapefile_rios_con_pesos(distrito_shapefile, output_folder, temp_folder="/tmp/hydro_temp"):
    """
    Genera el shapefile de buffers de distancia a ríos con pesos a partir del DEM.
    
    Parámetros:
    - distrito_shapefile: GeoDataFrame del distrito para recortar
    - output_folder: Carpeta donde se guardará el shapefile final
    - temp_folder: Carpeta temporal para archivos intermedios
    
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
    
    # Verificar que existe el DEM
    if not os.path.exists(RUTA_DEM):
        print(f"❌ No se encontró el DEM en: {RUTA_DEM}")
        return None
    
    print(f"[1/6] ✂️ Recortando DEM al distrito...")
    
    try:
        # Cargar límite del distrito
        limit = distrito_shapefile.copy()
        
        with rasterio.open(RUTA_DEM) as dem:
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
        with rasterio.open(RUTA_DEM) as src:
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
            
            threshold = UMBRALES_RIOS[INTENSIDAD_RIOS]
            print(f"      [2.4/4] Extrayendo red de ríos (umbral: {threshold} celdas)...")
            if not os.path.exists(streams_raster):
                wbt.extract_streams(flow_acc, streams_raster, threshold)
                print(f"      ✅ Red de ríos extraída")
            else:
                print(f"      ⚡ Usando streams_raster existente")
            
            print(f"      [2.5/4] Vectorizando red de ríos...")
            if not os.path.exists(streams_vector):
                wbt.raster_streams_to_vector(streams_raster, flow_dir, streams_vector)
                print(f"      ✅ Red de ríos vectorizada")
            else:
                print(f"      ⚡ Usando streams_vector existente")
        
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
    print(f"[3/6] 📍 Cargando red de ríos...")
    
    try:
        rivers = gpd.read_file(streams_vector)
        
        if rivers.crs is None:
            with rasterio.open(dem_clipped) as dem_src:
                rivers = rivers.set_crs(dem_src.crs)
        
        if rivers.crs != limit.crs:
            limit_final = limit.to_crs(rivers.crs)
        else:
            limit_final = limit.copy()
        
        rivers_clip = gpd.clip(rivers, limit_final)
        print(f"      ✅ {len(rivers_clip)} segmentos de ríos")
        
    except Exception as e:
        print(f"❌ Error cargando ríos: {e}")
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
    print(f"[5/6] 🔄 Convirtiendo a CRS 3857...")
    
    try:
        buffers_gdf = buffers_gdf.to_crs(epsg=3857)
        print(f"      ✅ CRS convertido")
    except Exception as e:
        print(f"❌ Error convirtiendo CRS: {e}")
        return None
    
    # [6/6] Guardar shapefile
    print(f"[6/6] 💾 Guardando shapefile...")
    
    try:
        output_shp = os.path.join(output_folder, "buffers_distancia_rios_PESOS.shp")
        buffers_gdf.to_file(output_shp)
        
        print(f"      ✅ Shapefile guardado: {output_shp}")
        print(f"\n📊 Resumen:")
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

# ═══════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES PARA MAPAS
# ═══════════════════════════════════════════════════════════════════════════

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
    ax.text(7.5 + padding, 2.5, "MAPA N°", fontweight='bold', ha='left', va='center', fontsize=8)
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
    
    if gdf_oceano is not None:
        gdf_oceano.clip(box(*bbox)).plot(ax=ax, color="#A4D4FF", edgecolor="none", zorder=2)
    
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
    
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])
    ax.set_facecolor("#f0f8ff")
    ax.set_aspect('equal', adjustable='box')
    ax.axis('on')

def buscar_archivo_peligro(ruta_base, patron_busqueda, tipo_capa):
    """Busca archivos de peligro de forma inteligente"""
    print(f"   🔍 Buscando {tipo_capa} en: {ruta_base}")
    
    archivos_encontrados = []
    
    for root, dirs, files in os.walk(ruta_base):
        for file in files:
            if file.lower().endswith('.shp') and patron_busqueda.lower() in file.lower():
                ruta_completa = os.path.join(root, file)
                archivos_encontrados.append(ruta_completa)
                print(f"      ✅ Encontrado: {ruta_completa}")
    
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

# ═══════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIÓN PRINCIPAL CON 5 PARÁMETROS + CENTROS POBLADOS
# ═══════════════════════════════════════════════════════════════════════════

def generar_mapa_peligro(nombre_usuario, departamento_sel, provincia_sel, distrito_sel):
    print("\n" + "="*80)
    print("🗺️ INICIANDO PROCESO DE GENERACIÓN DE MAPA DE PELIGRO (5 PARÁMETROS)")
    print("="*80)
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")

    # CREAR CARPETA DE SALIDA
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "MAPA DE PELIGRO")
        os.makedirs(carpeta_salida, exist_ok=True)
        print(f"   - Carpeta de salida verificada: {carpeta_salida}")
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
        gdf_paises = gpd.read_file(f"{ruta_base}/DATA/MAPA DE UBICACION/PAISES DE SUDAMERICA/Sudamérica.shp").to_crs(3857)
        gdf_oceano = gpd.read_file(f"{ruta_base}/DATA/MAPA DE UBICACION/OCEANO/Océano.shp").to_crs(3857)
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
    gdf_dpto_sel = gdf_departamentos[gdf_departamentos[col_dpto] == departamento_sel]
    gdf_prov_sel = gdf_provincias[gdf_provincias[col_prov] == provincia_sel]
    gdf_distrito = gdf_distritos[(gdf_distritos[col_distr] == distrito_sel) & 
                                  (gdf_distritos[col_prov] == provincia_sel)]
    gdf_distritos_en_provincia = gdf_distritos[gdf_distritos[col_prov] == provincia_sel]

    if gdf_distrito.empty:
        print(f"❌ Error: No se pudo encontrar la geometría para el distrito '{distrito_sel}'.")
        return None

    print(f"   ✅ Distrito encontrado con geometría válida")

    # 🆕 GENERAR SHAPEFILE DE RÍOS AUTOMÁTICAMENTE
    print("\n" + "="*80)
    print("🌊 PASO 1: GENERANDO SHAPEFILE DE DISTANCIA A RÍOS")
    print("="*80)
    
    ruta_rios = os.path.join(RUTA_BASE_RIOS, "buffers_distancia_rios_PESOS.shp")
    
    # Verificar si ya existe el shapefile
    if os.path.exists(ruta_rios):
        print(f"⚠️ El shapefile ya existe: {ruta_rios}")
        print("   Opciones: [U]sar existente | [R]egenerar")
        respuesta = input("   Seleccione (U/R) [por defecto: U]: ").strip().upper()
        
        if respuesta == 'R':
            print("   🔄 Regenerando shapefile de ríos...")
            ruta_rios = generar_shapefile_rios_con_pesos(
                gdf_distrito, 
                RUTA_BASE_RIOS,
                temp_folder=os.path.join(carpeta_usuario, "temp_hydro")
            )
            if not ruta_rios:
                print("❌ Error generando shapefile de ríos")
                return None
        else:
            print("   ✅ Usando shapefile existente")
    else:
        print("   🆕 Generando shapefile de ríos por primera vez...")
        ruta_rios = generar_shapefile_rios_con_pesos(
            gdf_distrito, 
            RUTA_BASE_RIOS,
            temp_folder=os.path.join(carpeta_usuario, "temp_hydro")
        )
        if not ruta_rios:
            print("❌ Error generando shapefile de ríos")
            return None

    # 🆕 CARGAR LAS CINCO CAPAS DE PELIGRO
    print("\n" + "="*80)
    print("🌊 PASO 2: CARGANDO CAPAS DE PELIGRO (5 PARÁMETROS)")
    print("="*80)
    
    try:
        # 1️⃣ PENDIENTE
        print(f"\n   🔍 Buscando capa de PENDIENTE para {provincia_sel}...")
        ruta_pendiente = buscar_archivo_peligro(RUTA_BASE_PENDIENTE, provincia_sel, "PENDIENTE")
        if not ruta_pendiente:
            ruta_pendiente = buscar_archivo_peligro(RUTA_BASE_PENDIENTE, departamento_sel, "PENDIENTE")
        if not ruta_pendiente:
            ruta_pendiente = buscar_archivo_peligro(RUTA_BASE_PENDIENTE, "peso", "PENDIENTE")
        
        if not ruta_pendiente:
            raise FileNotFoundError(f"No se encontró archivo de PENDIENTE")
        
        gdf_pendiente = gpd.read_file(ruta_pendiente).to_crs(epsg=3857)
        print(f"      ✅ Pendiente cargada: {len(gdf_pendiente)} registros")
        
        # 2️⃣ GEOMORFOLOGÍA
        print(f"\n   🔍 Buscando capa de GEOMORFOLOGÍA...")
        ruta_geomorfo = buscar_archivo_peligro(RUTA_BASE_GEOMORFOLOGIA, departamento_sel.lower(), "GEOMORFOLOGÍA")
        if not ruta_geomorfo:
            ruta_geomorfo = buscar_archivo_peligro(RUTA_BASE_GEOMORFOLOGIA, "peso", "GEOMORFOLOGÍA")
        
        if not ruta_geomorfo:
            raise FileNotFoundError(f"No se encontró archivo de GEOMORFOLOGÍA")
        
        gdf_geomorfo = gpd.read_file(ruta_geomorfo).to_crs(epsg=3857)
        print(f"      ✅ Geomorfología cargada: {len(gdf_geomorfo)} registros")
        
        # 3️⃣ PP MÁXIMA
        print(f"\n   🔍 Buscando capa de PP MÁXIMA...")
        ruta_ppmax = buscar_archivo_peligro(RUTA_BASE_PPMAX, "ppmax", "PP MÁXIMA")
        if not ruta_ppmax:
            ruta_ppmax = buscar_archivo_peligro(RUTA_BASE_PPMAX, "peso", "PP MÁXIMA")
        
        if not ruta_ppmax:
            raise FileNotFoundError(f"No se encontró archivo de PP MÁXIMA")
        
        gdf_ppmax = gpd.read_file(ruta_ppmax).to_crs(epsg=3857)
        print(f"      ✅ PP Máxima cargada: {len(gdf_ppmax)} registros")
        
        # 4️⃣ 🆕 DISTANCIA A RÍOS (ya generado)
        print(f"\n   🔍 Cargando capa de DISTANCIA A RÍOS...")
        gdf_rios = gpd.read_file(ruta_rios)
        
        # Ya debería estar en 3857, pero verificar
        if gdf_rios.crs.to_epsg() != 3857:
            gdf_rios = gdf_rios.to_crs(epsg=3857)
        
        print(f"      ✅ Distancia a Ríos cargada: {len(gdf_rios)} registros")
        print(f"      📋 Columnas: {list(gdf_rios.columns)}")
        
        # 5️⃣ 🆕 GEOLOGÍA
        print(f"\n   🔍 Cargando capa de GEOLOGÍA...")
        ruta_geologia = os.path.join(RUTA_BASE_GEOLOGIA, "geolo_cusco_con_pesos.shp")
        
        if not os.path.exists(ruta_geologia):
            raise FileNotFoundError(f"No se encontró archivo de GEOLOGÍA en: {ruta_geologia}")
        
        gdf_geologia = gpd.read_file(ruta_geologia)
        
        # Convertir a EPSG:3857 si es necesario
        if gdf_geologia.crs is None or gdf_geologia.crs.to_epsg() != 3857:
            if gdf_geologia.crs is None:
                gdf_geologia.set_crs(epsg=4326, inplace=True)
            gdf_geologia = gdf_geologia.to_crs(epsg=3857)
        
        print(f"      ✅ Geología cargada: {len(gdf_geologia)} registros")
        print(f"      📋 Columnas: {list(gdf_geologia.columns)}")
        
        # VERIFICAR COLUMNAS
        if 'PESO_PENDI' not in gdf_pendiente.columns:
            raise ValueError(f"La columna 'PESO_PENDI' no existe")
        if 'PESO_GEOMO' not in gdf_geomorfo.columns:
            raise ValueError(f"La columna 'PESO_GEOMO' no existe")
        if 'PESO_PPMAX' not in gdf_ppmax.columns:
            raise ValueError(f"La columna 'PESO_PPMAX' no existe")
        if 'PESO_RIO' not in gdf_rios.columns:
            raise ValueError(f"La columna 'PESO_RIO' no existe en el shapefile de ríos")
        if 'PESO_GEOL' not in gdf_geologia.columns:
            raise ValueError(f"La columna 'PESO_GEOL' no existe en el shapefile de geología")
        
        print(f"\n   ✅ Todas las 5 capas cargadas exitosamente")
        
    except Exception as e:
        print(f"\n❌ Error cargando capas de peligro: {e}")
        import traceback
        traceback.print_exc()
        return None

    # RECORTAR CAPAS DE PELIGRO AL DISTRITO
    print("\n✂️ Recortando capas de peligro al distrito...")
    try:
        gdf_pendiente_clip = gpd.clip(gdf_pendiente, gdf_distrito)
        gdf_geomorfo_clip = gpd.clip(gdf_geomorfo, gdf_distrito)
        gdf_ppmax_clip = gpd.clip(gdf_ppmax, gdf_distrito)
        gdf_rios_clip = gpd.clip(gdf_rios, gdf_distrito)
        gdf_geologia_clip = gpd.clip(gdf_geologia, gdf_distrito)
        
        print(f"   ✅ Capas recortadas exitosamente")
        print(f"      - Pendiente: {len(gdf_pendiente_clip)} registros")
        print(f"      - Geomorfología: {len(gdf_geomorfo_clip)} registros")
        print(f"      - PP Máxima: {len(gdf_ppmax_clip)} registros")
        print(f"      - Distancia a Ríos: {len(gdf_rios_clip)} registros")
        print(f"      - Geología: {len(gdf_geologia_clip)} registros")
        
    except Exception as e:
        print(f"❌ Error recortando capas: {e}")
        return None

    # 🆕 COMBINAR LAS CINCO CAPAS MEDIANTE INTERSECCIÓN
    print("\n🔄 Combinando capas de peligro (5 parámetros)...")
    try:
        # Intersección de las cinco capas
        print("   [1/5] Intersectando Pendiente ∩ Geomorfología...")
        gdf_intersect1 = gpd.overlay(gdf_pendiente_clip, gdf_geomorfo_clip, how='intersection')
        
        print("   [2/5] Intersectando con PP Máxima...")
        gdf_intersect2 = gpd.overlay(gdf_intersect1, gdf_ppmax_clip, how='intersection')
        
        print("   [3/5] Intersectando con Distancia a Ríos...")
        gdf_intersect3 = gpd.overlay(gdf_intersect2, gdf_rios_clip, how='intersection')
        
        print("   [4/5] Intersectando con Geología...")
        gdf_peligro = gpd.overlay(gdf_intersect3, gdf_geologia_clip, how='intersection')
        
        # 🆕 VERIFICAR Y LIMPIAR NOMBRES DE COLUMNAS
        print("\n   📋 Verificando columnas después de intersección...")
        print(f"      Columnas disponibles: {list(gdf_peligro.columns)}")
        
        # Buscar las columnas de peso (pueden tener sufijos _1, _2, etc.)
        col_pendi = None
        col_geomo = None
        col_ppmax = None
        col_rio = None
        col_geol = None
        
        for col in gdf_peligro.columns:
            if 'PESO_PENDI' in col:
                col_pendi = col
            elif 'PESO_GEOMO' in col:
                col_geomo = col
            elif 'PESO_PPMAX' in col:
                col_ppmax = col
            elif 'PESO_RIO' in col:
                col_rio = col
            elif 'PESO_GEOL' in col:
                col_geol = col
        
        print(f"\n   📊 Columnas identificadas:")
        print(f"      - Pendiente: {col_pendi}")
        print(f"      - Geomorfología: {col_geomo}")
        print(f"      - PP Máxima: {col_ppmax}")
        print(f"      - Distancia Ríos: {col_rio}")
        print(f"      - Geología: {col_geol}")
        
        # Verificar que todas las columnas existen
        if not all([col_pendi, col_geomo, col_ppmax, col_rio, col_geol]):
            raise ValueError(f"No se encontraron todas las columnas de peso necesarias")
        
        # 🆕 CALCULAR EL ÍNDICE DE PELIGRO CON 5 PARÁMETROS
        print("\n   [5/5] Calculando índice de peligro...")
        gdf_peligro['PELIGRO'] = (
            gdf_peligro[col_pendi] + 
            gdf_peligro[col_geomo] + 
            gdf_peligro[col_ppmax] +
            gdf_peligro[col_rio] +
            gdf_peligro[col_geol]
        ) / 5.0
        
        # 🆕 MOSTRAR ESTADÍSTICAS DETALLADAS DE CADA PARÁMETRO
        print(f"\n   📊 Estadísticas ANTES del promedio:")
        print(f"      - {col_pendi}: min={gdf_peligro[col_pendi].min():.2f}, max={gdf_peligro[col_pendi].max():.2f}, media={gdf_peligro[col_pendi].mean():.2f}")
        print(f"      - {col_geomo}: min={gdf_peligro[col_geomo].min():.2f}, max={gdf_peligro[col_geomo].max():.2f}, media={gdf_peligro[col_geomo].mean():.2f}")
        print(f"      - {col_ppmax}: min={gdf_peligro[col_ppmax].min():.2f}, max={gdf_peligro[col_ppmax].max():.2f}, media={gdf_peligro[col_ppmax].mean():.2f}")
        print(f"      - {col_rio}: min={gdf_peligro[col_rio].min():.2f}, max={gdf_peligro[col_rio].max():.2f}, media={gdf_peligro[col_rio].mean():.2f}")
        print(f"      - {col_geol}: min={gdf_peligro[col_geol].min():.2f}, max={gdf_peligro[col_geol].max():.2f}, media={gdf_peligro[col_geol].mean():.2f}")
        
        print(f"\n   📊 Estadísticas DESPUÉS del promedio (PELIGRO):")
        print(f"      - Peligro: min={gdf_peligro['PELIGRO'].min():.3f}, max={gdf_peligro['PELIGRO'].max():.3f}, media={gdf_peligro['PELIGRO'].mean():.3f}")
        
        # 🆕 MOSTRAR DISTRIBUCIÓN POR NIVEL DE PELIGRO
        print(f"\n   📊 Distribución por nivel de peligro:")
        nivel_baja = len(gdf_peligro[(gdf_peligro['PELIGRO'] >= 1.0) & (gdf_peligro['PELIGRO'] < 2.0)])
        nivel_media = len(gdf_peligro[(gdf_peligro['PELIGRO'] >= 2.0) & (gdf_peligro['PELIGRO'] < 3.0)])
        nivel_alta = len(gdf_peligro[(gdf_peligro['PELIGRO'] >= 3.0) & (gdf_peligro['PELIGRO'] < 4.0)])
        nivel_muy_alta = len(gdf_peligro[(gdf_peligro['PELIGRO'] >= 4.0) & (gdf_peligro['PELIGRO'] <= 5.0)])
        
        total = len(gdf_peligro)
        print(f"      - Baja (1.0-2.0):      {nivel_baja:5d} polígonos ({100*nivel_baja/total:5.1f}%)")
        print(f"      - Media (2.0-3.0):     {nivel_media:5d} polígonos ({100*nivel_media/total:5.1f}%)")
        print(f"      - Alta (3.0-4.0):      {nivel_alta:5d} polígonos ({100*nivel_alta/total:5.1f}%)")
        print(f"      - Muy Alta (4.0-5.0):  {nivel_muy_alta:5d} polígonos ({100*nivel_muy_alta/total:5.1f}%)")
        
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
    ax_titulo.text(0.5, 0.5, f"MAPA DE SUSCEPTIBILIDAD ANTE DESLIZAMIENTOS - DISTRITO DE {distrito_sel.upper()}",
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
                
                # Agregar etiquetas de nombres si existe la columna
                nombre_col = None
                for col in ['NOMB_CCPP', 'NOMBRE', 'NOMBCCPP', 'CCPP', 'NAME']:
                    if col in centros_en_mapa.columns:
                        nombre_col = col
                        break
                
                if nombre_col:
                    for idx, row in centros_en_mapa.iterrows():
                        x, y = row.geometry.x, row.geometry.y
                        nombre = str(row[nombre_col])
                        ax_main.annotate(nombre, 
                                       xy=(x, y), 
                                       xytext=(5, 5),
                                       textcoords='offset points',
                                       fontsize=6,
                                       color='#006400',  # Verde oscuro
                                       weight='bold',
                                       path_effects=[path_effects.withStroke(linewidth=2.5, foreground='white')],
                                       zorder=11)
                
                print(f"      ✅ {len(centros_en_mapa)} centros poblados agregados al mapa")
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
        Patch(facecolor=COLORES_PELIGRO[0], edgecolor='black', label='Baja (1.00 - 2.00)'),
        Patch(facecolor=COLORES_PELIGRO[1], edgecolor='black', label='Media (2.00 - 3.00)'),
        Patch(facecolor=COLORES_PELIGRO[2], edgecolor='black', label='Alta (3.00 - 4.00)'),
        Patch(facecolor=COLORES_PELIGRO[3], edgecolor='black', label='Muy Alta (4.00 - 5.00)')
    ])

    legend_elements.extend([
        Patch(facecolor='white', edgecolor='white', label='', linewidth=0),
        Patch(facecolor='white', edgecolor='white', label='PARÁMETROS:', linewidth=0),
        Patch(facecolor='white', edgecolor='white', label='• Pendiente', linewidth=0),
        Patch(facecolor='white', edgecolor='white', label='• Geomorfología', linewidth=0),
        Patch(facecolor='white', edgecolor='white', label='• PP Máxima', linewidth=0),
        Patch(facecolor='white', edgecolor='white', label='• Distancia a Ríos', linewidth=0),
        Patch(facecolor='white', edgecolor='white', label='• Geología', linewidth=0),
        Patch(facecolor='white', edgecolor='white', label='', linewidth=0),
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
            print(f"   📂 Ubicación: {ruta_guardado_final}")
            print(f"   📊 Tamaño: {file_size:.2f} MB")
            print(f"   🎯 Parámetros: 5 (Pendiente + Geomorfología + PP Máxima + Distancia a Ríos + Geología)")
            print(f"   🏘️ Centros poblados: Incluidos")
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
