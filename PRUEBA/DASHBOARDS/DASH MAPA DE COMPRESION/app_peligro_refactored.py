# Archivo: app_peligro_refactored.py - DASHBOARD COMPLETO REFACTORIZADO

from dash import Dash, html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import re
import os
import time
import threading
import uuid
import geopandas as gpd

# Importar funciones de generación
from mapa_peligro import generar_mapa_peligro
from elementos_expuestos import generar_mapa_elementos_expuestos

# Diccionario global para rastrear procesos en segundo plano
PROCESS_STATUS = {}

# ==================== CONFIGURACIÓN DE LA APP ====================
app = Dash(
    __name__, 
    external_stylesheets=[dbc.themes.BOOTSTRAP], 
    suppress_callback_exceptions=True
)

# ==================== CARGAR HTML EXTERNO ====================
try:
    with open('index.html', 'r', encoding='utf-8') as f:
        app.index_string = f.read()
    print("✅ Template HTML cargado correctamente desde index.html")
except FileNotFoundError:
    print("⚠️ ADVERTENCIA: No se encontró index.html, usando template por defecto")
    app.index_string = '''
    <!DOCTYPE html>
    <html lang="es">
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    '''

# ==================== USUARIOS VÁLIDOS ====================
VALID_USERS = {'admin': 'admin', 'usuario': 'admin'}

def leer_sql(ruta):
    if not os.path.exists(ruta):
        print(f"⚠️ ADVERTENCIA: La ruta del archivo SQL no existe: '{ruta}'")
        return []
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    patron = r"INSERT INTO `\w+` VALUES \(([^)]+)\);"
    matches = re.findall(patron, contenido)
    return [[v.strip().strip("'") for v in match.split(',')] for match in matches]

# ==================== CARGA DE DATOS ====================
try:
    ruta_departamentos = '/workspaces/AUTOMATIZACION_DASH/PRUEBA/DASHBOARDS/departamentos.sql'
    ruta_provincias = '/workspaces/AUTOMATIZACION_DASH/PRUEBA/DASHBOARDS/provincias.sql'
    ruta_distritos = '/workspaces/AUTOMATIZACION_DASH/PRUEBA/DASHBOARDS/distritos.sql'
    print("Cargando datos SQL para todo el Perú...")
    depa_data, prov_data, dist_data = leer_sql(ruta_departamentos), leer_sql(ruta_provincias), leer_sql(ruta_distritos)
    if not all([depa_data, prov_data, dist_data]): raise ValueError("Archivos SQL no encontrados.")
    departamentos = {d[0]: d[1] for d in depa_data}
    provincias = {p[0]: {'nombre': p[1], 'id_depa': p[2]} for p in prov_data}
    distritos = {d[0]: {'nombre': d[1], 'id_prov': d[2]} for d in dist_data}
    PROVINCIAS_POR_DEPA, DISTRITOS_POR_PROV = {}, {}
    for prov_id, prov_info in provincias.items():
        if (depa_id := prov_info['id_depa']) in departamentos:
            PROVINCIAS_POR_DEPA.setdefault(departamentos[depa_id], []).append(prov_info['nombre'])
    for dist_id, dist_info in distritos.items():
        if (prov_id := dist_info['id_prov']) in provincias:
            DISTRITOS_POR_PROV.setdefault(provincias[prov_id]['nombre'], []).append(dist_info['nombre'])
    LISTA_DEPARTAMENTOS = sorted(PROVINCIAS_POR_DEPA.keys())
    print("✅ Datos SQL cargados correctamente.")
except Exception as e:
    print(f"❌ Error crítico al cargar datos SQL: {e}. Usando datos de respaldo.")
    LISTA_DEPARTAMENTOS, PROVINCIAS_POR_DEPA, DISTRITOS_POR_PROV = ['LIMA'], {'LIMA': ['LIMA']}, {'LIMA': ['MIRAFLORES']}

# ==================== CARGAR GEODATAFRAMES ====================
print("\n📦 Cargando GeoDataFrames de límites administrativos...")

ruta_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA"

try:
    ruta_shp_distritos = f"{ruta_base}/DATA/MAPA DE UBICACION/DISTRITOS DEL PERU/DISTRITOS_inei_geogpsperu_suyopomalia.shp"
    ruta_shp_provincias = f"{ruta_base}/DATA/MAPA DE UBICACION/PROVINCIAS DEL PERU/PROVINCIAS_inei_geogpsperu_suyopomalia.shp"
    ruta_shp_departamentos = f"{ruta_base}/DATA/MAPA DE UBICACION/DEPARTAMENTOS DEL PERU/DEPARTAMENTOS_inei_geogpsperu_suyopomalia.shp"
    
    if os.path.exists(ruta_shp_distritos):
        gdf_distritos = gpd.read_file(ruta_shp_distritos)
        if gdf_distritos.crs is None:
            gdf_distritos.set_crs(epsg=4326, inplace=True)
        if gdf_distritos.crs.to_epsg() != 3857:
            gdf_distritos = gdf_distritos.to_crs(epsg=3857)
        print(f"   ✅ Distritos cargados: {len(gdf_distritos)} registros")
    else:
        gdf_distritos = None
        print("   ⚠️ Distritos: No encontrados")
    
    if os.path.exists(ruta_shp_provincias):
        gdf_provincias = gpd.read_file(ruta_shp_provincias)
        if gdf_provincias.crs is None:
            gdf_provincias.set_crs(epsg=4326, inplace=True)
        if gdf_provincias.crs.to_epsg() != 3857:
            gdf_provincias = gdf_provincias.to_crs(epsg=3857)
        print(f"   ✅ Provincias cargadas: {len(gdf_provincias)} registros")
    else:
        gdf_provincias = None
        print("   ⚠️ Provincias: No encontradas")
    
    if os.path.exists(ruta_shp_departamentos):
        gdf_departamentos = gpd.read_file(ruta_shp_departamentos)
        if gdf_departamentos.crs is None:
            gdf_departamentos.set_crs(epsg=4326, inplace=True)
        if gdf_departamentos.crs.to_epsg() != 3857:
            gdf_departamentos = gdf_departamentos.to_crs(epsg=3857)
        print(f"   ✅ Departamentos cargados: {len(gdf_departamentos)} registros")
    else:
        gdf_departamentos = None
        print("   ⚠️ Departamentos: No encontrados")
    
    if gdf_distritos is None or gdf_provincias is None or gdf_departamentos is None:
        print("\n⚠️ ADVERTENCIA: Algunos GeoDataFrames no se pudieron cargar")
        
except Exception as e:
    print(f"\n❌ Error cargando GeoDataFrames: {e}")
    gdf_distritos = gdf_provincias = gdf_departamentos = None

# ==================== LAYOUT DE LOGIN ====================
login_layout = dbc.Container([
    html.Div([
        html.A([
            html.I(className="bi bi-globe2 me-2"),
            "escuelar.org"
        ], href="https://escuelar.org/", target="_blank"),
        html.A([
            html.I(className="bi bi-linkedin me-2"),
            "LinkedIn"
        ], href="https://www.linkedin.com/company/escuelar/about/", target="_blank")
    ], className='contact-footer'),
    
    dbc.Row(
        dbc.Col(
            html.Div([
                html.Div([
                    html.Img(
                        src='/assets/LOGO.png',
                        style={'width': '120px', 'height': 'auto', 'marginBottom': '30px', 'filter': 'drop-shadow(0 4px 12px rgba(231, 76, 60, 0.3))'}
                    )
                ], className='text-center'),
                
                dbc.Card([
                    dbc.CardBody([
                        html.H1("Comprensión del riesgo", className="login-title text-center"),
                        html.P("Análisis de Peligros y Elementos Expuestos", className="login-subtitle text-center"),
                        
                        html.Hr(style={'opacity': '0.3', 'margin': '2rem 0'}),
                        
                        html.Div([
                            html.Label([
                                html.I(className="bi bi-person-circle"),
                                "Usuario"
                            ]),
                            dbc.Input(
                                id='username-input',
                                placeholder='Ingrese su usuario',
                                type='text',
                                className='mb-4'
                            )
                        ]),
                        
                        html.Div([
                            html.Label([
                                html.I(className="bi bi-shield-lock"),
                                "Contraseña"
                            ]),
                            dbc.Input(
                                id='password-input',
                                placeholder='Ingrese su contraseña',
                                type='password',
                                className='mb-4'
                            )
                        ]),
                        
                        dbc.Button([
                            html.I(className="bi bi-box-arrow-in-right me-2"),
                            'Iniciar Sesión'
                        ], 
                        id='login-button',
                        color='success',
                        className='w-100 btn-success',
                        style={'padding': '14px', 'fontSize': '1rem'}),
                        
                        html.Div(id='login-alert', className='mt-3')
                    ])
                ], className='login-container border-0')
            ], 
            className='animated',
            style={'marginTop': '60px', 'maxWidth': '440px'}),
            width=12
        ),
        justify='center'
    )
], fluid=True, className="p-4")

# ==================== LAYOUT DEL DASHBOARD ====================
dashboard_layout = dbc.Container([
    dcc.Download(id="download-map-image"),
    
    # Stores para gestionar el estado
    dcc.Store(id='map-filepath-store', storage_type='memory'),
    dcc.Store(id='loading-state', storage_type='memory', data=False),
    dcc.Store(id='selected-tipo-peligro', storage_type='memory', data=None),
    dcc.Store(id='selected-elementos-expuestos', storage_type='memory', data=False),
    dcc.Store(id='tipo-locked', storage_type='memory', data=False),
    dcc.Store(id='process-id', storage_type='memory'),
    dcc.Store(id='generation-status', storage_type='memory', data={'status': 'idle'}),
    dcc.Store(id='peligro-downloaded', storage_type='memory', data=False),
    dcc.Store(id='elementos-downloaded', storage_type='memory', data=False),
    dcc.Store(id='ubicacion-locked', storage_type='memory', data=False),
    
    dcc.Interval(id='check-process', interval=2000, disabled=True),
    
    html.Div([
        html.A([
            html.I(className="bi bi-globe2 me-2"),
            "escuelar.org"
        ], href="https://escuelar.org/", target="_blank"),
        html.A([
            html.I(className="bi bi-linkedin me-2"),
            "LinkedIn"
        ], href="https://www.linkedin.com/company/escuelar/about/", target="_blank")
    ], className='contact-footer'),
    
    dbc.NavbarSimple(
        children=[
            dbc.NavItem(
                html.Span(id='user-display-nav', style={'color': 'var(--text-primary)', 'fontWeight': '600', 'marginRight': '20px', 'display': 'flex', 'alignItems': 'center', 'gap': '8px'})
            ),
            dbc.NavItem(
                dbc.Button([
                    html.I(className="bi bi-box-arrow-right me-2"),
                    "Cerrar Sesión"
                ], id='logout-button', color='danger', size='sm')
            )
        ],
        brand=[
            html.Img(src='/assets/LOGO.png', style={'height': '40px', 'marginRight': '15px'}),
            html.Span("Comprensión de riesgo")
        ],
        color="dark",
        dark=True,
        className='mb-4 navbar',
        fluid=True
    ),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div(className='section-title', children=[
                        html.I(className="bi bi-sliders2-vertical"),
                        'Parámetros de Análisis'
                    ]),
                    
                    html.Div([
                        html.Label([
                            html.I(className="bi bi-person-check"),
                            "Responsable del Análisis"
                        ]),
                        dbc.Input(
                            id='user-name-input',
                            type='text',
                            placeholder='Nombre completo',
                            className='mb-4'
                        )
                    ]),
                    
                    html.Hr(),
                    
                    # SECCIÓN: UBICACIÓN GEOGRÁFICA
                    html.Div([
                        html.Label([
                            html.I(className="bi bi-geo-alt"),
                            "Zona de Estudio"
                        ], style={'marginBottom': '15px'}),
                        
                        html.Div([
                            html.Label([
                                html.I(className="bi bi-globe"),
                                "Región / Departamento"
                            ]),
                            dcc.Dropdown(
                                id='departamento-dropdown',
                                options=LISTA_DEPARTAMENTOS,
                                placeholder='Seleccione región',
                                className='mb-3'
                            )
                        ]),
                        
                        html.Div([
                            html.Label([
                                html.I(className="bi bi-pin-map"),
                                "Provincia"
                            ]),
                            dcc.Dropdown(
                                id='provincia-dropdown',
                                placeholder='Seleccione provincia',
                                disabled=True,
                                className='mb-3'
                            )
                        ]),
                        
                        html.Div([
                            html.Label([
                                html.I(className="bi bi-buildings"),
                                "Distrito"
                            ]),
                            dcc.Dropdown(
                                id='distrito-dropdown',
                                placeholder='Seleccione distrito',
                                disabled=True,
                                className='mb-4'
                            )
                        ])
                    ]),

                    html.Hr(),
                    
                    # SECCIÓN: TIPOS DE PELIGRO
                    html.Div([
                        html.Label([
                            html.I(className="bi bi-exclamation-triangle"),
                            "Tipos de Peligro"
                        ], style={'marginBottom': '15px'}),
                        html.Div(className='tipo-selector', children=[
                            dbc.Button([
                                html.I(className="bi bi-droplet-fill"),
                                "Inundación Pluvial"
                            ], id='btn-inundacion pluvial', className='btn-tipo', n_clicks=0),
                            
                            dbc.Button([
                                html.I(className="bi bi-arrow-down-right-circle-fill"),
                                "Deslizamiento Pluvial",
                                html.Span("PRÓXIMAMENTE", className="badge-soon")
                            ], id='btn-deslizamiento', className='btn-tipo', disabled=True, n_clicks=0),
                            
                            dbc.Button([
                                html.I(className="bi bi-snow2"),
                                "Heladas",
                                html.Span("PRÓXIMAMENTE", className="badge-soon")
                            ], id='btn-heladas', className='btn-tipo', disabled=True, n_clicks=0)
                        ])
                    ], className='mb-4'),
                    
                    html.Hr(),
                    
                    # SECCIÓN: ELEMENTOS EXPUESTOS
                    html.Div([
                        html.Label([
                            html.I(className="bi bi-layers"),
                            "Elementos Expuestos"
                        ], style={'marginBottom': '8px'}),
                        html.P([
                            html.I(className="bi bi-info-circle me-2", style={'fontSize': '0.9rem'}),
                            "Mapa de infraestructura y zonas vulnerables"
                        ], style={'fontSize': '0.85rem', 'color': 'var(--text-secondary)', 'marginBottom': '12px'}),
                        
                        dbc.Button([
                            html.I(className="bi bi-pin-map"),
                            "Generar Mapa de Elementos Expuestos"
                        ], id='btn-elementos-expuestos', className='btn-tipo', n_clicks=0, disabled=True,
                        style={'width': '100%', 'fontSize': '0.85rem', 'padding': '16px 14px !important'})
                    ], className='mb-4')
                ])
            ], className='control-panel')
        ], lg=4, className='mb-4 mb-lg-0'),
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div(
                        id='map-container',
                        children=[
                            dbc.Alert([
                                html.Div([
                                    html.I(className="bi bi-map spin", style={'fontSize': '3rem', 'color': 'var(--accent)', 'marginBottom': '15px'})
                                ], className='text-center'),
                                html.H5("Sistema de Análisis de Riesgo", className="alert-heading text-center"),
                                html.P("Configure los parámetros y seleccione el tipo de análisis:", className='text-center mb-3', style={'fontSize': '0.95rem', 'color': 'var(--text-secondary)'}),
                                html.Ul([
                                    html.Li([html.Strong("Peligros:"), " Inundación pluvial, Deslizamiento, Heladas"]),
                                    html.Li([html.Strong("Elementos Expuestos:"), " Agrícola, CP, IE, Vías"])
                                ], style={'textAlign': 'left', 'fontSize': '0.9rem', 'color': 'var(--text-secondary)'})
                            ], color="light", className='border-0 mb-4')
                        ],
                        className="result-panel"
                    ),
                    
                    html.Hr(),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Div(className='section-title', style={'fontSize': '1rem', 'marginBottom': '1rem'}, children=[
                                html.I(className="bi bi-clipboard-check"),
                                'Resumen'
                            ]),
                            html.Div(
                                id='selection-summary',
                                children=[
                                    dbc.Alert([
                                        html.I(className="bi bi-info-circle me-2"),
                                        "Complete los parámetros para continuar"
                                    ], color="light", className='mb-0', style={'fontSize': '0.9rem'})
                                ],
                                className='selection-summary'
                            )
                        ], lg=5, className='mb-3 mb-lg-0'),
                        
                        dbc.Col([
                            dbc.Button([
                                html.I(className="bi bi-lightning-fill me-2"),
                                'Generar Mapa'
                            ], id='generate-map-button', color='success', className='w-100 mb-3 btn-success', disabled=True),
                            
                            dbc.Button([
                                html.I(className="bi bi-download me-2"),
                                'Descargar'
                            ], id='download-button', color='info', className='w-100 mb-3 btn-info', disabled=True),
                            
                            dbc.Button([
                                html.I(className="bi bi-arrow-repeat me-2"),
                                'Nuevo Análisis'
                            ], id='reset-button', color='warning', className='w-100 btn-warning', disabled=True)
                        ], lg=7)
                    ], className='g-3')
                ])
            ], className="result-panel")
        ], lg=8)
    ], className='g-4', style={'marginBottom': '2rem'})
], fluid=True, className="main-container")

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='session-store', storage_type='session'),
    html.Div(id='page-content')
])

# ==================== CALLBACKS ====================

@app.callback(
    Output('page-content', 'children'), 
    Input('session-store', 'data')
)
def display_page(session_data): 
    return dashboard_layout if session_data and session_data.get('logged_in') else login_layout

@app.callback(
    Output('session-store', 'data'), 
    Output('login-alert', 'children'), 
    Input('login-button', 'n_clicks'), 
    State('username-input', 'value'), 
    State('password-input', 'value'), 
    prevent_initial_call=True
)
def login_user(n_clicks, username, password):
    if not username or not password: 
        return {'logged_in': False}, dbc.Alert([
            html.I(className="bi bi-exclamation-triangle me-2"),
            "Complete todos los campos para continuar"
        ], color="warning")
    if username in VALID_USERS and VALID_USERS[username] == password: 
        return {'logged_in': True, 'username': username}, None
    return {'logged_in': False}, dbc.Alert([
        html.I(className="bi bi-x-circle me-2"),
        "Usuario o contraseña incorrectos"
    ], color="danger")

@app.callback(
    Output('session-store', 'data', allow_duplicate=True), 
    Input('logout-button', 'n_clicks'), 
    prevent_initial_call=True
)
def logout_user(n_clicks): 
    return {'logged_in': False}

@app.callback(
    Output('user-display-nav', 'children'), 
    Input('session-store', 'data')
)
def display_user_nav(session_data): 
    return [
        html.I(className="bi bi-person-circle me-2"),
        session_data.get('username', 'Usuario')
    ] if session_data and session_data.get('logged_in') else None

# ==================== CALLBACK PRINCIPAL PARA BOTONES DE TIPO ====================
@app.callback(
    [Output('btn-inundacion pluvial', 'className'),
     Output('btn-deslizamiento', 'className'),
     Output('btn-heladas', 'className'),
     Output('btn-elementos-expuestos', 'className'),
     Output('btn-elementos-expuestos', 'disabled'),
     Output('selected-tipo-peligro', 'data'),
     Output('selected-elementos-expuestos', 'data'),
     Output('tipo-locked', 'data'),
     Output('ubicacion-locked', 'data')],
    [Input('btn-inundacion pluvial', 'n_clicks'),
     Input('btn-deslizamiento', 'n_clicks'),
     Input('btn-heladas', 'n_clicks'),
     Input('btn-elementos-expuestos', 'n_clicks'),
     Input('peligro-downloaded', 'data'),
     Input('elementos-downloaded', 'data')],
    State('tipo-locked', 'data'),
    prevent_initial_call=False
)
def update_tipo_selection(inun_clicks, desli_clicks, heladas_clicks, elem_clicks,
                          peligro_down, elem_down, is_locked):
    from dash import callback_context
    
    if not callback_context.triggered:
        return ('btn-tipo', 'btn-tipo', 'btn-tipo', 'btn-tipo', True, None, False, False, False)
    
    button_id = callback_context.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'btn-inundacion pluvial' and not is_locked:
        return ('btn-tipo btn-tipo-active', 'btn-tipo', 'btn-tipo', 'btn-tipo',
                True, 'inundacion pluvial', False, True, True)
    
    if peligro_down and not elem_down:
        if button_id == 'btn-elementos-expuestos':
            return ('btn-tipo btn-tipo-active', 'btn-tipo', 'btn-tipo', 'btn-tipo btn-tipo-active',
                    True, 'inundacion', True, True, True)
        else:
            return ('btn-tipo btn-tipo-active', 'btn-tipo', 'btn-tipo', 'btn-tipo',
                    False, 'inundacion pluvial', False, True, True)
    
    if peligro_down and elem_down:
        return ('btn-tipo btn-tipo-active', 'btn-tipo', 'btn-tipo', 'btn-tipo btn-tipo-active',
                True, 'inundacion pluvial', True, True, True)
    
    if is_locked:
        elementos_disabled = not peligro_down or elem_down
        return ('btn-tipo btn-tipo-active', 'btn-tipo', 'btn-tipo', 'btn-tipo',
                elementos_disabled, 'inundacion pluvial', False, True, True)
    
    return ('btn-tipo', 'btn-tipo', 'btn-tipo', 'btn-tipo', True, None, False, False, False)

# ==================== BLOQUEAR/DESBLOQUEAR UBICACIÓN ====================
@app.callback(
    [Output('departamento-dropdown', 'disabled'),
     Output('provincia-dropdown', 'disabled', allow_duplicate=True),
     Output('distrito-dropdown', 'disabled', allow_duplicate=True),
     Output('ubicacion-locked', 'data', allow_duplicate=True)],
    [Input('selected-tipo-peligro', 'data'),
     Input('reset-button', 'n_clicks')],
    [State('departamento-dropdown', 'value'),
     State('provincia-dropdown', 'value'),
     State('distrito-dropdown', 'value')],
    prevent_initial_call=True
)
def lock_unlock_location(tipo_peligro, reset_clicks, depa, prov, dist):
    from dash import callback_context
    
    button_id = callback_context.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'reset-button':
        return (False, False, False, False)
    
    if tipo_peligro and all([depa, prov, dist]):
        return (True, True, True, True)
    
    return (False, False, False, False)

@app.callback(
    Output('provincia-dropdown', 'options'), 
    Output('provincia-dropdown', 'disabled'), 
    Output('provincia-dropdown', 'value'), 
    Input('departamento-dropdown', 'value'),
    prevent_initial_call=True
)
def update_provincias(departamento):
    if departamento: 
        return [{'label': prov, 'value': prov} for prov in sorted(PROVINCIAS_POR_DEPA.get(departamento, []))], False, None
    return [], True, None

@app.callback(
    Output('distrito-dropdown', 'options'), 
    Output('distrito-dropdown', 'disabled'), 
    Output('distrito-dropdown', 'value'), 
    Input('provincia-dropdown', 'value'),
    prevent_initial_call=True
)
def update_distritos(provincia):
    if provincia: 
        return [{'label': dist, 'value': dist} for dist in sorted(DISTRITOS_POR_PROV.get(provincia, []))], False, None
    return [], True, None

# ==================== HABILITAR BOTÓN GENERAR ====================
@app.callback(
    Output('generate-map-button', 'disabled', allow_duplicate=True),
    [Input('user-name-input', 'value'),
     Input('departamento-dropdown', 'value'),
     Input('provincia-dropdown', 'value'),
     Input('distrito-dropdown', 'value'),
     Input('selected-tipo-peligro', 'data'),
     Input('selected-elementos-expuestos', 'data'),
     Input('loading-state', 'data'),
     Input('peligro-downloaded', 'data'),
     Input('elementos-downloaded', 'data'),
     Input('generation-status', 'data')],
    prevent_initial_call=True
)
def enable_generate(user, depa, prov, dist, tipo_peligro, elem_exp, loading, peligro_down, elem_down, gen_status):
    if loading:
        return True
    
    if gen_status and gen_status.get('status') == 'completed':
        return True
    
    if elem_down:
        return True
    
    if peligro_down and not elem_exp:
        return True
    
    form_complete = all([user, depa, prov, dist])
    
    if peligro_down and elem_exp and form_complete:
        return False
    
    if tipo_peligro and form_complete and not peligro_down:
        return False
    
    return True

# ==================== RESUMEN ====================
@app.callback(
    Output('selection-summary', 'children'),
    [Input('user-name-input', 'value'),
     Input('departamento-dropdown', 'value'),
     Input('provincia-dropdown', 'value'),
     Input('distrito-dropdown', 'value'),
     Input('selected-tipo-peligro', 'data'),
     Input('selected-elementos-expuestos', 'data')]
)
def update_summary(user, depa, prov, dist, tipo_peligro, elem_exp):
    if not any([user, depa, prov, dist]):
        return dbc.Alert([
            html.I(className="bi bi-info-circle me-2"),
            "Complete los parámetros para continuar"
        ], color="light", className='mb-0', style={'fontSize': '0.9rem'})
    
    items = []
    
    if elem_exp:
        items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-layers"),
            html.Span([html.Strong("Análisis:"), " Elementos Expuestos"])
        ]))
    elif tipo_peligro:
        peligro_map = {'inundacion pluvial': ('Inundación', 'bi-droplet-fill')}
        nombre, icono = peligro_map.get(tipo_peligro, ('Inundación', 'bi-droplet-fill'))
        items.append(html.Div(className='summary-item', children=[
            html.I(className=f"bi {icono}"),
            html.Span([html.Strong("Peligro:"), f" {nombre}"])
        ]))
    
    if user:
        items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-person-fill"),
            html.Span([html.Strong("Usuario:"), f" {user}"])
        ]))
    if depa:
        items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-geo-alt-fill"),
            html.Span([html.Strong("Región:"), f" {depa}"])
        ]))
    if prov:
        items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-pin-map-fill"),
            html.Span([html.Strong("Provincia:"), f" {prov}"])
        ]))
    if dist:
        items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-buildings"),
            html.Span([html.Strong("Distrito:"), f" {dist}"])
        ]))
    
    return html.Div(items)

# ==================== INICIAR GENERACIÓN ====================
@app.callback(
    [Output('loading-state', 'data', allow_duplicate=True),
     Output('generate-map-button', 'children', allow_duplicate=True),
     Output('generate-map-button', 'disabled', allow_duplicate=True),
     Output('check-process', 'disabled'),
     Output('process-id', 'data'),
     Output('generation-status', 'data', allow_duplicate=True)],
    Input('generate-map-button', 'n_clicks'),
    [State('user-name-input', 'value'),
     State('departamento-dropdown', 'value'),
     State('provincia-dropdown', 'value'),
     State('distrito-dropdown', 'value'),
     State('selected-tipo-peligro', 'data'),
     State('selected-elementos-expuestos', 'data')],
    prevent_initial_call=True
)
def start_generation(n_clicks, user, depa, prov, dist, tipo_peligro, elem_exp):
    process_id = str(uuid.uuid4())
    
    if elem_exp:
        tipo_analisis = "ELEMENTOS EXPUESTOS"
        map_type = "elementos"
    else:
        tipo_analisis = f"PELIGRO - {tipo_peligro.upper() if tipo_peligro else 'INUNDACION'}"
        map_type = "peligro"
    
    print(f"\n{'='*60}")
    print(f"🚀 INICIANDO: {tipo_analisis}".center(60))
    print(f"{'='*60}")
    print(f"🆔 Process ID: {process_id}")
    print(f"📍 Ubicación: {dist}, {prov}, {depa}")
    print(f"👤 Usuario: {user}")
    print(f"{'='*60}\n")
    
    PROCESS_STATUS[process_id] = {
        'status': 'processing',
        'start_time': time.time(),
        'filepath': None,
        'error': None,
        'user_name': user,
        'departamento': depa,
        'provincia': prov,
        'distrito': dist,
        'map_type': map_type,
        'tipo_analisis': tipo_analisis
    }
    
    def background_task():
        try:
            if map_type == "elementos":
                print(f"🗺️ [{process_id}] Generando ELEMENTOS EXPUESTOS...")
                if gdf_distritos is None or gdf_provincias is None or gdf_departamentos is None:
                    raise Exception("GeoDataFrames no disponibles")
                ruta = generar_mapa_elementos_expuestos(user, depa, prov, dist)
            else:
                print(f"⚠️ [{process_id}] Generando PELIGRO...")
                ruta = generar_mapa_peligro(user, depa, prov, dist)
            
            tiempo = time.time() - PROCESS_STATUS[process_id]['start_time']
            
            if ruta and os.path.exists(ruta):
                file_size = os.path.getsize(ruta) / (1024 * 1024)
                PROCESS_STATUS[process_id]['status'] = 'completed'
                PROCESS_STATUS[process_id]['filepath'] = ruta
                PROCESS_STATUS[process_id]['file_size'] = file_size
                PROCESS_STATUS[process_id]['duration'] = tiempo
                print(f"✅ [{process_id}] COMPLETADO: {os.path.basename(ruta)} ({file_size:.2f} MB)")
            else:
                PROCESS_STATUS[process_id]['status'] = 'error'
                PROCESS_STATUS[process_id]['error'] = 'Archivo no generado'
        except Exception as e:
            tiempo = time.time() - PROCESS_STATUS[process_id]['start_time']
            PROCESS_STATUS[process_id]['status'] = 'error'
            PROCESS_STATUS[process_id]['error'] = str(e)
            PROCESS_STATUS[process_id]['duration'] = tiempo
            print(f"❌ [{process_id}] ERROR: {e}")
    
    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()
    
    return (True,
            [html.I(className="bi bi-hourglass-split spin me-2"), f'Procesando {tipo_analisis}...'],
            True, False, process_id,
            {'status': 'processing', 'process_id': process_id, 'tipo': tipo_analisis})

# ==================== VERIFICAR ESTADO DEL PROCESO ====================
@app.callback(
    [Output('map-container', 'children'),
     Output('map-filepath-store', 'data'),
     Output('loading-state', 'data'),
     Output('generate-map-button', 'children'),
     Output('check-process', 'disabled', allow_duplicate=True),
     Output('generation-status', 'data'),
     Output('generate-map-button', 'disabled', allow_duplicate=True),
     Output('download-button', 'disabled'),
     Output('download-button', 'children', allow_duplicate=True),
     Output('download-button', 'className', allow_duplicate=True)],
    Input('check-process', 'n_intervals'),
    State('process-id', 'data'),
    prevent_initial_call=True
)
def check_process(n_intervals, process_id):
    if not process_id or process_id not in PROCESS_STATUS:
        return (dbc.Alert("Error: Proceso no encontrado", color="danger"),
                None, False, [html.I(className="bi bi-lightning-fill me-2"), 'Generar Mapa'],
                True, {'status': 'idle'}, False, True,
                [html.I(className="bi bi-download me-2"), 'Descargar'],
                'w-100 mb-3 btn-info')
    
    status = PROCESS_STATUS[process_id]
    current_status = status['status']
    tiempo = time.time() - status['start_time']
    minutos = int(tiempo // 60)
    segundos = int(tiempo % 60)
    tipo_analisis = status.get('tipo_analisis', 'Análisis')
    
    if current_status == 'processing':
        progress = dbc.Alert([
            html.Div([
                html.I(className="bi bi-hourglass-split spin", 
                      style={'fontSize': '3rem', 'color': 'var(--accent)', 'marginBottom': '15px'})
            ], className='text-center'),
            html.H5(f"Generando {tipo_analisis}", className="alert-heading text-center"),
            html.Hr(style={'opacity': '0.5'}),
            html.Div([
                html.Div(className='summary-item', children=[
                    html.I(className="bi bi-clock"),
                    html.Span([html.Strong("Tiempo:"), f" {minutos}m {segundos}s"])
                ]),
                html.Div(className='summary-item', children=[
                    html.I(className="bi bi-geo-alt"),
                    html.Span([html.Strong("Ubicación:"), f" {status['distrito']}, {status['provincia']}"])
                ])
            ], className='mt-3'),
            html.P("Esta página se actualizará automáticamente...", 
                   className='text-center mt-3', style={'fontSize': '0.9rem', 'color': 'var(--text-secondary)'})
        ], color="info", className='border-0')
        
        return (progress, None, True,
                [html.I(className="bi bi-hourglass-split spin me-2"), f'Procesando... {minutos}m {segundos}s'],
                False, {'status': 'processing'}, True, True,
                [html.I(className="bi bi-download me-2"), 'Descargar'],
                'w-100 mb-3 btn-info')
    
    elif current_status == 'completed':
        filepath = status['filepath']
        file_size = status['file_size']
        duration = status['duration']
        dur_min = int(duration // 60)
        dur_sec = int(duration % 60)
        map_type = status.get('map_type', 'peligro')
        
        if map_type == 'peligro':
            next_msg = "Descarga el mapa. Luego podrás generar Elementos Expuestos."
        else:
            next_msg = "Descarga el mapa. Luego podrás hacer un Nuevo Análisis."
        
        success = html.Div([
            dbc.Alert([
                html.Div([
                    html.I(className="bi bi-check-circle-fill success-icon")
                ], className='text-center mb-3'),
                html.H5("¡Mapa Generado Exitosamente!", className="alert-heading text-center"),
                html.Hr(style={'opacity': '0.5'}),
                html.Div([
                    html.Div(className='summary-item', children=[
                        html.I(className="bi bi-file-earmark-image"),
                        html.Span([html.Strong("Archivo:"), html.Code(os.path.basename(filepath), 
                                  style={'fontSize': '0.85em', 'background': 'rgba(15, 52, 96, 0.8)', 
                                         'padding': '4px 8px', 'borderRadius': '6px'})])
                    ]),
                    html.Div(className='summary-item', children=[
                        html.I(className="bi bi-hdd"),
                        html.Span([html.Strong("Tamaño:"), f" {file_size:.2f} MB"])
                    ]),
                    html.Div(className='summary-item', children=[
                        html.I(className="bi bi-clock"),
                        html.Span([html.Strong("Tiempo:"), f" {dur_min}m {dur_sec}s"])
                    ])
                ], className='mt-3')
            ], color="success", className='border-0 mb-3'),
            
            html.Div([
                html.H6([
                    html.I(className="bi bi-arrow-down-circle-fill me-2"),
                    "✅ Archivo listo para descargar"
                ], className='text-center mb-2', style={'fontWeight': '700', 'color': 'var(--success)'}),
                html.P(next_msg, className='text-center mb-0', 
                       style={'fontSize': '0.9rem', 'color': 'var(--text-secondary)'})
            ], className='download-section')
        ])
        
        def cleanup():
            time.sleep(30)
            if process_id in PROCESS_STATUS:
                del PROCESS_STATUS[process_id]
        
        threading.Thread(target=cleanup, daemon=True).start()
        
        return (success, filepath, False,
                [html.I(className="bi bi-lightning-fill me-2"), 'Generar Mapa'],
                True, {'status': 'completed', 'filepath': filepath, 'map_type': map_type},
                True, False,
                [html.I(className="bi bi-download me-2"), 'Descargar'],
                'w-100 mb-3 btn-info')
    
    elif current_status == 'error':
        error_msg = status.get('error', 'Error desconocido')
        duration = status.get('duration', tiempo)
        dur_min = int(duration // 60)
        dur_sec = int(duration % 60)
        
        error = dbc.Alert([
            html.Div([
                html.I(className="bi bi-x-octagon-fill", 
                       style={'fontSize': '2.5rem', 'color': '#c0392b', 'marginBottom': '15px'})
            ], className='text-center'),
            html.H5("Error en la Generación", className="alert-heading text-center"),
            html.Hr(style={'opacity': '0.5'}),
            html.P(f"Detalle: {error_msg}", style={'fontSize': '0.9rem'}),
            html.P(f"Tiempo: {dur_min}m {dur_sec}s", 
                   style={'fontSize': '0.85rem', 'color': 'var(--text-secondary)', 'marginTop': '15px'})
        ], color="danger", className='border-0')
        
        def cleanup():
            time.sleep(30)
            if process_id in PROCESS_STATUS:
                del PROCESS_STATUS[process_id]
        
        threading.Thread(target=cleanup, daemon=True).start()
        
        return (error, None, False,
                [html.I(className="bi bi-lightning-fill me-2"), 'Generar Mapa'],
                True, {'status': 'error', 'error': error_msg}, False, True,
                [html.I(className="bi bi-download me-2"), 'Descargar'],
                'w-100 mb-3 btn-info')

# ==================== DESCARGAR Y ACTUALIZAR FLUJO ====================
@app.callback(
    [Output('download-map-image', 'data'),
     Output('download-button', 'children', allow_duplicate=True),
     Output('download-button', 'className', allow_duplicate=True),
     Output('download-button', 'disabled', allow_duplicate=True),
     Output('peligro-downloaded', 'data'),
     Output('elementos-downloaded', 'data'),
     Output('reset-button', 'disabled'),
     Output('btn-elementos-expuestos', 'disabled', allow_duplicate=True),
     Output('generate-map-button', 'disabled', allow_duplicate=True),
     Output('generation-status', 'data', allow_duplicate=True),
     Output('map-container', 'children', allow_duplicate=True)],
    Input('download-button', 'n_clicks'),
    [State('map-filepath-store', 'data'),
     State('generation-status', 'data'),
     State('peligro-downloaded', 'data'),
     State('elementos-downloaded', 'data')],
    prevent_initial_call=True,
    allow_duplicate=True
)
def download_file(n_clicks, filepath, gen_status, peligro_down, elem_down):
    from dash import callback_context
    
    if not n_clicks:
        return (None, [html.I(className="bi bi-download me-2"), 'Descargar'],
                'w-100 mb-3 btn-info', False, peligro_down, elem_down, True, True, True,
                gen_status, dbc.Alert("Error: Sin clicks", color="danger"))
    
    if not filepath:
        return (None, [html.I(className="bi bi-download me-2"), 'Descargar'],
                'w-100 mb-3 btn-info', False, peligro_down, elem_down, True, True, True,
                gen_status, dbc.Alert("Error: No hay archivo para descargar", color="danger"))
    
    if not os.path.exists(filepath):
        return (None, [html.I(className="bi bi-download me-2"), 'Descargar'],
                'w-100 mb-3 btn-info', False, peligro_down, elem_down, True, True, True,
                gen_status, dbc.Alert(f"Error: Archivo no existe: {filepath}", color="danger"))
    
    downloading = dbc.Alert([
        html.Div([
            html.I(className="bi bi-download spin", 
                  style={'fontSize': '3rem', 'color': 'var(--accent)', 'marginBottom': '15px'})
        ], className='text-center'),
        html.H5("📥 Descargando Archivo...", className="alert-heading text-center"),
        html.Hr(style={'opacity': '0.5'}),
        html.Div([
            html.Div(className='summary-item', children=[
                html.I(className="bi bi-file-earmark-image"),
                html.Span([html.Strong("Archivo:"), html.Code(os.path.basename(filepath), 
                          style={'fontSize': '0.85em', 'background': 'rgba(15, 52, 96, 0.8)', 
                                 'padding': '4px 8px', 'borderRadius': '6px'})])
            ]),
            html.Div(className='summary-item', children=[
                html.I(className="bi bi-hdd"),
                html.Span([html.Strong("Tamaño:"), f" {os.path.getsize(filepath) / (1024*1024):.2f} MB"])
            ])
        ], className='mt-3'),
        html.P("El archivo se está descargando a tu dispositivo...", 
               className='text-center mt-3', style={'fontSize': '0.9rem', 'color': 'var(--text-secondary)'})
    ], color="info", className='border-0')
    
    try:
        map_type = gen_status.get('map_type', 'peligro') if gen_status else 'peligro'
        
        success_msg = dbc.Alert([
            html.Div([
                html.I(className="bi bi-check-circle-fill success-icon")
            ], className='text-center mb-3'),
            html.H5("✅ ¡Descarga Completada!", className="alert-heading text-center"),
            html.Hr(style={'opacity': '0.5'}),
            html.Div([
                html.Div(className='summary-item', children=[
                    html.I(className="bi bi-file-earmark-image"),
                    html.Span([html.Strong("Archivo:"), html.Code(os.path.basename(filepath), 
                              style={'fontSize': '0.85em', 'background': 'rgba(15, 52, 96, 0.8)', 
                                     'padding': '4px 8px', 'borderRadius': '6px'})])
                ]),
                html.Div(className='summary-item', children=[
                    html.I(className="bi bi-check-lg"),
                    html.Span([html.Strong("Estado:"), " ✅ Descargado correctamente"])
                ])
            ], className='mt-3')
        ], color="success", className='border-0')
        
        if map_type == 'peligro':
            return (dcc.send_file(filepath),
                    [html.I(className="bi bi-check-circle me-2"), 'Descargado ✓'],
                    'w-100 mb-3 btn-downloaded', True,
                    True, False, True, False, True,
                    {'status': 'idle'}, success_msg)
        else:
            return (dcc.send_file(filepath),
                    [html.I(className="bi bi-check-circle me-2"), 'Descargado ✓'],
                    'w-100 mb-3 btn-downloaded', True,
                    True, True, False, True, True,
                    {'status': 'idle'}, success_msg)
    except Exception as e:
        error_alert = dbc.Alert([
            html.Div([
                html.I(className="bi bi-x-octagon-fill", 
                       style={'fontSize': '2rem', 'color': '#c0392b', 'marginBottom': '10px'})
            ], className='text-center'),
            html.H5("Error en la Descarga", className="alert-heading text-center"),
            html.Hr(style={'opacity': '0.5'}),
            html.P(f"Detalle: {str(e)}", style={'fontSize': '0.9rem'})
        ], color="danger", className='border-0')
        return (None, [html.I(className="bi bi-download me-2"), 'Descargar'],
                'w-100 mb-3 btn-info', False, peligro_down, elem_down, True, True, False,
                gen_status, error_alert)

# ==================== RESETEAR TODO ====================
@app.callback(
    [Output('user-name-input', 'value'),
     Output('departamento-dropdown', 'value'),
     Output('peligro-downloaded', 'data', allow_duplicate=True),
     Output('elementos-downloaded', 'data', allow_duplicate=True),
     Output('download-button', 'children', allow_duplicate=True),
     Output('download-button', 'className', allow_duplicate=True),
     Output('download-button', 'disabled', allow_duplicate=True),
     Output('map-container', 'children', allow_duplicate=True),
     Output('tipo-locked', 'data', allow_duplicate=True),
     Output('selected-tipo-peligro', 'data', allow_duplicate=True),
     Output('selected-elementos-expuestos', 'data', allow_duplicate=True),
     Output('map-filepath-store', 'data', allow_duplicate=True),
     Output('generation-status', 'data', allow_duplicate=True),
     Output('ubicacion-locked', 'data', allow_duplicate=True)],
    Input('reset-button', 'n_clicks'),
    prevent_initial_call=True
)
def reset_all(n_clicks):
    initial_message = dbc.Alert([
        html.Div([
            html.I(className="bi bi-map spin", style={'fontSize': '3rem', 'color': 'var(--accent)', 'marginBottom': '15px'})
        ], className='text-center'),
        html.H5("Sistema de Análisis de Riesgo", className="alert-heading text-center"),
        html.P("Configure los parámetros y seleccione el tipo de análisis:", className='text-center mb-3', 
               style={'fontSize': '0.95rem', 'color': 'var(--text-secondary)'}),
        html.Ul([
            html.Li([html.Strong("Peligros:"), " Inundación pluvial, Deslizamiento, Heladas"]),
            html.Li([html.Strong("Elementos Expuestos:"), " Agrícola, CP, IE, Vías"])
        ], style={'textAlign': 'left', 'fontSize': '0.9rem', 'color': 'var(--text-secondary)'})
    ], color="light", className='border-0 mb-4')
    
    return (None, None, False, False,
            [html.I(className="bi bi-download me-2"), 'Descargar'],
            'w-100 mb-3 btn-info', True, initial_message,
            False, None, False, None, {'status': 'idle'}, False)

if __name__ == '__main__':
    print(f"\n{'='*80}")
    print("🚀 DASHBOARD DE COMPRENSIÓN DE RIESGO - VERSIÓN REFACTORIZADA".center(80))
    print(f"{'='*80}")
    
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.timeout = 600
    app.server.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    app.run(debug=False, port=8052, threaded=True)