# -*- coding: utf-8 -*-
"""
🎯 SCRIPT INTEGRADO: MAPA DE PELIGRO CON 3 PARÁMETROS + CENTROS POBLADOS
- Calcula el mapa de peligro combinando: Pendiente + Geomorfología + Geología
- Muestra centros poblados con etiquetas FUERA de la zona de estudio
- Líneas blancas gruesas y separación automática entre etiquetas
- SOPORTE EXCLUSIVO PARA PIURA Y SECHURA
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

# --- CONFIGURACIÓN GLOBAL ---
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"
AMARILLO_CLARO = "#FFEE58"

# 🆕 CONFIGURACIÓN DE RUTAS POR PROVINCIA (PIURA Y SECHURA)
CAPAS_POR_PROVINCIA = {
    "PIURA": {
        "GEOLOGIA": f"{ruta_base}/DATA/PELIGRO/GEOLOGIA/geologia_piura_con_pesos.shp",
        "GEOMORFOLOGIA": f"{ruta_base}/DATA/PELIGRO/GEOMORFOLOGIA/geomorfologia_piura_con_pesos.shp",
        "PENDIENTE": f"{ruta_base}/DATA/PELIGRO/PENDIENTE/PIURA/pendientes_piura.shp"
    },
    "SECHURA": {
        "GEOLOGIA": f"{ruta_base}/DATA/PELIGRO/GEOLOGIA/geologia_sechura_con_pesos.shp",
        "GEOMORFOLOGIA": f"{ruta_base}/DATA/PELIGRO/GEOMORFOLOGIA/geomorfologia_sechura_con_pesos.shp",
        "PENDIENTE": f"{ruta_base}/DATA/PELIGRO/PENDIENTE/PIURA/pendientes_piura.shp"
    }
}

RUTA_CENTROS_POBLADOS = f"{ruta_base}/DATA/CENTROS POBLADOS/Centros_Poblados_INEI_geogpsperu_SuyoPomalia.shp"

# PALETA DE COLORES PARA NIVELES DE PELIGRO
COLORES_PELIGRO = ['#00FF00', '#FFFF00', '#FFA500', '#FF0000']
ETIQUETAS_PELIGRO = ['Baja', 'Media', 'Alta', 'Muy Alta']
RANGOS_PELIGRO = [1.00, 2.00, 3.00, 4.00, 5.00]

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIONES DE ETIQUETADO DE CENTROS POBLADOS (MEJORADAS)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

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
            
            # 🆕 DIBUJAR LÍNEA BLANCA GRUESA desde el punto hasta la etiqueta
            ax.plot(
                [x_orig, x_label],
                [y_orig, y_label],
                'w-',  # Línea BLANCA sólida
                linewidth=0.8,  # MÁS GRUESA (antes era 0.45)
                alpha=0.95,
                zorder=5
            )
            
            # Agregar punto pequeño en la ubicación original (dentro del distrito)
            ax.plot(x_orig, y_orig, 'o', color='#006400', markersize=4, zorder=6)
            
            # Agregar etiqueta con fondo FUERA del distrito
            ax.text(
                x_label, y_label,
                nombre,
                fontsize=6.2,  # Ligeramente más grande
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

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES PARA MAPAS
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

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

# 🆕 FUNCIÓN PARA OBTENER RUTAS DE CAPAS SEGÚN PROVINCIA
def obtener_rutas_capas(provincia_sel):
    """
    Obtiene las rutas de las capas de peligro según la provincia seleccionada.
    
    Parámetros:
    -----------
    provincia_sel : str
        Nombre de la provincia (PIURA o SECHURA)
    
    Retorna:
    --------
    dict : Diccionario con las rutas de las capas o None si la provincia no es válida
    """
    provincia_upper = provincia_sel.upper()
    
    if provincia_upper not in CAPAS_POR_PROVINCIA:
        print(f"❌ Error: La provincia '{provincia_sel}' no está configurada.")
        print(f"   Provincias disponibles: {list(CAPAS_POR_PROVINCIA.keys())}")
        return None
    
    rutas = CAPAS_POR_PROVINCIA[provincia_upper]
    
    # Verificar que existen los archivos
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

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIÓN PRINCIPAL CON 3 PARÁMETROS (GEOLOGÍA + GEOMORFOLOGÍA + PENDIENTE)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def generar_mapa_peligro_3param(nombre_usuario, departamento_sel, provincia_sel, distrito_sel):
    print("\n" + "="*80)
    print("🗺️ INICIANDO PROCESO DE GENERACIÓN DE MAPA DE PELIGRO (3 PARÁMETROS)")
    print("="*80)
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")
    
    # 🆕 VERIFICAR QUE LA PROVINCIA SEA PIURA O SECHURA
    provincia_upper = provincia_sel.upper()
    if provincia_upper not in ['PIURA', 'SECHURA']:
        print(f"\n❌ ERROR: Esta función solo funciona para PIURA y SECHURA")
        print(f"   Provincia recibida: {provincia_sel}")
        print(f"   Provincias válidas: PIURA, SECHURA")
        return None
    