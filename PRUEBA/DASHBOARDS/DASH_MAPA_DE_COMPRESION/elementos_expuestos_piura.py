# -*- coding: utf-8 -*-
"""
🎯 SCRIPT COMPLETO Y CORREGIDO: MAPA DE ELEMENTOS EXPUESTOS
- Solución final al error de filtrado de límites administrativos (PASO 3: usando .str.contains() para Provincia y Distrito).
- MEJORA: Implementación de lógica de FALLBACK en cargar_shapefile para base de distritos (PASO 2).
"""

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
import pandas as pd
import unicodedata
import traceback 

# --- CONFIGURACIÓN GLOBAL ---
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"
AMARILLO_CLARO = "#FFEE58"

# RUTAS DE ELEMENTOS EXPUESTOS (BASES)
RUTA_BASE_AGRICOLA = f"{ruta_base}/DATA/EXPUESTO/AGRICOLA"
RUTA_BASE_CP = f"{ruta_base}/DATA/EXPUESTO/CP"
RUTA_BASE_IE = f"{ruta_base}/DATA/EXPUESTO/IE"
RUTA_BASE_URBE = f"{ruta_base}/DATA/EXPUESTO/URBE"
RUTA_BASE_VIAS = f"{ruta_base}/DATA/MAPA DE UBICACION/VIAS"

# PALETA DE COLORES
COLORES_ELEMENTOS = {
    'agricola': '#90EE90',           
    'cp': '#006400',                 
    'ie': '#FF6B6B',                 
    'urbe': '#7E3030',               
    'via_nacional': '#000000',       
    'via_departamental': '#FF8C00',  
    'via_vecinal': '#FFD700'         
}

# ══════════════════════════════════════════════════════════════════════════════
# 🛠️ FUNCIONES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

def normalizar_texto(texto):
    """Normaliza texto para comparaciones: Mayúsculas, sin acentos ni espacios extra."""
    if pd.isna(texto) or texto is None:
        return ""
    texto = str(texto).upper().strip()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(char for char in texto if unicodedata.category(char) != 'Mn')
    return texto

def buscar_shapefile(nombre_busqueda):
    """Busca shapefiles en toda la estructura (simplificado)"""
    for root, _, files in os.walk(ruta_base):
        for file in files:
            # Buscar por "distrital", "distritos", etc.
            if file.lower().endswith((".shp", ".geojson")) and normalizar_texto(nombre_busqueda) in normalizar_texto(file):
                return os.path.join(root, file)
    return None

def cargar_shapefile(nombre, alias):
    """Carga shapefile con manejo de CRS (simplificado)"""
    path = None

    if nombre.lower() == 'departamento':
        path = f"{ruta_base}/DATA/MAPA DE UBICACION/limites_departamentales.geojson"
    elif nombre.lower() == 'provincia':
        path = f"{ruta_base}/DATA/MAPA DE UBICACION/limites_provinciales.geojson"
    elif nombre.lower() == 'distrito':
        # 1. Intento de ruta hardcodeada (esperada)
        path = f"{ruta_base}/DATA/MAPA DE UBICACION/limites_distritales.geojson"
        
        # 2. Lógica de FALLBACK si la ruta hardcodeada falla
        if not os.path.exists(path):
            print(f"   ⚠️  FALLBACK: La capa base de distritos no se encontró en la ruta esperada. Buscando genéricamente...")
            path = buscar_shapefile('limites_distritales') # Búsqueda flexible

    # 3. Intento de búsqueda genérica para otras capas (no base)
    else:
        path = buscar_shapefile(nombre) 
    
    # 4. Verificación final
    if not path or not os.path.exists(path):
        print(f"   ❌ CAPA CRÍTICA FALTANTE: {alias}")
        return None

    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf.set_crs(epsg=4326, inplace=True)
        gdf_3857 = gdf.to_crs(epsg=3857)
        return gdf_3857
    except Exception as e:
        print(f"   ❌ Error cargando {alias} desde {path}: {e}")
        return None

def encontrar_columna_nombre(gdf, opciones_columnas):
    """Encuentra la columna de nombre más probable en un GeoDataFrame"""
    for col in opciones_columnas:
        if col in gdf.columns:
            return col
    for col in gdf.columns:
        if gdf[col].dtype == 'object' and col != 'geometry':
            return col
    return None

def buscar_shapefile_inteligente(ruta_base, patrones_busqueda, nombre_tipo):
    """Busca shapefiles con múltiples patrones"""
    if not os.path.exists(ruta_base): return None
    
    for root, dirs, files in os.walk(ruta_base):
        for file in files:
            if not file.lower().endswith('.shp'): continue
            file_normalizado = normalizar_texto(file)
            for patron in patrones_busqueda:
                patron_normalizado = normalizar_texto(patron)
                if patron_normalizado in file_normalizado:
                    return os.path.join(root, file)
    return None

def cargar_y_preparar_shapefile(ruta, nombre_elemento, target_crs=3857):
    """Carga shapefile y lo prepara"""
    if not ruta or not os.path.exists(ruta): return None
    try:
        gdf = gpd.read_file(ruta)
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)
        if gdf.crs.to_epsg() != target_crs:
            gdf = gdf.to_crs(epsg=target_crs)
        return gdf
    except Exception as e:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 🗺️ FUNCIONES DE VISUALIZACIÓN (Sin cambios)
# ══════════════════════════════════════════════════════════════════════════════

def add_north_arrow_blanco_completo(ax, xy_pos=(0.93, 0.08), size=0.06):
    """Agrega flecha de norte al mapa con contorno."""
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
    
    ax.add_patch(Polygon(points_body_data, facecolor='white', edgecolor='black', 
                        linewidth=1.5, zorder=11, transform=ax.transData))
    ax.add_patch(Polygon(points_head_data, facecolor='white', edgecolor='black', 
                        linewidth=1.5, zorder=11, transform=ax.transData))
    ax.text(x_pos, y_pos + s * 1.5 + 0.015, "N", transform=ax.transAxes, fontsize=16, 
           fontweight='bold', ha='center', va='center', color='white', 
           path_effects=[path_effects.withStroke(linewidth=3, foreground='black')], zorder=12)

def calculate_numeric_scale(ax, fig):
    """Calcula escala numérica del mapa (1:N)"""
    xlim = ax.get_xlim()
    ground_width_m = xlim[1] - xlim[0]
    fig_width_in = fig.get_size_inches()[0]
    ax_pos = ax.get_position()
    ax_width_in = fig_width_in * ax_pos.width
    scale_denominator = ground_width_m / (ax_width_in * 0.0254)
    # Redondeo a la unidad de escala más cercana 
    rounding = 5000 if scale_denominator > 100000 else 1000 if scale_denominator > 10000 else 500
    scale_rounded = int(round(scale_denominator / rounding) * rounding)
    return f"1:{scale_rounded:,}"

def add_membrete(ax, dpto, prov, dist, main_map_ax, fig_obj):
    """Agrega membrete con información del mapa en el espacio reservado."""
    escala_numerica = calculate_numeric_scale(main_map_ax, fig_obj)
    info = {
        "MAPA": f"MAPA DE ELEMENTOS EXPUESTOS: DISTRITO DE {dist.upper()}",
        "DPTO": dpto.upper(),
        "PROVINCIA": prov.upper(),
        "DISTRITO": dist.upper(),
        "MAPA_N": "004-2025",
        "ESCALA": escala_numerica,
        "FECHA": datetime.date.today().strftime("%d / %m / %Y")
    }
    
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis('off')
    
    # Dibujar las divisiones del membrete
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

def grillado_utm_proyectado(ax, bbox, ndiv=8):
    """Agrega grillado UTM y formatea las etiquetas de coordenadas."""
    x0, y0, x1, y1 = bbox
    
    # Dibujar líneas de cuadrícula
    for x in np.linspace(x0, x1, ndiv):
        ax.plot([x, x], [y0, y1], color="black", linestyle="-", linewidth=0.4, alpha=0.6, zorder=0)
    
    for y in np.linspace(y0, y1, ndiv):
        ax.plot([x0, x1], [y, y], color="black", linestyle="-", linewidth=0.4, alpha=0.6, zorder=0)
    
    def fmt_este(x, pos):
        # Formato NNN MMM E (ej. 518 000 E)
        return f"{int(x):06d}"[:3] + " " + f"{int(x):06d}"[3:] + " E"
    
    def fmt_norte(y, pos):
        # Formato N NNN MMM N (ej. 9 130 000 N)
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


# ══════════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def generar_mapa_elementos_expuestos(nombre_usuario, departamento_sel, provincia_sel, distrito_sel):
    
    print("\n" + "="*80)
    print("🗺️ INICIANDO GENERACIÓN DE MAPA DE ELEMENTOS EXPUESTOS")
    print("="*80)
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")

    # PASO 1: CREAR ESTRUCTURA DE CARPETAS
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "ELEMENTOS EXPUESTOS")
        os.makedirs(carpeta_salida, exist_ok=True)
        print(f"   ✅ Carpeta de salida: {carpeta_salida}")
    except Exception as e:
        print(f"❌ Error creando carpeta: {e}")
        return None, False

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 2: CARGAR LÍMITES ADMINISTRATIVOS
    # ══════════════════════════════════════════════════════════════════════════
    print("\n📦 Cargando límites administrativos...")
    # USANDO LA FUNCIÓN MEJORADA CON FALLBACK
    gdf_distritos = cargar_shapefile("distrito", "Distritos del Perú")

    if gdf_distritos is None:
        print("❌ Faltan capa base de distritos. Abortando.")
        return None, False

    # Intenta detectar columnas, si no existen se usan las por defecto
    col_dpto = 'NOMBDEP' if 'NOMBDEP' in gdf_distritos.columns else gdf_distritos.columns[0]
    col_prov = 'NOMBPROV' if 'NOMBPROV' in gdf_distritos.columns else gdf_distritos.columns[1]
    col_distr = 'NOMBDIST' if 'NOMBDIST' in gdf_distritos.columns else gdf_distritos.columns[2]


    print(f"   ✅ Distritos del Perú cargado: {len(gdf_distritos)} registros")
    print(f"   ✅ Columnas detectadas: {col_dpto}, {col_prov}, {col_distr}")

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 3: FILTRAR ÁREA SELECCIONADA
    # ══════════════════════════════════════════════════════════════════════════
    print("\n🔍 Filtrando datos del área seleccionada...")

    # A. Normalizar las entradas del usuario
    dpto_norm = normalizar_texto(departamento_sel)
    prov_norm = normalizar_texto(provincia_sel)
    distr_norm = normalizar_texto(distrito_sel)

    try:
        # Crear columnas normalizadas temporales
        gdf_distritos_temp = gdf_distritos.copy()
        gdf_distritos_temp['TEMP_DIST_NORM'] = gdf_distritos_temp[col_distr].apply(normalizar_texto)
        gdf_distritos_temp['TEMP_PROV_NORM'] = gdf_distritos_temp[col_prov].apply(normalizar_texto)
        gdf_distritos_temp['TEMP_DPTO_NORM'] = gdf_distritos_temp[col_dpto].apply(normalizar_texto)

        # 🎯 FILTRO CORREGIDO: Se usa .str.contains() para Provincia y Distrito para flexibilidad
        gdf_distrito = gdf_distritos_temp[
            (gdf_distritos_temp['TEMP_PROV_NORM'].str.contains(prov_norm, na=False)) & 
            (gdf_distritos_temp['TEMP_DIST_NORM'].str.contains(distr_norm, na=False))
        ].copy() 
        
        if gdf_distrito.empty:
            print(f"❌ Error: No se pudo encontrar el distrito '{distrito_sel}' en la provincia '{provincia_sel}'.")
            
            # Intento alternativo solo por distrito y departamento
            gdf_distrito_alternativo = gdf_distritos_temp[
                (gdf_distritos_temp['TEMP_DIST_NORM'].str.contains(distr_norm, na=False)) &
                (gdf_distritos_temp['TEMP_DPTO_NORM'] == dpto_norm)
            ]
            if not gdf_distrito_alternativo.empty:
                 gdf_distrito = gdf_distrito_alternativo.copy()
                 print(f"   ✅ Advertencia: Se encontró el distrito por nombre y departamento, ignorando el error de provincia.")
            else:
                return None, False

        limite_distrito = gdf_distrito.iloc[0].geometry
        print(f"   ✅ Límite del distrito '{distrito_sel}' encontrado y listo.")

    except Exception as e:
        print(f"❌ Error al filtrar límites administrativos: {e}")
        traceback.print_exc()
        return None, False

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 4: CARGAR ELEMENTOS EXPUESTOS (RUTAS FIJAS CONFIRMADAS)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n📦 Cargando elementos expuestos...")
    
    elementos_cargados = {}
    
    # RUTAS FIJAS CONFIRMADAS:
    ruta_agricola_fija = f"{ruta_base}/DATA/EXPUESTO/AGRICOLA/AGRICOLA_PIURA.shp"
    ruta_cp_fija = f"{ruta_base}/DATA/EXPUESTO/CP/CP_PIURA.shp"
    ruta_ie_fija = f"{ruta_base}/DATA/EXPUESTO/IE/IE_PIURA.shp"
    ruta_urbe_fija = f"{ruta_base}/DATA/EXPUESTO/URBE/piura_edificios_microsoft_COMPLETO.shp"
    
    
    gdf_agricola = cargar_y_preparar_shapefile(ruta_agricola_fija, "Agrícola")
    if gdf_agricola is not None: elementos_cargados['agricola'] = gdf_agricola
    
    gdf_cp = cargar_y_preparar_shapefile(ruta_cp_fija, "Centros Poblados")
    if gdf_cp is not None: elementos_cargados['cp'] = gdf_cp
    
    gdf_ie = cargar_y_preparar_shapefile(ruta_ie_fija, "IE")
    if gdf_ie is not None: elementos_cargados['ie'] = gdf_ie
        
    gdf_urbe = cargar_y_preparar_shapefile(ruta_urbe_fija, "Urbe")
    if gdf_urbe is not None: elementos_cargados['urbe'] = gdf_urbe
    
    # Vías (Se mantiene la lógica de búsqueda por patrón para las vías)
    vias_tipos = [
        ('nacional', ['nacional', 'red_vial_nacional']),
        ('departamental', ['departamental', 'red_vial_departamental']),
        ('vecinal', ['vecinal', 'red_vial_vecinal'])
    ]
    
    for via_tipo, patrones in vias_tipos:
        ruta_via = buscar_shapefile_inteligente(RUTA_BASE_VIAS, patrones, f"Vía {via_tipo.capitalize()}")
        if ruta_via:
            gdf_via = cargar_y_preparar_shapefile(ruta_via, f"Vía {via_tipo}")
            if gdf_via is not None:
                elementos_cargados[f'via_{via_tipo}'] = gdf_via
    
    if not elementos_cargados:
        print("❌ No se cargó ningún elemento expuesto")
        return None, False
    
    print(f"\n   ✅ Elementos cargados: {len(elementos_cargados)}")
    
    # ══════════════════════════════════════════════════════════════════════════
    # PASO 5: RECORTAR ELEMENTOS AL DISTRITO
    # ══════════════════════════════════════════════════════════════════════════
    print("\n✂️ Recortando elementos al distrito...")
    
    elementos_procesados = {}
    
    for key, gdf_elemento in elementos_cargados.items():
        try:
            if gdf_elemento.crs != gdf_distrito.crs:
                gdf_elemento = gdf_elemento.to_crs(gdf_distrito.crs)
                
            gdf_clip = gpd.clip(gdf_elemento, gdf_distrito)
            
            if len(gdf_clip) > 0:
                elementos_procesados[key] = gdf_clip
                print(f"   ✅ {key}: {len(gdf_clip)} elementos recortados")
            else:
                print(f"   ⚠️  {key}: Sin elementos en el distrito después del recorte")
        
        except Exception as e:
            print(f"   ❌ Error recortando {key}: {e}")
    
    if not elementos_procesados:
        print("❌ Ningún elemento tiene datos en el distrito después del recorte")
        return None, False
    
    print(f"   ✅ Recorte de {len(elementos_procesados)} capas completado.")
    
    # ══════════════════════════════════════════════════════════════════════════
    # PASO 6: GENERAR LAYOUT DEL MAPA
    # ══════════════════════════════════════════════════════════════════════════
    print("\n🎨 Generando layout del mapa...")
    
    fig = plt.figure(figsize=(14, 9.9))
    grid = plt.GridSpec(1, 2, width_ratios=[3.0, 1], wspace=0.05)
    gs_izquierda = grid[0, 0].subgridspec(3, 1, height_ratios=[0.08, 3.5, 0.42], hspace=0.08)

    # TÍTULO
    ax_titulo = fig.add_subplot(gs_izquierda[0])
    ax_titulo.text(0.5, 0.5, f"MAPA DE ELEMENTOS EXPUESTOS - DISTRITO DE {distrito_sel.upper()}",
                   ha='center', va='center', fontsize=11, fontweight="normal",
                   bbox=dict(boxstyle='square,pad=0.5', facecolor='white', 
                            edgecolor='black', linewidth=1.5, alpha=0.95))
    ax_titulo.axis('off')

    # MAPA PRINCIPAL
    ax_main = fig.add_subplot(gs_izquierda[1])

    # CÁLCULO DE BBOX
    minx, miny, maxx, maxy = gdf_distrito.total_bounds
    buffer_factor = 0.15
    buffer_x = (maxx - minx) * buffer_factor
    buffer_y = (maxy - miny) * buffer_factor
    bbox_temp = (minx - buffer_x, miny - buffer_y, maxx + buffer_x, maxy + buffer_y)
    
    # Ajuste de aspecto
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

    # MAPA BASE SATELITAL
    try:
        ctx.add_basemap(ax_main, source=ctx.providers.Esri.WorldImagery, attribution=False, zoom='auto')
    except Exception as e:
        ax_main.set_facecolor("#e8e8e8")

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 7: VISUALIZAR ELEMENTOS
    # ══════════════════════════════════════════════════════════════════════════
    print("   🎨 Renderizando elementos...")
    
    # Orden de visualización: Polígonos -> Líneas -> Puntos
    orden_visualizacion = [
        'agricola', 'urbe', 'via_vecinal', 'via_departamental', 
        'via_nacional', 'ie', 'cp'
    ]
    
    for elemento_tipo in orden_visualizacion:
        if elemento_tipo not in elementos_procesados:
            continue
        
        gdf_elem = elementos_procesados[elemento_tipo]
        
        try:
            if elemento_tipo == 'agricola':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='darkgreen', linewidth=0.3, alpha=0.6, zorder=5)
            
            elif elemento_tipo == 'urbe':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='white', linewidth=0.1, alpha=0.9, zorder=5.5)
            
            elif elemento_tipo == 'cp':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='white', markersize=50, marker='o', 
                            linewidth=1.0, alpha=0.95, zorder=10)
                # Anotación de puntos (CP)
                col_nombre = encontrar_columna_nombre(gdf_elem, ['NOMB_CCPP', 'NOMBRE', 'NOMBCCPP', 'CCPP', 'NAME'])
                if col_nombre:
                    for idx, row in gdf_elem.iterrows():
                        x, y = row.geometry.x, row.geometry.y
                        nombre = str(row[col_nombre])[:20]
                        ax_main.annotate(nombre, xy=(x, y), xytext=(5, 5), textcoords='offset points', fontsize=6, color=COLORES_ELEMENTOS['cp'], weight='bold', path_effects=[path_effects.withStroke(linewidth=2, foreground='white')], zorder=11)
            
            elif elemento_tipo == 'ie':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='white', markersize=40, marker='s', 
                            linewidth=0.8, alpha=0.9, zorder=9)
                # Anotación de puntos (IE)
                col_nombre = encontrar_columna_nombre(gdf_elem, ['NOMBRE', 'NOMB', 'NAME', 'COD_LOCAL'])
                if col_nombre:
                    for idx, row in gdf_elem.iterrows():
                        x, y = row.geometry.x, row.geometry.y
                        nombre = str(row[col_nombre])[:15]
                        ax_main.annotate(nombre, xy=(x, y), xytext=(3, 3), textcoords='offset points', fontsize=5, color=COLORES_ELEMENTOS['ie'], weight='bold', path_effects=[path_effects.withStroke(linewidth=1.5, foreground='white')], zorder=10)
            
            elif elemento_tipo in ['via_nacional', 'via_departamental', 'via_vecinal']:
                linewidth_map = {'via_nacional': 2.0, 'via_departamental': 1.5, 'via_vecinal': 1.0}
                zorder_map = {'via_nacional': 8, 'via_departamental': 7, 'via_vecinal': 6}
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            linewidth=linewidth_map[elemento_tipo], 
                            alpha=0.8, zorder=zorder_map[elemento_tipo])
            
        except Exception as e:
            print(f"      ⚠️  Error renderizando {elemento_tipo}: {e}")

    # LÍMITE DISTRITAL
    gdf_distrito.plot(ax=ax_main, facecolor="none", edgecolor="black", 
                     linewidth=1.5, linestyle='-', alpha=1.0, zorder=15)

    # ELEMENTOS CARTOGRÁFICOS
    grillado_utm_proyectado(ax_main, bbox_main, ndiv=8)
    add_north_arrow_blanco_completo(ax_main, xy_pos=(0.93, 0.08), size=0.06)
    ax_main.add_artist(ScaleBar(1, units="m", location="lower left", 
                                box_alpha=0.6, border_pad=0.5, scale_loc='bottom'))

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 8: MEMBRETE Y LEYENDA
    # ══════════════════════════════════════════════════════════════════════════
    
    # MEMBRETE
    gs_memb_ley = gs_izquierda[2].subgridspec(1, 2, wspace=0.1)
    ax_membrete = fig.add_subplot(gs_memb_ley[0])
    ax_leyenda = fig.add_subplot(gs_memb_ley[1])
    
    add_membrete(ax_membrete, departamento_sel, provincia_sel, distrito_sel, ax_main, fig)

    # LEYENDA
    ax_leyenda.axis('off')

    legend_elements = [
        Patch(facecolor='white', edgecolor='white', label='ELEMENTOS:', linewidth=0)
    ]
    
    # Agregar elementos según lo que se cargó
    if 'agricola' in elementos_procesados:
        legend_elements.append(
            Patch(facecolor=COLORES_ELEMENTOS['agricola'], edgecolor='darkgreen', label='Zona Agrícola')
        )
    
    if 'urbe' in elementos_procesados:
        legend_elements.append(
            Patch(facecolor=COLORES_ELEMENTOS['urbe'], edgecolor='white', linewidth=0.1, label='Urbe / Edificios')
        )
        
    if 'cp' in elementos_procesados:
        legend_elements.append(
            Line2D([0], [0], marker='o', color='w', markerfacecolor=COLORES_ELEMENTOS['cp'], 
                   markeredgecolor='white', markersize=7, linestyle='None', 
                   label='Centro Poblado', markeredgewidth=1.0)
        )
    
    if 'ie' in elementos_procesados:
        legend_elements.append(
            Line2D([0], [0], marker='s', color='w', markerfacecolor=COLORES_ELEMENTOS['ie'], 
                   markeredgecolor='white', markersize=6, linestyle='None', 
                   label='Infraestructura Educativa', markeredgewidth=0.8)
        )
    
    # Vías
    vias_incluidas = [v for v in ['via_nacional', 'via_departamental', 'via_vecinal'] if v in elementos_procesados]
    if vias_incluidas:
        legend_elements.extend([
            Patch(facecolor='white', edgecolor='white', label='', linewidth=0),
            Patch(facecolor='white', edgecolor='white', label='VÍAS:', linewidth=0)
        ])
        if 'via_nacional' in vias_incluidas:
            legend_elements.append(Line2D([0], [0], color=COLORES_ELEMENTOS['via_nacional'], lw=2.0, label='Vía Nacional'))
        if 'via_departamental' in vias_incluidas:
            legend_elements.append(Line2D([0], [0], color=COLORES_ELEMENTOS['via_departamental'], lw=1.5, label='Vía Departamental'))
        if 'via_vecinal' in vias_incluidas:
            legend_elements.append(Line2D([0], [0], color=COLORES_ELEMENTOS['via_vecinal'], lw=1.0, label='Vía Vecinal'))
    
    legend_elements.extend([
        Patch(facecolor='white', edgecolor='white', label='', linewidth=0),
        Line2D([0], [0], color='black', lw=1.5, linestyle='-', label='Límite Distrital')
    ])

    leg = ax_leyenda.legend(
        handles=legend_elements, loc='center', ncol=1, frameon=True, fontsize=7,
        title="LEYENDA", title_fontproperties={'size': 10, 'weight': 'bold'},
        handletextpad=0.5, columnspacing=1.0, borderpad=0.7, handlelength=1.5
    )
    leg.get_title().set_ha('center')
    leg.get_frame().set_edgecolor('black')
    leg.get_frame().set_linewidth(1.2)

    # AJUSTES FINALES
    plt.subplots_adjust(top=0.98, bottom=0.02, left=0.02, right=0.98, hspace=0.2, wspace=0.05)

    # MARCO EXTERIOR
    rect_frame = fig.add_axes([0, 0, 1, 1], frameon=False)
    rect_frame.set_xticks([])
    rect_frame.set_yticks([])
    rect_frame.patch.set_visible(False)

    for spine in rect_frame.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(2)
        spine.set_color('black')

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 9: GUARDAR MAPA
    # ══════════════════════════════════════════════════════════════════════════
    print("\n💾 Guardando mapa...")
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = f"MAPA_ELEMENTOS_EXPUESTOS_{distrito_sel.replace(' ', '_')}_{timestamp}.png"
    ruta_guardado_final = os.path.join(carpeta_salida, nombre_base)

    try:
        plt.savefig(ruta_guardado_final, dpi=300, bbox_inches='tight', pad_inches=0.01)
        plt.close(fig)

        if os.path.exists(ruta_guardado_final):
            file_size = os.path.getsize(ruta_guardado_final) / (1024 * 1024)
            
            print(f"\n{'='*80}")
            print(f"✅ MAPA GENERADO EXITOSAMENTE")
            print(f"   📂 Ubicación: {ruta_guardado_final}")
            print(f"   📊 Tamaño: {file_size:.2f} MB")
            print(f"{'='*80}\n")
            
            return ruta_guardado_final, True
        else:
            return None, False

    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        traceback.print_exc()
        plt.close(fig)
        return None, False