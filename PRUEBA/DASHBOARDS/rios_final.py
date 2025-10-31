# Archivo: rios_final.py - VERSIÓN SIMPLIFICADA

import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
from matplotlib_scalebar.scalebar import ScaleBar
import os
import numpy as np
import matplotlib.patheffects as path_effects
from shapely.geometry import box
import pyproj
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Polygon, Rectangle, Patch
from matplotlib.lines import Line2D
import datetime
import rasterio
from rasterio.mask import mask as rio_mask
from whitebox import WhiteboxTools
from shapely.ops import unary_union
import tempfile
import shutil
import pandas as pd

# --- RUTA BASE ORIGINAL ---
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"

# PALETA DE COLORES PARA DISTANCIA A RIOS
COLORES_RIOS = ['#FF0000', '#FF7F00', '#FFFF00', '#00FF00', '#0080FF']
ETIQUETAS_RIOS = ['0-50m', '50-100m', '100-150m', '150-200m', '>200m']

# CONFIGURACIÓN DE BUFFERS
BUFFERS_CONFIG = [
    {"name": "0-50m", "inner": 0, "outer": 50, "color": "#FF0000"},
    {"name": "50-100m", "inner": 50, "outer": 100, "color": "#FF7F00"},
    {"name": "100-150m", "inner": 100, "outer": 150, "color": "#FFFF00"},
    {"name": "150-200m", "inner": 150, "outer": 200, "color": "#00FF00"},
    {"name": ">200m", "inner": 200, "outer": None, "color": "#0080FF"}
]

# FUNCIÓN PARA GENERAR RED DE RÍOS DESDE GEOTIFF
def generar_red_rios_desde_geotiff(ruta_dem, gdf_distrito, intensidad="media"):
    """Genera red hidrográfica desde un archivo DEM GeoTIFF"""
    print("   Generando red hidrográfica desde DEM...")
    
    try:
        if not os.path.exists(ruta_dem):
            print(f"   ERROR: El archivo no existe: {ruta_dem}")
            return None, None
        
        print(f"   Archivo DEM encontrado: {ruta_dem}")
        
        temp_dir = tempfile.mkdtemp()
        print(f"   Directorio temporal: {temp_dir}")
        
        try:
            wbt = WhiteboxTools()
            wbt.set_working_dir(temp_dir)
            wbt.set_verbose_mode(False)
            
            with rasterio.open(ruta_dem) as src:
                print(f"   CRS del DEM: {src.crs}")
                print(f"   Dimensiones: {src.width} x {src.height}")
                
                gdf_distrito_reproj = gdf_distrito.to_crs(src.crs)
                
                from shapely.geometry import mapping
                
                buffer_dist = 1000
                gdf_buffer = gdf_distrito_reproj.copy()
                gdf_buffer['geometry'] = gdf_buffer.geometry.buffer(buffer_dist)
                
                geoms = [mapping(geom) for geom in gdf_buffer.geometry]
                
                out_image, out_transform = rio_mask(src, geoms, crop=True, filled=False)
                elevation = out_image[0]
                
                dem_clipped = os.path.join(temp_dir, "dem_clipped.tif")
                
                out_meta = src.meta.copy()
                out_meta.update({
                    "driver": "GTiff",
                    "height": elevation.shape[0],
                    "width": elevation.shape[1],
                    "transform": out_transform
                })
                
                with rasterio.open(dem_clipped, "w", **out_meta) as dest:
                    dest.write(elevation, 1)
                
                print(f"   DEM recortado guardado")
            
            filled_dem = os.path.join(temp_dir, "filled.tif")
            flow_dir = os.path.join(temp_dir, "flow_dir.tif")
            flow_acc = os.path.join(temp_dir, "flow_acc.tif")
            streams_raster = os.path.join(temp_dir, "streams.tif")
            streams_vector = os.path.join(temp_dir, "streams.shp")
            
            print("   1/5 Rellenando depresiones...")
            wbt.fill_depressions(dem_clipped, filled_dem)
            
            print("   2/5 Calculando dirección de flujo...")
            wbt.d8_pointer(filled_dem, flow_dir)
            
            print("   3/5 Calculando acumulación de flujo...")
            wbt.d8_flow_accumulation(filled_dem, flow_acc, out_type="cells")
            
            UMBRALES = {
                "muy_alta": 50,
                "alta": 200,
                "media": 500,
                "baja": 1000,
                "muy_baja": 2000
            }
            
            threshold = UMBRALES.get(intensidad, 500)
            print(f"   Umbral de acumulación: {threshold} celdas (intensidad: {intensidad})")
            
            print("   4/5 Extrayendo red de ríos...")
            wbt.extract_streams(flow_acc, streams_raster, threshold)
            
            print("   5/5 Convirtiendo a vector...")
            wbt.raster_streams_to_vector(streams_raster, flow_dir, streams_vector)
            
            rivers = gpd.read_file(streams_vector)
            
            if rivers.crs is None:
                with rasterio.open(dem_clipped) as dem_src:
                    rivers = rivers.set_crs(dem_src.crs)
            
            rivers_3857 = rivers.to_crs(3857)
            
            gdf_distrito_3857 = gdf_distrito.to_crs(3857)
            rivers_clipped = gpd.clip(rivers_3857, gdf_distrito_3857)
            
            print(f"   Red de ríos generada: {len(rivers_clipped)} segmentos")
            
            rivers_clipped['length_km'] = rivers_clipped.geometry.length / 1000
            total_length = rivers_clipped['length_km'].sum()
            
            print(f"   Longitud total: {total_length:.2f} km")
            
            stats = {
                'segmentos': len(rivers_clipped),
                'longitud_total_km': total_length,
                'longitud_promedio_km': rivers_clipped['length_km'].mean() if len(rivers_clipped) > 0 else 0,
                'intensidad': intensidad,
                'umbral': threshold
            }
            
            return rivers_clipped, stats
            
        finally:
            try:
                shutil.rmtree(temp_dir)
                print("   Archivos temporales eliminados")
            except:
                pass
                
    except Exception as e:
        print(f"   ERROR generando red de ríos: {e}")
        import traceback
        traceback.print_exc()
        return None, None

# FUNCIÓN PARA GENERAR BUFFERS DE DISTANCIA
def generar_buffers_distancia(rivers_gdf, gdf_distrito):
    """Genera buffers de distancia a ríos"""
    print("   Generando buffers de distancia...")
    
    try:
        rivers_union = unary_union(rivers_gdf.geometry)
        
        buffer_list = []
        
        for config in BUFFERS_CONFIG:
            name = config["name"]
            inner = config["inner"]
            outer = config["outer"]
            
            if outer is None:
                outer_buffer = gdf_distrito.geometry.union_all()
                inner_buffer = rivers_union.buffer(inner)
                buffer_ring = outer_buffer.difference(inner_buffer)
            else:
                outer_buffer = rivers_union.buffer(outer)
                inner_buffer = rivers_union.buffer(inner)
                buffer_ring = outer_buffer.difference(inner_buffer)
                
                buffer_ring = buffer_ring.intersection(gdf_distrito.geometry.union_all())
            
            area_km2 = buffer_ring.area / 1_000_000
            
            gdf = gpd.GeoDataFrame(
                {
                    'clase': [name],
                    'distancia_min_m': [inner],
                    'distancia_max_m': [outer if outer else 999999],
                    'area_km2': [area_km2],
                    'color': [config["color"]]
                },
                geometry=[buffer_ring],
                crs=rivers_gdf.crs
            )
            
            buffer_list.append(gdf)
            print(f"      {name:12} - Área: {area_km2:.4f} km²")
        
        buffers_gdf = gpd.GeoDataFrame(pd.concat(buffer_list, ignore_index=True))
        
        return buffers_gdf
        
    except Exception as e:
        print(f"   ERROR generando buffers: {e}")
        import traceback
        traceback.print_exc()
        return None

# FUNCIONES AUXILIARES
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
        "MAPA": f"MAPA DE RED HIDROGRÁFICA: DISTRITO DE {dist.upper()}",
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
        print(f"   Error cargando {alias} desde {path}: {e}")
        return None

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
            gdf_context.plot(ax=ax, color="#FFEE58", edgecolor="black", linewidth=0.7, zorder=3)
    elif tipo_mapa == "provincia":
        if gdf_base_map is not None:
            gdf_base_map.plot(ax=ax, color="#f0eee8", edgecolor="black", linewidth=0.4, zorder=1)
        if gdf_context is not None:
            gdf_context.plot(ax=ax, color="#FFEE58", edgecolor="black", linewidth=0.7, zorder=3)
    elif tipo_mapa == "distrito":
        if gdf_provincias is not None:
            gdf_provincias[gdf_provincias[col_prov] != provincia_sel].plot(
                ax=ax, color='lightgray', edgecolor='darkgray', linewidth=0.4, zorder=2)
            gdf_prov_sel.plot(ax=ax, color="#FFEE58", edgecolor='black', linewidth=0.7, zorder=3)
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

# FUNCIÓN PRINCIPAL DE GENERACIÓN DE MAPA DE RÍOS
def generar_mapa_rios(nombre_usuario, departamento_sel, provincia_sel, distrito_sel, 
                      ruta_dem=None, intensidad="media"):
    print("\n" + "="*80)
    print("INICIANDO PROCESO DE GENERACIÓN DE MAPA DE RED HIDROGRÁFICA...")
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")
    print(f"   - Intensidad de red: {intensidad}")
    
    if ruta_dem is None:
        ruta_dem = f"{ruta_base}/DATA/PENDIENTES/DEM.tif"
    
    if not os.path.exists(ruta_dem):
        print(f"ERROR: El archivo DEM no existe: {ruta_dem}")
        return None
    
    print(f"   - DEM: {ruta_dem}")
    
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "MAPA DE RIOS")
        os.makedirs(carpeta_salida, exist_ok=True)
        print(f"   - Carpeta de salida verificada: {carpeta_salida}")
    except Exception as e:
        print(f"Error creando la estructura de carpetas para el usuario: {e}")
        return None
    
    print("\nCargando capas base...")
    gdf_departamentos = cargar_shapefile("departamento", "Departamentos")
    gdf_provincias = cargar_shapefile("provincia", "Provincias")
    gdf_distritos = cargar_shapefile("distrito", "Distritos del Perú")
    
    try:
        gdf_paises = gpd.read_file(f"{ruta_base}/DATA/MAPA DE UBICACION/PAISES DE SUDAMERICA/Sudamerica.shp").to_crs(3857)
        gdf_oceano = gpd.read_file(f"{ruta_base}/DATA/MAPA DE UBICACION/OCEANO/Oceano.shp").to_crs(3857)
    except Exception as e:
        print(f"Error cargando shapefiles de Países u Océano: {e}")
        gdf_paises = None
        gdf_oceano = None
    
    if gdf_departamentos is None or gdf_provincias is None or gdf_distritos is None:
        print("Faltan capas base (departamento, provincia o distrito). Abortando.")
        return None
    
    col_dpto = next((c for c in ['NOMBDEP', 'DEPARTAMEN'] if c in gdf_departamentos.columns), None)
    col_prov = next((c for c in ['NOMBPROV', 'PROVINCIA'] if c in gdf_provincias.columns), None)
    col_distr = next((c for c in ['NOMBDIST', 'DISTRITO'] if c in gdf_distritos.columns), None)
    
    if not all([col_dpto, col_prov, col_distr]):
        print("No se pudieron identificar las columnas de nombres en los shapefiles")
        return None
    
    print("\nFiltrando datos del área seleccionada...")
    gdf_dpto_sel = gdf_departamentos[gdf_departamentos[col_dpto] == departamento_sel]
    gdf_prov_sel = gdf_provincias[gdf_provincias[col_prov] == provincia_sel]
    gdf_distrito = gdf_distritos[(gdf_distritos[col_distr] == distrito_sel) & 
                                  (gdf_distritos[col_prov] == provincia_sel)]
    gdf_distritos_en_provincia = gdf_distritos[gdf_distritos[col_prov] == provincia_sel]
    
    if gdf_distrito.empty:
        print(f"Error: No se pudo encontrar la geometría para el distrito '{distrito_sel}'.")
        return None
    
    print(f"   Distrito encontrado con geometría válida")
    
    print("\nGenerando red hidrográfica desde DEM...")
    resultado = generar_red_rios_desde_geotiff(ruta_dem, gdf_distrito, intensidad)
    
    if resultado is None:
        print("ERROR: generar_red_rios_desde_geotiff retornó None")
        return None
    
    rivers_gdf, stats = resultado
    
    if rivers_gdf is None or stats is None:
        print("ERROR: No se pudo generar la red de ríos correctamente")
        return None
    
    if rivers_gdf.empty:
        print("ADVERTENCIA: No se detectaron ríos en el área")
    
    print("\nEstadísticas de red hidrográfica:")
    print(f"   Segmentos de ríos:     {stats['segmentos']:>8}")
    print(f"   Longitud total:        {stats['longitud_total_km']:>8.2f} km")
    print(f"   Longitud promedio:     {stats['longitud_promedio_km']:>8.2f} km")
    
    buffers_gdf = None
    if not rivers_gdf.empty:
        print("\nGenerando buffers de distancia a ríos...")
        buffers_gdf = generar_buffers_distancia(rivers_gdf, gdf_distrito.to_crs(3857))
        
        if buffers_gdf is not None:
            print("   Buffers generados correctamente")
    
    print("\nGenerando layout del mapa...")
    fig = plt.figure(figsize=(14, 9.9))
    
    # LAYOUT CON MAPAS DE UBICACIÓN
    grid = plt.GridSpec(1, 2, width_ratios=[3.0, 1], wspace=0.05)
    gs_izquierda = grid[0, 0].subgridspec(3, 1, height_ratios=[0.08, 3.5, 0.42], hspace=0.08)
    
    # Título
    ax_titulo = fig.add_subplot(gs_izquierda[0])
    ax_titulo.text(0.5, 0.5, f"MAPA DE RED HIDROGRÁFICA - DISTRITO DE {distrito_sel.upper()}",
                   ha='center', va='center', fontsize=12, fontweight="normal",
                   bbox=dict(boxstyle='square,pad=0.5', facecolor='white', 
                            edgecolor='black', linewidth=1.5, alpha=0.95))
    ax_titulo.axis('off')
    
    ax_main = fig.add_subplot(gs_izquierda[1])
    
    # BBOX con aspect ratio consistente
    minx, miny, maxx, maxy = gdf_distrito.to_crs(3857).total_bounds
    buffer_factor = 0.15
    buffer_x = (maxx - minx) * buffer_factor
    buffer_y = (maxy - miny) * buffer_factor
    bbox_temp = (minx - buffer_x, miny - buffer_y, maxx + buffer_x, maxy + buffer_y)
    
    aspect_ratio_objetivo = 1.21
    cx = (bbox_temp[0] + bbox_temp[2]) / 2
    cy = (bbox_temp[1] + bbox_temp[3]) / 2
    ancho_actual = bbox_temp[2] - bbox_temp[0]
    alto_actual = bbox_temp[3] - bbox_temp[1]
    
    if (ancho_actual / alto_actual) > aspect_ratio_objetivo:
        nuevo_alto = ancho_actual / aspect_ratio_objetivo
        bbox_main = (bbox_temp[0], cy - nuevo_alto/2, bbox_temp[2], cy + nuevo_alto/2)
    else:
        nuevo_ancho = alto_actual * aspect_ratio_objetivo
        bbox_main = (cx - nuevo_ancho/2, bbox_temp[1], cx + nuevo_ancho/2, bbox_temp[3])
    
    ax_main.set_xlim(bbox_main[0], bbox_main[2])
    ax_main.set_ylim(bbox_main[1], bbox_main[3])
    ax_main.set_aspect('equal', adjustable='box')
    
    print("   Descargando imagen satelital...")
    try:
        ctx.add_basemap(ax_main, source=ctx.providers.Esri.WorldImagery, 
                       attribution=False, zoom='auto')
    except Exception as e:
        print(f"   No se pudo cargar el mapa base: {e}")
        ax_main.set_facecolor("#e8e8e8")
    
    print("   Dibujando capas...")
    
    # Dibujar buffers si existen
    if buffers_gdf is not None and not buffers_gdf.empty:
        for idx, row in buffers_gdf.iterrows():
            gpd.GeoSeries([row.geometry]).plot(
                ax=ax_main,
                color=row['color'],
                edgecolor='white',
                linewidth=0.3,
                alpha=0.6,
                zorder=4
            )
    
    # Dibujar ríos
    if not rivers_gdf.empty:
        rivers_gdf.plot(ax=ax_main, color='#00BFFF', linewidth=2.0, 
                       alpha=0.9, zorder=10,
                       path_effects=[path_effects.withStroke(linewidth=3, foreground='white')])
    
    # Límite distrital
    gdf_distrito.to_crs(3857).plot(ax=ax_main, facecolor="none", edgecolor="red", 
                                    linewidth=2, linestyle='--', alpha=0.9, zorder=15)
    
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
    
    legend_elements = [
        Patch(facecolor='white', edgecolor='white', label='DISTANCIA A RÍOS:', linewidth=0)
    ]
    
    # Agregar colores de buffers
    if buffers_gdf is not None:
        for idx, etiqueta in enumerate(ETIQUETAS_RIOS):
            legend_elements.append(
                Patch(facecolor=COLORES_RIOS[idx], edgecolor='black', label=etiqueta)
            )
    
    legend_elements.extend([
        Patch(facecolor='white', edgecolor='white', label='', linewidth=0),
        Line2D([0], [0], color='#00BFFF', lw=2.5, label='Red Hidrográfica'),
        Line2D([0], [0], color='red', lw=2, linestyle='--', label='Límite Distrital'),
        Line2D([0], [0], color='black', ls='-', lw=1, label='Grillado UTM')
    ])
    
    leg = ax_leyenda.legend(
        handles=legend_elements,
        loc='center',
        ncol=1,
        frameon=True,
        fontsize=8,
        title="LEYENDA",
        title_fontproperties={'size': 10, 'weight': 'bold'},
        handletextpad=0.5,
        columnspacing=1.0,
        borderpad=0.7,
        handlelength=1.5
    )
    
    leg.get_title().set_ha('center')
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(1.2)
    
    print("   Generando mapas de ubicación...")
    
    # MAPAS DE UBICACIÓN LATERAL
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
    
    # Marco exterior
    rect_frame = fig.add_axes([0, 0, 1, 1], frameon=False)
    rect_frame.set_xticks([])
    rect_frame.set_yticks([])
    rect_frame.patch.set_visible(False)
    
    for spine in rect_frame.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(2)
        spine.set_color('black')
    
    print("\nGuardando mapa final en carpeta de usuario...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = f"MAPA_RIOS_{distrito_sel.replace(' ', '_')}_{timestamp}.png"
    ruta_guardado_final = os.path.join(carpeta_salida, nombre_base)
    
    try:
        plt.savefig(ruta_guardado_final, dpi=300, bbox_inches='tight', pad_inches=0.01)
        plt.close(fig)
        
        if os.path.exists(ruta_guardado_final):
            file_size = os.path.getsize(ruta_guardado_final) / (1024 * 1024)
            print(f"✅ Mapa de red hidrográfica guardado exitosamente")
            print(f"   📍 Ubicación: {ruta_guardado_final}")
            print(f"   💾 Tamaño: {file_size:.2f} MB")
            
            # Mostrar distribución de buffers si existen
            if buffers_gdf is not None and not buffers_gdf.empty:
                print(f"\n{'='*65}")
                print("DISTRIBUCIÓN DE ÁREAS POR DISTANCIA A RÍOS")
                print(f"{'='*65}")
                total_area = buffers_gdf['area_km2'].sum()
                for idx, row in buffers_gdf.iterrows():
                    porcentaje = (row['area_km2'] / total_area) * 100 if total_area > 0 else 0
                    print(f"   {row['clase']:<15}: {row['area_km2']:>8.4f} km² ({porcentaje:>5.1f}%)")
                print(f"{'='*65}")
                print(f"   {'TOTAL':<15}: {total_area:>8.4f} km²")
                print(f"{'='*65}\n")
            
            # Guardar shapefile de ríos
            if not rivers_gdf.empty:
                rivers_output = os.path.join(carpeta_salida, f"red_rios_{distrito_sel.replace(' ', '_')}.shp")
                try:
                    rivers_gdf.to_file(rivers_output)
                    print(f"   📄 Shapefile de ríos guardado: {rivers_output}")
                except Exception as e:
                    print(f"   ⚠️  No se pudo guardar shapefile de ríos: {e}")
            
            # Guardar shapefile de buffers
            if buffers_gdf is not None and not buffers_gdf.empty:
                buffers_output = os.path.join(carpeta_salida, f"buffers_rios_{distrito_sel.replace(' ', '_')}.shp")
                try:
                    buffers_gdf.to_file(buffers_output)
                    print(f"   📄 Shapefile de buffers guardado: {buffers_output}")
                except Exception as e:
                    print(f"   ⚠️  No se pudo guardar shapefile de buffers: {e}")
            
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
    