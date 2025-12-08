# Archivo: geologia_final.py

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
import matplotlib.colors as mcolors
import math
import pandas as pd

# --- RUTA BASE ORIGINAL ---
ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"

AMARILLO_CLARO = "#E6D07A"  # tono menos brillante que el original
LABEL_COLOR = "#0B66C3"     # azul para etiquetas de alcance/etiqueta
COLOR_FOCUS = "#C03030"     # rojo menos saturado para límites/área de foco
PAISES_COLOR = "#CFCFCF"    # plomo claro para la capa de países

# ═══════════════════════════════════════════════════════════════════════════════
# 🎨 FUNCIÓN PARA GENERAR PALETA DE COLORES GEOLÓGICOS
# ═══════════════════════════════════════════════════════════════════════════════
def generar_paleta_geologia(num_categorias):
    """Genera una paleta de colores distintiva para geología (estratigrafía)"""
    # Colores basados en la carta estratigráfica internacional
    colores_base = [
        '#F04028', '#F0C868', '#FFC848', '#FFD848', '#F8E468',
        '#E0C860', '#F4D438', '#FFE030', '#FFEC20', '#FFF418',
        '#7FC64E', '#8CD446', '#A0DC3E', '#B4E436', '#C8EC2E',
        '#34B2C8', '#28A8DC', '#1C9EF0', '#1094FF', '#048AFF',
        '#9C82BC', '#B896D4', '#D4AAEC', '#D0A0E0', '#CC96D4',
        '#808080', '#999999', '#B3B3B3', '#CCCCCC', '#E6E6E6'
    ]
    
    if num_categorias <= len(colores_base):
        return colores_base[:num_categorias]
    else:
        colores_extra = []
        for i in range(num_categorias - len(colores_base)):
            h = (i / (num_categorias - len(colores_base))) % 1.0
            rgb = mcolors.hsv_to_rgb((h, 0.7, 0.85))
            colores_extra.append(mcolors.rgb2hex(rgb))
        return colores_base + colores_extra

# ═══════════════════════════════════════════════════════════════════════════════
# 🪨 FUNCIÓN PARA CARGAR GEOLOGÍA
# ═══════════════════════════════════════════════════════════════════════════════
def cargar_geologia(departamento):
    """Carga el shapefile de geología según el departamento seleccionado"""
    rutas_posibles = [
        f"{ruta_base}/DATA/GEOLOGIA/{departamento.upper()}/geolo_{departamento.lower()}.shp",
        f"{ruta_base}/DATA/GEOLOGIA/{departamento.lower()}/geolo_{departamento.lower()}.shp",
        f"{ruta_base}/DATA/GEOLOGIA/geolo_{departamento.lower()}.shp",
        f"{ruta_base}/DATA/GEOLOGIA/{departamento.upper()}/geologia_{departamento.lower()}.shp",
        f"{ruta_base}/DATA/GEOLOGIA/{departamento.lower()}/geologia_{departamento.lower()}.shp"
    ]
    
    ruta_geologia = None
    for ruta in rutas_posibles:
        print(f"   Buscando en: {ruta}")
        if os.path.exists(ruta):
            ruta_geologia = ruta
            print(f"   ✅ Archivo encontrado!")
            break
    
    if ruta_geologia is None:
        print(f"   ❌ No se encontró geología para {departamento} en ninguna ubicación")
        return None
    
    try:
        gdf_geologia = gpd.read_file(ruta_geologia)
        if gdf_geologia.crs is None:
            gdf_geologia.set_crs(epsg=4326, inplace=True)
        gdf_geologia = gdf_geologia.to_crs(epsg=3857)
        print(f"   ✅ Geología cargada: {len(gdf_geologia)} polígonos")
        return gdf_geologia
    except Exception as e:
        print(f"   ❌ Error cargando geología: {e}")
        import traceback
        traceback.print_exc()
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════════════
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


def add_north_arrow_esquina(ax, xy_pos=(0.96, 0.96), size=0.04, offset=0.02, halo_width=0.8):
    """Dibuja una flecha de norte cerca de la esquina superior derecha.
    Cambios respecto a la versión anterior:
    - Se desplaza hacia adentro usando `offset` para separarla de la esquina.
    - Se dibuja la forma interior como un único polígono blanco con contorno negro
      (evita las separaciones negras entre triángulo y asta).
    - Contorno más fino y más limpio.
    """
    # Ajustar posición hacia adentro desde la esquina (offset en unidades de axes)
    base_x = xy_pos[0] - offset
    base_y = xy_pos[1] - offset
    x = base_x
    y = base_y
    s = size

    # Coordenadas del polígono combinado (triángulo + rectángulo) en coordenadas de ejes
    tip = (x, y)
    left_base = (x - s * 0.45, y - s * 0.60)
    left_body_bottom = (x - s * 0.12, y - s * 1.02)
    right_body_bottom = (x + s * 0.12, y - s * 1.02)
    right_base = (x + s * 0.45, y - s * 0.60)

    # En lugar de usar escala uniforme (que producía formas no deseadas), construimos
    # explícitamente una flecha compuesta por punta triangular y asta rectangular.
    tip = (x, y)
    tip_y = y
    base_y = y - s * 0.60
    shaft_bottom_y = y - s * 1.08

    left_tip = (x - s * 0.45, base_y)
    right_tip = (x + s * 0.45, base_y)
    left_shaft = (x - s * 0.18, base_y)
    right_shaft = (x + s * 0.18, base_y)
    left_shaft_bottom = (x - s * 0.18, shaft_bottom_y)
    right_shaft_bottom = (x + s * 0.18, shaft_bottom_y)

    # Polígono exterior negro (sirve como borde)
    outer_coords = np.array([
        tip,
        left_tip,
        left_shaft,
        left_shaft_bottom,
        right_shaft_bottom,
        right_shaft,
        right_tip
    ])
    # Dibujar la flecha totalmente negra con un halo blanco delgado
    poly = Polygon(outer_coords, transform=ax.transAxes, facecolor='black', edgecolor='none', linewidth=0, zorder=61)
    poly.set_path_effects([path_effects.withStroke(linewidth=halo_width, foreground='white')])
    ax.add_patch(poly)

    # (Se elimina el polígono interior blanco para dejar la flecha completamente negra)

    # Texto 'N' encima, con halo blanco fino
    ax.text(x, tip_y + s * 0.08, 'N', transform=ax.transAxes, fontsize=10, fontweight='bold',
            ha='center', va='bottom', color='black', zorder=62,
            path_effects=[path_effects.withStroke(linewidth=1.2, foreground='white')])

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
        "MAPA": f"MAPA GEOLÓGICO: DISTRITO DE {dist.upper()}",
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
        print(f"   ❌ No se encontró shapefile: {alias}")
        return None
    
    try:
        gdf = gpd.read_file(path)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf.set_crs(epsg=4326, inplace=True)
        return gdf.to_crs(epsg=3857)
    except Exception as e:
        print(f"   ❌ Error cargando {alias} desde {path}: {e}")
        return None


def cargar_shapfile_por_ruta(ruta_posible, alias=None):
    """Intenta cargar un shapefile desde una ruta absoluta o su nombre buscando en `ruta_base`.
    Devuelve un GeoDataFrame proyectado a EPSG:3857 o `None` si falla."""
    if ruta_posible is None:
        return None

    candidatos = []
    # Si la ruta es absoluta y existe
    if os.path.isabs(ruta_posible) and os.path.exists(ruta_posible):
        candidatos.append(ruta_posible)

    # Intentar ruta relativa dentro de ruta_base
    ruta_rel = os.path.join(ruta_base, os.path.relpath(ruta_posible, '/workspaces/AUTOMATIZACION_DASH/PRUEBA'))
    if os.path.exists(ruta_rel):
        candidatos.append(ruta_rel)

    # Intentar buscar por nombre de archivo
    nombre_archivo = os.path.basename(ruta_posible)
    encontrado = buscar_shapefile(nombre_archivo)
    if encontrado:
        candidatos.append(encontrado)

    for ruta in candidatos:
        try:
            gdf = gpd.read_file(ruta)
            if gdf.crs is None:
                gdf.set_crs(epsg=4326, inplace=True)
            gdf = gdf.to_crs(epsg=3857)
            print(f"   ✅ Cargado {alias or nombre_archivo} desde: {ruta}")
            return gdf
        except Exception as e:
            print(f"   ⚠️ Error cargando {alias or nombre_archivo} desde {ruta}: {e}")

    print(f"   ❌ No se pudo localizar ni cargar: {alias or nombre_archivo}")
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
        # Para el inset de distrito queremos un acercamiento mayor
        # Usar preferentemente la extensión de la provincia seleccionada (más zoom)
        try:
            if gdf_prov_sel is not None and not gdf_prov_sel.empty:
                bbox_geom = gdf_prov_sel.total_bounds
                # reducir el buffer para acercar más (5% de la dimensión)
                dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.05, (bbox_geom[3] - bbox_geom[1]) * 0.05
            else:
                # fallback: usar la heurística previa (provincia + vecinas)
                provincia_seleccionada_geom = gdf_prov_sel.geometry.unary_union if gdf_prov_sel is not None else None
                geoms_vecinas = [prov.geometry for _, prov in gdf_provincias.iterrows() 
                                if prov[col_prov] != provincia_sel and provincia_seleccionada_geom is not None and prov.geometry.touches(provincia_seleccionada_geom)]
                area_de_interes = gpd.GeoSeries([provincia_seleccionada_geom] + geoms_vecinas).unary_union
                bbox_geom = area_de_interes.bounds
                dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.08, (bbox_geom[3] - bbox_geom[1]) * 0.08
        except Exception:
            # en caso de error, usar la provincia si está disponible o un fallback amplio
            try:
                if gdf_prov_sel is not None and not gdf_prov_sel.empty:
                    bbox_geom = gdf_prov_sel.total_bounds
                    dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.05, (bbox_geom[3] - bbox_geom[1]) * 0.05
                else:
                    bbox_geom = gdf_departamentos.total_bounds
                    dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.25, (bbox_geom[3] - bbox_geom[1]) * 0.25
            except Exception:
                bbox_geom = gdf_departamentos.total_bounds
                dx, dy = (bbox_geom[2] - bbox_geom[0]) * 0.25, (bbox_geom[3] - bbox_geom[1]) * 0.25
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
            # pintar países con tono plomo claro
            gdf_base_map.plot(ax=ax, color=PAISES_COLOR, edgecolor="black", linewidth=0.4, zorder=1)
        if gdf_context is not None:
            # Pintar otros departamentos en plomo claro y el departamento seleccionado en amarillo
            try:
                col_name_dpto = next((c for c in ['NOMBDEP', 'NOMBRE', 'NOMB', 'NOMBDEP', 'DEPARTAMEN'] if c in gdf_context.columns), None)
                if col_name_dpto is not None and departamento_sel is not None:
                    try:
                        gdf_context[gdf_context[col_name_dpto] != departamento_sel].plot(
                            ax=ax, color=PAISES_COLOR, edgecolor='black', linewidth=0.4, zorder=1)
                    except Exception:
                        pass
                    try:
                        gdf_context[gdf_context[col_name_dpto] == departamento_sel].plot(
                            ax=ax, color=AMARILLO_CLARO, edgecolor='black', linewidth=0.7, zorder=3)
                    except Exception:
                        pass
                else:
                    # fallback: pintar todo el contexto en amarillo
                    gdf_context.plot(ax=ax, color=AMARILLO_CLARO, edgecolor='black', linewidth=0.7, zorder=3)
            except Exception:
                try:
                    gdf_context.plot(ax=ax, color=AMARILLO_CLARO, edgecolor='black', linewidth=0.7, zorder=3)
                except Exception:
                    pass
        # Etiquetar países con letra azul
        try:
            if gdf_base_map is not None:
                # intentar columnas estándar
                # Priorizar columna con nombres completos en español si existe (según datos adjuntos)
                possible_name_cols = ['NOMB_PAIS', 'NOMB', 'NOMBRE', 'NAME', 'Name', 'PAIS', 'PAÍS', 'COUNTRY', 'COUNTRY_NAME', 'NAME_0', 'ADMIN']
                name_col = next((c for c in possible_name_cols if c in gdf_base_map.columns), None)
                x0, y0, x1, y1 = bbox
                for _, row in gdf_base_map.iterrows():
                    if row.geometry is None:
                        continue
                    centroid = row.geometry.representative_point()
                    # Solo etiquetar si la centroid está dentro del bbox visible
                    if not (centroid.x >= x0 and centroid.x <= x1 and centroid.y >= y0 and centroid.y <= y1):
                        continue

                    label_val = None
                    if name_col and pd.notna(row.get(name_col)):
                        label_val = str(row.get(name_col))
                    else:
                        # fallback: buscar la primera columna con texto no vacío
                        for col in row.index:
                            val = row.get(col)
                            if isinstance(val, str) and val.strip():
                                label_val = val.strip()
                                break

                    # excluir etiqueta para Perú
                    if label_val and label_val.strip().lower() not in ['peru', 'perú', 'república del perú', 'republica del perú']:
                        ax.text(centroid.x, centroid.y, label_val, fontsize=6, color='black', ha='center', va='center', zorder=9,
                                path_effects=[path_effects.withStroke(linewidth=0.8, foreground='white')])

                # Forzar etiquetas específicas (Brasil y Chile) aunque su centroid esté fuera del bbox
                def _get_label_from_row(r):
                    if name_col and pd.notna(r.get(name_col)):
                        return str(r.get(name_col))
                    for c in r.index:
                        v = r.get(c)
                        if isinstance(v, str) and v.strip():
                            return v.strip()
                    return None

                # Colocar las etiquetas en el extremo derecho del bbox (margen pequeño) para que siempre se vean
                tx_edge = x1 - (x1 - x0) * 0.02
                ty_top = y1 - (y1 - y0) * 0.12
                ty_bottom = y0 + (y1 - y0) * 0.12

                forced_list = [
                    ('BRASIL', (tx_edge, ty_top)),
                    ('CHILE',  (tx_edge, ty_bottom))
                ]

                for country_key, (tx, ty) in forced_list:
                    found = None
                    for _, r in gdf_base_map.iterrows():
                        lab = _get_label_from_row(r)
                        if lab and country_key in lab.upper():
                            found = r
                            break
                    if found is not None:
                        try:
                            centroid_c = found.geometry.representative_point()
                            # Dibujar anotación en el extremo con una cola hacia la geometría
                            ax.annotate(_get_label_from_row(found), xy=(centroid_c.x, centroid_c.y), xytext=(tx, ty),
                                        textcoords='data', fontsize=6, color='black', ha='center', va='center', zorder=12,
                                        path_effects=[path_effects.withStroke(linewidth=0.8, foreground='white')],
                                        arrowprops=dict(arrowstyle='-', linewidth=0.8, color='black', shrinkA=0, shrinkB=0))
                        except Exception:
                            pass
                # Además, colocar etiquetas de países vecinos pegadas a Perú (con espacio prudencial)
                try:
                    # Buscar la fila de Perú para usar como referencia
                    peru_row = None
                    for _, r in gdf_base_map.iterrows():
                        labr = _get_label_from_row(r)
                        if labr and labr.strip().lower() in ['peru', 'perú', 'república del perú', 'republica del perú']:
                            peru_row = r
                            break

                    if peru_row is not None:
                        peru_cent = peru_row.geometry.representative_point()
                        S = max(x1 - x0, y1 - y0)
                        base_x = peru_cent.x + S * 0.03
                        base_y = peru_cent.y
                        spacing = S * 0.035  # espacio prudencial entre etiquetas

                        vecinos = ['ECUADOR', 'COLOMBIA', 'BOLIVIA', 'BRASIL', 'CHILE']
                        idx = 0
                        for vecino in vecinos:
                            # buscar fila del vecino
                            found_v = None
                            for _, r in gdf_base_map.iterrows():
                                labv = _get_label_from_row(r)
                                if labv and vecino in labv.upper():
                                    found_v = r
                                    break
                            if found_v is None:
                                continue

                            # si su centroid ya está dentro del bbox, omitimos (ya fue etiquetado)
                            try:
                                ccent = found_v.geometry.representative_point()
                                if (ccent.x >= x0 and ccent.x <= x1 and ccent.y >= y0 and ccent.y <= y1):
                                    continue
                            except Exception:
                                pass

                            ty = base_y + (idx - len(vecinos)//2) * spacing
                            try:
                                ax.annotate(_get_label_from_row(found_v), xy=(ccent.x, ccent.y), xytext=(base_x, ty),
                                            textcoords='data', fontsize=6, color='black', ha='center', va='center', zorder=12,
                                            path_effects=[path_effects.withStroke(linewidth=0.8, foreground='white')],
                                            arrowprops=dict(arrowstyle='-', linewidth=0.8, color='black', shrinkA=0, shrinkB=0))
                            except Exception:
                                pass
                            idx += 1
                except Exception:
                    pass
        except Exception:
            pass
        # Etiquetar océano (si está disponible) dentro del bbox
        try:
            if gdf_oceano is not None:
                # Priorizar columna `CNTRY_NAME` (observada en los datos de océano), luego otras opciones
                oce_col = next((c for c in ['CNTRY_NAME', 'CNTRY_NAM', 'NAME', 'Name', 'NOMBRE', 'OCÉANO', 'OCEANO', 'OCEAN', 'DESCRIP'] if c in gdf_oceano.columns), None)
                if oce_col:
                    x0, y0, x1, y1 = bbox
                    for _, row in gdf_oceano.iterrows():
                        if row.geometry is None:
                            continue
                        try:
                            # Si el océano intersecta el bbox, etiquetamos en la intersección para que la etiqueta quede dentro
                            bbox_poly = box(x0, y0, x1, y1)
                            if row.geometry.intersects(bbox_poly):
                                geom_int = row.geometry.intersection(bbox_poly)
                                if not geom_int.is_empty:
                                    label_point = geom_int.representative_point()
                                else:
                                    label_point = row.geometry.representative_point()
                            else:
                                # Si no intersecta, usar centroid habitual (posiblemente estará fuera y se omitirá)
                                label_point = row.geometry.representative_point()

                            # Etiqueta en azul sin halo (según petición)
                            if label_point.x >= x0 and label_point.x <= x1 and label_point.y >= y0 and label_point.y <= y1:
                                ax.text(label_point.x, label_point.y, str(row[oce_col]), fontsize=6, color=LABEL_COLOR, ha='center', va='center', zorder=8)
                            else:
                                # Si queda fuera, dibujar etiqueta en el borde derecho-centro con una cola, en azul sin halo
                                tx = x1 - (x1 - x0) * 0.02
                                ty = (y0 + y1) / 2
                                ax.annotate(str(row[oce_col]), xy=(label_point.x, label_point.y), xytext=(tx, ty),
                                            textcoords='data', fontsize=6, color=LABEL_COLOR, ha='center', va='center', zorder=8,
                                            arrowprops=dict(arrowstyle='-', linewidth=0.8, color=LABEL_COLOR, shrinkA=0, shrinkB=0))
                        except Exception:
                            continue
        except Exception:
            pass
    elif tipo_mapa == "provincia":
        # Pintar todos los departamentos en plomo claro y el departamento seleccionado en amarillo
        try:
            if gdf_departamentos is not None:
                gdf_departamentos.plot(ax=ax, color=PAISES_COLOR, edgecolor='black', linewidth=0.4, zorder=1)
        except Exception:
            # fallback: si no está gdf_departamentos, usar gdf_base_map
            try:
                if gdf_base_map is not None:
                    gdf_base_map.plot(ax=ax, color=PAISES_COLOR, edgecolor='black', linewidth=0.4, zorder=1)
            except Exception:
                pass

        try:
            # dibujar el departamento seleccionado en amarillo (puede llegar como gdf_dpto_sel o gdf_context)
            dpto_sel_gdf = gdf_dpto_sel if gdf_dpto_sel is not None else gdf_context
            if dpto_sel_gdf is not None and not dpto_sel_gdf.empty:
                dpto_sel_gdf.plot(ax=ax, color=AMARILLO_CLARO, edgecolor='black', linewidth=0.7, zorder=3)
        except Exception:
            pass

        # Etiquetar departamentos en negro, excepto el departamento seleccionado (no mostrarlo)
        try:
            if gdf_departamentos is not None:
                col_name_dpto = next((c for c in ['NOMBDEP', 'NOMBRE', 'NOMB', 'NOMBDEP', 'DEPARTAMEN'] if c in gdf_departamentos.columns), None)
                if col_name_dpto:
                    x0, y0, x1, y1 = bbox
                    for _, row in gdf_departamentos.iterrows():
                        if row.geometry is None:
                            continue
                        # Omitir etiqueta si corresponde al departamento seleccionado
                        try:
                            vname = str(row[col_name_dpto]) if pd.notna(row[col_name_dpto]) else ''
                        except Exception:
                            vname = ''
                        if vname.strip().upper() == (departamento_sel or '').strip().upper():
                            continue

                        centroid = row.geometry.representative_point()
                        # Solo etiquetar si la centroid está dentro del bbox visible
                        if centroid.x >= x0 and centroid.x <= x1 and centroid.y >= y0 and centroid.y <= y1:
                            ax.text(centroid.x, centroid.y, vname, fontsize=6, color='black', ha='center', va='center', zorder=9)
        except Exception:
            pass

        # Etiquetar océano en azul sin halo si está disponible
        try:
            if gdf_oceano is not None:
                oce_col = next((c for c in ['CNTRY_NAME', 'CNTRY_NAM', 'NAME', 'Name', 'NOMBRE', 'OCÉANO', 'OCEANO', 'OCEAN', 'DESCRIP'] if c in gdf_oceano.columns), None)
                if oce_col:
                    x0, y0, x1, y1 = bbox
                    for _, row in gdf_oceano.iterrows():
                        if row.geometry is None:
                            continue
                        try:
                            bbox_poly = box(x0, y0, x1, y1)
                            if row.geometry.intersects(bbox_poly):
                                geom_int = row.geometry.intersection(bbox_poly)
                                if not geom_int.is_empty:
                                    label_point = geom_int.representative_point()
                                else:
                                    label_point = row.geometry.representative_point()
                            else:
                                label_point = row.geometry.representative_point()

                            if label_point.x >= x0 and label_point.x <= x1 and label_point.y >= y0 and label_point.y <= y1:
                                ax.text(label_point.x, label_point.y, str(row[oce_col]), fontsize=6, color=LABEL_COLOR, ha='center', va='center', zorder=8)
                            else:
                                tx = x1 - (x1 - x0) * 0.02
                                ty = (y0 + y1) / 2
                                ax.annotate(str(row[oce_col]), xy=(label_point.x, label_point.y), xytext=(tx, ty),
                                            textcoords='data', fontsize=6, color=LABEL_COLOR, ha='center', va='center', zorder=8,
                                            arrowprops=dict(arrowstyle='-', linewidth=0.8, color=LABEL_COLOR, shrinkA=0, shrinkB=0))
                        except Exception:
                            continue
        except Exception:
            pass
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
        # Etiqueta del foco: en el mapa 'pais' usar texto más pequeño, negro y halo delgado; en otros mapas mantener azul
        fx = gdf_focus.geometry.centroid.iloc[0].x
        fy = gdf_focus.geometry.centroid.iloc[0].y
        if tipo_mapa == "pais":
            ax.text(fx, fy, etiqueta.upper(), color='black', fontsize=6, ha="center", va="center", zorder=9,
                    path_effects=[path_effects.withStroke(linewidth=0.8, foreground='white')])
        else:
            ax.text(fx, fy, etiqueta.upper(), color=LABEL_COLOR, fontsize=8, ha="center", va="center", zorder=9,
                    path_effects=[path_effects.withStroke(linewidth=3, foreground='white')])
    
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])
    ax.set_facecolor("#f0f8ff")
    ax.set_aspect('equal', adjustable='box')
    ax.axis('on')

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL DE GENERACIÓN DE MAPA GEOLÓGICO
# ═══════════════════════════════════════════════════════════════════════════════
def generar_mapa_geologia(nombre_usuario, departamento_sel, provincia_sel, distrito_sel):
    print("\n" + "="*80)
    print("🪨 INICIANDO PROCESO DE GENERACIÓN DE MAPA GEOLÓGICO...")
    print(f"   - Usuario: {nombre_usuario}")
    print(f"   - Ubicación: {distrito_sel}, {provincia_sel}, {departamento_sel}")
    
    try:
        carpeta_usuario = os.path.join(ruta_base, "USUARIOS", nombre_usuario)
        carpeta_salida = os.path.join(carpeta_usuario, "MAPA GEOLOGICO")
        os.makedirs(carpeta_salida, exist_ok=True)
        print(f"   ✅ Carpeta de salida verificada: {carpeta_salida}")
    except Exception as e:
        print(f"❌ Error creando la estructura de carpetas para el usuario: {e}")
        return None
    
    print("\n📂 Cargando capas base...")
    gdf_departamentos = cargar_shapefile("departamento", "Departamentos")
    gdf_provincias = cargar_shapefile("provincia", "Provincias")
    gdf_distritos = cargar_shapefile("distrito", "Distritos del Perú")
    
    try:
        gdf_paises = gpd.read_file(f"{ruta_base}/DATA/MAPA_DE_UBICACION/PAISES_DE_SUDAMERICA/Sudamérica.shp").to_crs(3857)
        gdf_oceano = gpd.read_file(f"{ruta_base}/DATA/MAPA_DE_UBICACION/OCEANO/Océano.shp").to_crs(3857)
    except Exception as e:
        print(f"⚠️ Error cargando shapefiles de Países u Océano: {e}")
        gdf_paises = None
        gdf_oceano = None
    
    if gdf_departamentos is None or gdf_provincias is None or gdf_distritos is None:
        print("❌ Faltan capas base (departamento, provincia o distrito). Abortando.")
        return None
    
    col_dpto = next((c for c in ['NOMBDEP', 'DEPARTAMEN'] if c in gdf_departamentos.columns), None)
    col_prov = next((c for c in ['NOMBPROV', 'PROVINCIA'] if c in gdf_provincias.columns), None)
    col_distr = next((c for c in ['NOMBDIST', 'DISTRITO'] if c in gdf_distritos.columns), None)
    
    if not all([col_dpto, col_prov, col_distr]):
        print("❌ No se pudieron identificar las columnas de nombres en los shapefiles")
        return None
    
    print("\n🗺️ Filtrando datos del área seleccionada...")
    gdf_dpto_sel = gdf_departamentos[gdf_departamentos[col_dpto] == departamento_sel]
    gdf_prov_sel = gdf_provincias[gdf_provincias[col_prov] == provincia_sel]
    gdf_distrito = gdf_distritos[(gdf_distritos[col_distr] == distrito_sel) & 
                                  (gdf_distritos[col_prov] == provincia_sel)]
    gdf_distritos_en_provincia = gdf_distritos[gdf_distritos[col_prov] == provincia_sel]
    
    if gdf_distrito.empty:
        print(f"❌ Error: No se pudo encontrar la geometría para el distrito '{distrito_sel}'.")
        return None
    
    print(f"   ✅ Distrito encontrado con geometría válida")
    
    print("\n🪨 Cargando datos geológicos...")
    gdf_geologia = cargar_geologia(departamento_sel)
    
    if gdf_geologia is None:
        print("❌ No se pudo cargar la geología para este departamento")
        return None
    
    print("   ✂️ Recortando geología al área del distrito...")
    try:
        gdf_geologia_clipped = gpd.clip(gdf_geologia, gdf_distrito)
        
        if gdf_geologia_clipped.empty:
            print("❌ No hay unidades geológicas en el área del distrito")
            return None
        
        # Buscar columna con información geológica
        col_geologia = None
        columnas_posibles = ['UNIDAD', 'FORMACION', 'LITOLOGIA', 'EDAD', 'SIMBOLO', 'NOMBRE', 
                            'DESCRIPCI', 'SIMB', 'ERA', 'PERIODO', 'GEOLOGIA']
        
        for col in columnas_posibles:
            if col in gdf_geologia_clipped.columns:
                col_geologia = col
                print(f"   ✅ Usando columna geológica: {col_geologia}")
                break
        
        if col_geologia is None:
            col_geologia = gdf_geologia_clipped.columns[0]
            print(f"   ⚠️ No se encontró columna estándar, usando: {col_geologia}")
        
        unidades_geologia = sorted(gdf_geologia_clipped[col_geologia].dropna().unique())
        paleta_geologia = generar_paleta_geologia(len(unidades_geologia))
        
        print(f"   ✅ Geología recortada: {len(unidades_geologia)} unidades encontradas")
        
    except Exception as e:
        print(f"❌ Error al recortar geología: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    print("\n🎨 Generando layout del mapa...")
    fig = plt.figure(figsize=(14, 9.9))
    grid = plt.GridSpec(1, 2, width_ratios=[3.0, 1], wspace=0.05)
    gs_izquierda = grid[0, 0].subgridspec(3, 1, height_ratios=[0.08, 3.5, 0.42], hspace=0.08)
    
    ax_titulo = fig.add_subplot(gs_izquierda[0])
    ax_titulo.text(0.5, 0.5, f"MAPA GEOLÓGICO - DISTRITO DE {distrito_sel.upper()}",
                   ha='center', va='center', fontsize=12, fontweight="normal",
                   bbox=dict(boxstyle='square,pad=0.5', facecolor='white', 
                            edgecolor='black', linewidth=1.5, alpha=0.95))
    ax_titulo.axis('off')
    
    ax_main = fig.add_subplot(gs_izquierda[1])
    
    # BBOX con aspect ratio consistente
    minx, miny, maxx, maxy = gdf_distrito.total_bounds
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
    
    print("   🛰️ Descargando imagen satelital...")
    try:
        ctx.add_basemap(ax_main, source=ctx.providers.Esri.WorldImagery, 
                       attribution=False, zoom='auto')
    except Exception as e:
        print(f"   ⚠️ No se pudo cargar el mapa base: {e}")
        ax_main.set_facecolor("#e8e8e8")

    # ---- CARGA Y DIBUJO DE CAPAS ADICIONALES SOLICITADAS ----
    print("   📥 Cargando capas adicionales (lagos, ríos, vías)...")
    capas_paths = {
        'lagos': f"{ruta_base}/DATA/MAPA_DE_UBICACION/LAGOS/Lago_y_Laguna_IGN_IDEP_geogpsperu_SuyoPomalia.shp",
        'rios': f"{ruta_base}/DATA/MAPA_DE_UBICACION/RIOS/rios_lineal_idep_ign_100k_geogpsperu.shp",
        'vias_departamental': f"{ruta_base}/DATA/MAPA_DE_UBICACION/VIAS/VIA_DEPARTAMENTAL/red_vial_departamental_dic18.shp",
        'vias_nacional': f"{ruta_base}/DATA/MAPA_DE_UBICACION/VIAS/VIA_NACIONAL/red_vial_nacional_dic18.shp",
        'vias_vecinal': f"{ruta_base}/DATA/MAPA_DE_UBICACION/VIAS/VIA_VECINAL/red_vial_vecinal_dic18.shp",
        'centros_poblados': f"{ruta_base}/DATA/CENTROS_POBLADOS/Centros_Poblados_INEI_geogpsperu_SuyoPomalia.shp",
    }

    gdf_lagos = cargar_shapfile_por_ruta(capas_paths['lagos'], alias='Lagos')
    gdf_rios = cargar_shapfile_por_ruta(capas_paths['rios'], alias='Ríos')
    gdf_vias_dep = cargar_shapfile_por_ruta(capas_paths['vias_departamental'], alias='Vías departamental')
    gdf_vias_nac = cargar_shapfile_por_ruta(capas_paths['vias_nacional'], alias='Vías nacional')
    gdf_vias_vec = cargar_shapfile_por_ruta(capas_paths['vias_vecinal'], alias='Vías vecinal')
    gdf_centros = cargar_shapfile_por_ruta(capas_paths['centros_poblados'], alias='Centros Poblados')

    # Función auxiliar para plotear con simbología fina (líneas delgadas o puntos pequeños)
    def plot_capa_simbologia(gdf, ax, tipo='line', color='#000000', lw=0.6, markersize=6, zorder=10, alpha=0.9):
        if gdf is None or gdf.empty:
            return
        geom_tipo = gdf.geom_type.iloc[0] if 'geom_type' in gdf.columns else gdf.geom_type.iloc[0]
        try:
            if geom_tipo.lower().startswith('point') or tipo == 'point':
                gdf.plot(ax=ax, marker='o', color=color, markersize=markersize, zorder=zorder, alpha=alpha)
            elif geom_tipo.lower().startswith('line') or tipo == 'line':
                gdf.plot(ax=ax, color=color, linewidth=lw, zorder=zorder, alpha=alpha)
            else:
                # Polígonos
                gdf.plot(ax=ax, facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder)
        except Exception:
            # Intentar plotear según geom manually
            try:
                if gdf.geometry.iloc[0].geom_type in ['Point', 'MultiPoint']:
                    gdf.plot(ax=ax, marker='o', color=color, markersize=markersize, zorder=zorder, alpha=alpha)
                elif gdf.geometry.iloc[0].geom_type in ['LineString', 'MultiLineString']:
                    gdf.plot(ax=ax, color=color, linewidth=lw, zorder=zorder, alpha=alpha)
                else:
                    gdf.plot(ax=ax, facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder)
            except Exception as e:
                print(f"   ⚠️ Error al plotear capa: {e}")

    # Recortar al distrito para evitar dibujar todo el país
    try:
        if gdf_lagos is not None:
            gdf_lagos_c = gpd.clip(gdf_lagos, gdf_distrito)
            plot_capa_simbologia(gdf_lagos_c, ax_main, tipo='polygon', color='#4DA6FF', alpha=0.6, zorder=2)

        if gdf_rios is not None:
            gdf_rios_c = gpd.clip(gdf_rios, gdf_distrito)
            plot_capa_simbologia(gdf_rios_c, ax_main, tipo='line', color='#1f78b4', lw=0.7, zorder=12, alpha=0.9)

        if gdf_vias_nac is not None:
            gdf_vias_nac_c = gpd.clip(gdf_vias_nac, gdf_distrito)
            plot_capa_simbologia(gdf_vias_nac_c, ax_main, tipo='line', color='#D62728', lw=0.9, zorder=13, alpha=0.95)

        if gdf_vias_dep is not None:
            gdf_vias_dep_c = gpd.clip(gdf_vias_dep, gdf_distrito)
            plot_capa_simbologia(gdf_vias_dep_c, ax_main, tipo='line', color='#FF7F0E', lw=0.8, zorder=13, alpha=0.9)

        if gdf_vias_vec is not None:
            gdf_vias_vec_c = gpd.clip(gdf_vias_vec, gdf_distrito)
            plot_capa_simbologia(gdf_vias_vec_c, ax_main, tipo='line', color='#8C564B', lw=0.6, zorder=13, alpha=0.85)
    except Exception as e:
        print(f"   ⚠️ Error al recortar/plotear capas adicionales: {e}")
    # ---- FIN CAPAS ADICIONALES ----

    
    print("   🎨 Dibujando unidades geológicas...")
    for idx, unidad in enumerate(unidades_geologia):
        gdf_unidad = gdf_geologia_clipped[gdf_geologia_clipped[col_geologia] == unidad]
        # Pintar unidades geológicas sin líneas de contorno para un aspecto más limpio
        gdf_unidad.plot(ax=ax_main, color=paleta_geologia[idx], edgecolor='none',
                       linewidth=0, alpha=0.85, zorder=4)

    # Dibujar centros poblados (puntos pequeños, color plomo oscuro) encima de las unidades
    try:
        if 'gdf_centros' in locals() and gdf_centros is not None:
            gdf_centros_c = gpd.clip(gdf_centros, gdf_distrito)
            plot_capa_simbologia(gdf_centros_c, ax_main, tipo='point', color='#2f2f2f', markersize=6, zorder=16, alpha=0.95)
            # Etiquetar Centros Poblados: nombre capitalizado (Primera letra mayúscula, resto minúsculas),
            # tamaño pequeño y halo blanco delgado para legibilidad
            try:
                # intentar identificar columna de nombre
                possible_name_cols = ['NOMBRE', 'NOM', 'NAME', 'nombre', 'name', 'NOMCP', 'CENTRO', 'NOM_CENT', 'DESC']
                name_col = next((c for c in possible_name_cols if c in gdf_centros_c.columns), None)

                for _, r in gdf_centros_c.iterrows():
                    try:
                        if r.geometry is None:
                            continue
                        # obtener etiqueta
                        label_val = None
                        if name_col and pd.notna(r.get(name_col)):
                            label_val = str(r.get(name_col)).strip()
                        else:
                            # fallback: buscar primera columna de texto no vacía
                            for c in r.index:
                                v = r.get(c)
                                if isinstance(v, str) and v.strip():
                                    label_val = v.strip()
                                    break
                        if not label_val:
                            continue

                        # Formatear: primera letra de cada palabra mayúscula, resto minúscula
                        label_fmt = label_val.title()

                        # Determinar punto para etiqueta (representative_point funciona para puntos y polígonos)
                        try:
                            p = r.geometry.representative_point()
                        except Exception:
                            p = r.geometry

                        # Usar annotate con desplazamiento en puntos para separar el texto del símbolo
                        ax.annotate(label_fmt, xy=(p.x, p.y), xytext=(4, 0), textcoords='offset points',
                                    fontsize=6, color='#2f2f2f', ha='left', va='center', zorder=200, clip_on=False,
                                    path_effects=[path_effects.withStroke(linewidth=0.5, foreground='white')])
                    except Exception:
                        continue
            except Exception:
                pass
    except Exception as e:
        print(f"   ⚠️ Error al plotear Centros Poblados: {e}")
    
    gdf_distrito.plot(ax=ax_main, facecolor="none", edgecolor="red", linewidth=2,
                     linestyle='--', alpha=0.9, zorder=15)
    
    grillado_utm_proyectado(ax_main, bbox_main, ndiv=8)
    # Colocar flecha norte en esquina superior derecha con estilo similar a la imagen proporcionada
    add_north_arrow_esquina(ax_main, xy_pos=(0.985, 0.985), size=0.05)
    ax_main.add_artist(ScaleBar(1, units="m", location="lower left", 
                                box_alpha=0.6, border_pad=0.5, scale_loc='bottom'))
    
    # Reservar espacio en la esquina inferior izquierda para un logo,
    # colocar un rectángulo marcador y acercar el membrete lo más posible
    # Mantener el ancho original del membrete pero pegado al recuadro del logo
    gs_memb_ley = gs_izquierda[2].subgridspec(1, 3, wspace=0.02, width_ratios=[0.4, 2.0, 1.0])

    # Espacio para logo (dibujar rectángulo placeholder para colocar logo)
    ax_logo = fig.add_subplot(gs_memb_ley[0])
    ax_logo.axis('off')
    # Dibujar rectángulo indicador en coordenadas del eje (ligero padding)
    try:
        from matplotlib.patches import Rectangle as MplRect
        # Hacer el recuadro un poco más pequeño para aprovechar espacio
        rect = MplRect((0.10, 0.08), 0.8, 0.84, transform=ax_logo.transAxes,
                   facecolor='none', edgecolor='black', linewidth=1.4)
        ax_logo.add_patch(rect)
    except Exception:
        pass

    # Membrete: ahora en la columna central, justo a la derecha del rectángulo
    ax_membrete = fig.add_subplot(gs_memb_ley[1])
    fig.canvas.draw()
    add_membrete(ax_membrete, departamento_sel, provincia_sel, distrito_sel, ax_main, fig)

    # Caja de leyenda en la columna derecha
    ax_leyenda = fig.add_subplot(gs_memb_ley[2])
    ax_leyenda.axis('off')

    # --- Leyenda de GEOLOGÍA en el mapa principal (esquina superior izquierda) ---
    if len(unidades_geologia) > 0:
        handles_geo = []
        # Subtítulo de la leyenda: usar 'GEOLOGÍA' sin ':' (se formateará en negrita y alineado a la izquierda)
        handles_geo.append(Patch(facecolor='white', edgecolor='white', label='GEOLOGÍA', linewidth=0))
        max_items_leyenda = min(8, len(unidades_geologia))
        for idx in range(max_items_leyenda):
            unidad = unidades_geologia[idx]
            nombre_corto = str(unidad)[:30] + '...' if len(str(unidad)) > 30 else str(unidad)
            handles_geo.append(Patch(facecolor=paleta_geologia[idx], edgecolor='black', label=nombre_corto))
        if len(unidades_geologia) > max_items_leyenda:
            handles_geo.append(Patch(facecolor='white', edgecolor='white', label=f'(+{len(unidades_geologia)-max_items_leyenda} más)', linewidth=0))

        try:
            leg_geo = ax_main.legend(handles=handles_geo, loc='upper left', bbox_to_anchor=(0.02, 0.98),
                                   frameon=True, fontsize=7.5, title='LEYENDA', ncol=1,
                                   title_fontproperties={'size': 9, 'weight': 'bold'})
            leg_geo.get_frame().set_edgecolor('black')
            leg_geo.get_frame().set_linewidth(1.0)
            # Formatear el primer texto (subtítulo) en negrita y alineado a la izquierda dentro de la leyenda
            try:
                texts = leg_geo.get_texts()
                if len(texts) > 0:
                    texts[0].set_fontweight('bold')
                    texts[0].set_ha('left')
            except Exception:
                pass
            ax_main.add_artist(leg_geo)
        except Exception:
            # Fallback simple legend
            ax_main.legend(handles=handles_geo, loc='upper left', frameon=True, fontsize=7.5, title='GEOLOGÍA')

    # --- Caja de simbología (todo lo demás) en la columna derecha ---
    # Orden: puntos -> líneas -> polígonos -> otros
    legend_elements = []
    # Puntos (Centros poblados)
    legend_elements.append(Line2D([0], [0], marker='o', color='#2f2f2f', label='Centros Poblados', markersize=6, linestyle='None'))
    # Líneas (Ríos y Vías)
    legend_elements.append(Line2D([0], [0], color='#1f78b4', lw=1.0, label='Ríos'))
    legend_elements.append(Line2D([0], [0], color='#D62728', lw=1.0, label='Vía Nacional'))
    legend_elements.append(Line2D([0], [0], color='#FF7F0E', lw=1.0, label='Vía Departamental'))
    legend_elements.append(Line2D([0], [0], color='#8C564B', lw=1.0, label='Vía Vecinal'))
    # Polígonos (Lagos)
    legend_elements.append(Patch(facecolor='#4DA6FF', edgecolor='none', label='Lagos'))
    # Otros elementos
    legend_elements.append(Line2D([0], [0], color='red', lw=2, linestyle='--', label='Límite Distrital'))

    # Organizar en columnas internas: máximo 5 elementos por columna
    items_count = len(legend_elements)
    max_per_col = 5
    ncols_internal = max(1, math.ceil(items_count / max_per_col))

    # Usar ncol = ncols_internal para distribuir en columnas internas cuando sean necesarias
    leg = ax_leyenda.legend(handles=legend_elements, loc='center', ncol=ncols_internal, frameon=True,
                           fontsize=8, title="Simbología", title_fontproperties={'size': 10, 'weight': 'bold'},
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
    
    print("\n💾 Guardando mapa final en carpeta de usuario...")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = f"MAPA_GEOLOGICO_{distrito_sel.replace(' ', '_')}_{timestamp}.png"
    ruta_guardado_final = os.path.join(carpeta_salida, nombre_base)
    
    try:
        plt.savefig(ruta_guardado_final, dpi=300, bbox_inches='tight', pad_inches=0.01)
        plt.close(fig)
        
        if os.path.exists(ruta_guardado_final):
            file_size = os.path.getsize(ruta_guardado_final) / (1024 * 1024)
            print(f"✅ Mapa geológico guardado exitosamente")
            print(f"   📍 Ubicación: {ruta_guardado_final}")
            print(f"   📦 Tamaño: {file_size:.2f} MB")
            print(f"   🪨 Unidades geológicas: {len(unidades_geologia)}")
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


# ═══════════════════════════════════════════════════════════════════════════════
# EJEMPLO DE USO
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Ejemplo de uso del script
    resultado = generar_mapa_geologia(
        nombre_usuario="USUARIO_PRUEBA1",
        departamento_sel="PIURA",
        provincia_sel="PIURA",
        distrito_sel="PIURA"
    )
    
    if resultado:
        print(f"🎉 ¡Mapa generado exitosamente en: {resultado}")
    else:
        print("❌ No se pudo generar el mapa geológico")