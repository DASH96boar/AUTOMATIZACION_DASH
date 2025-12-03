# -*- coding: utf-8 -*-
"""pendientes_final.py - VERSIÓN CORREGIDA COMPLETA Y ROBUSTA"""

import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx
from matplotlib_scalebar.scalebar import ScaleBar
import os
import numpy as np
import matplotlib.patheffects as path_effects
from shapely.geometry import box, mapping
import pyproj
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Polygon, Rectangle, Patch, PathPatch
from matplotlib.path import Path
from matplotlib.lines import Line2D
import datetime
import rasterio
from rasterio.mask import mask as rio_mask
from matplotlib.colors import BoundaryNorm, ListedColormap
import shutil
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
import unicodedata
import tempfile
import traceback

# --- RUTA BASE ---
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"
AMARILLO_CLARO = "#FFEE58"

# PALETA DE COLORES PARA PENDIENTES
COLORES_PENDIENTE = ['#7FBF3F', '#BFDF3F', '#FFFF00', '#FF9F00', '#FF0000']
ETIQUETAS_PENDIENTE = ['< 5°', '5° - 15°', '15° - 25°', '25° - 45°', '> 45°']

# ════════════════════════════════════════════════════════════════════════
# FUNCIÓN PARA CARGAR Y RECORTAR RASTER SOLO AL DISTRITO
# ════════════════════════════════════════════════════════════════════════
def cargar_y_recortar_raster(ruta_pendientes, gdf_distrito):
    """Carga el raster y lo recorta EXACTAMENTE a la geometría del distrito (no rectangular)"""
    
    # Función auxiliar para manejar la reproyección y recorte temporal
    def _reproject_and_mask(src, gdf_target, dst_crs):
        try:
            # Calcular transformación para la reproyección
            transform, width, height = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
            dst_width = int(width)
            dst_height = int(height)
            dst_transform = transform

            tmp_reproj = None
            with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_file:
                tmp_reproj = tmp_file.name

            dst_kwargs = src.meta.copy()
            dst_kwargs.update({
                'crs': dst_crs,
                'transform': dst_transform,
                'width': dst_width,
                'height': dst_height,
                'nodata': src.nodata # Mantener el nodata original
            })

            with rasterio.open(tmp_reproj, 'w', **dst_kwargs) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=dst_transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.bilinear
                    )
            
            # Recortar con geometría en el CRS de destino
            with rasterio.open(tmp_reproj) as src2:
                geoms = [mapping(geom) for geom in gdf_target.geometry]
                
                original_nodata = src2.nodata if src2.nodata is not None else 0
                out_image, out_transform = rio_mask(src2, geoms, crop=True, filled=True, nodata=original_nodata)
                
                raster_data = out_image[0].astype(np.float32)
                
                # Reemplazar nodata y 0 por NaN
                if original_nodata is not None:
                    raster_data = np.where(raster_data == original_nodata, np.nan, raster_data)
                raster_data = np.where(raster_data == 0, np.nan, raster_data)
                
                bounds = gdf_target.total_bounds
                
                print(f"   Reproyección a {dst_crs} y recorte exitosos (temporal: {tmp_reproj})")
                return raster_data, out_transform, dst_crs, bounds
        except Exception as e:
            print(f"   Falló la reproyección/recorte en {dst_crs}: {e}")
            return None, None, None, None
        finally:
            if tmp_reproj is not None and os.path.exists(tmp_reproj):
                try:
                    os.remove(tmp_reproj)
                except Exception:
                    pass


    try:
        with rasterio.open(ruta_pendientes) as src:
            print(f"   CRS del raster: {src.crs}")
            print(f"   Dtype del raster: {src.dtypes[0]}")
            
            # 1. Intento inicial: Recortar en el CRS nativo del raster
            gdf_reproj = gdf_distrito.to_crs(src.crs)

            raster_bounds = src.bounds
            gb = gdf_reproj.total_bounds
            from shapely.geometry import box as shapely_box
            raster_poly = shapely_box(*raster_bounds)
            distrito_poly = shapely_box(gb[0], gb[1], gb[2], gb[3])
            
            if not raster_poly.intersects(distrito_poly):
                print("   ⚠️ ADVERTENCIA: La geometría del distrito reproyectada NO se solapa con el raster.")
                
                # Intento 1b: Probar buffers progresivos en CRS del raster
                for buf_m in (1000, 5000):
                    try:
                        print(f"   Intentando buffer de {buf_m} metros sobre el distrito en CRS del raster...")
                        gdf_buf = gdf_reproj.copy()
                        gdf_buf['geometry'] = gdf_buf.geometry.buffer(buf_m)
                        gb_buf = gdf_buf.total_bounds
                        distrito_poly_buf = shapely_box(gb_buf[0], gb_buf[1], gb_buf[2], gb_buf[3])
                        if raster_poly.intersects(distrito_poly_buf):
                            print(f"   ✅ Buffer de {buf_m}m permite solapamiento. Recortando usando buffer.")
                            geoms = [mapping(geom) for geom in gdf_buf.geometry]
                            
                            original_nodata = src.nodata if src.nodata is not None else 0
                            out_image, out_transform = rio_mask(src, geoms, crop=True, filled=True, nodata=original_nodata)
                            
                            raster_data = out_image[0].astype(np.float32)
                            if original_nodata is not None:
                                raster_data = np.where(raster_data == original_nodata, np.nan, raster_data)
                            raster_data = np.where(raster_data == 0, np.nan, raster_data)
                            
                            bounds = gdf_buf.total_bounds # Usar bounds del buffer para la extensión de visualización
                            print(f"   Recorte con buffer {buf_m}m exitoso.")
                            return raster_data, out_transform, src.crs, bounds
                    except Exception as e:
                        print(f"   Error al intentar buffer {buf_m}m: {e}")
                        continue
                
                # Intento 2: Reproyectar a EPSG:4326 (lat/lon) y recortar
                print("   Intentando reproyectar a EPSG:4326 y recortar...")
                gdf_4326 = gdf_distrito.to_crs(4326)
                raster_data, out_transform, src_crs_out, bounds = _reproject_and_mask(src, gdf_4326, 'EPSG:4326')
                if raster_data is not None:
                    return raster_data, out_transform, src_crs_out, bounds
                
                # Intento 3: Reproyectar a EPSG:3857 (Web Mercator) y recortar
                print("   Intentando reproyectar a EPSG:3857 y recortar...")
                gdf_3857 = gdf_distrito.to_crs(3857)
                raster_data, out_transform, src_crs_out, bounds = _reproject_and_mask(src, gdf_3857, 'EPSG:3857')
                if raster_data is not None:
                    return raster_data, out_transform, src_crs_out, bounds
                
                print("   ❌ Fallaron todos los intentos de recorte y reproyección.")
                print("   Verifica que el raster cubra la zona seleccionada.")
                return None, None, None, None

            # 2. Recorte en el CRS nativo del raster (Ruta de éxito normal)
            geoms = [mapping(geom) for geom in gdf_reproj.geometry]
            
            original_nodata = src.nodata if src.nodata is not None else 0
            out_image, out_transform = rio_mask(src, geoms, crop=True, filled=True, nodata=original_nodata)
            
            raster_data = out_image[0].astype(np.float32)
            
            # Reemplazar valores nodata con NaN
            if original_nodata is not None:
                raster_data = np.where(raster_data == original_nodata, np.nan, raster_data)
            
            # También convertir valores 0 a NaN si no son pendientes válidas (asumiendo que 0 significa nodata o plano)
            raster_data = np.where(raster_data == 0, np.nan, raster_data)
            
            bounds = gdf_reproj.total_bounds
            
            print(f"   Raster recortado: {raster_data.shape}")
            print(f"   Valores válidos: {np.count_nonzero(~np.isnan(raster_data))}")
            print(f"   Valores NaN (fuera del distrito): {np.count_nonzero(np.isnan(raster_data))}")
            print(f"   Rango de valores: {np.nanmin(raster_data):.2f} - {np.nanmax(raster_data):.2f}")
            
            return raster_data, out_transform, src.crs, bounds
            
    except Exception as e:
        print(f"   ERROR CRÍTICO en cargar_y_recortar_raster: {e}")
        traceback.print_exc()
        return None, None, None, None


def encontrar_raster_pendientes_por_departamento(departamento_sel):
    """Busca un raster de pendientes específico para el departamento y devuelve la ruta.
    Si no encuentra uno, devuelve el raster nacional por defecto.
    La búsqueda es tolerante a mayúsculas/minúsculas y a variantes de nombre.
    """
    carpeta = os.path.join(ruta_base, "DATA", "PENDIENTES")

    # Normalizar nombre (sin acentos, minúsculas)
    def _norm(s):
        s2 = unicodedata.normalize('NFKD', s)
        s2 = ''.join(ch for ch in s2 if not unicodedata.combining(ch))
        return s2.lower().replace(' ', '_')

    # Nombre buscado: ej. "cusco_pendientes.tif"
    buscado = f"{_norm(departamento_sel)}_pendientes.tif"
    
    if os.path.isdir(carpeta):
        archivos = sorted(os.listdir(carpeta))

        # 1) Coincidencia exacta normalizada (Ej: cusco_pendientes.tif)
        for f in archivos:
            if f.lower().endswith(('.tif', '.tiff')) and _norm(f) == buscado:
                ruta = os.path.join(carpeta, f)
                print(f"   Usando raster por departamento (match exacto normalizado): {ruta}")
                return ruta

        # 2) Coincidencia aproximada: contiene el nombre del departamento y 'pendient'
        for f in archivos:
            if f.lower().endswith(('.tif', '.tiff')):
                n = _norm(f)
                if _norm(departamento_sel) in n and 'pendient' in n:
                    ruta = os.path.join(carpeta, f)
                    print(f"   Usando raster por departamento (match aproximado): {ruta}")
                    return ruta

        # 3) Buscar ficheros que contengan el nombre del departamento aunque no tengan 'pendient'
        for f in archivos:
            if f.lower().endswith(('.tif', '.tiff')) and _norm(departamento_sel) in _norm(f):
                ruta = os.path.join(carpeta, f)
                print(f"   Usando raster por departamento (match por nombre): {ruta}")
                return ruta

        # 4) fallback: si existe 'pendientes.tif' usarlo (Raster nacional)
        fallback = os.path.join(carpeta, 'pendientes.tif')
        if os.path.exists(fallback):
            print(f"   Usando raster nacional fallback: {fallback}")
            return fallback

        # 5) si hay cualquier otro .tif, devolver el primero disponible (orden alfabético)
        tifs = [f for f in archivos if f.lower().endswith(('.tif', '.tiff'))]
        if tifs:
            ruta = os.path.join(carpeta, tifs[0])
            print(f"   Usando primer .tif disponible en carpeta: {ruta}")
            return ruta

    print(f"   No se encontró ningún raster de pendientes en la carpeta: {carpeta}")
    return os.path.join(carpeta, 'pendientes.tif') # Devuelve la ruta esperada aunque no exista

# ════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ════════════════════════════════════════════════════════════════════════
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
        "MAPA": f"MAPA DE PENDIENTES: DISTRITO DE {dist.upper()}",
        "DPTO": dpto.upper(),
        "PROVINCIA": prov.upper(),
        "DISTRITO": dist.upper(),
        "MAPA_N": "002-2025",
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
        if gdf.crs is None:
            # Asume 4326 si no tiene CRS, luego reproyecta
            gdf.set_crs(epsg=4326, inplace=True)
        elif gdf.crs.to_epsg() != 4326:
             gdf = gdf.to_crs(epsg=4326) # Asegura que esté en 4326 para estandarizar
            
        return gdf.to_crs(epsg=3857) # Reproyecta a 3857 para visualización con contextily
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
        # Ajustado para UTM (7 dígitos para N)
        y_str = f"{int(y):07d}"
        if len(y_str) < 7: # Manejo de casos si el número es pequeño
             y_str = '0' * (7 - len(y_str)) + y_str
             
        return y_str[0] + " " + y_str[1:4] + " " + y_str[4:] + " N"
    
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
    
    # Asegurar que el linspace tenga al menos 2 puntos (ndiv>1)
    if ndiv < 2: ndiv = 2
    
    for lon in np.linspace(lon_start, lon_end, ndiv):
        xs, ys = transformer.transform(np.full(2, lon), [lat_start, lat_end])
        ax.plot(xs, ys, color="gray", linestyle="--", linewidth=0.3, alpha=0.5, zorder=0)
    
    for lat in np.linspace(lat_start, lat_end, ndiv):
        xs, ys = transformer.transform([lon_start, lon_end], np.full(2, lat))
        ax.plot(xs, ys, color="gray", linestyle="--", linewidth=0.3, alpha=0.5, zorder=0)
    
    def fmt_lon(x, pos):
        # Usar un punto intermedio en Y para la transformación
        lon, _ = transformer.transform(x, (y0 + y1) / 2) 
        return f"{abs(lon):.{decimales}f}°{'W' if lon < 0 else 'E'}"
    
    def fmt_lat(y, pos):
        # Usar un punto intermedio en X para la transformación
        _, lat = transformer.transform((x0 + x1) / 2, y) 
        return f"{abs(lat):.{decimales}f}°{'S' if lat < 0 else 'N'}"
    
    # Nota: Los ejes UTM (proyectados) no se usan para los labels de grados
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
    
    # Verificación inicial de enfoque y base
    is_focus_valid = gdf_focus is not None and not gdf_focus.empty and all(np.isfinite(gdf_focus.total_bounds))
    
    # CÁLCULO DE BBOX
    if tipo_mapa == "pais":
        # Asume que gdf_departamentos siempre es válido si se llegó a este punto
        bbox_geom = gdf_departamentos.total_bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.25, (bbox_geom[3] - bbox_geom[1]) * 0.25
        
    elif tipo_mapa == "provincia":
        # Si el Dpto. seleccionado no es válido, usa la Provincia o el país como fallback
        if gdf_dpto_sel is not None and not gdf_dpto_sel.empty:
            bbox_geom = gdf_dpto_sel.total_bounds
        else:
            print(f"   ⚠️ Fallback BBOX: Dpto no encontrado para mapa '{titulo}'. Usando Provincia.")
            # Verificar si la Provincia está disponible como fallback
            bbox_geom = gdf_prov_sel.total_bounds if gdf_prov_sel is not None and not gdf_prov_sel.empty else gdf_departamentos.total_bounds
            
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.12, (bbox_geom[3] - bbox_geom[1]) * 0.12
        
    elif tipo_mapa == "distrito":
        # Lógica de BBOX más compleja para el mapa de distrito (incluir vecinos)
        if gdf_prov_sel is None or gdf_prov_sel.empty:
            print("   ❌ Error: Provincia seleccionada no válida para mapa de distrito.")
            # Fallback a departamento si existe o a país
            bbox_geom = gdf_dpto_sel.total_bounds if gdf_dpto_sel is not None and not gdf_dpto_sel.empty else gdf_departamentos.total_bounds
        else:
            # 1. Caso Dpto Válido: Se usa el Dpto. para recortar las provincias vecinas
            if gdf_dpto_sel is not None and not gdf_dpto_sel.empty and gdf_provincias is not None:
                provincia_seleccionada_geom = gdf_prov_sel.geometry.unary_union
                # Clip de provincias al bbox del departamento para acelerar
                gdf_provincias_clip = gdf_provincias.clip(gdf_dpto_sel.total_bounds)
                
                geoms_vecinas = [prov.geometry for _, prov in gdf_provincias_clip.iterrows() 
                                if prov[col_prov].upper() != provincia_sel.upper() and prov.geometry.touches(provincia_seleccionada_geom)]
                
                area_de_interes = gpd.GeoSeries([provincia_seleccionada_geom] + geoms_vecinas, crs=gdf_provincias.crs).unary_union
                bbox_geom = area_de_interes.bounds
                
            # 2. Caso Dpto NO Válido o no se pudo recortar (se usa solo la Provincia)
            else:
                print("   ⚠️ Fallback BBOX: Dpto no encontrado para mapa 'distrito'. Calculando BBOX extendido sin clip por Dpto.")
                bbox_geom = gdf_prov_sel.total_bounds
                 
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.15, (bbox_geom[3] - bbox_geom[1]) * 0.15
        
    else:
        # Fallback genérico (debería ser el país)
        bbox_geom = gdf_departamentos.total_bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.25, (bbox_geom[3] - bbox_geom[1]) * 0.25
    
    # Construir el BBOX final (cuadrado)
    x0, y0, x1, y1 = bbox_geom[0] - dx, bbox_geom[1] - dy, bbox_geom[2] + dx, bbox_geom[3] + dy
    S = max(x1 - x0, y1 - y0) 
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bbox = (cx - S / 2, cy - S / 2, cx + S / 2, cy + S / 2)
    
    # DIBUJO DEL MAPA
    if gdf_oceano is not None:
        gdf_oceano.clip(box(*bbox, ccw=True)).plot(ax=ax, color="#A4D4FF", edgecolor="none", zorder=2)
    
    if tipo_mapa == "pais":
        if gdf_base_map is not None:
            gdf_base_map.plot(ax=ax, color="#f0eee8", edgecolor="black", linewidth=0.4, zorder=1)
        if gdf_context is not None and not gdf_context.empty:
            # Dpto de interés
            gdf_context.plot(ax=ax, color=AMARILLO_CLARO, edgecolor="black", linewidth=0.7, zorder=3)
    elif tipo_mapa == "provincia":
        if gdf_base_map is not None and not gdf_base_map.empty:
            # Departamentos
            gdf_base_map.plot(ax=ax, color="#f0eee8", edgecolor="black", linewidth=0.4, zorder=1)
        if gdf_context is not None and not gdf_context.empty:
            # Dpto de interés
            gdf_context.plot(ax=ax, color=AMARILLO_CLARO, edgecolor="black", linewidth=0.7, zorder=3)
    elif tipo_mapa == "distrito":
        # Se requiere gdf_provincias y gdf_prov_sel para el contexto
        if gdf_provincias is not None and gdf_prov_sel is not None and not gdf_prov_sel.empty:
            # Provincias vecinas
            gdf_provincias[gdf_provincias[col_prov].str.upper() != provincia_sel.upper()].plot(
                ax=ax, color='lightgray', edgecolor='darkgray', linewidth=0.4, zorder=2)
            # Provincia de interés
            gdf_prov_sel.plot(ax=ax, color=AMARILLO_CLARO, edgecolor='black', linewidth=0.7, zorder=3)
        if gdf_context is not None and not gdf_context.empty:
            # Distritos en la provincia de interés (para contexto)
            gdf_context.plot(ax=ax, facecolor='none', edgecolor="gray", linewidth=0.4, zorder=4)
    
    # Elemento de enfoque (distrito/provincia/departamento)
    if is_focus_valid:
        gdf_focus.plot(ax=ax, facecolor="red", edgecolor="red", linewidth=0.2, hatch='o', zorder=5)
    
    # Grillado y Etiquetas
    if all(np.isfinite(bbox)):
        grillado_grados_mejorado(ax, bbox, ndiv=5, decimales=1)
    
    ax.text(0.03, 0.05, titulo, transform=ax.transAxes, color="white", fontsize=8, 
            ha="left", va="bottom", zorder=8, 
            bbox=dict(facecolor="#4A90E2", edgecolor="black", boxstyle="round,pad=0.3", alpha=0.9))
    
    if is_focus_valid and tipo_mapa == "distrito":
        # Etiqueta del distrito solo en el mapa de distrito
        ax.text(gdf_focus.geometry.centroid.iloc[0].x, gdf_focus.geometry.centroid.iloc[0].y, 
                etiqueta.upper(), color="white", fontsize=8, ha="center", va="center", zorder=9, 
                path_effects=[path_effects.withStroke(linewidth=3, foreground="black")])
    
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])
    ax.set_facecolor("#f0f8ff")
    ax.set_aspect('equal', adjustable='box')
    ax.axis('on')

# ════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL DE GENERACIÓN DE MAPA DE PENDIENTES
# ════════════════════════════════════════════════════════════════════════
def generar_mapa_pendientes(nombre_usuario, departamento_sel, provincia_sel, distrito_sel):
    print("\n" + "="*80)
    print("🗺️ INICIANDO PROCESO DE GENERACIÓN DE MAPA DE PENDIENTES...")
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")

    # 1. BUSCAR Y VERIFICAR RASTER DE PENDIENTES (Lógica por departamento incluida aquí)
    ruta_pendientes = encontrar_raster_pendientes_por_departamento(departamento_sel)
    
    if not os.path.exists(ruta_pendientes):
        print(f"❌ ERROR: Archivo de pendientes no encontrado: {ruta_pendientes}")
        print("   Asegúrate de que exista un archivo como 'cusco_pendientes.tif' o 'pendientes.tif' en la carpeta PENDIENTES.")
        return None
    
    # 2. CREAR CARPETA DE SALIDA
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "MAPA DE PENDIENTES")
        os.makedirs(carpeta_salida, exist_ok=True)
        print(f"   - Carpeta de salida verificada: {carpeta_salida}")
    except Exception as e:
        print(f"❌ Error creando la estructura de carpetas para el usuario: {e}")
        return None

    # 3. CARGAR CAPAS BASE
    print("\n📦 Cargando capas base...")
    gdf_departamentos = cargar_shapefile("departamento", "Departamentos")
    gdf_provincias = cargar_shapefile("provincia", "Provincias")
    gdf_distritos = cargar_shapefile("distrito", "Distritos del Perú")

    try:
        # Los paths deben ser corregidos para apuntar a la DATA/MAPA_DE_UBICACION
        gdf_paises = gpd.read_file(os.path.join(ruta_base, "DATA/MAPA_DE_UBICACION/PAISES_DE_SUDAMERICA/Sudamérica.shp")).to_crs(3857)
        gdf_oceano = gpd.read_file(os.path.join(ruta_base, "DATA/MAPA_DE_UBICACION/OCEANO/Océano.shp")).to_crs(3857)
    except Exception as e:
        print(f"❌ Error cargando shapefiles de Países u Océano: {e}")
        gdf_paises = None
        gdf_oceano = None

    if gdf_departamentos is None or gdf_provincias is None or gdf_distritos is None:
        print("❌ Faltan capas base (departamento, provincia o distrito). Abortando.")
        return None

    # Asumiendo que el campo de nombre de provincia en distritos puede ser diferente al de provincias
    col_dpto = next((c for c in ['NOMBDEP', 'DEPARTAMEN'] if c in gdf_departamentos.columns), None)
    col_prov_provincia = next((c for c in ['NOMBPROV', 'PROVINCIA', 'PROVINCIAS'] if c in gdf_provincias.columns), None)
    col_prov_distrito = next((c for c in ['NOMBPROV', 'PROVINCIA', 'PROVINCIAS'] if c in gdf_distritos.columns), None)
    col_distr = next((c for c in ['NOMBDIST', 'DISTRITO'] if c in gdf_distritos.columns), None)

    if not all([col_dpto, col_prov_provincia, col_prov_distrito, col_distr]):
        print("❌ No se pudieron identificar las columnas de nombres en los shapefiles")
        return None

    # 4. FILTRADO GEOGRÁFICO
    print("\n🔍 Filtrando datos del área seleccionada (con filtro insensible a mayúsculas/minúsculas)...")
    
    # *** CORRECCIÓN CLAVE 1: Uso de .str.upper() ***
    gdf_dpto_sel = gdf_departamentos[gdf_departamentos[col_dpto].str.upper() == departamento_sel.upper()]
    gdf_prov_sel = gdf_provincias[gdf_provincias[col_prov_provincia].str.upper() == provincia_sel.upper()]
    gdf_distrito = gdf_distritos[(gdf_distritos[col_distr].str.upper() == distrito_sel.upper()) & 
                                  (gdf_distritos[col_prov_distrito].str.upper() == provincia_sel.upper())]
    gdf_distritos_en_provincia = gdf_distritos[gdf_distritos[col_prov_distrito].str.upper() == provincia_sel.upper()]

    # *** CORRECCIÓN CLAVE 2: Verificación explícita de Geometrías ***
    if gdf_distrito.empty or gdf_dpto_sel.empty or gdf_prov_sel.empty:
        print(f"❌ Error: No se pudo encontrar la geometría para el distrito/provincia/departamento seleccionado.")
        print(f"   - Dpto '{departamento_sel.upper()}' encontrado: {not gdf_dpto_sel.empty}")
        print(f"   - Prov '{provincia_sel.upper()}' encontrado: {not gdf_prov_sel.empty}")
        print(f"   - Dist '{distrito_sel.upper()}' encontrado: {not gdf_distrito.empty}")
        print("   Verifique que los nombres en sus shapefiles coincidan con las entradas (e.g., 'PROVINCIA' en el shapefile de distritos).")
        return None

    print(f"   ✅ Geometrías de límite encontradas")
    
    # 5. CARGAR Y RECORTAR RASTER
    print("\n✂️ Recortando raster AL DISTRITO (no rectangular)...")
    # Se añade un argumento para ser compatible con la nueva lógica de BBOX en mapa_ubicacion
    raster_data, out_transform, src_crs_out, raster_bounds = cargar_y_recortar_raster(ruta_pendientes, gdf_distrito)

    if raster_data is None:
        print("❌ ERROR: No se pudo recortar el raster. Abortando generación de mapa.")
        return None

    # 6. GENERAR LAYOUT Y MAPA PRINCIPAL
    print("\n🎨 Generando layout del mapa...")
    fig = plt.figure(figsize=(14, 9.9))
    grid = plt.GridSpec(1, 2, width_ratios=[3.0, 1], wspace=0.05)
    gs_izquierda = grid[0, 0].subgridspec(3, 1, height_ratios=[0.08, 3.5, 0.42], hspace=0.08)

    ax_titulo = fig.add_subplot(gs_izquierda[0])
    ax_titulo.text(0.5, 0.5, f"MAPA DE PENDIENTES - DISTRITO DE {distrito_sel.upper()}",
                   ha='center', va='center', fontsize=12, fontweight="normal",
                   bbox=dict(boxstyle='square,pad=0.5', facecolor='white', 
                            edgecolor='black', linewidth=1.5, alpha=0.95))
    ax_titulo.axis('off')

    ax_main = fig.add_subplot(gs_izquierda[1])

    # CÁLCULO DE BBOX (con la geometría del distrito en el CRS final)
    gdf_distrito_viz = gdf_distrito.to_crs(src_crs_out)
    minx, miny, maxx, maxy = gdf_distrito_viz.total_bounds
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

    # Si el CRS de salida no es 3857, necesitamos re-ajustar el mapa base
    if src_crs_out != 'EPSG:3857':
        print(f"   Advertencia: Raster no está en 3857 ({src_crs_out}). Usando fondo gris.")
        ax_main.set_facecolor("#e8e8e8")
    else:
        print("   📡 Descargando imagen satelital (Contextily)...")
        try:
            ctx.add_basemap(ax_main, source=ctx.providers.Esri.WorldImagery, attribution=False, zoom='auto')
        except Exception as e:
            print(f"   ⚠️ No se pudo cargar el mapa base: {e}")
            ax_main.set_facecolor("#e8e8e8")

    # CREAR COLORMAP Y NORMALIZADOR
    cmap = ListedColormap(COLORES_PENDIENTE)
    cmap.set_bad(color='none', alpha=0)
    # Los valores del raster son enteros (1 a 5) representando las categorías.
    # Los límites deben estar entre los valores enteros: 0.5 a 5.5
    norm = BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5, 5.5], cmap.N)

    # VISUALIZAR RASTER
    print("   🎨 Renderizando raster de pendientes...")
    masked_raster = np.ma.masked_invalid(raster_data)
    
    im = ax_main.imshow(
        masked_raster, 
        extent=[raster_bounds[0], raster_bounds[2], raster_bounds[1], raster_bounds[3]], 
        cmap=cmap, 
        norm=norm, 
        aspect='auto', 
        alpha=0.8, 
        zorder=4, 
        origin='upper', 
        interpolation='nearest'
    )
    
    print(f"   ✅ Raster renderizado - Píxeles válidos: {np.count_nonzero(~masked_raster.mask)}")

    # RECORTAR VISUALMENTE EL RASTER A LA GEOMETRÍA DEL DISTRITO (en el CRS de salida)
    geom_distrito_out = gdf_distrito.to_crs(src_crs_out).geometry.iloc[0]
    
    if geom_distrito_out.geom_type == 'Polygon':
        exterior_coords = list(geom_distrito_out.exterior.coords)
        vertices = exterior_coords
        codes = [Path.MOVETO] + [Path.LINETO] * (len(exterior_coords) - 1)
        path = Path(vertices, codes)
    elif geom_distrito_out.geom_type == 'MultiPolygon':
        vertices = []
        codes = []
        for poly in geom_distrito_out.geoms:
            exterior_coords = list(poly.exterior.coords)
            vertices.extend(exterior_coords)
            codes.extend([Path.MOVETO] + [Path.LINETO] * (len(exterior_coords) - 1))
        path = Path(vertices, codes)
    else:
        path = None
    
    # Aplicar el clip path al raster
    if path:
        patch = PathPatch(path, facecolor='none', edgecolor='none', transform=ax_main.transData)
        ax_main.add_patch(patch)
        im.set_clip_path(patch)
    
    # LÍMITE DISTRITAL
    gdf_distrito_viz.plot(ax=ax_main, facecolor="none", edgecolor="black", 
                     linewidth=1.0, linestyle=':', alpha=1.0, zorder=15)

    grillado_utm_proyectado(ax_main, bbox_main, ndiv=8)
    add_north_arrow_blanco_completo(ax_main, xy_pos=(0.93, 0.08), size=0.06)
    # Se usa 1 para ScaleBar ya que el CRS de salida es el CRS de la visualización
    ax_main.add_artist(ScaleBar(1, units="m", location="lower left", 
                                box_alpha=0.6, border_pad=0.5, scale_loc='bottom'))

    # MEMBRETE Y LEYENDA
    gs_memb_ley = gs_izquierda[2].subgridspec(1, 2, wspace=0.1)
    ax_membrete = fig.add_subplot(gs_memb_ley[0])
    fig.canvas.draw()
    add_membrete(ax_membrete, departamento_sel, provincia_sel, distrito_sel, ax_main, fig)

    ax_leyenda = fig.add_subplot(gs_memb_ley[1])
    ax_leyenda.axis('off')

    legend_elements = [Patch(facecolor='white', edgecolor='white', label='PENDIENTES (°):', linewidth=0)]
    for idx, etiqueta in enumerate(ETIQUETAS_PENDIENTE):
        legend_elements.append(Patch(facecolor=COLORES_PENDIENTE[idx], edgecolor='black', label=etiqueta))

    legend_elements.extend([
        Patch(facecolor='white', edgecolor='white', label='', linewidth=0),
        Line2D([0], [0], color='black', lw=1, linestyle=':', label='Límite Distrital')
    ])

    leg = ax_leyenda.legend(handles=legend_elements, loc='center', ncol=1, frameon=True, fontsize=8,
                           title="LEYENDA", title_fontproperties={'size': 10, 'weight': 'bold'},
                           handletextpad=0.5, columnspacing=1.0, borderpad=0.7, handlelength=1.5)
    leg.get_title().set_ha('center')
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(1.2)

    # 7. MAPAS DE UBICACIÓN
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
                   gdf_departamentos=gdf_departamentos, gdf_oceano=gdf_oceano,
                   gdf_prov_sel=gdf_prov_sel) # Se añade gdf_prov_sel para el fallback en mapa_ubicacion

    mapa_ubicacion(ax_dist, gdf_prov_sel, gdf_distritos_en_provincia, gdf_distrito,
                   f"DISTRITO DE\n{distrito_sel.upper()}", distrito_sel,
                   tipo_mapa="distrito", gdf_prov_sel=gdf_prov_sel, 
                   provincia_sel=provincia_sel, col_prov=col_prov_provincia, 
                   gdf_provincias=gdf_provincias, gdf_oceano=gdf_oceano,
                   gdf_dpto_sel=gdf_dpto_sel) # Se añade gdf_dpto_sel para el chequeo de robustez

    plt.subplots_adjust(top=0.98, bottom=0.02, left=0.02, right=0.98, hspace=0.2, wspace=0.05)

    # Borde final del mapa
    rect_frame = fig.add_axes([0, 0, 1, 1], frameon=False)
    rect_frame.set_xticks([])
    rect_frame.set_yticks([])
    rect_frame.patch.set_visible(False)

    for spine in rect_frame.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(2)
        spine.set_color('black')

    # 8. GUARDAR
    print("\n💾 Guardando mapa final en carpeta de usuario...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = f"MAPA_PENDIENTES_{distrito_sel.replace(' ', '_')}_{timestamp}.png"
    ruta_guardado_final = os.path.join(carpeta_salida, nombre_base)

    try:
        plt.savefig(ruta_guardado_final, dpi=300, bbox_inches='tight', pad_inches=0.01)
        plt.close(fig)

        if os.path.exists(ruta_guardado_final):
            file_size = os.path.getsize(ruta_guardado_final) / (1024 * 1024)
            print(f"✅ Mapa de pendientes guardado exitosamente")
            print(f"   📂 Ubicación: {ruta_guardado_final}")
            print(f"   📊 Tamaño: {file_size:.2f} MB")
            print("="*80 + "\n")
            return ruta_guardado_final
        else:
            print("❌ El archivo no se guardó correctamente")
            return None

    except Exception as e:
        print(f"❌ Error al guardar el archivo: {e}")
        traceback.print_exc()
        plt.close(fig)
        return None