import xarray as xr
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from shapely.geometry import Point
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# 1. CARGAR DATOS
print("Cargando datos PISCO...")
pisco_path = '/content/drive/MyDrive/Colab Notebooks/PR_50/PISCOv2p1_pp_daily.nc'
ds = xr.open_dataset(pisco_path)

print("Cargando shapefile de Anta...")
shp_path = '/content/drive/MyDrive/Colab Notebooks/PR_50/PROV_ANTA/ANTA_PROV.shp'
anta_gdf = gpd.read_file(shp_path)

if anta_gdf.crs != 'EPSG:4326':
    anta_gdf = anta_gdf.to_crs('EPSG:4326')

# 2. RECORTAR DATOS
minx, miny, maxx, maxy = anta_gdf.total_bounds
print(f"Límites de Anta: Lon[{minx:.2f}, {maxx:.2f}], Lat[{miny:.2f}, {maxy:.2f}]")

margin = 0.3
ds_clip = ds.sel(
    X=slice(minx - margin, maxx + margin),
    Y=slice(maxy + margin, miny - margin)
)

# 3. CREAR GRID DE ALTA RESOLUCIÓN
print("\nCreando grid de alta resolución...")

lons_orig = ds_clip.X.values
lats_orig = ds_clip.Y.values

lon_hr = np.linspace(lons_orig.min(), lons_orig.max(), len(lons_orig) * 4)
lat_hr = np.linspace(lats_orig.min(), lats_orig.max(), len(lats_orig) * 4)
lon_grid_hr, lat_grid_hr = np.meshgrid(lon_hr, lat_hr)

# Máscara
anta_geom = anta_gdf.union_all()
mask_hr = np.zeros(lon_grid_hr.shape, dtype=bool)

for i in range(lon_grid_hr.shape[0]):
    for j in range(lon_grid_hr.shape[1]):
        point = Point(lon_grid_hr[i, j], lat_grid_hr[i, j])
        mask_hr[i, j] = anta_geom.contains(point) or anta_geom.boundary.distance(point) < 0.05

print(f"Píxeles: {mask_hr.sum()}")

# 4. CALCULAR CLIMATOLOGÍA
print("\nCalculando climatología mensual...")

prec_data = ds_clip['Prec']
time_index = pd.DatetimeIndex(ds_clip.T.values)

monthly_climatology_smooth = []

for month in range(1, 13):
    print(f"  Mes {month:02d}/12...", end=' ')

    month_mask = time_index.month == month
    month_indices = np.where(month_mask)[0]
    years = time_index[month_indices].year
    unique_years = np.unique(years)

    monthly_sums = []
    for year in unique_years:
        year_mask = years == year
        year_indices = month_indices[year_mask]
        year_data = prec_data.isel(T=year_indices)
        monthly_sum = year_data.sum(dim='T')
        monthly_sums.append(monthly_sum)

    monthly_avg = sum(monthly_sums) / len(monthly_sums)

    # Interpolación
    lon_orig_grid, lat_orig_grid = np.meshgrid(lons_orig, lats_orig)
    points_orig = np.column_stack([lon_orig_grid.ravel(), lat_orig_grid.ravel()])
    values_orig = monthly_avg.values.ravel()

    valid_mask = ~np.isnan(values_orig)
    points_valid = points_orig[valid_mask]
    values_valid = values_orig[valid_mask]

    points_hr = np.column_stack([lon_grid_hr.ravel(), lat_grid_hr.ravel()])
    values_hr = griddata(points_valid, values_valid, points_hr, method='cubic', fill_value=np.nan)
    values_hr = values_hr.reshape(lon_grid_hr.shape)

    values_hr_smooth = gaussian_filter(values_hr, sigma=1.5)

    # Rellenar NaNs
    nan_mask = np.isnan(values_hr_smooth) & mask_hr
    if nan_mask.any():
        points_hr_valid = points_hr[~np.isnan(values_hr.ravel())]
        values_hr_valid = values_hr.ravel()[~np.isnan(values_hr.ravel())]
        points_hr_nan = points_hr[nan_mask.ravel()]

        if len(points_hr_valid) > 0 and len(points_hr_nan) > 0:
            filled_values = griddata(points_hr_valid, values_hr_valid, points_hr_nan, method='nearest')
            values_hr_smooth[nan_mask] = filled_values

    values_hr_smooth = np.where(mask_hr, values_hr_smooth, np.nan)
    monthly_climatology_smooth.append(values_hr_smooth)

    print(f"{np.nanmean(values_hr_smooth):.1f} mm")

# 5. COLORMAP PROFESIONAL - Gradiente completamente suave
# ROJO (seco) → AMARILLO → VERDE → AZUL (húmedo)
import matplotlib.cm as cm
from matplotlib.colors import LinearSegmentedColormap

# Paleta personalizada con transiciones ultra suaves
colors_precip = [
    (0.60, 0.00, 0.00),  # Rojo oscuro (muy seco)
    (0.75, 0.10, 0.05),
    (0.85, 0.20, 0.10),
    (0.95, 0.35, 0.15),  # Rojo-naranja
    (1.00, 0.50, 0.20),
    (1.00, 0.65, 0.25),  # Naranja
    (1.00, 0.80, 0.30),
    (1.00, 0.90, 0.40),  # Amarillo-naranja
    (1.00, 1.00, 0.50),  # Amarillo
    (0.90, 1.00, 0.50),
    (0.75, 1.00, 0.55),  # Amarillo-verde
    (0.60, 0.95, 0.60),
    (0.45, 0.90, 0.65),  # Verde
    (0.35, 0.85, 0.75),
    (0.25, 0.75, 0.85),  # Verde-celeste
    (0.20, 0.65, 0.90),
    (0.15, 0.50, 0.85),  # Celeste
    (0.10, 0.40, 0.75),
    (0.05, 0.30, 0.65),
    (0.00, 0.20, 0.55),  # Azul (muy húmedo)
]

cmap_precip = LinearSegmentedColormap.from_list('precipitacion_suave', colors_precip, N=256)

# Aplicar interpolación suave
cmap_precip._init()
cmap_precip._lut[:-3, :-1] = cmap_precip._lut[:-3, :-1] ** 0.85  # Gamma correction para suavizar

meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

# 6. CREAR MAPAS CON UNA SOLA COLORBAR
print("\nGenerando mapas profesionales...")

# Calcular límites globales con mejor rango
all_values = np.concatenate([m[~np.isnan(m)] for m in monthly_climatology_smooth])
vmin = np.percentile(all_values, 2)  # Cambiado de 1 a 2
vmax = np.percentile(all_values, 98) # Cambiado de 99 a 98

# Path del shapefile
anta_boundary = anta_gdf.geometry.iloc[0]
if hasattr(anta_boundary, 'geoms'):
    vertices = []
    codes = []
    for geom in anta_boundary.geoms:
        v = np.array(geom.exterior.coords)
        vertices.append(v)
        codes.append([Path.MOVETO] + [Path.LINETO] * (len(v) - 2) + [Path.CLOSEPOLY])
    vertices = np.vstack(vertices)
    codes = np.hstack(codes)
else:
    vertices = np.array(anta_boundary.exterior.coords)
    codes = [Path.MOVETO] + [Path.LINETO] * (len(vertices) - 2) + [Path.CLOSEPOLY]

clip_path = Path(vertices, codes)

# Crear figura
fig = plt.figure(figsize=(22, 26))
gs = fig.add_gridspec(5, 3, hspace=0.25, wspace=0.15,
                      left=0.05, right=0.95, top=0.94, bottom=0.06)

# Buffer mínimo para que esté pegado
buffer = 0.01

for i, (month_data, mes_nombre) in enumerate(zip(monthly_climatology_smooth, meses)):
    ax = fig.add_subplot(gs[i // 3, i % 3], projection=ccrs.PlateCarree())

    # Plotear contornos rellenos con muchos niveles para gradiente suave
    im = ax.contourf(lon_grid_hr, lat_grid_hr, month_data,
                     levels=100, cmap=cmap_precip, vmin=vmin, vmax=vmax,
                     transform=ccrs.PlateCarree(), extend='both')

    # ISOLÍNEAS con etiquetas
    data_range = np.nanmax(month_data) - np.nanmin(month_data)
    if data_range > 100:
        contour_interval = 50
    elif data_range > 50:
        contour_interval = 25
    elif data_range > 20:
        contour_interval = 10
    else:
        contour_interval = 5

    contour_levels = np.arange(
        np.floor(np.nanmin(month_data) / contour_interval) * contour_interval,
        np.ceil(np.nanmax(month_data) / contour_interval) * contour_interval + contour_interval,
        contour_interval
    )

    # Dibujar isolíneas
    cs = ax.contour(lon_grid_hr, lat_grid_hr, month_data,
                    levels=contour_levels, colors='black', linewidths=0.6,
                    alpha=0.4, transform=ccrs.PlateCarree())

    # Etiquetas en las isolíneas
    ax.clabel(cs, inline=True, fontsize=8, fmt='%1.0f', colors='black')

    # CLIP MEJORADO - Acceso correcto a colecciones en GeoContourSet
    clip_patch = PathPatch(clip_path, transform=ax.transData,
                          facecolor='none', edgecolor='none')

    # Clip para contornos rellenos (acceso mediante atributo correcto)
    if hasattr(im, 'collections'):
        for collection in im.collections:
            collection.set_clip_path(clip_patch)
    else:
        # Para GeoContourSet, acceder mediante el método get_children()
        for artist in ax.get_children():
            if hasattr(artist, 'set_clip_path') and artist != clip_patch:
                try:
                    artist.set_clip_path(clip_patch)
                except:
                    pass

    # Clip para isolíneas
    if hasattr(cs, 'collections'):
        for collection in cs.collections:
            collection.set_clip_path(clip_patch)
    else:
        for artist in cs.collections if hasattr(cs, 'collections') else []:
            artist.set_clip_path(clip_patch)

    # Borde del shapefile
    anta_gdf.boundary.plot(ax=ax, edgecolor='black', linewidth=2.5,
                          transform=ccrs.PlateCarree(), zorder=5)

    # Extensión ajustada (pegado al shape)
    ax.set_extent([minx - buffer, maxx + buffer,
                   miny - buffer, maxy + buffer],
                  crs=ccrs.PlateCarree())

    # Sin bordes del eje
    ax.spines['geo'].set_visible(False)

    # Gridlines sutiles
    gl = ax.gridlines(draw_labels=True, linewidth=0.25, color='gray',
                     alpha=0.3, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 9, 'color': 'gray'}
    gl.ylabel_style = {'size': 9, 'color': 'gray'}

    if i % 3 != 0:
        gl.left_labels = False
    if i < 9:
        gl.bottom_labels = False

    # Título limpio
    mean_prec = np.nanmean(month_data)
    ax.set_title(f'{mes_nombre}\n{mean_prec:.1f} mm',
                 fontsize=13, fontweight='bold', pad=8)

# COLORBAR ÚNICA EN LA PARTE INFERIOR
cbar_ax = fig.add_axes([0.15, 0.02, 0.7, 0.015])
cbar = plt.colorbar(im, cax=cbar_ax, orientation='horizontal', extend='both')
cbar.set_label('Precipitación Mensual (mm)', fontsize=14, fontweight='bold', labelpad=10)
cbar.ax.tick_params(labelsize=11)

# Título principal
fig.text(0.5, 0.975, 'CLIMATOLOGÍA MENSUAL DE PRECIPITACIÓN',
         ha='center', fontsize=20, fontweight='bold')
fig.text(0.5, 0.960, 'Provincia de Anta - Cusco, Perú',
         ha='center', fontsize=16, style='italic')
fig.text(0.5, 0.947, 'Promedio Histórico 1981-2016  |  PISCO v2.1',
         ha='center', fontsize=13, color='gray')

plt.savefig('mapas_mensuales_anta_profesional.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("\n✓ Mapa profesional guardado: mapas_mensuales_anta_profesional.png")
plt.show()

# 7. MAPA ESTACIONAL
print("\nGenerando mapa estacional...")

estaciones = {
    'Verano\n(DEF)': [11, 0, 1],
    'Otoño\n(MAM)': [2, 3, 4],
    'Invierno\n(JJA)': [5, 6, 7],
    'Primavera\n(SON)': [8, 9, 10]
}

fig2 = plt.figure(figsize=(20, 11))
gs2 = fig2.add_gridspec(1, 4, hspace=0.15, wspace=0.15,
                        left=0.05, right=0.95, top=0.88, bottom=0.12)

estacion_data_all = []
for meses_idx in estaciones.values():
    est_data = sum([monthly_climatology_smooth[i] for i in meses_idx])
    estacion_data_all.append(est_data)

all_est_vals = np.concatenate([e[~np.isnan(e)] for e in estacion_data_all])
vmin_est = np.percentile(all_est_vals, 2)  # Cambiado de 1 a 2
vmax_est = np.percentile(all_est_vals, 98) # Cambiado de 99 a 98

for idx, (estacion, meses_idx) in enumerate(estaciones.items()):
    ax = fig2.add_subplot(gs2[0, idx], projection=ccrs.PlateCarree())

    estacion_data = estacion_data_all[idx]

    # Contornos rellenos con muchos niveles
    im = ax.contourf(lon_grid_hr, lat_grid_hr, estacion_data,
                     levels=100, cmap=cmap_precip, vmin=vmin_est, vmax=vmax_est,
                     transform=ccrs.PlateCarree(), extend='both')

    # ISOLÍNEAS con etiquetas
    data_range = np.nanmax(estacion_data) - np.nanmin(estacion_data)
    if data_range > 200:
        contour_interval = 100
    elif data_range > 100:
        contour_interval = 50
    else:
        contour_interval = 25

    contour_levels = np.arange(
        np.floor(np.nanmin(estacion_data) / contour_interval) * contour_interval,
        np.ceil(np.nanmax(estacion_data) / contour_interval) * contour_interval + contour_interval,
        contour_interval
    )

    cs = ax.contour(lon_grid_hr, lat_grid_hr, estacion_data,
                    levels=contour_levels, colors='black', linewidths=0.7,
                    alpha=0.5, transform=ccrs.PlateCarree())

    ax.clabel(cs, inline=True, fontsize=9, fmt='%1.0f', colors='black')

    # CLIP MEJORADO
    clip_patch = PathPatch(clip_path, transform=ax.transData,
                          facecolor='none', edgecolor='none')

    # Clip para contornos
    if hasattr(im, 'collections'):
        for collection in im.collections:
            collection.set_clip_path(clip_patch)
    else:
        for artist in ax.get_children():
            if hasattr(artist, 'set_clip_path') and artist != clip_patch:
                try:
                    artist.set_clip_path(clip_patch)
                except:
                    pass

    # Clip para isolíneas
    if hasattr(cs, 'collections'):
        for collection in cs.collections:
            collection.set_clip_path(clip_patch)

    anta_gdf.boundary.plot(ax=ax, edgecolor='black', linewidth=3,
                          transform=ccrs.PlateCarree(), zorder=5)

    ax.set_extent([minx - buffer, maxx + buffer,
                   miny - buffer, maxy + buffer],
                  crs=ccrs.PlateCarree())

    # Sin bordes del eje
    ax.spines['geo'].set_visible(False)

    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray',
                     alpha=0.3, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 10, 'color': 'gray'}
    gl.ylabel_style = {'size': 10, 'color': 'gray'}

    if idx > 0:
        gl.left_labels = False

    mean_prec = np.nanmean(estacion_data)
    ax.set_title(f'{estacion}\n{mean_prec:.1f} mm',
                fontsize=15, fontweight='bold', pad=10)

# Colorbar única
cbar_ax2 = fig2.add_axes([0.15, 0.05, 0.7, 0.025])
cbar2 = plt.colorbar(im, cax=cbar_ax2, orientation='horizontal', extend='both')
cbar2.set_label('Precipitación Estacional (mm)', fontsize=14, fontweight='bold', labelpad=10)
cbar2.ax.tick_params(labelsize=11)

# Título
fig2.text(0.5, 0.96, 'PRECIPITACIÓN ESTACIONAL',
         ha='center', fontsize=20, fontweight='bold')
fig2.text(0.5, 0.935, 'Provincia de Anta - Cusco, Perú  |  1981-2016',
         ha='center', fontsize=14, style='italic')

plt.savefig('mapas_estacionales_anta_profesional.png', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("✓ Mapa estacional guardado: mapas_estacionales_anta_profesional.png")
plt.show()

print("\n" + "="*70)
print("¡PROCESO COMPLETADO!")
print("Mapas profesionales con una sola barra de colores generados")
print("="*70)