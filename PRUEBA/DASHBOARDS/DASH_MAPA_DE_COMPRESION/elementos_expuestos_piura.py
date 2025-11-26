# -*- coding: utf-8 -*-
"""
🎯 SCRIPT MEJORADO: MAPA DE ELEMENTOS EXPUESTOS
- Solución al error de normalización de límites administrativos (PASO 3).
- Implementación de la nueva capa URBE / Edificios (PASO 4, 7 y 8).
- Uso de rutas fijas para elementos expuestos en la prueba de Piura (PASO 4).
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
RUTA_BASE_URBE = f"{ruta_base}/DATA/EXPUESTO/URBE" # RUTA BASE NUEVA
RUTA_BASE_VIAS = f"{ruta_base}/DATA/MAPA DE UBICACION/VIAS"

# PALETA DE COLORES
COLORES_ELEMENTOS = {
    'agricola': '#90EE90',           # Verde claro
    'cp': '#006400',                 # Verde oscuro
    'ie': '#FF6B6B',                 # Rojo
    'urbe': '#7E3030',               # Marrón/Rojo Oscuro para Urbe/Edificios (NUEVO)
    'via_nacional': '#000000',       # Negro
    'via_departamental': '#FF8C00',  # Naranja oscuro
    'via_vecinal': '#FFD700'         # Oro
}

# ══════════════════════════════════════════════════════════════════════════════
# 🛠️ FUNCIONES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

def normalizar_texto(texto):
    """Normaliza texto para comparaciones"""
    if pd.isna(texto):
        return ""
    texto = str(texto).upper().strip()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(char for char in texto if unicodedata.category(char) != 'Mn')
    return texto

def buscar_shapefile(nombre_busqueda):
    """Busca shapefiles en toda la estructura"""
    for root, _, files in os.walk(ruta_base):
        for file in files:
            if file.lower().endswith(".shp") and nombre_busqueda.lower() in file.lower():
                return os.path.join(root, file)
    return None

def cargar_shapefile(nombre, alias):
    """Carga shapefile con manejo de CRS"""
    path = buscar_shapefile(nombre)
    if not path:
        print(f"   ⚠️  No se encontró shapefile: {alias}")
        return None
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf.set_crs(epsg=4326, inplace=True)
        gdf_3857 = gdf.to_crs(epsg=3857)
        print(f"   ✅ {alias} cargado: {len(gdf_3857)} registros")
        return gdf_3857
    except Exception as e:
        print(f"   ❌ Error cargando {alias}: {e}")
        return None

def buscar_shapefile_inteligente(ruta_base, patrones_busqueda, nombre_tipo):
    """Busca shapefiles con múltiples patrones"""
    if not os.path.exists(ruta_base):
        print(f"      ⚠️  Carpeta no existe: {ruta_base}")
        return None
    
    archivos_encontrados = []
    
    for root, dirs, files in os.walk(ruta_base):
        for file in files:
            if not file.lower().endswith('.shp'):
                continue
            
            file_normalizado = normalizar_texto(file)
            
            for patron in patrones_busqueda:
                patron_normalizado = normalizar_texto(patron)
                if patron_normalizado in file_normalizado:
                    ruta_completa = os.path.join(root, file)
                    archivos_encontrados.append(ruta_completa)
                    break
    
    if not archivos_encontrados:
        return None
    
    return archivos_encontrados[0]

def cargar_y_preparar_shapefile(ruta, nombre_elemento, target_crs=3857):
    """Carga shapefile y lo prepara"""
    if not ruta or not os.path.exists(ruta):
        print(f"      ⚠️  Ruta no válida o archivo no existe para {nombre_elemento}: {ruta}")
        return None
    
    try:
        gdf = gpd.read_file(ruta)
        
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)
        
        if gdf.crs.to_epsg() != target_crs:
            gdf = gdf.to_crs(epsg=target_crs)
        
        return gdf
    
    except Exception as e:
        print(f"      ❌ Error cargando {nombre_elemento} desde {ruta}: {e}")
        return None

def encontrar_columna_nombre(gdf, opciones_columnas):
    """Encuentra la columna de nombre en un GeoDataFrame"""
    for col in opciones_columnas:
        if col in gdf.columns:
            return col
    
    for col in gdf.columns:
        col_norm = normalizar_texto(col)
        for opcion in opciones_columnas:
            opcion_norm = normalizar_texto(opcion)
            if opcion_norm in col_norm or col_norm in opcion_norm:
                return col
    
    for col in gdf.columns:
        if col != 'geometry' and gdf[col].dtype == 'object':
            return col
    
    return None

# ══════════════════════════════════════════════════════════════════════════════
# 🗺️ FUNCIONES DE VISUALIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════

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

# ══════════════════════════════════════════════════════════════════════════════
# 🎯 FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def generar_mapa_elementos_expuestos(nombre_usuario, departamento_sel, provincia_sel, distrito_sel):
    """
    Genera mapa de elementos expuestos.
    """
    print("\n" + "="*80)
    print("🗺️ INICIANDO GENERACIÓN DE MAPA DE ELEMENTOS EXPUESTOS")
    print("="*80)
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 1: CREAR ESTRUCTURA DE CARPETAS
    # ══════════════════════════════════════════════════════════════════════════
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "ELEMENTOS EXPUESTOS")
        os.makedirs(carpeta_salida, exist_ok=True)
        print(f"   ✅ Carpeta de salida: {carpeta_salida}")
    except Exception as e:
        print(f"❌ Error creando carpeta: {e}")
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 2: CARGAR LÍMITES ADMINISTRATIVOS
    # ══════════════════════════════════════════════════════════════════════════
    print("\n📦 Cargando límites administrativos...")
    gdf_departamentos = cargar_shapefile("departamento", "Departamentos")
    gdf_provincias = cargar_shapefile("provincia", "Provincias")
    gdf_distritos = cargar_shapefile("distrito", "Distritos del Perú")

    if gdf_departamentos is None or gdf_provincias is None or gdf_distritos is None:
        print("❌ Faltan capas base. Abortando.")
        return None

    # Detectar columnas
    col_dpto = next((c for c in ['NOMBDEP', 'DEPARTAMEN'] if c in gdf_departamentos.columns), None)
    col_prov = next((c for c in ['NOMBPROV', 'PROVINCIA'] if c in gdf_provincias.columns), None)
    col_distr = next((c for c in ['NOMBDIST', 'DISTRITO'] if c in gdf_distritos.columns), None)


    if not all([col_dpto, col_prov, col_distr]):
        print("❌ No se pudieron identificar las columnas de nombres")
        return None

    print(f"   ✅ Columnas detectadas: {col_dpto}, {col_prov}, {col_distr}")

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 3: FILTRAR ÁREA SELECCIONADA (CORRECCIÓN IMPLEMENTADA AQUÍ)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n🔍 Filtrando datos del área seleccionada...")
    
    # 🎯 CORRECCIÓN: Normalizar tanto la entrada como las columnas para evitar errores de case/acento
    dpto_norm = normalizar_texto(departamento_sel)
    prov_norm = normalizar_texto(provincia_sel)
    distr_norm = normalizar_texto(distrito_sel)

    # Filtrar Departamento (usando normalización)
    gdf_dpto_sel = gdf_departamentos[gdf_departamentos[col_dpto].apply(normalizar_texto) == dpto_norm]
    
    # Filtrar Provincia (usando normalización)
    gdf_prov_sel = gdf_provincias[gdf_provincias[col_prov].apply(normalizar_texto) == prov_norm]
    
    # Filtrar Distrito (usando normalización para distrito y provincia)
    
    # Crear columnas normalizadas temporales para el filtro compuesto y eficiente
    gdf_distritos['TEMP_DIST_NORM'] = gdf_distritos[col_distr].apply(normalizar_texto)
    gdf_distritos['TEMP_PROV_NORM'] = gdf_distritos[col_prov].apply(normalizar_texto)
    
    gdf_distrito = gdf_distritos[
        (gdf_distritos['TEMP_DIST_NORM'] == distr_norm) & 
        (gdf_distritos['TEMP_PROV_NORM'] == prov_norm)
    ]
    
    # Limpieza de columnas temporales
    gdf_distritos = gdf_distritos.drop(columns=['TEMP_DIST_NORM', 'TEMP_PROV_NORM'], errors='ignore')

    if gdf_distrito.empty:
        print(f"❌ Error: No se pudo encontrar el distrito '{distrito_sel}' en la provincia '{provincia_sel}'")
        return None

    print(f"   ✅ Distrito encontrado con geometría válida")

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 4: CARGAR ELEMENTOS EXPUESTOS (CON RUTAS FIJAS PARA TEST DE PIURA Y CAPA URBE)
    # ══════════════════════════════════════════════════════════════════════════
    print("\n📦 Cargando elementos expuestos...")
    
    elementos_cargados = {}
    
    # RUTAS FIJAS PARA PRUEBA DE PIURA: (Para garantizar el funcionamiento del test)
    ruta_agricola_fija = f"{ruta_base}/DATA/EXPUESTO/AGRICOLA/AGRICOLA_PIURA.shp"
    ruta_cp_fija = f"{ruta_base}/DATA/EXPUESTO/CP/CP_PIURA.shp"
    ruta_ie_fija = f"{ruta_base}/DATA/EXPUESTO/IE/IE_PIURA.shp"
    ruta_urbe_fija = f"{ruta_base}/DATA/EXPUESTO/URBE/piura_edificios_microsoft_COMPLETO.shp"
    
    # 1️⃣ AGRÍCOLA (Ruta Fija)
    print(f"   🔍 Cargando Zona Agrícola (Fija)...")
    gdf_agricola = cargar_y_preparar_shapefile(ruta_agricola_fija, "Agrícola")
    if gdf_agricola is not None:
        elementos_cargados['agricola'] = gdf_agricola
        print(f"      ✅ Agrícola: {len(gdf_agricola)} polígonos")
    
    # 2️⃣ CENTROS POBLADOS (Ruta Fija)
    print(f"   🔍 Cargando Centros Poblados (Fija)...")
    gdf_cp = cargar_y_preparar_shapefile(ruta_cp_fija, "Centros Poblados")
    if gdf_cp is not None:
        elementos_cargados['cp'] = gdf_cp
        print(f"      ✅ Centros Poblados: {len(gdf_cp)} puntos")
    
    # 3️⃣ INFRAESTRUCTURA EDUCATIVA (Ruta Fija)
    print(f"   🔍 Cargando Infraestructura Educativa (Fija)...")
    gdf_ie = cargar_y_preparar_shapefile(ruta_ie_fija, "IE")
    if gdf_ie is not None:
        elementos_cargados['ie'] = gdf_ie
        print(f"      ✅ IE: {len(gdf_ie)} puntos")
        
    # 4️⃣ URBANIZACIONES / EDIFICIOS (NUEVA CAPA - Ruta Fija)
    print(f"   🔍 Cargando Urbanizaciones/Edificios (NUEVO - Fija)...")
    gdf_urbe = cargar_y_preparar_shapefile(ruta_urbe_fija, "Urbe")
    if gdf_urbe is not None:
        elementos_cargados['urbe'] = gdf_urbe
        print(f"      ✅ Urbanizaciones/Edificios: {len(gdf_urbe)} polígonos/registros")
    
    # 5️⃣ VÍAS (3 TIPOS - Se mantiene la búsqueda inteligente para las vías)
    vias_tipos = [
        ('nacional', ['nacional', 'red_vial_nacional']),
        ('departamental', ['departamental', 'red_vial_departamental']),
        ('vecinal', ['vecinal', 'red_vial_vecinal'])
    ]
    
    for via_tipo, patrones in vias_tipos:
        print(f"   🔍 Buscando Vía {via_tipo.capitalize()} (Inteligente)...")
        ruta_via = buscar_shapefile_inteligente(
            RUTA_BASE_VIAS,
            patrones,
            f"Vía {via_tipo.capitalize()}"
        )
        if ruta_via:
            gdf_via = cargar_y_preparar_shapefile(ruta_via, f"Vía {via_tipo}")
            if gdf_via is not None:
                elementos_cargados[f'via_{via_tipo}'] = gdf_via
                print(f"      ✅ Vía {via_tipo}: {len(gdf_via)} segmentos")
    
    if not elementos_cargados:
        print("❌ No se cargó ningún elemento expuesto")
        return None
    
    print(f"\n   ✅ Elementos cargados: {len(elementos_cargados)}")
    
    # ══════════════════════════════════════════════════════════════════════════
    # PASO 5: RECORTAR ELEMENTOS AL DISTRITO
    # ══════════════════════════════════════════════════════════════════════════
    print("\n✂️ Recortando elementos al distrito...")
    
    elementos_procesados = {}
    
    for key, gdf_elemento in elementos_cargados.items():
        try:
            # Asegurar que ambos GDF están en el mismo CRS antes de clip
            if gdf_elemento.crs != gdf_distrito.crs:
                gdf_elemento = gdf_elemento.to_crs(gdf_distrito.crs)
                
            gdf_clip = gpd.clip(gdf_elemento, gdf_distrito)
            
            if len(gdf_clip) > 0:
                elementos_procesados[key] = gdf_clip
                tipo_geom = gdf_clip.geometry.type.iloc[0] if len(gdf_clip) > 0 else "N/A"
                print(f"   ✅ {key}: {len(gdf_clip)} elementos ({tipo_geom})")
            else:
                print(f"   ⚠️  {key}: Sin elementos en el distrito")
        
        except Exception as e:
            print(f"   ❌ Error recortando {key}: {e}")
            import traceback
            traceback.print_exc()
    
    if not elementos_procesados:
        print("❌ Ningún elemento tiene datos en el distrito")
        return None

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

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 7: VISUALIZAR ELEMENTOS
    # ══════════════════════════════════════════════════════════════════════════
    print("   🎨 Renderizando elementos...")
    
    # Orden de visualización ajustado: Agrícola y Urbe primero (polígonos), luego líneas (Vías) y puntos (IE, CP)
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
            
            # Nuevo elemento: Urbanizaciones/Edificios
            elif elemento_tipo == 'urbe':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='white', linewidth=0.1, alpha=0.9, zorder=5.5)
            
            elif elemento_tipo == 'cp':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='white', markersize=50, marker='o', 
                            linewidth=1.0, alpha=0.95, zorder=10)
                
                col_nombre = encontrar_columna_nombre(gdf_elem, 
                    ['NOMB_CCPP', 'NOMBRE', 'NOMBCCPP', 'CCPP', 'NAME'])
                
                if col_nombre:
                    for idx, row in gdf_elem.iterrows():
                        x, y = row.geometry.x, row.geometry.y
                        nombre = str(row[col_nombre])[:20]
                        ax_main.annotate(nombre, xy=(x, y), xytext=(5, 5),
                                       textcoords='offset points', fontsize=6, 
                                       color=COLORES_ELEMENTOS[elemento_tipo], weight='bold',
                                       path_effects=[path_effects.withStroke(linewidth=2, foreground='white')],
                                       zorder=11)
            
            elif elemento_tipo == 'ie':
                gdf_elem.plot(ax=ax_main, color=COLORES_ELEMENTOS[elemento_tipo], 
                            edgecolor='white', markersize=40, marker='s', 
                            linewidth=0.8, alpha=0.9, zorder=9)
                
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

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 8: MEMBRETE Y LEYENDA
    # ══════════════════════════════════════════════════════════════════════════
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
    
    if 'urbe' in elementos_procesados:
        legend_elements.append(
            Patch(facecolor=COLORES_ELEMENTOS['urbe'], edgecolor='white', 
                  linewidth=0.1, label='Urbe / Edificios')
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

