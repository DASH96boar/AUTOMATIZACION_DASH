# -*- coding: utf-8 -*-
"""
🎯 SCRIPT MEJORADO: MAPA DE ELEMENTOS EXPUESTOS
- Sigue la estructura de mapa_peligro.py
- Recibe GeoDataFrames pre-cargados
- Búsqueda inteligente de archivos
- Manejo robusto de errores
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

# --- CONFIGURACIÓN GLOBAL ---
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"
AMARILLO_CLARO = "#FFEE58"

# RUTAS DE ELEMENTOS EXPUESTOS
RUTA_BASE_AGRICOLA = f"{ruta_base}/DATA/EXPUESTO/AGRICOLA"
RUTA_BASE_CP = f"{ruta_base}/DATA/EXPUESTO/CP"
RUTA_BASE_IE = f"{ruta_base}/DATA/EXPUESTO/IE"
RUTA_BASE_VIAS = f"{ruta_base}/DATA/MAPA DE UBICACION/VIAS"

# PALETA DE COLORES
COLORES_ELEMENTOS = {
    'agricola': '#90EE90',           # Verde claro
    'cp': '#006400',                 # Verde oscuro
    'ie': '#FF6B6B',                 # Rojo
    'via_nacional': '#000000',       # Negro
    'via_departamental': '#FF8C00',  # Naranja oscuro
    'via_vecinal': '#FFD700'         # Oro
}

# ═══════════════════════════════════════════════════════════════════════
# 🛠️ FUNCIONES AUXILIARES MEJORADAS
# ═══════════════════════════════════════════════════════════════════════

def normalizar_texto(texto):
    """Normaliza texto para comparaciones (sin tildes, mayúsculas, espacios)"""
    if pd.isna(texto):
        return ""
    texto = str(texto).upper().strip()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(char for char in texto if unicodedata.category(char) != 'Mn')
    return texto

def buscar_shapefile_inteligente(ruta_base, patrones_busqueda, nombre_tipo):
    """
    Busca shapefiles de forma inteligente con múltiples patrones
    
    Args:
        ruta_base: Carpeta base donde buscar
        patrones_busqueda: Lista de strings para buscar
        nombre_tipo: Nombre descriptivo para logs
    
    Returns:
        Ruta del archivo encontrado o None
    """
    print(f"   🔍 Buscando {nombre_tipo}...")
    
    if not os.path.exists(ruta_base):
        print(f"      ⚠️  Carpeta no existe: {ruta_base}")
        return None
    
    archivos_encontrados = []
    
    for root, dirs, files in os.walk(ruta_base):
        for file in files:
            if not file.lower().endswith('.shp'):
                continue
            
            file_normalizado = normalizar_texto(file)
            
            # Buscar cualquier patrón
            for patron in patrones_busqueda:
                patron_normalizado = normalizar_texto(patron)
                if patron_normalizado in file_normalizado:
                    ruta_completa = os.path.join(root, file)
                    archivos_encontrados.append(ruta_completa)
                    print(f"      ✅ Encontrado: {os.path.basename(file)}")
                    break
    
    if not archivos_encontrados:
        print(f"      ❌ No se encontró {nombre_tipo}")
        print(f"         Patrones buscados: {patrones_busqueda}")
        return None
    
    if len(archivos_encontrados) > 1:
        print(f"      ⚠️  Múltiples archivos encontrados, usando el primero")
    
    return archivos_encontrados[0]

def cargar_y_preparar_shapefile(ruta, nombre_elemento, target_crs=3857):
    """
    Carga shapefile y lo prepara (CRS, validación)
    
    Args:
        ruta: Ruta del shapefile
        nombre_elemento: Nombre para logs
        target_crs: CRS objetivo (por defecto 3857)
    
    Returns:
        GeoDataFrame o None si falla
    """
    if not ruta or not os.path.exists(ruta):
        print(f"      ⚠️  Archivo no existe: {nombre_elemento}")
        return None
    
    try:
        gdf = gpd.read_file(ruta)
        
        # Configurar CRS si no existe
        if gdf.crs is None:
            print(f"      ⚠️  Sin CRS, asumiendo EPSG:4326")
            gdf.set_crs(epsg=4326, inplace=True)
        
        # Convertir a CRS objetivo
        if gdf.crs.to_epsg() != target_crs:
            gdf = gdf.to_crs(epsg=target_crs)
        
        print(f"      ✅ {nombre_elemento}: {len(gdf)} registros (CRS: {target_crs})")
        return gdf
    
    except Exception as e:
        print(f"      ❌ Error cargando {nombre_elemento}: {e}")
        return None

def encontrar_columna_nombre(gdf, opciones_columnas):
    """
    Encuentra la columna de nombre en un GeoDataFrame
    
    Args:
        gdf: GeoDataFrame
        opciones_columnas: Lista de posibles nombres de columna
    
    Returns:
        Nombre de columna encontrada o None
    """
    # Buscar coincidencia exacta
    for col in opciones_columnas:
        if col in gdf.columns:
            return col
    
    # Buscar coincidencia parcial
    for col in gdf.columns:
        col_norm = normalizar_texto(col)
        for opcion in opciones_columnas:
            opcion_norm = normalizar_texto(opcion)
            if opcion_norm in col_norm or col_norm in opcion_norm:
                return col
    
    # Fallback: primera columna no geométrica
    for col in gdf.columns:
        if col != 'geometry' and gdf[col].dtype == 'object':
            print(f"      ⚠️  Usando columna fallback: {col}")
            return col
    
    return None

def filtrar_geodataframe_por_nombre(gdf, columna, valor_buscado, nombre_tipo="elemento"):
    """
    Filtra GeoDataFrame por nombre con normalización
    
    Args:
        gdf: GeoDataFrame a filtrar
        columna: Nombre de columna para filtrar
        valor_buscado: Valor a buscar
        nombre_tipo: Tipo de elemento (para logs)
    
    Returns:
        GeoDataFrame filtrado
    """
    if columna not in gdf.columns:
        raise ValueError(f"Columna '{columna}' no existe en {nombre_tipo}")
    
    valor_normalizado = normalizar_texto(valor_buscado)
    
    # Intentar coincidencia exacta
    gdf_filtrado = gdf[gdf[columna].apply(normalizar_texto) == valor_normalizado].copy()
    
    if len(gdf_filtrado) == 0:
        # Intentar coincidencia parcial
        gdf_filtrado = gdf[
            gdf[columna].apply(lambda x: valor_normalizado in normalizar_texto(x))
        ].copy()
        
        if len(gdf_filtrado) == 0:
            # Mostrar valores disponibles
            valores_disponibles = sorted(gdf[columna].unique()[:10])
            raise ValueError(
                f"No se encontró '{valor_buscado}' en {nombre_tipo}. "
                f"Ejemplos: {', '.join(map(str, valores_disponibles))}"
            )
    
    return gdf_filtrado

# ═══════════════════════════════════════════════════════════════════════
# 📐 FUNCIONES DE VISUALIZACIÓN (IDÉNTICAS A MAPA_PELIGRO)
# ═══════════════════════════════════════════════════════════════════════

def add_north_arrow_blanco_completo(ax, xy_pos=(0.93, 0.08), size=0.06):
    """Agrega flecha de norte al mapa"""
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
           path_effects=[path_effects.withStroke(linewidth=3, foreground='black')])

def calculate_numeric_scale(ax, fig):
    """Calcula escala numérica del mapa"""
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
    """Agrega membrete con información del mapa"""
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
    """Agrega grillado UTM al mapa"""
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

# ═══════════════════════════════════════════════════════════════════════
# 🎯 FUNCIÓN PRINCIPAL MEJORADA
# ═══════════════════════════════════════════════════════════════════════

def generar_mapa_elementos_expuestos(nombre_usuario, departamento_sel, provincia_sel, 
                                     distrito_sel, gdf_distrito, gdf_departamentos, 
                                     gdf_provincias, gdf_paises=None, gdf_oceano=None):
    """
    Genera mapa de elementos expuestos siguiendo estructura de mapa_peligro.py
    
    Args:
        nombre_usuario: Nombre del usuario
        departamento_sel: Nombre del departamento
        provincia_sel: Nombre de la provincia
        distrito_sel: Nombre del distrito
        gdf_distrito: GeoDataFrame del distrito (pre-filtrado)
        gdf_departamentos: GeoDataFrame de todos los departamentos
        gdf_provincias: GeoDataFrame de todas las provincias
        gdf_paises: GeoDataFrame de países (opcional)
        gdf_oceano: GeoDataFrame de océano (opcional)
    
    Returns:
        Ruta del archivo generado o None si falla
    """
    print("\n" + "="*80)
    print("🗺️ INICIANDO GENERACIÓN DE MAPA DE ELEMENTOS EXPUESTOS")
    print("="*80)
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")

    # ═══════════════════════════════════════════════════════════════════
    # PASO 1: CREAR ESTRUCTURA DE CARPETAS
    # ═══════════════════════════════════════════════════════════════════
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "ELEMENTOS EXPUESTOS")
        os.makedirs(carpeta_salida, exist_ok=True)
        print(f"   ✅ Carpeta de salida: {carpeta_salida}")
    except Exception as e:
        print(f"❌ Error creando carpeta: {e}")
        return None

    # ═══════════════════════════════════════════════════════════════════
    # PASO 2: CARGAR ELEMENTOS EXPUESTOS CON BÚSQUEDA INTELIGENTE
    # ═══════════════════════════════════════════════════════════════════
    print("\n📦 Cargando elementos expuestos...")
    
    elementos_cargados = {}
    
    # 1️⃣ AGRÍCOLA
    ruta_agricola = buscar_shapefile_inteligente(
        RUTA_BASE_AGRICOLA,
        ['agricola', 'agric', provincia_sel],
        "Zona Agrícola"
    )
    if ruta_agricola:
        gdf_agricola = cargar_y_preparar_shapefile(ruta_agricola, "Agrícola")
        if gdf_agricola is not None:
            elementos_cargados['agricola'] = gdf_agricola
    
    # 2️⃣ CENTROS POBLADOS
    ruta_cp = buscar_shapefile_inteligente(
        RUTA_BASE_CP,
        ['cpoblado', 'centro_poblado', 'cp', provincia_sel],
        "Centros Poblados"
    )
    if ruta_cp:
        gdf_cp = cargar_y_preparar_shapefile(ruta_cp, "Centros Poblados")
        if gdf_cp is not None:
            elementos_cargados['cp'] = gdf_cp
    
    # 3️⃣ INFRAESTRUCTURA EDUCATIVA
    ruta_ie = buscar_shapefile_inteligente(
        RUTA_BASE_IE,
        ['ie', 'infraestructura_educativa', provincia_sel],
        "Infraestructura Educativa"
    )
    if ruta_ie:
        gdf_ie = cargar_y_preparar_shapefile(ruta_ie, "IE")
        if gdf_ie is not None:
            elementos_cargados['ie'] = gdf_ie
    
    # 4️⃣ VÍAS (3 TIPOS)
    vias_tipos = [
        ('nacional', ['nacional', 'red_vial_nacional']),
        ('departamental', ['departamental', 'red_vial_departamental']),
        ('vecinal', ['vecinal', 'red_vial_vecinal'])
    ]
    
    for via_tipo, patrones in vias_tipos:
        ruta_via = buscar_shapefile_inteligente(
            RUTA_BASE_VIAS,
            patrones,
            f"Vía {via_tipo.capitalize()}"
        )
        if ruta_via:
            gdf_via = cargar_y_preparar_shapefile(ruta_via, f"Vía {via_tipo}")
            if gdf_via is not None:
                elementos_cargados[f'via_{via_tipo}'] = gdf_via
    
    if not elementos_cargados:
        print("❌ No se cargó ningún elemento expuesto")
        return None
    
    print(f"\n   ✅ Elementos cargados: {len(elementos_cargados)}")

    # ═══════════════════════════════════════════════════════════════════
    # PASO 3: RECORTAR ELEMENTOS AL DISTRITO
    # ═══════════════════════════════════════════════════════════════════
    print("\n✂️ Recortando elementos al distrito...")
    
    elementos_procesados = {}
    
    for key, gdf_elemento in elementos_cargados.items():
        try:
            gdf_clip = gpd.clip(gdf_elemento, gdf_distrito)
            
            if len(gdf_clip) > 0:
                elementos_procesados[key] = gdf_clip
                tipo_geom = gdf_clip.geometry.type.iloc[0] if len(gdf_clip) > 0 else "N/A"
                print(f"   ✅ {key}: {len(gdf_clip)} elementos ({tipo_geom})")
            else:
                print(f"   ⚠️  {key}: Sin elementos en el distrito")
        
        except Exception as e:
            print(f"   ❌ Error recortando {key}: {e}")
    
    if not elementos_procesados:
        print("❌ Ningún elemento tiene datos en el distrito")
        return None

    # ═══════════════════════════════════════════════════════════════════
    # PASO 4: GENERAR LAYOUT DEL MAPA
    # ═══════════════════════════════════════════════════════════════════
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

    # CÁLCULO DE BBOX CON ASPECT RATIO
    minx, miny, maxx, maxy = gdf_distrito.total_bounds
    buffer_factor = 0.15
    buffer_x = (maxx - minx) * buffer_factor
    buffer_y = (maxy - miny) * buffer_factor
    bbox_temp = (minx - buffer_x, miny - buffer_y, maxx + buffer_x, maxy + buffer_y)
    
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
    print("   🛰️ Descargando imagen satelital...")
    try:
        ctx.add_basemap(ax_main, source=ctx.providers.Esri.WorldImagery, 
                       attribution=False, zoom='auto')
    except Exception as e:
        print(f"   ⚠️  No se pudo cargar mapa base: {e}")
        ax_main.set_facecolor("#e8e8e8")

    # ═══════════════════════════════════════════════════════════════════
    # PASO 5: VISUALIZAR ELEMENTOS CON ORDEN CORRECTO
    # ═══════════════════════════════════════════════════════════════════
    print("   🎨 Renderizando elementos...")
    
    orden_visualizacion = [
        'agricola', 'via_vecinal', 'via_departamental', 
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
            
            elif elemento_tipo == 'cp':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='white', markersize=50, marker='o', 
                            linewidth=1.0, alpha=0.95, zorder=10)
                
                # Etiquetas
                col_nombre = encontrar_columna_nombre(gdf_elem, 
                    ['NOMB_CCPP', 'NOMBRE', 'NOMBCCPP', 'CCPP', 'NAME'])
                
                if col_nombre:
                    for idx, row in gdf_elem.iterrows():
                        x, y = row.geometry.x, row.geometry.y
                        nombre = str(row[col_nombre])[:20]  # Limitar longitud
                        ax_main.annotate(nombre, xy=(x, y), xytext=(5, 5),
                                       textcoords='offset points', fontsize=6, 
                                       color=COLORES_ELEMENTOS[elemento_tipo], weight='bold',
                                       path_effects=[path_effects.withStroke(linewidth=2, foreground='white')],
                                       zorder=11)
            
            elif elemento_tipo == 'ie':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='white', markersize=40, marker='s', 
                            linewidth=0.8, alpha=0.9, zorder=9)
                
                # Etiquetas
                col_nombre = encontrar_columna_nombre(gdf_elem, 
                    ['NOMBRE', 'NOMB', 'NAME', 'COD_LOCAL'])
                
                if col_nombre:
                    for idx, row in gdf_elem.iterrows():
                        x, y = row.geometry.x, row.geometry.y
                        nombre = str(row[col_nombre])[:15]
                        ax_main.annotate(nombre, xy=(x, y), xytext=(3, 3),
                                       textcoords='offset points', fontsize=5, 
                                       color=COLORES_ELEMENTOS[elemento_tipo], weight='bold',
                                       path_effects=[path_effects.withStroke(linewidth=1.5, foreground='white')],
                                       zorder=10)
            
            elif elemento_tipo in ['via_nacional', 'via_departamental', 'via_vecinal']:
                linewidth_map = {
                    'via_nacional': 2.0, 
                    'via_departamental': 1.5, 
                    'via_vecinal': 1.0
                }
                zorder_map = {
                    'via_nacional': 8, 
                    'via_departamental': 7, 
                    'via_vecinal': 6
                }
                
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            linewidth=linewidth_map[elemento_tipo], 
                            alpha=0.8, zorder=zorder_map[elemento_tipo])
            
            print(f"      ✅ {elemento_tipo} renderizado")
        
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

    # ═══════════════════════════════════════════════════════════════════
    # PASO 6: MEMBRETE Y LEYENDA
    # ═══════════════════════════════════════════════════════════════════
    gs_memb_ley = gs_izquierda[2].subgridspec(1, 2, wspace=0.1)
    
    # MEMBRETE
    ax_membrete = fig.add_subplot(gs_memb_ley[0])
    fig.canvas.draw()
    add_membrete(ax_membrete, departamento_sel, provincia_sel, distrito_sel, ax_main, fig)

    # LEYENDA
    ax_leyenda = fig.add_subplot(gs_memb_ley[1])
    ax_leyenda.axis('off')

    legend_elements = [
        Patch(facecolor='white', edgecolor='white', label='ELEMENTOS:', linewidth=0)
    ]
    
    # Agregar elementos según lo que se cargó
    if 'agricola' in elementos_procesados:
        legend_elements.append(
            Patch(facecolor=COLORES_ELEMENTOS['agricola'], edgecolor='darkgreen', 
                  label='Zona Agrícola')
        )
    
    if 'cp' in elementos_procesados:
        legend_elements.append(
            Line2D([0], [0], marker='o', color='w', 
                   markerfacecolor=COLORES_ELEMENTOS['cp'], 
                   markeredgecolor='white', markersize=7, linestyle='None', 
                   label='Centro Poblado', markeredgewidth=1.0)
        )
    
    if 'ie' in elementos_procesados:
        legend_elements.append(
            Line2D([0], [0], marker='s', color='w', 
                   markerfacecolor=COLORES_ELEMENTOS['ie'], 
                   markeredgecolor='white', markersize=6, linestyle='None', 
                   label='Infraestructura Educativa', markeredgewidth=0.8)
        )
    
    # Vías
    if any(v in elementos_procesados for v in ['via_nacional', 'via_departamental', 'via_vecinal']):
        legend_elements.extend([
            Patch(facecolor='white', edgecolor='white', label='', linewidth=0),
            Patch(facecolor='white', edgecolor='white', label='VÍAS:', linewidth=0)
        ])
        
        if 'via_nacional' in elementos_procesados:
            legend_elements.append(
                Line2D([0], [0], color=COLORES_ELEMENTOS['via_nacional'], 
                       lw=2.0, label='Vía Nacional')
            )
        
        if 'via_departamental' in elementos_procesados:
            legend_elements.append(
                Line2D([0], [0], color=COLORES_ELEMENTOS['via_departamental'], 
                       lw=1.5, label='Vía Departamental')
            )
        
        if 'via_vecinal' in elementos_procesados:
            legend_elements.append(
                Line2D([0], [0], color=COLORES_ELEMENTOS['via_vecinal'], 
                       lw=1.0, label='Vía Vecinal')
            )
    
    legend_elements.extend([
        Patch(facecolor='white', edgecolor='white', label='', linewidth=0),
        Line2D([0], [0], color='black', lw=1.5, linestyle='-', label='Límite Distrital')
    ])

    leg = ax_leyenda.legend(
        handles=legend_elements, 
        loc='center', 
        ncol=1, 
        frameon=True, 
        fontsize=7,
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

    # AJUSTES FINALES
    plt.subplots_adjust(top=0.98, bottom=0.02, left=0.02, right=0.98, 
                       hspace=0.2, wspace=0.05)

    # MARCO EXTERIOR
    rect_frame = fig.add_axes([0, 0, 1, 1], frameon=False)
    rect_frame.set_xticks([])
    rect_frame.set_yticks([])
    rect_frame.patch.set_visible(False)

    for spine in rect_frame.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(2)
        spine.set_color('black')

    # ═══════════════════════════════════════════════════════════════════
    # PASO 7: GUARDAR MAPA
    # ═══════════════════════════════════════════════════════════════════
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
            print(f"{'='*80}")
            print(f"   📂 Ubicación: {ruta_guardado_final}")
            print(f"   📊 Tamaño: {file_size:.2f} MB")
            print(f"   🎯 Elementos incluidos:")
            for elem in elementos_procesados.keys():
                print(f"      • {elem}: {len(elementos_procesados[elem])} registros")
            print(f"{'='*80}\n")
            
            return ruta_guardado_final
        else:
            print("❌ Error: Archivo no guardado")
            return None

    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        import traceback
        traceback.print_exc()
        plt.close(fig)
        return None


# ═══════════════════════════════════════════════════════════════════════
# 🧪 FUNCIÓN DE PRUEBA
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 PRUEBA DE GENERACIÓN DE MAPA DE ELEMENTOS EXPUESTOS")
    print("="*80)
    
    # Cargar límites administrativos de prueba
    try:
        # Ajusta estas rutas según tu estructura
        ruta_distritos = f"{ruta_base}/DATA/LIMITES/DISTRITOS/DISTRITOS.shp"
        ruta_provincias = f"{ruta_base}/DATA/LIMITES/PROVINCIAS/PROVINCIAS.shp"
        ruta_departamentos = f"{ruta_base}/DATA/LIMITES/DEPARTAMENTOS/DEPARTAMENTOS.shp"
        
        print("\n📦 Cargando límites administrativos...")
        gdf_distritos_full = gpd.read_file(ruta_distritos).to_crs(epsg=3857)
        gdf_provincias_full = gpd.read_file(ruta_provincias).to_crs(epsg=3857)
        gdf_departamentos_full = gpd.read_file(ruta_departamentos).to_crs(epsg=3857)
        
        print(f"   ✅ Distritos: {len(gdf_distritos_full)}")
        print(f"   ✅ Provincias: {len(gdf_provincias_full)}")
        print(f"   ✅ Departamentos: {len(gdf_departamentos_full)}")
        
        # Parámetros de prueba (AJUSTA SEGÚN TUS DATOS)
        departamento_prueba = "CUSCO"
        provincia_prueba = "ANTA"
        distrito_prueba = "ANTA"
        usuario_prueba = "test_user"
        
        print(f"\n🎯 Parámetros de prueba:")
        print(f"   Departamento: {departamento_prueba}")
        print(f"   Provincia: {provincia_prueba}")
        print(f"   Distrito: {distrito_prueba}")
        
        # Detectar columnas
        col_dist = encontrar_columna_nombre(gdf_distritos_full, 
            ['NOMBDIST', 'NOMBRE', 'DISTRITO', 'NAME'])
        col_prov = encontrar_columna_nombre(gdf_provincias_full, 
            ['NOMBPROV', 'NOMBRE', 'PROVINCIA', 'NAME'])
        col_depa = encontrar_columna_nombre(gdf_departamentos_full, 
            ['NOMBDEP', 'NOMBRE', 'DEPARTAMENTO', 'NAME'])
        
        print(f"\n   Columnas detectadas:")
        print(f"   • Distrito: {col_dist}")
        print(f"   • Provincia: {col_prov}")
        print(f"   • Departamento: {col_depa}")
        
        # Filtrar distrito
        gdf_distrito = filtrar_geodataframe_por_nombre(
            gdf_distritos_full, col_dist, distrito_prueba, "Distrito"
        )
        
        print(f"\n   ✅ Distrito filtrado: {len(gdf_distrito)} geometría(s)")
        
        # Generar mapa
        ruta_mapa = generar_mapa_elementos_expuestos(
            usuario_prueba,
            departamento_prueba,
            provincia_prueba,
            distrito_prueba,
            gdf_distrito,
            gdf_departamentos_full,
            gdf_provincias_full
        )
        
        if ruta_mapa:
            print(f"\n✅ PRUEBA EXITOSA")
            print(f"   Mapa guardado en: {ruta_mapa}")
        else:
            print(f"\n❌ PRUEBA FALLIDA")
    
    except Exception as e:
        print(f"\n❌ Error en prueba: {e}")
        import traceback
        traceback.print_exc()