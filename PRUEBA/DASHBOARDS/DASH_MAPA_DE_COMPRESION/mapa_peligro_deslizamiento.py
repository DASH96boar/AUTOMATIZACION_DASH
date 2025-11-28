# -*- coding: utf-8 -*-
"""
🎯 SCRIPT INTEGRADO: MAPA DE PELIGRO CON 4 PARÁMETROS + CENTROS POBLADOS

MODIFICACIONES IMPLEMENTADAS:
- 1. ✅ CORRECCIÓN CRÍTICA (mapa_ubicacion): Se corrige el 'AttributeError: 'NoneType' object has no attribute 'total_bounds''
      dentro de 'mapa_ubicacion' (para tipo_mapa='provincia') al usar `gdf_context`.
- 2. ✅ CORRECCIÓN DE GUARDADO (fig.savefig): Se elimina 'bbox_inches='tight'' y se maneja el error de 'tight_layout'
      para prevenir fallos silenciosos/cuelgues durante el renderizado final (causa del error 'Archivo no generado').
- 3. ✅ Se mantienen las proporciones de layout más compactas.
- 4. ✅ AJUSTE DE COLOR: Se cambia el Verde Lima por un Verde Oscuro (#33A02C) para mejor contraste en el nivel 'Baja' (1).
- 5. 🚨 AJUSTE CRÍTICO DE CLASIFICACIÓN (FINAL): Se usa la función 'asignar_color_peligro' con umbrales ajustados 
      a [1.75, 2.50, 3.25] para convertir zonas Verdes/Amarillas en Rojas/Naranjas, respetando la estructura solicitada.
"""

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
PONDERACIONES = {
    "P_GEOLOGIA": 0.20,      
    "P_GEOMORFOLOGIA": 0.25, 
    "P_PENDIENTE": 0.45,     
    "P_PPMAX": 0.10          
}
# ===============================================================================

RUTA_PROVINCIAS = f"{ruta_base}/DATA/MAPA DE UBICACION/PROVINCIAS DEL PERU/PROVINCIAS_inei_geogpsperu_suyopomalia.shp"
RUTA_DEPARTAMENTOS = f"{ruta_base}/DATA/MAPA DE UBICACION/DEPARTAMENTOS_DEL_PERU/DEPARTAMENTOS_inei_geogpsperu_suyopomalia.shp"
RUTA_OCEANO = f"{ruta_base}/DATA/MAPA DE UBICACION/OCEANO/Océano.shp"

# PALETA DE COLORES PARA NIVELES DE PELIGRO
COLORES_PELIGRO = ['#33A02C', '#FFFF00', '#FFA500', '#FF0000'] # Verde Oscuro (Baja), Amarillo (Media), Naranja (Alta), Rojo (Muy Alta)
ETIQUETAS_PELIGRO = ['Baja', 'Media', 'Alta', 'Muy Alta']

# ==================== NOMBRES DE COLUMNAS ====================
COL_DPTO = 'NOMBDEP' 
COL_PROV = 'NOMBPROV' 
COL_DIST = 'NOMBDIST' 
COL_CCPP = 'NOMB_CCPP' 

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIONES DE ETIQUETADO DE CENTROS POBLADOS
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

def agregar_etiquetas_ordenadas_circularmente(gdf_distritos, gdf_centros_poblados, ax, radio_offset=0.12):
    """
    Agrega etiquetas de centros poblados FUERA del límite distrital de manera ordenada.
    """
    
    if gdf_centros_poblados is None or len(gdf_centros_poblados) == 0:
        return
    
    # CORRECCIÓN DE DEPRECACIÓN: Usar union_all()
    distrito_boundary = gdf_distritos.boundary.union_all()
    
    try:
        # CORRECCIÓN DE DEPRECACIÓN: Usar union_all()
        distrito_merged = gdf_distritos.union_all()
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
# FUNCIONES AUXILIARES PARA MAPAS Y CARGA DE DATOS 
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
            
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
            
        return gdf.to_crs(epsg=3857)
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
            
        current_crs_epsg = gdf.crs.to_epsg() if gdf.crs else None
        
        if current_crs_epsg != target_utm_crs:
            print(f"   🔄 Reproyectando {alias} de {gdf.crs.to_string() if gdf.crs else 'sin CRS'} a EPSG:{target_utm_crs}")
            gdf = gdf.to_crs(epsg=target_utm_crs)
        
        if not gdf.geometry.is_valid.all():
            print(f"   ⚠️ Reparando geometrías inválidas de {alias}...")
            gdf.geometry = gdf.buffer(0).simplify(0.001) 
        
        if not all(np.isfinite(gdf.total_bounds)):
             print(f"❌ Error CRÍTICO: BBox de {alias} es inválida incluso después de reparación. Abortando.")
             return None
            
        return gdf
    except Exception as e:
        print(f"   ❌ Error cargando/proyectando {alias} a UTM {target_utm_crs}: {e}")
        traceback.print_exc()
        return None

def add_north_arrow_blanco_completo(ax, xy_pos=(0.95, 0.95), size=0.06):
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
    """
    Agrega el membrete. La altura total de la caja es muy reducida para ser un pie de página compacto.
    """
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
    
    # 🎯 Ajuste de límites: Altura reducida de 4 a 1.0 (más compacto que 1.5)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1.0) 
    ax.axis('off')
    
    # Dibuja la cuadrícula del membrete (Altura total 1.0)
    ax.add_patch(Rectangle((0, 0), 10, 1.0, fill=False, edgecolor='black', lw=1.2))
    ax.plot([0, 10], [0.65, 0.65], color='black', lw=1.2) # Línea superior (Título)
    ax.plot([0, 7.5], [0.35, 0.35], color='black', lw=1.2) # Línea media
    ax.plot([2.5, 2.5], [0.35, 0.65], color='black', lw=1.2)
    ax.plot([5, 5], [0, 0.65], color='black', lw=1.2)
    ax.plot([7.5, 7.5], [0, 0.65], color='black', lw=1.2)
    
    # Agrega el texto del membrete (ajustando las posiciones Y)
    padding = 0.15
    font_size_small = 6.0
    font_size_medium = 7.0
    
    ax.text(0 + padding, 0.85, "MAPA:", fontweight='bold', va='center', fontsize=font_size_medium)
    ax.text(1.8 + padding, 0.85, info["MAPA"], va='center', fontsize=font_size_medium)
    
    # Fila de Títulos (Y=0.5)
    ax.text(0 + padding, 0.5, "DPTO:", fontweight='bold', va='center', fontsize=font_size_small)
    ax.text(2.5 + padding, 0.5, "PROVINCIA:", fontweight='bold', va='center', fontsize=font_size_small)
    ax.text(5 + padding, 0.5, "DISTRITO:", fontweight='bold', va='center', fontsize=font_size_small)
    ax.text(7.5 + padding, 0.5, "MAPA Nº", fontweight='bold', ha='left', va='center', fontsize=font_size_small)
    
    # Fila de Contenido (Y=0.17)
    ax.text(0 + padding, 0.17, info["DPTO"], va='center', fontsize=font_size_small)
    ax.text(2.5 + padding, 0.17, info["PROVINCIA"], va='center', fontsize=font_size_small)
    ax.text(5 + padding, 0.17, info["DISTRITO"], va='center', fontsize=font_size_small)
    ax.text(7.5 + padding, 0.17, info["MAPA_N"], ha='left', va='center', fontsize=font_size_medium)


def grillado_utm_proyectado(ax, bbox, ndiv=8):
    x0, y0, x1, y1 = bbox
    
    def fmt_este(x, pos):
        num_str = f"{int(x):06d}"
        return num_str[:3] + " " + num_str[3:] + " E"
    
    def fmt_norte(y, pos):
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

def mapa_ubicacion(ax, gdf_base_map, gdf_context, gdf_focus, titulo, etiqueta, tipo_mapa, 
                   gdf_dpto_sel=None, gdf_prov_sel=None, col_prov=COL_PROV, col_dpto=COL_DPTO, 
                   departamento_sel=None, provincia_sel=None, gdf_departamentos=None, 
                   gdf_provincias=None, gdf_oceano=None):
    
    is_focus_valid = not gdf_focus.empty and all(np.isfinite(gdf_focus.total_bounds))
    
    if tipo_mapa == "departamento": 
        # Usa el GeoDataFrame de departamentos (pasado como palabra clave) para la extensión nacional
        bbox_geom = gdf_departamentos.total_bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.25, (bbox_geom[3] - bbox_geom[1]) * 0.25
        
    elif tipo_mapa == "provincia": 
        # FIX CRÍTICO: Usar gdf_context (que es gdf_dpto_sel) para la extensión departamental
        if gdf_context.empty:
             print("⚠️ Advertencia: gdf_context (departamento) está vacío en mapa_ubicacion.")
             return 
             
        # CÓDIGO CORREGIDO: Usar gdf_context que es el dpto (gdf_dpto_sel)
        bbox_geom = gdf_context.total_bounds 
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.15, (bbox_geom[3] - bbox_geom[1]) * 0.15

    elif tipo_mapa == "distrito": 
        # CORRECCIÓN DE DEPRECACIÓN: Usar union_all()
        provincia_seleccionada_geom = gdf_prov_sel.geometry.union_all()
        try:
            geoms_vecinas = [prov.geometry for _, prov in gdf_provincias.iterrows() 
                            if prov[col_prov] != provincia_sel and prov.geometry.touches(provincia_seleccionada_geom)]
            # CORRECCIÓN DE DEPRECACIÓN: Usar union_all()
            area_de_interes = gpd.GeoSeries([provincia_seleccionada_geom] + geoms_vecinas, crs=gdf_prov_sel.crs).union_all()
        except:
            area_de_interes = provincia_seleccionada_geom
            
        bbox_geom = area_de_interes.bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.1, (bbox_geom[3] - bbox_geom[1]) * 0.1
        
    else: 
        bbox_geom = gdf_departamentos.total_bounds
        dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.25, (bbox_geom[3] - bbox_geom[1]) * 0.25
    
    x0, y0, x1, y1 = bbox_geom[0] - dx, bbox_geom[1] - dy, bbox_geom[2] + dx, bbox_geom[3] + dy
    S = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bbox = (cx - S / 2, cy - S / 2, cx + S / 2, cy + S / 2)
    
    if gdf_oceano is not None:
        gdf_oceano.clip(box(*bbox)).plot(ax=ax, color="#A4D4FF", edgecolor="none", zorder=2)
    
    if tipo_mapa == "departamento":
        gdf_departamentos.plot(ax=ax, color="#f0eee8", edgecolor="black", linewidth=0.4, zorder=1)
        # Usar gdf_dpto_sel (opcional) para dibujar el foco, ya que gdf_focus es la bandera
        if gdf_dpto_sel is not None:
             gdf_dpto_sel.plot(ax=ax, color=AMARILLO_CLARO, edgecolor="black", linewidth=1.0, zorder=3)
        
    elif tipo_mapa == "provincia":
        gdf_departamentos.plot(ax=ax, color="#f0eee8", edgecolor="gray", linewidth=0.4, zorder=1)
        if gdf_context is not None: # gdf_context es el departamento seleccionado (gdf_dpto_sel)
             gdf_context.plot(ax=ax, facecolor='none', edgecolor="black", linewidth=0.8, zorder=2)
        if gdf_prov_sel is not None:
             gdf_prov_sel.plot(ax=ax, color=AMARILLO_CLARO, edgecolor="black", linewidth=1.0, zorder=3)
        
    elif tipo_mapa == "distrito":
        if gdf_provincias is not None:
            gdf_provincias[gdf_provincias[col_prov] != provincia_sel].plot(
                ax=ax, color='lightgray', edgecolor='darkgray', linewidth=0.4, zorder=2)
        if gdf_prov_sel is not None:
             gdf_prov_sel.plot(ax=ax, color=AMARILLO_CLARO, edgecolor='black', linewidth=0.7, zorder=3)
        gdf_context.plot(ax=ax, facecolor='none', edgecolor="gray", linewidth=0.4, zorder=4)

    if is_focus_valid:
        # gdf_focus aquí es el distrito, provincia o dpto que queremos resaltar.
        gdf_focus.plot(ax=ax, facecolor="red", edgecolor="red", linewidth=0.2, hatch='o', zorder=5)
    
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
    
    ax.tick_params(left=False, right=False, top=False, bottom=False, labelleft=False, labelbottom=False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axis('on') 
    
    for spine in ax.spines.values():
        spine.set_edgecolor('black')
        spine.set_linewidth(1.2)
        spine.set_visible(True)

def obtener_rutas_capas(provincia_sel):
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
# 🚨 FUNCIÓN DE ASIGNACIÓN DE COLOR MODIFICADA CON UMBRALES AGRESIVOS
# ════════════════════════════════════════════════════════════════════════════════════
def asignar_color_peligro(valor):
    """
    Asigna el color basado en el Índice de Peligro (valor), 
    usando umbrales más agresivos para forzar más zonas rojas/naranjas.
    """
    if valor is None or pd.isna(valor):
        return COLORES_PELIGRO[0] # Default

    # 🚨 AJUSTE CRÍTICO: Umbrales [1.75, 2.50, 3.25]
    if 1.00 <= valor < 1.75:
        return COLORES_PELIGRO[0] # Verde Oscuro (Baja)
    elif 1.75 <= valor < 2.50:
        return COLORES_PELIGRO[1] # Amarillo (Media)
    elif 2.50 <= valor < 3.25:
        return COLORES_PELIGRO[2] # Naranja (Alta)
    elif 3.25 <= valor <= 5.00:
        return COLORES_PELIGRO[3] # Rojo (Muy Alta)
    else:
        return COLORES_PELIGRO[0]


# ════════════════════════════════════════════════════════════════════════════════════
# 🚀 FUNCIÓN PRINCIPAL DE GENERACIÓN DE MAPA (CON LÓGICA DE CLASIFICACIÓN CORREGIDA)
# ════════════════════════════════════════════════════════════════════════════════════

def generar_mapa_peligro_deslizamiento(distrito, provincia, departamento="PIURA", nombre_usuario=None):
    """
    Genera el mapa de peligro (susceptibilidad) para un distrito específico
    combinando 4 capas. Implementa el layout 4x2 con proporciones ajustadas.
    """
    
    distrito_upper = distrito.upper()
    provincia_upper = provincia.upper()
    
    if re.search(r'[/\\]', str(departamento)) or len(str(departamento)) > 20:
        departamento_upper = "PIURA"
    else:
        departamento_upper = str(departamento).upper()

    UTM_CRS = 32717 

    print("="*80)
    print(f"🔥 INICIANDO GENERACIÓN DE MAPA DE PELIGRO POR DESLIZAMIENTOS PLUVIALES (4 PARÁMETROS)")
    print(f"   Distrito: {distrito_upper}, Provincia: {provincia_upper}, Dpto: {departamento_upper}")
    print(f"   CRS de Intersección (UTM): EPSG:{UTM_CRS}")
    print("="*80)
    
    # 1. Cargar capas administrativas
    try:
        gdf_distritos = cargar_capa_admin(RUTA_DISTRITOS, "DISTRITOS")
        gdf_provincias = cargar_capa_admin(RUTA_PROVINCIAS, "PROVINCIAS")
        gdf_departamentos = cargar_capa_admin(RUTA_DEPARTAMENTOS, "DEPARTAMENTOS")
        gdf_ccpp = cargar_capa_admin(RUTA_CENTROS_POBLADOS, "CENTROS POBLADOS")
        gdf_oceano = cargar_capa_admin(RUTA_OCEANO, "OCÉANO")
        
        if gdf_distritos is None or gdf_provincias is None or gdf_departamentos is None:
             print(f"❌ Error fatal al cargar una o más GeoDataFrame base (DISTRITOS, PROVINCIAS, DEPARTAMENTOS).")
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
            print(f"❌ Distrito '{distrito}' no encontrado.")
            return None

        gdf_provincia_sel = gdf_provincias[
            (gdf_provincias[COL_PROV] == provincia_upper) & 
            (gdf_provincias[COL_DPTO] == departamento_upper)
        ]
        
        gdf_dpto_sel = gdf_departamentos[
            (gdf_departamentos[COL_DPTO] == departamento_upper)
        ]
        
        if gdf_dpto_sel.empty or gdf_provincia_sel.empty:
             print(f"❌ Error: Departamento/Provincia '{departamento_upper}/{provincia_upper}' no encontrado/a en la capa administrativa.")

    except KeyError as e:
        print(f"❌ Error: Columna de filtro no encontrada. Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error filtrando capas: {e}")
        return None

    # 2. Cargar capas de peligro específicas
    rutas_capas = obtener_rutas_capas(provincia_upper)
    if not rutas_capas:
        return None

    capas_peligro = {}
    for nombre, ruta in rutas_capas.items():
        gdf = cargar_capa_peligro(ruta, nombre, UTM_CRS) 
        if gdf is None:
            print(f"❌ Error CRÍTICO: La capa '{nombre}' no pudo ser cargada/proyectada.")
            return None
        capas_peligro[nombre] = gdf
    
    if len(capas_peligro) < 4:
        print("❌ Error: Faltan capas de peligro (se requieren 4). Abortando.")
        return None

    # 3. Intersección, filtro y cálculo de índice de peligro
    distrito_proj_utm = gdf_distrito_sel.to_crs(epsg=UTM_CRS)
    # CORRECCIÓN DE DEPRECACIÓN: Usar union_all()
    distrito_geom_union = distrito_proj_utm.geometry.union_all()
    
    if not distrito_geom_union.is_valid:
        distrito_geom_union = distrito_geom_union.buffer(0).buffer(0) 

    print("\n🔬 Procesando capas de peligro y calculando índice...")
    
    gdf_final = None
    
    for nombre, gdf_capa_utm in capas_peligro.items():
        try:
            col_peso_especifico = PESO_COLUMNAS_MAP.get(nombre)
            columna_salida = f'P_{nombre}' 
            
            if col_peso_especifico not in gdf_capa_utm.columns:
                print(f"❌ Error crítico: La capa '{nombre}' NO tiene la columna de peso esperada '{col_peso_especifico}'.")
                return None

            gdf_recortada = gpd.clip(gdf_capa_utm, distrito_geom_union)
            
            if gdf_recortada.empty:
                print(f"❌ Alerta: La capa '{nombre}' quedó **VACÍA** después de recortar.")
                return None

            gdf_select_renamed = gdf_recortada[[col_peso_especifico, 'geometry']].copy()
            
            try:
                 gdf_select_renamed[col_peso_especifico] = pd.to_numeric(gdf_select_renamed[col_peso_especifico], errors='coerce')
            except Exception as e:
                print(f"⚠️ Advertencia: Error al convertir la columna '{col_peso_especifico}' de {nombre} a numérica: {e}")

            gdf_select_renamed.rename(columns={col_peso_especifico: columna_salida}, inplace=True)
            
            if gdf_final is None:
                gdf_final = gdf_select_renamed.copy()
                gdf_final.geometry = gdf_final.buffer(0) 
            else:
                gdf_final = gpd.overlay(gdf_final, gdf_select_renamed, how='intersection', keep_geom_type=False)
                gdf_final.geometry = gdf_final.buffer(0)
                
                if gdf_final.empty:
                    print(f"❌ Error: El resultado de la intersección de capas se vació después de procesar '{nombre}'.")
                    return None
                
        except Exception as e:
            print(f"❌ Error CRÍTICO durante la intersección/recorte con {nombre}: {e}")
            traceback.print_exc()
            return None

    # Cálculo del índice de peligro
    if gdf_final is not None and not gdf_final.empty:
        columnas_peso = [col for col in gdf_final.columns if col.startswith('P_')]

        if len(columnas_peso) == 4:
            for col in columnas_peso:
                 gdf_final[col] = pd.to_numeric(gdf_final[col], errors='coerce').fillna(0)
            
            gdf_final['INDICE_PELIGRO'] = (
                gdf_final['P_GEOLOGIA'] * PONDERACIONES['P_GEOLOGIA'] +
                gdf_final['P_GEOMORFOLOGIA'] * PONDERACIONES['P_GEOMORFOLOGIA'] +
                gdf_final['P_PENDIENTE'] * PONDERACIONES['P_PENDIENTE'] +
                gdf_final['P_PPMAX'] * PONDERACIONES['P_PPMAX']
            )

            # 5. CLASIFICACIÓN DE PELIGRO Y ASIGNACIÓN DE COLOR 
            
            # Usamos los bins agresivos para el texto, hasta 5.01 para incluir el max (5.00)
            bins_agresivos = [1.00, 1.75, 2.50, 3.25, 5.01] 
            
            # Asignar la clasificación de texto (usando los bins agresivos)
            gdf_final['NIVEL_PELIGRO_TEXTO'] = pd.cut(
                gdf_final['INDICE_PELIGRO'], 
                bins=bins_agresivos, 
                labels=ETIQUETAS_PELIGRO, # ['Baja', 'Media', 'Alta', 'Muy Alta']
                right=False, 
                include_lowest=True
            ).astype(str)
            
            # 🚨 Asignar color usando la función modificada con umbrales agresivos.
            gdf_final['COLOR_PELIGRO'] = gdf_final['INDICE_PELIGRO'].apply(asignar_color_peligro)

            print(f"   ✅ Cálculo del Índice y Nivel de Peligro completado.")
            print(f"   ⚠️ Lógica de color ajustada: Umbrales agresivos: [1.75, 2.50, 3.25] para forzar más Rojos/Naranjas.")

        else:
            print(f"❌ Error: Se esperaban 4 columnas de peso, se encontraron {len(columnas_peso)}. Abortando.")
            return None
    else:
        print("❌ El GeoDataFrame final de peligro está vacío. Abortando.")
        return None

    # 5. Preparación de Centros Poblados y Proyección
    gdf_peligro_plot = gdf_final.to_crs(epsg=3857) 
    gdf_distrito_sel_3857 = gdf_distrito_sel 
    
    try:
        gdf_ccpp_dentro_proj = gpd.sjoin(gdf_ccpp, gdf_distrito_sel_3857, predicate='within', how='inner')
        cols_to_drop = [col for col in gdf_ccpp_dentro_proj.columns if col.startswith('index_')]
        gdf_ccpp_dentro_proj = gdf_ccpp_dentro_proj.drop(columns=cols_to_drop, errors='ignore')

    except Exception as e:
        gdf_ccpp_dentro_proj = gpd.GeoDataFrame(geometry=[], crs=3857)

    # 6. Generación del Mapa (LAYOUT 4x2 CON PROPORCIONES MÁS COMPACTAS)
    
    # 🎯 Ajuste 1: Figura menos vertical. Aspecto (18 ancho, 14 alto)
    fig = plt.figure(figsize=(18, 14)) 
    
    # 🎯 Ajuste 2: Reducción extrema de la altura de la fila inferior (Membrete/Leyenda)
    # Ratios de altura: [Mapa/Ubicación 1, Mapa/Ubicación 2, Mapa/Ubicación 3, Membrete/Leyenda]
    gs = fig.add_gridspec(
        4, 2, 
        height_ratios=[1.2, 1.2, 1.2, 0.25],  # 0.25 es muy compacto
        width_ratios=[2, 1]          
    )
    
    # --- Asignación de Paneles ---
    ax_mapa = fig.add_subplot(gs[0:3, 0])      
    ax_membrete = fig.add_subplot(gs[3, 0])    
    ax_loc_dpto = fig.add_subplot(gs[0, 1])    
    ax_loc_prov = fig.add_subplot(gs[1, 1])    
    ax_loc_dist = fig.add_subplot(gs[2, 1])    
    ax_leyenda = fig.add_subplot(gs[3, 1])     

    
    # --- Dibujo del Mapa Principal (ax_mapa) ---
    print("🛰️ Descargando imagen satelital...")
    ctx.add_basemap(ax_mapa, crs=gdf_peligro_plot.crs.to_string(), source=ctx.providers.OpenStreetMap.Mapnik, zoom=12)
    print("🎨 Dibujando niveles de peligro y etiquetas...")
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
    add_north_arrow_blanco_completo(ax_mapa, xy_pos=(0.95, 0.95)) 
    ax_mapa.add_artist(ScaleBar(1.0, units='km', location='lower right', box_alpha=0.8, 
                                frameon=True, color='black', box_color='white'))
    grillado_utm_proyectado(ax_mapa, (x_min, y_min, x_max, y_max), ndiv=8)


    # --- Dibujo de Mapas de Ubicación (Columna 1) ---
    print("🗺️ Generando Mapas de Ubicación...")
    distritos_provincia = gdf_distritos[
        (gdf_distritos[COL_PROV] == provincia_upper) & 
        (gdf_distritos[COL_DPTO] == departamento_upper)
    ]
    
    # 1. UBICACIÓN NACIONAL (Focus: Departamento)
    mapa_ubicacion(ax_loc_dpto, gdf_departamentos, gdf_dpto_sel, gdf_dpto_sel, 
                   "UBICACIÓN NACIONAL", departamento_upper, "departamento",
                   gdf_prov_sel=gdf_provincia_sel,
                   departamento_sel=departamento_upper, provincia_sel=provincia_upper,
                   col_prov=COL_PROV, col_dpto=COL_DPTO, gdf_departamentos=gdf_departamentos,
                   gdf_provincias=gdf_provincias, gdf_oceano=gdf_oceano)

    # 2. UBICACIÓN DEPARTAMENTAL (Context: Departamento, Focus: Provincia)
    mapa_ubicacion(ax_loc_prov, gdf_departamentos, gdf_dpto_sel, gdf_provincia_sel, 
                   "UBICACIÓN DEPARTAMENTAL", provincia_upper, "provincia",
                   gdf_prov_sel=gdf_provincia_sel,
                   departamento_sel=departamento_upper, provincia_sel=provincia_upper,
                   col_prov=COL_PROV, col_dpto=COL_DPTO, gdf_departamentos=gdf_departamentos,
                   gdf_provincias=gdf_provincias, gdf_oceano=gdf_oceano)
                   
    # 3. UBICACIÓN PROVINCIAL (Context: Distritos vecinos, Focus: Distrito)
    mapa_ubicacion(ax_loc_dist, gdf_provincias, distritos_provincia, gdf_distrito_sel, 
                   "UBICACIÓN PROVINCIAL", distrito_upper, "distrito",
                   gdf_dpto_sel=gdf_dpto_sel, 
                   gdf_prov_sel=gdf_provincia_sel, # Se pasa para el cálculo de bounds del mapa distrital.
                   departamento_sel=departamento_upper, provincia_sel=provincia_upper,
                   col_prov=COL_PROV, col_dpto=COL_DPTO, gdf_departamentos=gdf_departamentos,
                   gdf_provincias=gdf_provincias, gdf_oceano=gdf_oceano)
                   

    # --- Membrete y Leyenda (Fila 3) ---

    # 4. Dibujar el Membrete (ax_membrete) - Usa la función 'add_membrete' modificada
    add_membrete(ax_membrete, departamento_upper, provincia_upper, distrito_upper, ax_mapa, fig)
    
    # 5. Dibujar la Leyenda (ax_leyenda)
    ax_leyenda.axis('off')
    
    legend_handles = []
    # Usar los colores y etiquetas definidos globalmente
    for color, label in zip(COLORES_PELIGRO, ETIQUETAS_PELIGRO):
        patch = Patch(facecolor=color, edgecolor='black', linewidth=0.5, label=label)
        legend_handles.append(patch)
        
    ccpp_handle = Line2D([0], [0], marker='o', color='w', label='Centros Poblados',
                         markerfacecolor='#006400', markersize=6, linestyle='None')
    legend_handles.append(ccpp_handle)
    
    ax_leyenda.legend(handles=legend_handles, title="Nivel de Susceptibilidad", 
                      loc='center left', frameon=True, fontsize=6.5, title_fontsize=8, 
                      framealpha=0.9, fancybox=True, edgecolor='black', bbox_to_anchor=(0.0, 1.0)) 


    # 7. Guardado del mapa
    
    if nombre_usuario:
        output_dir = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
    else:
        output_dir = os.path.join(ruta_base, "RESULTADOS", "MAPAS_DE_PELIGRO", provincia_upper, distrito_upper)
    
    os.makedirs(output_dir, exist_ok=True)
    nombre_archivo = f"MAPA_PELIGRO_DESLIZAMIENTO_{distrito_upper}_{provincia_upper}_4P_AJUSTADO.png"
    ruta_guardado_final = os.path.join(output_dir, nombre_archivo)
    
    print(f"🖼️ Intentando ajustar y guardar el mapa en: {ruta_guardado_final}")
    
    # CORRECCIÓN CLAVE: Envolver tight_layout en un try/except para evitar cuelgues.
    try:
        fig.tight_layout(rect=[0, 0.0, 1, 1]) 
        print("✅ tight_layout aplicado.")
    except Exception as e:
        print(f"⚠️ Advertencia: Error en tight_layout ({e}). Continuando con layout predeterminado.")
        pass 
        
    try:
        # CORRECCIÓN CLAVE: Se remueve bbox_inches='tight' (que causó el error anterior)
        fig.savefig(ruta_guardado_final, dpi=300) 
        plt.close(fig)

        if not os.path.exists(ruta_guardado_final):
             raise IOError("El archivo no se escribió en disco a pesar de que savefig terminó sin excepción.")
        
        print("="*80)
        print(f"✅ Mapa de peligro guardado exitosamente (Proporciones más compactas, Colores ajustados)")
        print(f"   📁 Ubicación: {ruta_guardado_final}")
        print("="*80 + "\n")
        return ruta_guardado_final
    except Exception as e:
        print(f"❌ Error CRÍTICO al guardar el archivo: {e}")
        traceback.print_exc()
        plt.close(fig)
        return None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🚀 EJECUCIÓN DEL SCRIPT
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # EJEMPLO DE USO 
    distrito_ejemplo = "SECHURA" 
    provincia_ejemplo = "SECHURA"
    departamento_ejemplo = "PIURA"
    
    # Nombre de usuario para la subcarpeta de guardado (cambie esto según sea necesario)
    nombre_usuario_ejemplo = "USUARIOS" 

    print(f"📌 Ejecutando script con guardado personalizado para: {nombre_usuario_ejemplo}")
    generar_mapa_peligro_deslizamiento(
        distrito_ejemplo, 
        provincia_ejemplo, 
        departamento_ejemplo,
        nombre_usuario=nombre_usuario_ejemplo 
    )