# Archivo: geografica_final_con_hillshade.py

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
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.plot import show

# --- RUTA BASE CORREGIDA ---
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"

AMARILLO_CLARO = "#FFEE58"

# ════════════════════════════════════════════════════════════════════════
# 🏔️ FUNCIÓN PARA GENERAR HILLSHADE
# ════════════════════════════════════════════════════════════════════════
def generar_hillshade(dem_array, azimuth=315, altitude=45):
    """
    Genera un hillshade a partir de un array DEM
    
    Args:
        dem_array: Array numpy con elevaciones
        azimuth: Ángulo azimutal de la luz (0-360, donde 315 es noroeste)
        altitude: Ángulo de altitud de la luz (0-90)
    
    Returns:
        Array numpy con valores de hillshade (0-255)
    """
    print("   🏔️ Generando hillshade...")
    
    # Convertir ángulos a radianes
    azimuth_rad = np.radians(360 - azimuth + 90)
    altitude_rad = np.radians(altitude)
    
    # Calcular gradientes
    x, y = np.gradient(dem_array)
    
    # Calcular pendiente y aspecto
    slope = np.pi / 2. - np.arctan(np.sqrt(x*x + y*y))
    aspect = np.arctan2(-x, y)
    
    # Calcular hillshade
    shaded = np.sin(altitude_rad) * np.sin(slope) + \
             np.cos(altitude_rad) * np.cos(slope) * \
             np.cos(azimuth_rad - aspect)
    
    # Normalizar a rango 0-255
    hillshade = ((shaded + 1) / 2 * 255).astype(np.uint8)
    
    print("   ✅ Hillshade generado exitosamente")
    return hillshade

# ════════════════════════════════════════════════════════════════════════
# 🗺️ FUNCIÓN PARA CARGAR Y REPROYECTAR DEM
# ════════════════════════════════════════════════════════════════════════
def cargar_dem_y_hillshade(ruta_dem, bbox_web_mercator):
    """
    Carga el DEM, lo reproyecta a Web Mercator, recorta al bbox y genera hillshade
    
    Args:
        ruta_dem: Ruta al archivo DEM.tif
        bbox_web_mercator: Tupla (minx, miny, maxx, maxy) en EPSG:3857
    
    Returns:
        hillshade_array, transform, extent (para plotear con matplotlib)
    """
    print(f"\n📂 Cargando DEM desde: {ruta_dem}")
    
    if not os.path.exists(ruta_dem):
        print(f"❌ No se encontró el archivo DEM en {ruta_dem}")
        return None, None, None
    
    try:
        with rasterio.open(ruta_dem) as src:
            print(f"   - CRS original: {src.crs}")
            print(f"   - Dimensiones: {src.width} x {src.height}")
            print(f"   - Bounds: {src.bounds}")
            
            # Reproyectar a Web Mercator (EPSG:3857)
            dst_crs = 'EPSG:3857'
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds)
            
            # Crear array de destino
            dem_reproj = np.empty((height, width), dtype=src.dtypes[0])
            
            # Reproyectar
            reproject(
                source=rasterio.band(src, 1),
                destination=dem_reproj,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear
            )
            
            print(f"   ✅ DEM reproyectado a {dst_crs}")
            
            # Recortar al bbox del mapa principal
            minx, miny, maxx, maxy = bbox_web_mercator
            
            # Convertir bbox a índices del raster
            col_start, row_start = ~transform * (minx, maxy)
            col_end, row_end = ~transform * (maxx, miny)
            
            col_start, col_end = int(max(0, col_start)), int(min(width, col_end))
            row_start, row_end = int(max(0, row_start)), int(min(height, row_end))
            
            # Recortar DEM
            dem_clipped = dem_reproj[row_start:row_end, col_start:col_end]
            
            # Actualizar transform para el área recortada
            transform_clipped = rasterio.transform.from_bounds(
                minx, miny, maxx, maxy, 
                dem_clipped.shape[1], dem_clipped.shape[0]
            )
            
            print(f"   ✅ DEM recortado a bbox del mapa")
            
            # Generar hillshade
            hillshade = generar_hillshade(dem_clipped, azimuth=315, altitude=45)
            
            # Extent para matplotlib (minx, maxx, miny, maxy)
            extent = [minx, maxx, miny, maxy]
            
            return hillshade, transform_clipped, extent
            
    except Exception as e:
        print(f"❌ Error procesando DEM: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

# ════════════════════════════════════════════════════════════════════════
# 💧 FUNCIÓN PARA CARGAR LAGOS Y LAGUNAS
# ════════════════════════════════════════════════════════════════════════
def cargar_lagos():
    """Carga el shapefile de lagos y lagunas"""
    ruta_lagos = f"{ruta_base}/DATA/MAPA DE UBICACION/LAGOS/Lago_y_Laguna_IGN_IDEP_geogpsperu_SuyoPomalia.shp"
    
    if os.path.exists(ruta_lagos):
        try:
            print(f"📂 Encontrado lagos en: {ruta_lagos}")
            gdf_lagos = gpd.read_file(ruta_lagos)
            if gdf_lagos.crs is None:
                gdf_lagos.set_crs(epsg=4326, inplace=True)
            gdf_lagos = gdf_lagos.to_crs(epsg=3857)
            print(f"✅ Lagos cargados: {len(gdf_lagos)} registros")
            return gdf_lagos
        except Exception as e:
            print(f"⚠️ Error cargando lagos: {e}")
    else:
        print(f"❌ No se encontró archivo de lagos en {ruta_lagos}")
    
    return None

# ════════════════════════════════════════════════════════════════════════
# 🌊 FUNCIÓN PARA CARGAR RÍOS
# ════════════════════════════════════════════════════════════════════════
def cargar_rios():
    """Carga el shapefile de ríos"""
    ruta_directa = f"{ruta_base}/DATA/MAPA DE UBICACION/RIOS/rios_lineal_idep_ign_100k_geogpsperu.shp"
    
    if os.path.exists(ruta_directa):
        try:
            print(f"📂 Encontrado ríos en: {ruta_directa}")
            gdf_rios = gpd.read_file(ruta_directa)
            if gdf_rios.crs is None:
                gdf_rios.set_crs(epsg=4326, inplace=True)
            gdf_rios = gdf_rios.to_crs(epsg=3857)
            print(f"✅ Ríos cargados: {len(gdf_rios)} registros")
            return gdf_rios
        except Exception as e:
            print(f"⚠️ Error cargando ríos: {e}")
    
    print(f"❌ No se encontró archivo de ríos en {ruta_directa}")
    return None

# ════════════════════════════════════════════════════════════════════════
# 🛣️ FUNCIÓN PARA CARGAR VÍAS
# ════════════════════════════════════════════════════════════════════════
def cargar_vias():
    """Carga los shapefiles de vías (nacional, departamental, vecinal)"""
    base_vias = f"{ruta_base}/DATA/MAPA DE UBICACION/VIAS"
    
    vias = {
        'nacional': None,
        'departamental': None,
        'vecinal': None
    }
    
    rutas = {
        'nacional': f"{base_vias}/VIA NACIONAL/red_vial_nacional_dic18.shp",
        'departamental': f"{base_vias}/VIA DEPARTAMENTAL/red_vial_departamental_dic18.shp",
        'vecinal': f"{base_vias}/VIA VECINAL/red_vial_vecinal_dic18.shp"
    }
    
    for tipo, ruta in rutas.items():
        if os.path.exists(ruta):
            try:
                gdf = gpd.read_file(ruta)
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                vias[tipo] = gdf.to_crs(epsg=3857)
                print(f"✅ Vías {tipo}: {len(vias[tipo])} registros")
            except Exception as e:
                print(f"⚠️ Error cargando vías {tipo}: {e}")
        else:
            print(f"⚠️ No se encontró archivo de vías {tipo}")
    
    return vias

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
    # Zorder alto para estar sobre todas las capas
    ax.add_patch(Polygon(points_body_data, facecolor='white', edgecolor='black', 
                        linewidth=1.5, zorder=200, transform=ax.transData))
    ax.add_patch(Polygon(points_head_data, facecolor='white', edgecolor='black', 
                        linewidth=1.5, zorder=200, transform=ax.transData))
    ax.text(x_pos, y_pos + s * 1.5 + 0.015, "N", transform=ax.transAxes, 
           fontsize=16, fontweight='bold', ha='center', va='center', color='white',
           path_effects=[path_effects.withStroke(linewidth=3, foreground='black')],
           zorder=201)

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
        "MAPA": f"PLANO DE UBICACIÓN: DISTRITO DE {dist.upper()}",
        "DPTO": dpto.upper(),
        "PROVINCIA": prov.upper(),
        "DISTRITO": dist.upper(),
        "MAPA_N": "001-2025",
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
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf.set_crs(epsg=4326, inplace=True)
        return gdf.to_crs(epsg=3857)
    except Exception as e:
        print(f"❌ Error cargando {alias} desde {path}: {e}")
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
                   top=True, bottom=True, left=True, right=True, 
                   labeltop=True, labelright=False)
    
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
                        if prov[col_prov] != provincia_sel and 
                        prov.geometry.touches(provincia_seleccionada_geom)]
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
    
    # Dibujar océano solo si está disponible
    if gdf_oceano is not None:
        try:
            gdf_oceano_clipped = gdf_oceano.clip(box(*bbox))
            gdf_oceano_clipped.plot(ax=ax, color="#A4D4FF", edgecolor="none", zorder=2)
            if not gdf_oceano_clipped.empty and tipo_mapa == "pais":
                ocean_point = gdf_oceano_clipped.geometry.unary_union.representative_point()
                ax.text(ocean_point.x, ocean_point.y, "OCÉANO\nPACÍFICO",
                       transform=ax.transData, color="#00008B", fontsize=6,
                       ha='center', va='center', style='italic', rotation=-60,
                       path_effects=[path_effects.withStroke(linewidth=2, foreground="white")], 
                       zorder=10)
        except Exception as e:
            print(f"   ⚠️ Error dibujando océano: {e}")
    
    if tipo_mapa == "pais":
        if gdf_base_map is not None:
            gdf_base_map.plot(ax=ax, color="#f0eee8", edgecolor="black", linewidth=0.4, zorder=1)
            col_pais = next((c for c in ['NOMBDEP', 'NOMBRE', 'PAIS', 'PAÍS'] 
                           if c in gdf_base_map.columns), None)
            if col_pais and gdf_context is not None:
                peru_geom = gdf_context.unary_union
                for idx, row in gdf_base_map.iterrows():
                    if not row.geometry.intersects(peru_geom):
                        country_name = str(row[col_pais]) if row[col_pais] else ''
                        centroid = row.geometry.representative_point()
                        if bbox[0] < centroid.x < bbox[2] and bbox[1] < centroid.y < bbox[3]:
                            ax.text(centroid.x, centroid.y, country_name.upper(),
                                   transform=ax.transData, fontsize=5, ha='center', va='center',
                                   color='dimgray', 
                                   path_effects=[path_effects.withStroke(linewidth=1.5, 
                                                                        foreground='white')], 
                                   zorder=10)
        if gdf_context is not None:
            gdf_context.plot(ax=ax, color=AMARILLO_CLARO, edgecolor="black", 
                           linewidth=0.7, zorder=3)
    
    elif tipo_mapa == "provincia":
        if gdf_base_map is not None:
            gdf_base_map.plot(ax=ax, color="#f0eee8", edgecolor="black", linewidth=0.4, zorder=1)
            if col_dpto and gdf_context is not None:
                dpto_sel_geom = gdf_context.unary_union
                for idx, row in gdf_base_map.iterrows():
                    if not row.geometry.equals(dpto_sel_geom):
                        dpto_name = str(row[col_dpto]) if row[col_dpto] else ''
                        centroid = row.geometry.representative_point()
                        if bbox[0] < centroid.x < bbox[2] and bbox[1] < centroid.y < bbox[3]:
                            ax.text(centroid.x, centroid.y, dpto_name.upper(),
                                   transform=ax.transData, fontsize=5, ha='center', va='center',
                                   color='dimgray',
                                   path_effects=[path_effects.withStroke(linewidth=1.5, 
                                                                        foreground='white')], 
                                   zorder=10)
        if gdf_context is not None:
            gdf_context.plot(ax=ax, color=AMARILLO_CLARO, edgecolor="black", 
                           linewidth=0.7, zorder=3)
            
    elif tipo_mapa == "distrito":
        if gdf_provincias is not None:
            provincias_a_mostrar = gdf_provincias.clip(box(*bbox))
            provincias_a_mostrar[provincias_a_mostrar[col_prov] != provincia_sel].plot(
                ax=ax, color='lightgray', edgecolor='darkgray', linewidth=0.4, zorder=2)
            
            for idx, row in provincias_a_mostrar.iterrows():
                if row[col_prov] != provincia_sel:
                    prov_name = str(row[col_prov]) if row[col_prov] else ''
                    centroid = row.geometry.representative_point()
                    if bbox[0] < centroid.x < bbox[2] and bbox[1] < centroid.y < bbox[3]:
                        ax.text(centroid.x, centroid.y, prov_name.upper(),
                               transform=ax.transData, fontsize=5, ha='center', va='center',
                               color='dimgray',
                               path_effects=[path_effects.withStroke(linewidth=1.5, 
                                                                    foreground='white')], 
                               zorder=10)
            
            if gdf_prov_sel is not None:
                gdf_prov_sel.plot(ax=ax, color=AMARILLO_CLARO, edgecolor='black', 
                                linewidth=0.7, zorder=3)
        if gdf_context is not None:
            gdf_context.plot(ax=ax, facecolor='none', edgecolor="gray", 
                           linewidth=0.4, zorder=4)
    
    if is_focus_valid:
        gdf_focus.plot(ax=ax, facecolor="red", edgecolor="red", linewidth=0.2, 
                      hatch='o', zorder=5)
    
    if all(np.isfinite(bbox)):
        grillado_grados_mejorado(ax, bbox, ndiv=5, decimales=1)
    
    ax.text(0.03, 0.05, titulo, transform=ax.transAxes, color="white", fontsize=8, 
           ha="left", va="bottom", zorder=8, 
           bbox=dict(facecolor="#4A90E2", edgecolor="black", boxstyle="round,pad=0.3", 
                    alpha=0.9))
    
    if is_focus_valid:
        ax.text(gdf_focus.geometry.centroid.iloc[0].x, 
               gdf_focus.geometry.centroid.iloc[0].y, 
               etiqueta.upper(), color="white", fontsize=8, ha="center", va="center", 
               zorder=9, path_effects=[path_effects.withStroke(linewidth=3, foreground="black")])
    
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])
    ax.set_facecolor("#f0f8ff")
    ax.set_aspect('equal', adjustable='box')
    ax.axis('on')

# ════════════════════════════════════════════════════════════════════════
# 🗺️ FUNCIÓN PRINCIPAL DE GENERACIÓN DE MAPA
# ════════════════════════════════════════════════════════════════════════
def generar_mapa_final(nombre_usuario, departamento_sel, provincia_sel, distrito_sel):
    print("\n" + "="*80)
    print("🗺️  INICIANDO PROCESO DE GUARDADO LOCAL DE MAPA CON HILLSHADE Y LAGOS...")
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")
    
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "MAPA DE UBICACION GEOGRAFICA")
        os.makedirs(carpeta_salida, exist_ok=True)
        print(f"   - Carpeta de salida verificada: {carpeta_salida}")
    except Exception as e:
        print(f"❌ Error creando la estructura de carpetas para el usuario: {e}")
        return None

    print("\n🔍 Cargando capas base...")
    gdf_departamentos = cargar_shapefile("departamento", "Departamentos")
    gdf_provincias = cargar_shapefile("provincia", "Provincias")
    gdf_distritos = cargar_shapefile("distrito", "Distritos del Perú")
    
    # Buscar archivos de países y océano con mayor flexibilidad
    print("\n🔍 Buscando archivos de contexto geográfico...")
    gdf_paises = None
    gdf_oceano = None
    
    # Buscar archivo de países/sudamérica
    posibles_paises = [
        f"{ruta_base}/DATA/MAPA DE UBICACION/PAISES DE SUDAMERICA/Sudamérica.shp",
        f"{ruta_base}/DATA/MAPA DE UBICACION/PAISES/Sudamérica.shp",
        f"{ruta_base}/DATA/PAISES DE SUDAMERICA/Sudamérica.shp"
    ]
    
    for ruta_paises in posibles_paises:
        if os.path.exists(ruta_paises):
            try:
                gdf_paises = gpd.read_file(ruta_paises).to_crs(3857)
                print(f"   ✅ Países cargados desde: {ruta_paises}")
                break
            except Exception as e:
                print(f"   ⚠️ Error cargando {ruta_paises}: {e}")
    
    if gdf_paises is None:
        print("   ⚠️ No se encontró archivo de países - continuando sin contexto sudamericano")
    
    # Buscar archivo de océano
    posibles_oceano = [
        f"{ruta_base}/DATA/MAPA DE UBICACION/OCEANO/Océano.shp",
        f"{ruta_base}/DATA/OCEANO/Océano.shp",
        f"{ruta_base}/DATA/MAPA DE UBICACION/OCEANO/oceano.shp"
    ]
    
    for ruta_oceano in posibles_oceano:
        if os.path.exists(ruta_oceano):
            try:
                gdf_oceano = gpd.read_file(ruta_oceano).to_crs(3857)
                print(f"   ✅ Océano cargado desde: {ruta_oceano}")
                break
            except Exception as e:
                print(f"   ⚠️ Error cargando {ruta_oceano}: {e}")
    
    if gdf_oceano is None:
        print("   ⚠️ No se encontró archivo de océano - continuando sin capa de agua")

    if gdf_departamentos is None or gdf_provincias is None or gdf_distritos is None:
        print("❌ Faltan capas base (departamento, provincia o distrito). Abortando.")
        return None

    col_dpto = next((c for c in ['NOMBDEP', 'DEPARTAMEN'] if c in gdf_departamentos.columns), None)
    col_prov = next((c for c in ['NOMBPROV', 'PROVINCIA'] if c in gdf_provincias.columns), None)
    col_distr = next((c for c in ['NOMBDIST', 'DISTRITO'] if c in gdf_distritos.columns), None)

    print("\n🔍 Filtrando datos del área seleccionada...")
    gdf_dpto_sel = gdf_departamentos[gdf_departamentos[col_dpto] == departamento_sel]
    gdf_prov_sel = gdf_provincias[gdf_provincias[col_prov] == provincia_sel]
    gdf_distrito = gdf_distritos[(gdf_distritos[col_distr] == distrito_sel) & 
                                 (gdf_distritos[col_prov] == provincia_sel)]
    gdf_distritos_en_provincia = gdf_distritos[gdf_distritos[col_prov] == provincia_sel]
    
    if gdf_distrito.empty:
        print(f"❌ Error: No se pudo encontrar la geometría para el distrito '{distrito_sel}'.")
        return None

    print("\n💧🌊 Cargando lagos, ríos y vías...")
    gdf_lagos = cargar_lagos()
    gdf_rios = cargar_rios()
    vias = cargar_vias()

    print("\n🎨 Generando layout del mapa...")
    fig = plt.figure(figsize=(14, 9.9))
    grid = plt.GridSpec(1, 2, width_ratios=[3.0, 1], wspace=0.05)
    gs_izquierda = grid[0, 0].subgridspec(3, 1, height_ratios=[0.08, 3.5, 0.42], hspace=0.08)
    
    ax_titulo = fig.add_subplot(gs_izquierda[0])
    ax_titulo.text(0.5, 0.5, f"MAPA DE UBICACIÓN GEOGRÁFICA - DISTRITO DE {distrito_sel.upper()}", 
                   ha='center', va='center', fontsize=13, fontweight="normal", 
                   bbox=dict(boxstyle='square,pad=0.5', facecolor='white', 
                            edgecolor='black', linewidth=1.5, alpha=0.95))
    ax_titulo.axis('off')
    
    ax_main = fig.add_subplot(gs_izquierda[1])
    
    # Calcular bbox con aspect ratio consistente
    minx, miny, maxx, maxy = gdf_distrito.total_bounds
    buffer_factor = 0.15
    buffer_x = (maxx - minx) * buffer_factor
    buffer_y = (maxy - miny) * buffer_factor
    bbox_temp = (minx - buffer_x, miny - buffer_y, maxx + buffer_x, maxy + buffer_y)
    
    # Mantener aspect ratio consistente
    aspect_ratio_objetivo = 1.21
    cx = (bbox_temp[0] + bbox_temp[2]) / 2
    cy = (bbox_temp[1] + bbox_temp[3]) / 2
    ancho_actual = bbox_temp[2] - bbox_temp[0]
    alto_actual = bbox_temp[3] - bbox_temp[1]
    aspecto_actual = ancho_actual / alto_actual
    
    if aspecto_actual > aspect_ratio_objetivo:
        nuevo_alto = ancho_actual / aspect_ratio_objetivo
        bbox_main = (bbox_temp[0], cy - nuevo_alto/2, bbox_temp[2], cy + nuevo_alto/2)
    else:
        nuevo_ancho = alto_actual * aspect_ratio_objetivo
        bbox_main = (cx - nuevo_ancho/2, bbox_temp[1], cx + nuevo_ancho/2, bbox_temp[3])
    
    ax_main.set_xlim(bbox_main[0], bbox_main[2])
    ax_main.set_ylim(bbox_main[1], bbox_main[3])
    ax_main.set_aspect('equal', adjustable='box')
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 🏔️ CARGAR Y MOSTRAR HILLSHADE EN VEZ DE IMAGEN SATELITAL
    # ═══════════════════════════════════════════════════════════════════════════
    ruta_dem = f"{ruta_base}/DATA/MAPA DE UBICACION/RELIVE/DEM.tif"
    hillshade, transform, extent = cargar_dem_y_hillshade(ruta_dem, bbox_main)
    
    if hillshade is not None and extent is not None:
        # Mostrar el hillshade con un colormap de grises INVERTIDO y más visible
        ax_main.imshow(hillshade, extent=extent, cmap='gray_r', 
                      interpolation='bilinear', alpha=0.5, zorder=1)
        print("   ✅ Hillshade aplicado como fondo del mapa (colores invertidos, alpha=0.5)")
    else:
        print("   ⚠️ No se pudo cargar el hillshade, usando fondo blanco")
        ax_main.set_facecolor('white')
    
    # Dibujar el distrito con color MORADO MÁS SERIO (menos rosado)
    gdf_distrito.plot(ax=ax_main, color="#6B2C6E", edgecolor="black", 
                     linewidth=1.5, alpha=0.25, zorder=5)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 💧 DIBUJAR LAGOS Y LAGUNAS (CELESTE CON BORDE AZUL COMO RÍOS)
    # ═══════════════════════════════════════════════════════════════════════════
    if gdf_lagos is not None:
        try:
            gdf_lagos_clip = gdf_lagos.clip(box(*bbox_main))
            if not gdf_lagos_clip.empty:
                print(f"   💧 Dibujando lagos y lagunas... ({len(gdf_lagos_clip)} registros)")
                # Color celeste (#87CEEB) con borde azul (#1E90FF) como los ríos
                gdf_lagos_clip.plot(ax=ax_main, color='#87CEEB', edgecolor='#1E90FF', 
                                   linewidth=0.8, alpha=0.7, zorder=10)
        except Exception as e:
            print(f"   ⚠️ Error al recortar lagos: {e}")
    else:
        print("   ⚠️ No hay datos de lagos para mostrar")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 🌊 DIBUJAR RÍOS (MÁS DELGADOS Y CELESTE AZULADO)
    # ═══════════════════════════════════════════════════════════════════════════
    if gdf_rios is not None:
        try:
            gdf_rios_clip = gdf_rios.clip(box(*bbox_main))
            if not gdf_rios_clip.empty:
                print(f"   🌊 Dibujando ríos... ({len(gdf_rios_clip)} registros)")
                gdf_rios_clip.plot(ax=ax_main, color='#1E90FF', linewidth=0.8, zorder=11)
        except Exception as e:
            print(f"   ⚠️ Error al recortar ríos: {e}")
    else:
        print("   ⚠️ No hay datos de ríos para mostrar")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 🛣️ DIBUJAR VÍAS (MÁS DELGADAS Y CONTINUAS)
    # ═══════════════════════════════════════════════════════════════════════════
    print("   🛣️ Dibujando vías...")
    
    # Vía Nacional (más delgada y continua)
    if vias['nacional'] is not None:
        try:
            gdf_via_nacional_clip = vias['nacional'].clip(box(*bbox_main))
            if not gdf_via_nacional_clip.empty:
                gdf_via_nacional_clip.plot(ax=ax_main, color='#FF0000', 
                                          linewidth=1.0, linestyle='-', zorder=12)
                print(f"   ✅ Vías nacionales: {len(gdf_via_nacional_clip)} registros")
        except Exception as e:
            print(f"   ⚠️ Error al dibujar vías nacionales: {e}")
    
    # Vía Departamental (más delgada y continua)
    if vias['departamental'] is not None:
        try:
            gdf_via_departamental_clip = vias['departamental'].clip(box(*bbox_main))
            if not gdf_via_departamental_clip.empty:
                gdf_via_departamental_clip.plot(ax=ax_main, color='#32CD32', 
                                               linewidth=0.8, linestyle='-', zorder=13)
                print(f"   ✅ Vías departamentales: {len(gdf_via_departamental_clip)} registros")
        except Exception as e:
            print(f"   ⚠️ Error al dibujar vías departamentales: {e}")
    
    # Vía Vecinal (más delgada y continua)
    if vias['vecinal'] is not None:
        try:
            gdf_via_vecinal_clip = vias['vecinal'].clip(box(*bbox_main))
            if not gdf_via_vecinal_clip.empty:
                gdf_via_vecinal_clip.plot(ax=ax_main, color='#FFFF00', 
                                         linewidth=0.6, linestyle='-', zorder=15)
                print(f"   ✅ Vías vecinales: {len(gdf_via_vecinal_clip)} registros")
        except Exception as e:
            print(f"   ⚠️ Error al dibujar vías vecinales: {e}")
    else:
        print("   ⚠️ No se cargaron datos de vías vecinales")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 📍 DIBUJAR TODOS LOS DISTRITOS Y PROVINCIAS CON ETIQUETAS
    # ═══════════════════════════════════════════════════════════════════════════
    print("   📍 Dibujando distritos y provincias con etiquetas...")
    try:
        # Obtener la geometría del distrito principal
        distrito_principal_geom = gdf_distrito.geometry.unary_union
        
        # TODOS LOS DISTRITOS que se vean en el bbox (no solo los vecinos)
        distritos_en_mapa = gdf_distritos.clip(box(*bbox_main))
        distritos_otros = distritos_en_mapa[distritos_en_mapa[col_distr] != distrito_sel]
        
        if not distritos_otros.empty:
            # Dibujar TODOS los distritos visibles con borde NEGRO CONTINUO
            distritos_otros.plot(ax=ax_main, facecolor='none', edgecolor='black', 
                                linewidth=1.2, linestyle='-', zorder=6)
            
            # Agregar etiquetas a TODOS los distritos visibles
            for idx, row in distritos_otros.iterrows():
                nombre_distrito = str(row[col_distr])
                centroid = row.geometry.representative_point()
                
                # Verificar si el centroide está dentro del bbox
                if bbox_main[0] < centroid.x < bbox_main[2] and bbox_main[1] < centroid.y < bbox_main[3]:
                    ax_main.text(centroid.x, centroid.y, nombre_distrito.upper(),
                               fontsize=7.5, ha='center', va='center',
                               color='black', fontweight='bold',
                               path_effects=[path_effects.withStroke(linewidth=2.5, 
                                                                    foreground='white')],
                               zorder=150)
            
            print(f"   ✅ Distritos etiquetados: {len(distritos_otros)}")
        
        # TODAS LAS PROVINCIAS que se vean en el bbox
        provincias_en_mapa = gdf_provincias.clip(box(*bbox_main))
        provincias_otras = provincias_en_mapa[provincias_en_mapa[col_prov] != provincia_sel]
        
        if not provincias_otras.empty:
            # Dibujar límites de TODAS las provincias visibles
            provincias_otras.plot(ax=ax_main, facecolor='none', 
                                 edgecolor='#9370DB', linewidth=1.8, 
                                 linestyle=':', zorder=7)
            
            # Agregar etiquetas a TODAS las provincias visibles
            for idx, row in provincias_otras.iterrows():
                nombre_provincia = str(row[col_prov])
                centroid = row.geometry.representative_point()
                
                if bbox_main[0] < centroid.x < bbox_main[2] and bbox_main[1] < centroid.y < bbox_main[3]:
                    ax_main.text(centroid.x, centroid.y, 
                               f"PROV. {nombre_provincia.upper()}",
                               fontsize=9, ha='center', va='center',
                               color='#4B0082', fontweight='bold', style='italic',
                               path_effects=[path_effects.withStroke(linewidth=3.5, 
                                                                    foreground='white')],
                               zorder=151)
            
            print(f"   ✅ Provincias etiquetadas: {len(provincias_otras)}")
        
    except Exception as e:
        print(f"   ⚠️ Error al dibujar distritos/provincias: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 🧭 AGREGAR ELEMENTOS CARTOGRÁFICOS (SOBRE TODAS LAS CAPAS)
    # ═══════════════════════════════════════════════════════════════════════════
    grillado_utm_proyectado(ax_main, bbox_main, ndiv=8)
    
    # Flecha Norte con zorder alto
    add_north_arrow_blanco_completo(ax_main, xy_pos=(0.93, 0.08), size=0.06)
    
    # Escala gráfica con zorder alto
    scalebar = ScaleBar(1, units="m", location="lower left", 
                       box_alpha=0.8, border_pad=0.5, scale_loc='bottom')
    scalebar.set_zorder(100)  # Asegurar que esté sobre todo
    ax_main.add_artist(scalebar)
    
    gs_memb_ley = gs_izquierda[2].subgridspec(1, 2, wspace=0.1)
    ax_membrete = fig.add_subplot(gs_memb_ley[0])
    fig.canvas.draw()
    add_membrete(ax_membrete, departamento_sel, provincia_sel, distrito_sel, ax_main, fig)
    
    ax_leyenda = fig.add_subplot(gs_memb_ley[1])
    ax_leyenda.axis('off')
    
    legend_elements = [
        Patch(facecolor='#6B2C6E', edgecolor='black', alpha=0.45, label='Área del Distrito'),
        Line2D([0], [0], color='black', lw=2.0, linestyle='-', label='Límite Distrital'),
        Line2D([0], [0], color='#9370DB', lw=2.0, linestyle=':', label='Límite Provincial'),
        Patch(facecolor='#87CEEB', edgecolor='#1E90FF', alpha=0.7, label='Lagos y Lagunas'),
        Line2D([0], [0], color='#1E90FF', lw=2.0, label='Ríos'),
        Line2D([0], [0], color='#FF0000', lw=2.0, label='Vía Nacional'),
        Line2D([0], [0], color='#32CD32', lw=2.0, label='Vía Departamental'),
        Line2D([0], [0], color='#FFFF00', lw=2.0, label='Vía Vecinal'),
        Line2D([0], [0], color='black', ls='-', lw=1, label='Grillado UTM')
    ]
    
    leg = ax_leyenda.legend(
        handles=legend_elements, 
        loc='center', 
        ncol=2,
        frameon=True, 
        fontsize=8,
        title="LEYENDA", 
        title_fontproperties={'size': 10, 'weight': 'bold'},
        handletextpad=0.5,
        columnspacing=0.8,
        borderpad=0.6,
        handlelength=1.5
    )
    leg.get_title().set_ha('center')
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(1.2)
    
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
    
    plt.subplots_adjust(top=0.98, bottom=0.02, left=0.02, right=0.98, 
                       hspace=0.2, wspace=0.05)
    rect_frame = fig.add_axes([0, 0, 1, 1], frameon=False)
    rect_frame.set_xticks([])
    rect_frame.set_yticks([])
    rect_frame.patch.set_visible(False)
    for spine in rect_frame.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(2)
        spine.set_color('black')

    print("\n💾 Guardando mapa final en carpeta de usuario...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = f"MAPA_UBICACION_COMPLETO_{distrito_sel.replace(' ', '_')}_{timestamp}.png"
    ruta_guardado_final = os.path.join(carpeta_salida, nombre_base)
    
    plt.savefig(ruta_guardado_final, dpi=300, bbox_inches='tight', pad_inches=0.01)
    plt.close(fig)
    
    print(f"✅ Mapa guardado exitosamente en: {ruta_guardado_final}")
    print("="*80)
    
    return ruta_guardado_final


# ═══════════════════════════════════════════════════════════════════════════
# EJEMPLO DE USO
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Ejemplo de llamada a la función
    resultado = generar_mapa_final(
        nombre_usuario="dani2",
        departamento_sel="CUSCO",
        provincia_sel="ANTA",
        distrito_sel="ANTA"
    )
    
    if resultado:
        print(f"\n🎉 Proceso completado exitosamente!")
        print(f"📁 Mapa guardado en: {resultado}")