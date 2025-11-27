# -*- coding: utf-8 -*-
"""
🎯 SCRIPT INTEGRADO: MAPA DE PELIGRO CON 4 PARÁMETROS + CENTROS POBLADOS
- Calcula el mapa de peligro combinando: Pendiente + Geomorfología + Geología + pp_max
- Muestra centros poblados con etiquetas FUERA de la zona de estudio
- Líneas blancas gruesas y separación automática entre etiquetas
- SOPORTE EXCLUSIVO PARA PIURA Y SECHURA

MODIFICACIONES:
- 1. Guardado en carpeta /workspaces/AUTOMATIZACION_DASH/PRUEBA/USUARIOS/{NOMBRE_USUARIO}.
- 2. Limpieza de estructura de mapas de Ubicación (eliminación de grillado/coordenadas).
- 3. IMPLEMENTACIÓN DEL PROMEDIO PONDERADO.
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
import re 
import traceback 

# ==================== CONFIGURACIÓN GLOBAL ====================
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"
AMARILLO_CLARO = "#FFEE58"

# 🔑 RUTAS DE CAPAS POR PROVINCIA
CAPAS_POR_PROVINCIA = {
    "PIURA": {
        "GEOLOGIA": f"{ruta_base}/DATA/PELIGRO/GEOLOGIA/geologia_piura_con_pesos.shp",
        "GEOMORFOLOGIA": f"{ruta_base}/DATA/PELIGRO/GEOMORFOLOGIA/geomorfologia_piura_con_pesos.shp",
        "PENDIENTE": f"{ruta_base}/DATA/PELIGRO/PENDIENTE/PIURA/pendientes_piura.shp",
        "PPMAX": f"{ruta_base}/DATA/PELIGRO/PP_MAX/PIURA_TR50_Clasificacion.shp"
    },
    "SECHURA": {
        "GEOLOGIA": f"{ruta_base}/DATA/PELIGRO/GEOLOGIA/geologia_sechura_con_pesos.shp",
        "GEOMORFOLOGIA": f"{ruta_base}/DATA/PELIGRO/GEOMORFOLOGIA/geomorfologia_sechura_con_pesos.shp",
        "PENDIENTE": f"{ruta_base}/DATA/PELIGRO/PENDIENTE/PIURA/pendientes_piura.shp",
        "PPMAX": f"{ruta_base}/DATA/PELIGRO/PP_MAX/PIURA_TR50_Clasificacion.shp"
    }
}

# 🛠️ MAPEO DE COLUMNAS DE PESO ESPECÍFICAS (SEGÚN SU REQUERIMIENTO)
PESO_COLUMNAS_MAP = {
    "GEOLOGIA": "PESO_GEOL",
    "GEOMORFOLOGIA": "PESO_GEOMO",
    "PENDIENTE": "PESO",
    "PPMAX": "Nivel" # Columna PP_MAX tiene el nombre 'Nivel'
}

# 🔑 RUTAS DE LÍMITES ADMINISTRATIVOS Y CENTROS POBLADOS (RUTAS CORREGIDAS)
RUTA_CENTROS_POBLADOS = f"{ruta_base}/DATA/CENTROS_POBLADOS/Centros_Poblados_INEI_geogpsperu_SuyoPomalia.shp"
RUTA_DISTRITOS = f"{ruta_base}/DATA/MAPA DE UBICACION/DISTRITOS DEL PERU/DISTRITOS_inei_geogpsperu_suyopomalia.shp"

# ==================== PONDERACIONES PARA EL ÍNDICE DE PELIGRO ====================
# NOTA: La suma de todos los pesos DEBE ser 1.0 para que el rango de peligro sea de 1.0 a 4.0.
PONDERACIONES = {
    "P_GEOLOGIA": 0.15,      
    "P_GEOMORFOLOGIA": 0.15, 
    "P_PENDIENTE": 0.55,     
    "P_PPMAX": 0.20          
}
# ===============================================================================

RUTA_PROVINCIAS = f"{ruta_base}/DATA/MAPA DE UBICACION/PROVINCIAS DEL PERU/PROVINCIAS_inei_geogpsperu_suyopomalia.shp"
RUTA_DEPARTAMENTOS = f"{ruta_base}/DATA/MAPA DE UBICACION/DEPARTAMENTOS_DEL_PERU/DEPARTAMENTOS_inei_geogpsperu_suyopomalia.shp"
RUTA_OCEANO = f"{ruta_base}/DATA/MAPA DE UBICACION/OCEANO/Océano.shp"

# PALETA DE COLORES PARA NIVELES DE PELIGRO
COLORES_PELIGRO = ['#00FF00', '#FFFF00', '#FFA500', '#FF0000']
ETIQUETAS_PELIGRO = ['Baja', 'Media', 'Alta', 'Muy Alta']
RANGOS_PELIGRO = [1.00, 2.00, 3.00, 4.00, 5.00]

# ==================== NOMBRES DE COLUMNAS ====================
COL_DPTO = 'NOMBDEP' 
COL_PROV = 'NOMBPROV' 
COL_DIST = 'NOMBDIST' 
COL_CCPP = 'NOMB_CCPP' 

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIONES DE ETIQUETADO DE CENTROS POBLADOS (MEJORADAS)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

def agregar_etiquetas_ordenadas_circularmente(gdf_distritos, gdf_centros_poblados, ax, radio_offset=0.12):
    """
    Agrega etiquetas de centros poblados FUERA del límite distrital de manera ordenada.
    """
    
    if gdf_centros_poblados is None or len(gdf_centros_poblados) == 0:
        return
    
    distrito_boundary = gdf_distritos.boundary.unary_union
    
    try:
        distrito_merged = gdf_distritos.unary_union
        centroide = distrito_merged.centroid
    except:
        centroide = gdf_distritos.geometry.centroid.iloc[0]
    
    minx, miny, maxx, maxy = gdf_distritos.total_bounds
    ancho_distrito = maxx - minx
    alto_distrito = maxy - miny
    escala = max(ancho_distrito, alto_distrito)
    
    offset_perpendicular = escala * radio_offset
    
    posiciones_etiquetas = []
    distancia_minima_entre_etiquetas = escala * 0.04
    
    for idx, (i, row) in enumerate(gdf_centros_poblados.iterrows()):
        try:
            punto = row.geometry
            
            nombre = None
            for col in ['NOMB_CCPP', 'NOMBRE', 'NOMBCCPP', 'CCPP', 'NAME', 'nombre']:
                if col in row.index and pd.notna(row[col]):
                    nombre = str(row[col]).strip()
                    if nombre:
                        break
            
            if not nombre:
                nombre = f'Centro {idx}'
            
            x_orig, y_orig = punto.x, punto.y
            
            punto_limite = distrito_boundary.interpolate(
                distrito_boundary.project(punto)
            )
            
            dx = x_orig - centroide.x
            dy = y_orig - centroide.y
            dist_vec = np.sqrt(dx**2 + dy**2)
            
            if dist_vec > 0:
                dx_norm = dx / dist_vec
                dy_norm = dy / dist_vec
            else:
                dx_norm, dy_norm = 1, 0
            
            x_label = punto_limite.x + dx_norm * offset_perpendicular
            y_label = punto_limite.y + dy_norm * offset_perpendicular
            
            intentos_reubicacion = 0
            max_intentos = 12
            offset_adicional = 0
            
            while intentos_reubicacion < max_intentos:
                muy_cerca = False
                for pos_anterior in posiciones_etiquetas:
                    dist = np.sqrt((x_label - pos_anterior[0])**2 + (y_label - pos_anterior[1])**2)
                    if dist < distancia_minima_entre_etiquetas:
                        muy_cerca = True
                        break
                
                if not muy_cerca:
                    break
                else:
                    intentos_reubicacion += 1
                    offset_adicional = escala * 0.02 * intentos_reubicacion
                    x_label = punto_limite.x + dx_norm * (offset_perpendicular + offset_adicional)
                    y_label = punto_limite.y + dy_norm * (offset_perpendicular + offset_adicional)
            
            posiciones_etiquetas.append((x_label, y_label))
            
            ax.plot(
                [x_orig, x_label],
                [y_orig, y_label],
                'w-',
                linewidth=0.8,
                alpha=0.95,
                zorder=5
            )
            
            ax.plot(x_orig, y_orig, 'o', color='#006400', markersize=4, zorder=6)
            
            ax.text(
                x_label, y_label,
                nombre,
                fontsize=6.2,
                fontweight='bold',
                ha='center',
                va='center',
                bbox=dict(
                    boxstyle='round,pad=0.35',
                    facecolor='white',
                    edgecolor='black',
                    alpha=0.8,
                    linewidth=0.6
                ),
                zorder=8
            )
        except Exception as e:
            continue

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES PARA MAPAS Y CARGA DE DATOS (MODIFICADAS)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

def cargar_capa_admin(path, alias):
    """
    Carga capas administrativas (límites, CCPP) y las proyecta a EPSG:3857.
    """
    if not os.path.exists(path):
        print(f"   No se encontró shapefile: {alias} en la ruta {path}")
        return None
    try:
        gdf = gpd.read_file(path)
        
        if gdf.empty:
            print(f"   ⚠️ GeoDataFrame para {alias} está vacío.")
            return None
            
        # Forzar CRS a 4326 si no está definido, luego a 3857
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            # Asumir 4326 si no tiene CRS o si el CRS es incorrecto (p. ej. si lee 32717 o 32718)
            # Solo para que la conversión a 3857 sea consistente con GeoPandas.
            gdf = gdf.to_crs(epsg=4326)
            
        return gdf.to_crs(epsg=3857) # Proyección final para visualización/clipping inicial
    except Exception as e:
        print(f"   Error cargando {alias} desde {path}: {e}")
        return None

def cargar_capa_peligro(path, alias, target_utm_crs):
    """
    Carga las capas de peligro, las proyecta DIRECTAMENTE al CRS UTM de trabajo (32717)
    y repara las geometrías.
    """
    if not os.path.exists(path):
        print(f"   No se encontró shapefile: {alias} en la ruta {path}")
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.empty:
            print(f"   ⚠️ GeoDataFrame para {alias} está vacío.")
            return None
            
        # Reproyección directa al CRS UTM de trabajo (32717)
        current_crs_epsg = gdf.crs.to_epsg() if gdf.crs else None
        
        if current_crs_epsg != target_utm_crs:
            print(f"   🔄 Reproyectando {alias} de {gdf.crs.to_string() if gdf.crs else 'sin CRS'} a EPSG:{target_utm_crs}")
            gdf = gdf.to_crs(epsg=target_utm_crs)
        else:
            print(f"   ✅ {alias} ya está en EPSG:{target_utm_crs}")

        # 🛠️ Reparación de Geometrías (soluciona BBox [inf - inf] y fallas de clip)
        if not gdf.geometry.is_valid.all():
            print(f"   ⚠️ Reparando geometrías inválidas de {alias}...")
            # buffer(0) es la forma estándar de intentar reparar geometrías inválidas
            gdf.geometry = gdf.buffer(0).simplify(0.001) 
        
        # Última verificación para BBox, si sigue en inf/nan, salimos.
        if not all(np.isfinite(gdf.total_bounds)):
             print(f"❌ Error CRÍTICO: BBox de {alias} es inválida incluso después de reparación. Abortando.")
             return None
            
        return gdf
    except Exception as e:
        print(f"   ❌ Error cargando/proyectando {alias} a UTM {target_utm_crs}: {e}")
        traceback.print_exc()
        return None


# (Resto de funciones auxiliares como add_north_arrow_blanco_completo, 
# calculate_numeric_scale, add_membrete, grillado_utm_proyectado, etc. permanecen igual)
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


def grillado_utm_proyectado(ax, bbox, ndiv=8):
    x0, y0, x1, y1 = bbox
    
    # Intenta determinar la zona UTM a partir de la bbox (aproximado, pero útil)
    lon_mid, _ = pyproj.Transformer.from_crs(3857, 4326, always_xy=True).transform((x0 + x1) / 2, (y0 + y1) / 2)
    utm_zone = int(np.floor((lon_mid + 180) / 6) + 1)
    
    def fmt_este(x, pos):
        # Asegurarse de que el número tenga al menos 6 dígitos para la máscara
        num_str = f"{int(x):06d}"
        return num_str[:3] + " " + num_str[3:] + " E"
    
    def fmt_norte(y, pos):
        # Asegurarse de que el número tenga al menos 7 dígitos para la máscara
        num_str = f"{int(y):07d}"
        return num_str[0] + " " + num_str[1:4] + " " + num_str[4:] + " N"
    
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
                   gdf_dpto_sel=None, gdf_prov_sel=None, col_prov=COL_PROV, col_dpto=COL_DPTO, 
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
        # Intentar incluir provincias vecinas para el contexto
        try:
            geoms_vecinas = [prov.geometry for _, prov in gdf_provincias.iterrows() 
                            if prov[col_prov] != provincia_sel and prov.geometry.touches(provincia_seleccionada_geom)]
            area_de_interes = gpd.GeoSeries([provincia_seleccionada_geom] + geoms_vecinas, crs=gdf_prov_sel.crs).unary_union
        except:
            area_de_interes = provincia_seleccionada_geom
            
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
            # Dibujar provincias vecinas en gris claro
            gdf_provincias[gdf_provincias[col_prov] != provincia_sel].plot(
                ax=ax, color='lightgray', edgecolor='darkgray', linewidth=0.4, zorder=2)
            # Dibujar provincia de interés en amarillo
            gdf_prov_sel.plot(ax=ax, color=AMARILLO_CLARO, edgecolor='black', linewidth=0.7, zorder=3)
        if gdf_context is not None:
            # Dibujar el contorno de todos los distritos dentro de la provincia
            gdf_context.plot(ax=ax, facecolor='none', edgecolor="gray", linewidth=0.4, zorder=4)
    
    if is_focus_valid:
        # Dibujar el foco (distrito) en rojo con hatch para destacar
        gdf_focus.plot(ax=ax, facecolor="red", edgecolor="red", linewidth=0.2, hatch='o', zorder=5)
    
    # --- MODIFICACIÓN DE ESTRUCTURA: Eliminando el grillado y las coordenadas ---
    # Se eliminan los grillados de grados para limpiar el mapa de ubicación.
    # if all(np.isfinite(bbox)):
    #     grillado_grados_mejorado(ax, bbox, ndiv=5, decimales=1)
    
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
    
    # Limpieza de ejes (ticks y labels) manteniendo el marco visible (ax.axis('on'))
    ax.tick_params(left=False, right=False, top=False, bottom=False, labelleft=False, labelbottom=False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axis('on') # Se mantiene 'on' para conservar el marco (spines) y el fondo.
    
    # Asegurar que el marco sea visible
    for spine in ax.spines.values():
        spine.set_edgecolor('black')
        spine.set_linewidth(1.2)
        spine.set_visible(True)

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

# FUNCIÓN PARA OBTENER RUTAS DE CAPAS SEGÚN PROVINCIA
def obtener_rutas_capas(provincia_sel):
    """
    Obtiene las rutas de las capas de peligro según la provincia seleccionada.
    """
    provincia_upper = provincia_sel.upper()
    
    if provincia_upper not in CAPAS_POR_PROVINCIA:
        print(f"❌ Error: La provincia '{provincia_sel}' no está configurada.")
        print(f"   Provincias disponibles: {list(CAPAS_POR_PROVINCIA.keys())}")
        return None
    
    rutas = CAPAS_POR_PROVINCIA[provincia_upper]
    
    print(f"\n📂 Verificando archivos para provincia: {provincia_upper}")
    archivos_validos = True
    
    for tipo_capa, ruta in rutas.items():
        if os.path.exists(ruta):
            print(f"   ✅ {tipo_capa}: {os.path.basename(ruta)}")
        else:
            print(f"   ❌ {tipo_capa}: NO ENCONTRADO - {ruta}")
            archivos_validos = False
    
    if not archivos_validos:
        print(f"\n❌ Faltan archivos para la provincia {provincia_upper}")
        return None
    
    return rutas
    
# ════════════════════════════════════════════════════════════════════════════════════
# 🚀 FUNCIÓN PRINCIPAL DE GENERACIÓN DE MAPA (MODIFICADA PARA ACEPTAR USUARIO)
# ════════════════════════════════════════════════════════════════════════════════════

def generar_mapa_peligro_deslizamiento(distrito, provincia, departamento="PIURA", nombre_usuario=None):
    """
    Genera el mapa de peligro (susceptibilidad) para un distrito específico
    combinando 4 capas, con una opción de carpeta de guardado personalizada.
    """
    
    distrito_upper = distrito.upper()
    provincia_upper = provincia.upper()
    
    # 🔑 Sanitizar el argumento 'departamento'
    if re.search(r'[/\\]', str(departamento)) or len(str(departamento)) > 20:
        departamento_upper = "PIURA"
    else:
        departamento_upper = str(departamento).upper()

    # 💡 Configuración: Usar un CRS UTM estándar para Piura (Zona 17 Sur) para la intersección
    UTM_CRS = 32717 

    print("="*80)
    print(f"🔥 INICIANDO GENERACIÓN DE MAPA DE PELIGRO POR DESLIZAMIENTO (4 PARÁMETROS)")
    print(f"   Distrito: {distrito_upper}, Provincia: {provincia_upper}, Dpto: {departamento_upper}")
    print(f"   CRS de Intersección (UTM): EPSG:{UTM_CRS}")
    print("="*80)
    
    # 1. Cargar capas administrativas (usando cargar_capa_admin -> EPSG:3857)
    try:
        gdf_distritos = cargar_capa_admin(RUTA_DISTRITOS, "DISTRITOS")
        gdf_provincias = cargar_capa_admin(RUTA_PROVINCIAS, "PROVINCIAS")
        gdf_departamentos = cargar_capa_admin(RUTA_DEPARTAMENTOS, "DEPARTAMENTOS")
        gdf_ccpp = cargar_capa_admin(RUTA_CENTROS_POBLADOS, "CENTROS POBLADOS")
        gdf_oceano = cargar_capa_admin(RUTA_OCEANO, "OCÉANO")
        
        if gdf_distritos is None:
             print(f"❌ Error fatal al cargar GeoDataFrame de DISTRITOS.")
             return None
             
    except Exception as e:
        print(f"❌ Error al cargar capas base: {e}")
        return None

    # Filtrar el distrito, provincia y departamento de interés
    try:
        gdf_distrito_sel = gdf_distritos[
            (gdf_distritos[COL_DIST] == distrito_upper) & 
            (gdf_distritos[COL_PROV] == provincia_upper) & 
            (gdf_distritos[COL_DPTO] == departamento_upper)
        ]
        
        if gdf_distrito_sel.empty:
            print(f"❌ Distrito '{distrito}' no encontrado en el GeoDataFrame con los filtros aplicados (Dpto: {departamento_upper}).")
            return None

        gdf_provincia_sel = gdf_provincias[
            (gdf_provincias[COL_PROV] == provincia_upper) & 
            (gdf_provincias[COL_DPTO] == departamento_upper)
        ]
        
        gdf_dpto_sel = gdf_departamentos[
            (gdf_departamentos[COL_DPTO] == departamento_upper)
        ]

    except KeyError as e:
        print(f"❌ Error: Columna de filtro no encontrada. Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error filtrando capas: {e}")
        return None


    # 2. Cargar capas de peligro específicas (usando cargar_capa_peligro -> EPSG:32717)
    rutas_capas = obtener_rutas_capas(provincia_upper)
    if not rutas_capas:
        return None

    capas_peligro = {}
    for nombre, ruta in rutas_capas.items():
        print(f"   Cargando capa {nombre}...")
        # Llama a la nueva función que proyecta a UTM_CRS (32717) y repara geometría
        gdf = cargar_capa_peligro(ruta, nombre, UTM_CRS) 
        
        if gdf is None:
            print(f"❌ Error CRÍTICO: La capa '{nombre}' no pudo ser cargada/proyectada.")
            return None
            
        capas_peligro[nombre] = gdf
    
    if len(capas_peligro) < 4:
        print("❌ Error: Faltan capas de peligro (se requieren 4). Abortando.")
        return None

    # 3. Intersección, filtro y cálculo de índice de peligro
    
    # 1. Proyectar el límite del distrito al CRS UTM estándar (UTM_CRS = 32717)
    # gdf_distrito_sel está en 3857, necesitamos proyectarlo a 32717 para la intersección.
    distrito_proj_utm = gdf_distrito_sel.to_crs(epsg=UTM_CRS)
    distrito_geom_union = distrito_proj_utm.geometry.unary_union
    
    # Validación de geometría del distrito
    if not distrito_geom_union.is_valid:
        print("⚠️ Advertencia: La geometría del distrito no es válida. Intentando repararla...")
        distrito_geom_union = distrito_geom_union.buffer(0).buffer(0) 

    # DEBUG: Mostrar Bounding Boxes (en UTM)
    x0, y0, x1, y1 = distrito_geom_union.bounds
    print(f"\n   📏 Extensión (BBox) del Distrito de {distrito_upper} (UTM {UTM_CRS}): X:[{x0:.0f} - {x1:.0f}], Y:[{y0:.0f} - {y1:.0f}]")
    
    gdf_final = None
    
    print("\n🔬 Procesando capas de peligro y calculando índice...")
    
    for nombre, gdf_capa_utm in capas_peligro.items():
        try:
            col_peso_especifico = PESO_COLUMNAS_MAP.get(nombre)
            columna_salida = f'P_{nombre}' 
            
            # 1. Comprobar si la columna existe en la capa
            if col_peso_especifico not in gdf_capa_utm.columns:
                print(f"❌ Error crítico: La capa '{nombre}' NO tiene la columna de peso esperada '{col_peso_especifico}'. Columnas disponibles: {list(gdf_capa_utm.columns)}")
                return None

            # DEBUG: Mostrar BBox de la capa antes de recortar (ya está en UTM_CRS)
            gx0, gy0, gx1, gy1 = gdf_capa_utm.total_bounds
            print(f"   📏 Extensión (BBox) de la capa {nombre} (UTM {UTM_CRS}): X:[{gx0:.0f} - {gx1:.0f}], Y:[{gy0:.0f} - {gy1:.0f}]")

            # 3. Recortar la capa al límite del distrito 
            gdf_recortada = gpd.clip(gdf_capa_utm, distrito_geom_union)
            
            # 4. Verificar si el recorte fue exitoso
            if gdf_recortada.empty:
                print(f"❌ Alerta: La capa '{nombre}' quedó **VACÍA** después de recortar con el distrito de {distrito_upper}.")
                return None

            # 5. Seleccionar la columna de peso y renombrarla
            gdf_select_renamed = gdf_recortada[[col_peso_especifico, 'geometry']].copy()
            
            try:
                 gdf_select_renamed[col_peso_especifico] = pd.to_numeric(gdf_select_renamed[col_peso_especifico], errors='coerce')
            except Exception as e:
                print(f"⚠️ Advertencia: Error al convertir la columna '{col_peso_especifico}' de {nombre} a numérica: {e}")

            gdf_select_renamed.rename(columns={col_peso_especifico: columna_salida}, inplace=True)
            
            # 6. Realizar la operación de superposición (overlay)
            if gdf_final is None:
                gdf_final = gdf_select_renamed.copy()
                # 💡 CORRECCIÓN 1/2: Normalizar la geometría de la primera capa con buffer(0)
                gdf_final.geometry = gdf_final.buffer(0) 
                print(f"   GDF inicializado con {nombre}. Filas: {len(gdf_final)}")
            else:
                print(f"   Realizando overlay de GDF acumulado ({len(gdf_final)} filas) con capa {nombre} ({len(gdf_select_renamed)} filas)...")
                
                # Realizar la intersección para combinar los atributos de las capas
                gdf_final = gpd.overlay(gdf_final, gdf_select_renamed, how='intersection', keep_geom_type=False)
                
                # 💡 CORRECCIÓN 2/2: Normalizar la geometría después de cada intersección para evitar errores de tipos mixtos (Polygon/MultiPolygon)
                # Esto resuelve el error "NotImplementedError: df1 contains mixed geometry types."
                gdf_final.geometry = gdf_final.buffer(0)
                
                print(f"   Resultado del overlay: {len(gdf_final)} filas.")
                
                # 7. Verificar el resultado de la intersección
                if gdf_final.empty:
                    print(f"❌ Error: El resultado de la intersección de capas se vació después de procesar '{nombre}'. Esto indica que no hay áreas de coincidencia entre las capas.")
                    return None
                
        except Exception as e:
            print(f"❌ Error CRÍTICO durante la intersección/recorte con {nombre}: {e}")
            traceback.print_exc()
            return None

    # 4. Cálculo del índice de peligro (Promedio Ponderado)
    if gdf_final is not None and not gdf_final.empty:
        columnas_peso = [col for col in gdf_final.columns if col.startswith('P_')]

        # Verificar que se hayan definido las ponderaciones
        try:
            if not all(col in PONDERACIONES for col in columnas_peso):
                # Esto solo si se cambia el nombre de las columnas P_X en PESO_COLUMNAS_MAP
                print(f"❌ Error: Las ponderaciones no están definidas para todas las columnas de peso encontradas: {columnas_peso}")
                return None
        except NameError:
             # Esto ocurre si el diccionario PONDERACIONES no fue definido globalmente.
             print("❌ Error CRÍTICO: El diccionario 'PONDERACIONES' no está definido en el ámbito global.")
             return None
            
        if len(columnas_peso) == 4:
            
            # Re-confirmar que las columnas son numéricas antes de la suma
            for col in columnas_peso:
                 gdf_final[col] = pd.to_numeric(gdf_final[col], errors='coerce').fillna(0)
            
            # 🎯 Implementación del Promedio Ponderado (Suma de Pesos * Valores, sin división por 1.0)
            gdf_final['INDICE_PELIGRO'] = (
                gdf_final['P_GEOLOGIA'] * PONDERACIONES['P_GEOLOGIA'] +
                gdf_final['P_GEOMORFOLOGIA'] * PONDERACIONES['P_GEOMORFOLOGIA'] +
                gdf_final['P_PENDIENTE'] * PONDERACIONES['P_PENDIENTE'] +
                gdf_final['P_PPMAX'] * PONDERACIONES['P_PPMAX']
            )

            # Rango resultante es de 1.0 a 4.0.
            bins = [1.00, 2.00, 3.00, 4.00, 4.01] 
            
            gdf_final['NIVEL_PELIGRO'] = pd.cut(
                gdf_final['INDICE_PELIGRO'], 
                bins=bins, 
                labels=[1, 2, 3, 4], 
                right=False, 
                include_lowest=True
            ).astype(float)
            
            gdf_final['COLOR_PELIGRO'] = gdf_final['NIVEL_PELIGRO'].apply(asignar_color_peligro)
            print("   ✅ Cálculo del Índice y Nivel de Peligro completado (PROMEDIO PONDERADO).")
        else:
            print(f"❌ Error: Se esperaban 4 columnas de peso, se encontraron {len(columnas_peso)}. Columnas: {columnas_peso}")
            return None
    else:
        print("❌ El GeoDataFrame final de peligro está vacío. Falló en una intersección previa.")
        return None

    # 5. Preparación de Centros Poblados y Proyección
    # Proyectamos el resultado final a 3857 para el mapa con contextily
    gdf_peligro_plot = gdf_final.to_crs(epsg=3857) 
    
    # El GeoDataFrame del distrito seleccionado (gdf_distrito_sel) ya está en 3857
    gdf_distrito_sel_3857 = gdf_distrito_sel 
    
    # Recortar los CCPP que caen dentro del distrito usando sjoin.
    try:
        gdf_ccpp_dentro_proj = gpd.sjoin(gdf_ccpp, gdf_distrito_sel_3857, op='within', how='inner')
        
        cols_to_drop = [col for col in gdf_ccpp_dentro_proj.columns if col.startswith('index_')]
        gdf_ccpp_dentro_proj = gdf_ccpp_dentro_proj.drop(columns=cols_to_drop, errors='ignore')

    except Exception as e:
        print(f"⚠️ Advertencia: Error al realizar el sjoin de CCPP: {e}. Usando GeoDataFrame vacío para CCPP.")
        gdf_ccpp_dentro_proj = gpd.GeoDataFrame(geometry=[], crs=3857)

    # 6. Generación del Mapa
    fig = plt.figure(figsize=(12, 16))
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 0.4], width_ratios=[1, 1, 1])
    
    ax_mapa = fig.add_subplot(gs[:, 0:2])
    
    ax_loc_dpto = fig.add_subplot(gs[0, 2])
    ax_loc_prov = fig.add_subplot(gs[1, 2])
    ax_membrete = fig.add_subplot(gs[2, 2])
    
    # --- Dibujo del Mapa Principal ---
    
    ctx.add_basemap(ax_mapa, crs=gdf_peligro_plot.crs.to_string(), source=ctx.providers.OpenStreetMap.Mapnik, zoom=12)
    
    gdf_peligro_plot.plot(ax=ax_mapa, color=gdf_peligro_plot['COLOR_PELIGRO'], edgecolor='none', alpha=0.95, zorder=5)
    
    gdf_distrito_sel_3857.plot(ax=ax_mapa, facecolor='none', edgecolor='black', linewidth=1.5, zorder=6)
    
    agregar_etiquetas_ordenadas_circularmente(
        gdf_distrito_sel_3857, 
        gdf_ccpp_dentro_proj, 
        ax_mapa
    )
    
    ax_mapa.set_title(f"MAPA DE SUSCEPTIBILIDAD A DESLIZAMIENTOS PLUVIALES\nDISTRITO DE {distrito_upper}", 
                      fontsize=14, fontweight='bold', pad=15)
    
    x_min, y_min, x_max, y_max = gdf_peligro_plot.total_bounds
    ax_mapa.set_xlim(x_min, x_max)
    ax_mapa.set_ylim(y_min, y_max)
    ax_mapa.set_aspect('equal', adjustable='box')

    add_north_arrow_blanco_completo(ax_mapa)
    ax_mapa.add_artist(ScaleBar(1.0, units='km', location='lower left', box_alpha=0.8, 
                                frameon=True, color='black', box_color='white'))
    
    grillado_utm_proyectado(ax_mapa, (x_min, y_min, x_max, y_max), ndiv=8)


    # --- Dibujo de Mapas de Ubicación ---
    
    distritos_provincia = gdf_distritos[
        (gdf_distritos[COL_PROV] == provincia_upper) & 
        (gdf_distritos[COL_DPTO] == departamento_upper)
    ]
    
    # Mapa de Ubicación Departamental (Limpio)
    mapa_ubicacion(ax_loc_dpto, gdf_departamentos, gdf_dpto_sel, gdf_provincia_sel, 
                   "UBICACIÓN DEPARTAMENTAL", provincia_upper, "provincia",
                   gdf_dpto_sel=gdf_dpto_sel, gdf_prov_sel=gdf_provincia_sel,
                   departamento_sel=departamento_upper, provincia_sel=provincia_upper,
                   col_prov=COL_PROV, col_dpto=COL_DPTO, gdf_departamentos=gdf_departamentos,
                   gdf_provincias=gdf_provincias, gdf_oceano=gdf_oceano)

    # Mapa de Ubicación Provincial (Limpio)
    mapa_ubicacion(ax_loc_prov, distritos_provincia, gdf_provincia_sel, gdf_distrito_sel, 
                   "UBICACIÓN PROVINCIAL", distrito_upper, "distrito",
                   gdf_dpto_sel=gdf_dpto_sel, gdf_prov_sel=gdf_provincia_sel,
                   departamento_sel=departamento_upper, provincia_sel=provincia_upper,
                   col_prov=COL_PROV, col_dpto=COL_DPTO, gdf_departamentos=gdf_departamentos,
                   gdf_provincias=gdf_provincias, gdf_oceano=gdf_oceano)

    # --- Membrete y Leyenda ---

    add_membrete(ax_membrete, departamento_upper, provincia_upper, distrito_upper, ax_mapa, fig)
    
    # Posición de la leyenda ajustada para no superponerse
    ax_leyenda = fig.add_axes([0.70, 0.35, 0.2, 0.25], frameon=False) 
    ax_leyenda.axis('off')
    
    legend_handles = []
    
    for color, label in zip(COLORES_PELIGRO, ETIQUETAS_PELIGRO):
        patch = Patch(facecolor=color, edgecolor='black', linewidth=0.5, label=label)
        legend_handles.append(patch)
        
    ccpp_handle = Line2D([0], [0], marker='o', color='w', label='Centros Poblados',
                         markerfacecolor='#006400', markersize=6, linestyle='None')
    legend_handles.append(ccpp_handle)
    
    ax_leyenda.legend(handles=legend_handles, title="Nivel de Susceptibilidad", 
                      loc='center', frameon=True, fontsize=7, title_fontsize=9,
                      framealpha=0.9, fancybox=True, edgecolor='black')

    # 11. Guardado del mapa (MODIFICACIÓN AQUÍ para carpeta de usuario)
    
    # Determinar el directorio de salida
    if nombre_usuario:
        # Ruta personalizada para el usuario: /workspaces/AUTOMATIZACION_DASH/PRUEBA/USUARIOS/{nombre_usuario}
        output_dir = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
    else:
        # Ruta por defecto original (si no se proporciona usuario)
        output_dir = os.path.join(ruta_base, "RESULTADOS", "MAPAS_DE_PELIGRO", provincia_upper, distrito_upper)
    
    os.makedirs(output_dir, exist_ok=True)
    nombre_archivo = f"MAPA_PELIGRO_DESLIZAMIENTO_{distrito_upper}_{provincia_upper}_4P.png"
    ruta_guardado_final = os.path.join(output_dir, nombre_archivo)
    
    # Ajustar tight_layout para mejor espaciado
    fig.tight_layout(rect=[0, 0.0, 1, 1]) 
    
    try:
        fig.savefig(ruta_guardado_final, dpi=300, bbox_inches='tight')
        plt.close(fig)

        print("="*80)
        print(f"✅ Mapa de peligro guardado exitosamente")
        print(f"   📁 Ubicación: {ruta_guardado_final}")
        print("="*80 + "\n")
        return ruta_guardado_final
    except Exception as e:
        print(f"❌ Error al guardar el archivo: {e}")
        plt.close(fig)
        return None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🚀 EJECUCIÓN DEL SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # EJEMPLO DE USO (se añade el nombre de usuario para probar el guardado)
    distrito_ejemplo = "PIURA"
    provincia_ejemplo = "PIURA"
    departamento_ejemplo = "PIURA"
    
    # Nombre de usuario para la subcarpeta de guardado
    nombre_usuario_ejemplo = "USUARIO_EJEMPLO_PRUEBA1" 

    print(f"📌 Ejecutando script con guardado personalizado para: {nombre_usuario_ejemplo}")
    generar_mapa_peligro_deslizamiento(
        distrito_ejemplo, 
        provincia_ejemplo, 
        departamento_ejemplo,
        nombre_usuario=nombre_usuario_ejemplo 
    )