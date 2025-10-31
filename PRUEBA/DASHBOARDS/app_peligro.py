# Archivo: app_peligro.py - DASHBOARD PROFESIONAL PARA MAPA DE PELIGRO

from dash import Dash, html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import re
import os

# Importar la función del mapa de peligro
from mapa_peligro import generar_mapa_peligro

# ==================== CONFIGURACIÓN DE LA APP ====================
app = Dash(
    __name__, 
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=DM+Mono:wght@400;500&display=swap"
    ], 
    suppress_callback_exceptions=True
)

# Inyectar CSS profesional moderno
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* VARIABLES PROFESIONALES */
            :root {
                --primary: #1a1a2e;
                --secondary: #16213e;
                --accent: #e74c3c;
                --accent-light: #ff6b5b;
                --accent-dark: #c0392b;
                --success: #27ae60;
                --text-primary: #ecf0f1;
                --text-secondary: #bdc3c7;
                --border: #34495e;
                --hover: #0f3460;
            }
            
            * {
                font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            
            /* FONDO BASE */
            body {
                background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
                min-height: 100vh;
                color: var(--text-primary);
                overflow-x: hidden;
            }
            
            html, body, #react-entry-point {
                height: 100%;
            }
            
            /* NAVBAR PREMIUM */
            .navbar {
                background: rgba(26, 26, 46, 0.95) !important;
                backdrop-filter: blur(10px);
                border-bottom: 2px solid var(--border);
                padding: 1rem 2rem !important;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            }
            
            .navbar-brand {
                font-weight: 800 !important;
                font-size: 1.4rem !important;
                letter-spacing: -0.5px !important;
                color: var(--text-primary) !important;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            
            .navbar-brand img {
                height: 45px;
                filter: drop-shadow(0 2px 8px rgba(231, 76, 60, 0.3));
                transition: transform 0.3s ease;
            }
            
            .navbar-brand:hover img {
                transform: scale(1.05);
            }
            
            /* CARDS PREMIUM */
            .card {
                background: rgba(22, 33, 62, 0.8) !important;
                border: 1px solid var(--border) !important;
                border-radius: 16px !important;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3) !important;
                backdrop-filter: blur(10px);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            
            .card:hover {
                border-color: var(--accent) !important;
                box-shadow: 0 15px 50px rgba(231, 76, 60, 0.15) !important;
                transform: translateY(-2px);
            }
            
            .card-body {
                padding: 2rem !important;
            }
            
            /* INPUTS PROFESIONALES */
            .form-control, .form-select {
                background: rgba(15, 52, 96, 0.6) !important;
                border: 1.5px solid var(--border) !important;
                border-radius: 12px !important;
                padding: 12px 16px !important;
                color: var(--text-primary) !important;
                transition: all 0.3s ease;
                font-size: 0.95rem;
            }
            
            .form-control:focus, .form-select:focus {
                border-color: var(--accent) !important;
                box-shadow: 0 0 0 4px rgba(231, 76, 60, 0.1) !important;
                background: rgba(15, 52, 96, 0.8) !important;
                color: var(--text-primary) !important;
            }
            
            .form-control::placeholder {
                color: var(--text-secondary);
                opacity: 0.7;
            }
            
            /* LABELS */
            label {
                color: var(--accent);
                font-weight: 700;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            label i {
                font-size: 1rem;
                opacity: 0.9;
            }
            
            /* BOTONES PREMIUM */
            .btn {
                border-radius: 12px !important;
                padding: 12px 24px !important;
                font-weight: 700 !important;
                font-size: 0.95rem !important;
                letter-spacing: 0.5px !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                border: none !important;
                text-transform: uppercase;
            }
            
            .btn-success {
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                color: white !important;
                box-shadow: 0 6px 20px rgba(231, 76, 60, 0.3) !important;
            }
            
            .btn-success:hover:not(:disabled) {
                background: linear-gradient(135deg, var(--accent-light) 0%, var(--accent) 100%) !important;
                transform: translateY(-3px);
                box-shadow: 0 12px 30px rgba(231, 76, 60, 0.4) !important;
            }
            
            .btn-success:disabled {
                background: linear-gradient(135deg, var(--border) 0%, var(--text-secondary) 100%) !important;
                opacity: 0.5;
                cursor: not-allowed !important;
                box-shadow: none !important;
            }
            
            .btn-info {
                background: linear-gradient(135deg, var(--accent-dark) 0%, #a93226 100%) !important;
                color: white !important;
                box-shadow: 0 6px 20px rgba(192, 57, 43, 0.3) !important;
            }
            
            .btn-info:hover:not(:disabled) {
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                transform: translateY(-3px);
                box-shadow: 0 12px 30px rgba(192, 57, 43, 0.4) !important;
            }
            
            .btn-danger {
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                color: white !important;
                border-radius: 10px !important;
                padding: 8px 16px !important;
                font-size: 0.9rem !important;
            }
            
            .btn-danger:hover {
                transform: scale(1.05);
            }
            
            /* ALERTAS PROFESIONALES */
            .alert {
                border-radius: 14px !important;
                border: none !important;
                padding: 24px !important;
                box-shadow: 0 6px 25px rgba(0, 0, 0, 0.2) !important;
                backdrop-filter: blur(10px);
            }
            
            .alert-success {
                background: linear-gradient(135deg, rgba(39, 174, 96, 0.15) 0%, rgba(46, 204, 113, 0.1) 100%) !important;
                border-left: 5px solid var(--success) !important;
                color: var(--text-primary) !important;
            }
            
            .alert-danger {
                background: linear-gradient(135deg, rgba(231, 76, 60, 0.15) 0%, rgba(192, 57, 43, 0.1) 100%) !important;
                border-left: 5px solid var(--accent) !important;
                color: var(--text-primary) !important;
            }
            
            .alert-warning {
                background: linear-gradient(135deg, rgba(241, 196, 15, 0.15) 0%, rgba(230, 126, 34, 0.1) 100%) !important;
                border-left: 5px solid #f39c12 !important;
                color: var(--text-primary) !important;
            }
            
            .alert-light {
                background: rgba(236, 240, 241, 0.08) !important;
                border-left: 5px solid var(--border) !important;
                color: var(--text-primary) !important;
            }
            
            .alert-heading {
                font-weight: 800 !important;
                font-size: 1.1rem !important;
                letter-spacing: -0.3px !important;
            }
            
            /* SEPARADORES */
            hr {
                border-top: 1px solid var(--border) !important;
                opacity: 1;
                margin: 1.5rem 0 !important;
            }
            
            /* SECCIONES */
            .section-title {
                color: var(--text-primary);
                font-weight: 800;
                font-size: 1.2rem;
                letter-spacing: -0.3px;
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 1.5rem;
            }
            
            .section-title i {
                color: var(--accent);
                font-size: 1.4rem;
            }
            
            /* RESUMEN DE SELECCIÓN */
            .selection-summary {
                background: rgba(15, 52, 96, 0.6);
                padding: 20px;
                border-radius: 12px;
                border-left: 4px solid var(--accent);
                color: var(--text-primary);
            }
            
            .summary-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 0;
                font-size: 0.95rem;
            }
            
            .summary-item i {
                color: var(--accent);
                font-size: 1.1rem;
                min-width: 20px;
            }
            
            .summary-item strong {
                color: var(--accent);
                font-weight: 700;
            }
            
            /* LOGIN CONTAINER */
            .login-container {
                background: rgba(22, 33, 62, 0.95);
                backdrop-filter: blur(20px);
                border-radius: 20px;
                padding: 50px;
                box-shadow: 0 25px 70px rgba(231, 76, 60, 0.2);
                border: 1px solid var(--border);
            }
            
            .login-title {
                color: var(--text-primary);
                font-weight: 900;
                font-size: 2rem;
                letter-spacing: -0.5px;
                margin-bottom: 10px;
            }
            
            .login-subtitle {
                color: var(--text-secondary);
                font-size: 0.95rem;
                margin-bottom: 2rem;
            }
            
            /* ANIMACIONES */
            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            @keyframes slideInLeft {
                from {
                    opacity: 0;
                    transform: translateX(-30px);
                }
                to {
                    opacity: 1;
                    transform: translateX(0);
                }
            }
            
            @keyframes slideInRight {
                from {
                    opacity: 0;
                    transform: translateX(30px);
                }
                to {
                    opacity: 1;
                    transform: translateX(0);
                }
            }
            
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
            
            .animated {
                animation: fadeIn 0.6s ease-out;
            }
            
            .slide-left {
                animation: slideInLeft 0.6s ease-out;
            }
            
            .slide-right {
                animation: slideInRight 0.6s ease-out;
            }
            
            .spin {
                animation: spin 2s linear infinite;
            }
            
            /* SCROLLBAR */
            ::-webkit-scrollbar {
                width: 10px;
            }
            
            ::-webkit-scrollbar-track {
                background: var(--primary);
            }
            
            ::-webkit-scrollbar-thumb {
                background: linear-gradient(135deg, var(--border) 0%, var(--accent) 100%);
                border-radius: 5px;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%);
            }
            
            /* LAYOUT RESPONSIVE */
            .main-container {
                padding: 2rem;
                min-height: 100vh;
            }
            
            .control-panel {
                animation: slideInLeft 0.7s ease-out;
            }
            
            .result-panel {
                animation: slideInRight 0.7s ease-out;
            }
            
            /* FOOTER CONTACTO */
            .contact-footer {
                position: fixed;
                bottom: 25px;
                left: 25px;
                background: rgba(26, 26, 46, 0.95);
                backdrop-filter: blur(10px);
                padding: 14px 22px;
                border-radius: 12px;
                border: 1px solid var(--border);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                z-index: 1000;
                transition: all 0.3s ease;
                display: flex;
                gap: 16px;
            }
            
            .contact-footer:hover {
                background: rgba(22, 33, 62, 0.98);
                border-color: var(--accent);
                box-shadow: 0 12px 40px rgba(231, 76, 60, 0.2);
                transform: translateY(-3px);
            }
            
            .contact-footer a {
                color: var(--text-secondary);
                text-decoration: none;
                font-weight: 600;
                font-size: 0.85rem;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            
            .contact-footer a:hover {
                color: var(--accent);
            }
            
            /* ICONOS DE ÉXITO */
            .success-icon {
                color: var(--success);
                font-size: 3rem;
            }
            
            /* DESCARGA SECTION */
            .download-section {
                background: rgba(39, 174, 96, 0.1);
                padding: 20px;
                border-radius: 12px;
                border: 2px dashed var(--success);
                margin-top: 15px;
            }
            
            /* BOTONES DE TIPO DE PELIGRO */
            .peligro-selector {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 12px;
                margin-bottom: 0px;
            }
            
            .btn-peligro {
                padding: 18px 14px !important;
                border-radius: 14px !important;
                font-weight: 700 !important;
                font-size: 0.8rem !important;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                border: 2px solid var(--border) !important;
                background: rgba(15, 52, 96, 0.4) !important;
                color: var(--text-secondary) !important;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 10px;
                cursor: pointer;
                position: relative;
            }
            
            .btn-peligro i {
                font-size: 2rem;
                transition: all 0.3s ease;
            }
            
            .btn-peligro-active {
                background: linear-gradient(135deg, #27ae60 0%, #229954 100%) !important;
                border-color: #27ae60 !important;
                color: white !important;
                box-shadow: 0 8px 25px rgba(39, 174, 96, 0.5) !important;
                transform: translateY(-3px) scale(1.02);
                cursor: default !important;
                pointer-events: none !important;
            }
            
            .btn-peligro-active i {
                transform: scale(1.1);
            }
            
            .btn-peligro-active::after {
                content: '✓';
                position: absolute;
                top: 8px;
                right: 8px;
                background: rgba(255, 255, 255, 0.3);
                width: 24px;
                height: 24px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 900;
                font-size: 0.9rem;
            }
            
            .btn-peligro:not(.btn-peligro-active):not(:disabled):hover {
                border-color: #27ae60;
                background: rgba(39, 174, 96, 0.2) !important;
                transform: translateY(-2px);
            }
            
            .btn-peligro:not(.btn-peligro-active):not(:disabled):active {
                transform: translateY(0px) scale(0.98);
            }
            
            .btn-peligro:disabled {
                opacity: 0.35;
                cursor: not-allowed !important;
                background: rgba(15, 52, 96, 0.2) !important;
            }
            
            .btn-peligro:disabled i {
                opacity: 0.4;
            }
            
            .badge-soon {
                font-size: 0.65rem;
                padding: 3px 8px;
                background: rgba(241, 196, 15, 0.2);
                color: #f1c40f;
                border-radius: 6px;
                font-weight: 600;
                margin-top: -5px;
            }
            
            /* RESPONSIVE */
            @media (max-width: 768px) {
                .main-container {
                    padding: 1rem;
                }
                
                .card-body {
                    padding: 1.5rem !important;
                }
                
                .login-container {
                    padding: 30px;
                }
                
                .login-title {
                    font-size: 1.5rem;
                }
                
                .contact-footer {
                    flex-direction: column;
                    width: calc(100% - 50px);
                    left: 25px;
                    right: 25px;
                }
                
                .peligro-selector {
                    grid-template-columns: 1fr;
                }
            }
        </style>
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

VALID_USERS = {'admin': 'admin', 'usuario': 'admin'}

def leer_sql(ruta):
    if not os.path.exists(ruta):
        print(f"⚠️  ADVERTENCIA: La ruta del archivo SQL no existe: '{ruta}'")
        return []
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    patron = r"INSERT INTO `\w+` VALUES \(([^)]+)\);"
    matches = re.findall(patron, contenido)
    return [[v.strip().strip("'") for v in match.split(',')] for match in matches]

# Carga de datos SQL
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
                        html.P("Análisis de Peligros", className="login-subtitle text-center"),
                        
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
    dcc.Store(id='map-filepath-store', storage_type='memory'),
    dcc.Store(id='loading-state', storage_type='memory', data=False),
    dcc.Store(id='selected-peligro', storage_type='memory', data='inundacion'),
    dcc.Store(id='peligro-locked', storage_type='memory', data=False),
    
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
                    
                    html.Div([
                        html.Label([
                            html.I(className="bi bi-exclamation-triangle"),
                            "Tipo de Peligro"
                        ], style={'marginBottom': '15px'}),
                        html.Div(className='peligro-selector', children=[
                            dbc.Button([
                                html.I(className="bi bi-droplet-fill"),
                                "Inundación"
                            ], id='btn-inundacion', className='btn-peligro btn-peligro-active', n_clicks=0),
                            
                            dbc.Button([
                                html.I(className="bi bi-arrow-down-right-circle-fill"),
                                "Deslizamiento",
                                html.Span("PRÓXIMAMENTE", className="badge-soon")
                            ], id='btn-deslizamiento', className='btn-peligro', disabled=True, n_clicks=0),
                            
                            dbc.Button([
                                html.I(className="bi bi-snow2"),
                                "Heladas",
                                html.Span("PRÓXIMAMENTE", className="badge-soon")
                            ], id='btn-heladas', className='btn-peligro', disabled=True, n_clicks=0)
                        ])
                    ], className='mb-4'),
                    
                    html.Hr(),
                    
                    html.Div([
                        html.Label([
                            html.I(className="bi bi-globe"),
                            "Región / Departamento"
                        ]),
                        dcc.Dropdown(
                            id='departamento-dropdown',
                            options=LISTA_DEPARTAMENTOS,
                            placeholder='Seleccione región',
                            className='mb-4'
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
                            className='mb-4'
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
                                html.H5("Generador de Mapas de Susceptibilidad", className="alert-heading text-center"),
                                html.P("Configure los parámetros en el panel izquierdo y genere su mapa de análisis", className='text-center mb-0', style={'fontSize': '0.95rem', 'color': 'var(--text-secondary)'})
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
                            ], id='download-button', color='info', className='w-100 btn-info', disabled=True)
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
    dcc.Store(id='loading-state', storage_type='memory', data=False),
    dcc.Store(id='selected-peligro', storage_type='memory', data='inundacion'),
    dcc.Store(id='peligro-locked', storage_type='memory', data=False),
    html.Div(id='page-content')
])

# ==================== CALLBACKS ====================
@app.callback(Output('page-content', 'children'), Input('session-store', 'data'))
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

@app.callback(Output('user-display-nav', 'children'), Input('session-store', 'data'))
def display_user_nav(session_data): 
    return [
        html.I(className="bi bi-person-circle me-2"),
        session_data.get('username', 'Usuario')
    ] if session_data and session_data.get('logged_in') else None

# Callback para manejar la selección de tipo de peligro (SOLO SELECCIÓN, NO EJECUCIÓN)
@app.callback(
    [Output('btn-inundacion', 'className'),
     Output('btn-deslizamiento', 'className'),
     Output('btn-heladas', 'className'),
     Output('selected-peligro', 'data'),
     Output('peligro-locked', 'data')],
    [Input('btn-inundacion', 'n_clicks'),
     Input('btn-deslizamiento', 'n_clicks'),
     Input('btn-heladas', 'n_clicks')],
    [State('peligro-locked', 'data')],
    prevent_initial_call=False
)
def update_peligro_selection(inundacion_clicks, deslizamiento_clicks, heladas_clicks, is_locked):
    """
    Maneja la selección visual del tipo de peligro.
    IMPORTANTE: 
    - Solo actualiza la selección, NO ejecuta ningún código.
    - Una vez seleccionado, SE BLOQUEA y no se puede cambiar.
    - La ejecución ocurre al presionar "Generar Mapa".
    """
    from dash import callback_context
    
    # Si ya está bloqueado, mantener el estado actual sin cambios
    if is_locked:
        # Determinar cuál está activo basado en el estado bloqueado
        if inundacion_clicks and inundacion_clicks > 0:
            return (
                'btn-peligro btn-peligro-active',
                'btn-peligro',
                'btn-peligro',
                'inundacion',
                True
            )
        elif deslizamiento_clicks and deslizamiento_clicks > 0:
            return (
                'btn-peligro',
                'btn-peligro btn-peligro-active',
                'btn-peligro',
                'deslizamiento',
                True
            )
        elif heladas_clicks and heladas_clicks > 0:
            return (
                'btn-peligro',
                'btn-peligro',
                'btn-peligro btn-peligro-active',
                'heladas',
                True
            )
    
    # Valores por defecto al inicio (antes del primer clic)
    if not callback_context.triggered:
        return (
            'btn-peligro',  # Ninguno activo al inicio
            'btn-peligro',
            'btn-peligro',
            None,
            False
        )
    
    # Detectar qué botón fue presionado
    button_id = callback_context.triggered[0]['prop_id'].split('.')[0]
    
    # Actualizar clases según el botón presionado Y BLOQUEAR
    if button_id == 'btn-inundacion':
        print("✅ Tipo de peligro SELECCIONADO y BLOQUEADO: INUNDACIÓN")
        return (
            'btn-peligro btn-peligro-active',
            'btn-peligro',
            'btn-peligro',
            'inundacion',
            True  # BLOQUEAR después del primer clic
        )
    elif button_id == 'btn-deslizamiento':
        print("✅ Tipo de peligro SELECCIONADO y BLOQUEADO: DESLIZAMIENTO")
        return (
            'btn-peligro',
            'btn-peligro btn-peligro-active',
            'btn-peligro',
            'deslizamiento',
            True  # BLOQUEAR después del primer clic
        )
    elif button_id == 'btn-heladas':
        print("✅ Tipo de peligro SELECCIONADO y BLOQUEADO: HELADAS")
        return (
            'btn-peligro',
            'btn-peligro',
            'btn-peligro btn-peligro-active',
            'heladas',
            True  # BLOQUEAR después del primer clic
        )
    
    # Por defecto, mantener sin selección
    return (
        'btn-peligro',
        'btn-peligro',
        'btn-peligro',
        None,
        False
    )

@app.callback(
    Output('provincia-dropdown', 'options'), 
    Output('provincia-dropdown', 'disabled'), 
    Output('provincia-dropdown', 'value'), 
    Input('departamento-dropdown', 'value')
)
def update_provincias(departamento):
    if departamento: 
        return [{'label': prov, 'value': prov} for prov in sorted(PROVINCIAS_POR_DEPA.get(departamento, []))], False, None
    return [], True, None

@app.callback(
    Output('distrito-dropdown', 'options'), 
    Output('distrito-dropdown', 'disabled'), 
    Output('distrito-dropdown', 'value'), 
    Input('provincia-dropdown', 'value')
)
def update_distritos(provincia):
    if provincia: 
        return [{'label': dist, 'value': dist} for dist in sorted(DISTRITOS_POR_PROV.get(provincia, []))], False, None
    return [], True, None

@app.callback(
    Output('generate-map-button', 'disabled'), 
    Output('download-button', 'disabled'),
    [Input(c, 'value') for c in ['user-name-input', 'departamento-dropdown', 'provincia-dropdown', 'distrito-dropdown']],
    Input('loading-state', 'data')
)
def enable_buttons(*values): 
    loading_state = values[-1]
    form_values = values[:-1]
    
    if loading_state:
        return True, True
    
    all_filled = all(form_values)
    return not all_filled, not all_filled

@app.callback(
    Output('selection-summary', 'children'), 
    [Input(c, 'value') for c in ['user-name-input', 'departamento-dropdown', 'provincia-dropdown', 'distrito-dropdown']],
    Input('selected-peligro', 'data')
)
def update_summary(user_name, departamento, provincia, distrito, tipo_peligro):
    if not any([user_name, departamento, provincia, distrito]): 
        return dbc.Alert([
            html.I(className="bi bi-info-circle me-2"),
            "Complete los parámetros para continuar"
        ], color="light", className='mb-0', style={'fontSize': '0.9rem'})
    
    summary_items = []
    
    # Determinar tipo de peligro y su icono
    peligro_map = {
        'inundacion': ('Inundación', 'bi-droplet-fill'),
        'deslizamiento': ('Deslizamiento', 'bi-arrow-down-right-circle-fill'),
        'heladas': ('Heladas', 'bi-snow2')
    }
    
    peligro_nombre, peligro_icon = peligro_map.get(tipo_peligro, ('Inundación', 'bi-droplet-fill'))
    
    summary_items.append(html.Div(className='summary-item', children=[
        html.I(className=f"bi {peligro_icon}"),
        html.Span([html.Strong("Peligro:"), f" {peligro_nombre}"])
    ]))
    
    if user_name: 
        summary_items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-person-fill"),
            html.Span([html.Strong("Usuario:"), f" {user_name}"])
        ]))
    if departamento: 
        summary_items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-geo-alt-fill"),
            html.Span([html.Strong("Región:"), f" {departamento}"])
        ]))
    if provincia: 
        summary_items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-pin-map-fill"),
            html.Span([html.Strong("Provincia:"), f" {provincia}"])
        ]))
    if distrito: 
        summary_items.append(html.Div(className='summary-item', children=[
            html.I(className="bi bi-buildings"),
            html.Span([html.Strong("Distrito:"), f" {distrito}"])
        ]))
    
    return html.Div(summary_items)

@app.callback(
    Output('loading-state', 'data', allow_duplicate=True),
    Output('generate-map-button', 'children', allow_duplicate=True),
    Input('generate-map-button', 'n_clicks'),
    prevent_initial_call=True
)
def activate_loading(n_clicks):
    return True, [
        html.I(className="bi bi-hourglass-split spin me-2"),
        'Procesando...'
    ]

@app.callback(
    Output('map-container', 'children'),
    Output('map-filepath-store', 'data'),
    Output('loading-state', 'data'),
    Output('generate-map-button', 'children'),
    Input('generate-map-button', 'n_clicks'),
    [State('user-name-input', 'value'),
     State('departamento-dropdown', 'value'),
     State('provincia-dropdown', 'value'),
     State('distrito-dropdown', 'value'),
     State('selected-peligro', 'data')],
    prevent_initial_call=True
)
def generate_and_save_map_callback(n_clicks, user_name, departamento, provincia, distrito, tipo_peligro):
    """
    ESTE ES EL ÚNICO CALLBACK QUE EJECUTA EL CÓDIGO mapa_peligro.py
    Se ejecuta SOLO cuando el usuario presiona "Generar Mapa" después de:
    1. Seleccionar el tipo de peligro
    2. Completar todos los campos de ubicación
    """
    ruta_guardado = None
    
    try:
        # Determinar nombre del peligro para logging
        peligro_nombre = {
            'inundacion': 'Inundación',
            'deslizamiento': 'Deslizamiento',
            'heladas': 'Heladas'
        }.get(tipo_peligro, 'Inundación')
        
        print(f"\n{'='*60}")
        print(f"⚙️  EJECUTANDO mapa_peligro.py".center(60))
        print(f"{'='*60}")
        print(f"📍 Ubicación: {distrito}, {provincia}, {departamento}")
        print(f"💧 Tipo de peligro: {peligro_nombre}")
        print(f"👤 Responsable: {user_name}")
        print(f"{'='*60}\n")
        
        # AQUÍ SE EJECUTA EL CÓDIGO mapa_peligro.py
        ruta_guardado = generar_mapa_peligro(user_name, departamento, provincia, distrito)
        
        if ruta_guardado and os.path.exists(ruta_guardado):
            file_size_mb = os.path.getsize(ruta_guardado) / (1024 * 1024)
            
            success_alert = html.Div([
                dbc.Alert([
                    html.Div([
                        html.I(className="bi bi-check-circle-fill success-icon")
                    ], className='text-center mb-3'),
                    html.H5("¡Mapa Generado Exitosamente!", className="alert-heading text-center"),
                    html.Hr(style={'opacity': '0.5'}),
                    html.Div([
                        html.Div(className='summary-item', children=[
                            html.I(className="bi bi-file-earmark-image"),
                            html.Span([html.Strong("Archivo:"), html.Code(os.path.basename(ruta_guardado), style={'fontSize': '0.85em', 'background': 'rgba(15, 52, 96, 0.8)', 'padding': '4px 8px', 'borderRadius': '6px'})])
                        ]),
                        html.Div(className='summary-item', children=[
                            html.I(className="bi bi-hdd"),
                            html.Span([html.Strong("Tamaño:"), f" {file_size_mb:.2f} MB"])
                        ]),
                        html.Div(className='summary-item', children=[
                            html.I(className="bi bi-bar-chart"),
                            html.Span([html.Strong("Parámetros:"), " Pendiente, Geomorfología, PP Máxima"])
                        ]),
                        html.Div(className='summary-item', children=[
                            html.I(className="bi bi-graph-up"),
                            html.Span([html.Strong("Clasificación:"), " Baja, Media, Alta, Muy Alta"])
                        ])
                    ], className='mt-3')
                ], color="success", className='border-0 mb-3'),
                
                html.Div([
                    html.H6([
                        html.I(className="bi bi-arrow-down-circle-fill me-2"),
                        "Descarga tu archivo"
                    ], className='text-center mb-2', style={'fontWeight': '700'}),
                    html.P("Presiona el botón 'Descargar' para obtener el mapa", className='text-center mb-0', style={'fontSize': '0.9rem', 'color': 'var(--text-secondary)'})
                ], className='download-section')
            ])
            
            button_text = [
                html.I(className="bi bi-lightning-fill me-2"),
                'Generar Mapa'
            ]
            
            print(f"\n{'='*60}")
            print(f"✅ ÉXITO - mapa_peligro.py ejecutado correctamente".center(60))
            print(f"{'='*60}")
            print(f"📁 Ruta: {ruta_guardado}")
            print(f"💾 Tamaño: {file_size_mb:.2f} MB")
            print(f"{'='*60}\n")
            
            return success_alert, ruta_guardado, False, button_text
        else:
            print(f"\n❌ ERROR: El archivo no existe después de ejecutar mapa_peligro.py\n")
            
            error_alert = dbc.Alert([
                html.Div([
                    html.I(className="bi bi-exclamation-triangle-fill", style={'fontSize': '2.5rem', 'color': '#f39c12', 'marginBottom': '15px'})
                ], className='text-center'),
                html.H5("Error en la Generación", className="alert-heading text-center"),
                html.Hr(style={'opacity': '0.5'}),
                html.P("No se pudo generar el mapa correctamente. Verifica:", style={'fontSize': '0.95rem'}),
                html.Ul([
                    html.Li("Que existan los archivos de peligro (Pendiente, Geomorfología, PP)"),
                    html.Li("Que el distrito tenga datos disponibles"),
                    html.Li("Los logs en la terminal para más detalles")
                ], style={'fontSize': '0.9rem'})
            ], color="warning", className='border-0')
            
            button_text = [
                html.I(className="bi bi-lightning-fill me-2"),
                'Generar Mapa'
            ]
            
            return error_alert, None, False, button_text
            
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: Archivo no encontrado - {str(e)}\n")
        
        error_alert = dbc.Alert([
            html.Div([
                html.I(className="bi bi-file-excel-fill", style={'fontSize': '2.5rem', 'color': '#f39c12', 'marginBottom': '15px'})
            ], className='text-center'),
            html.H5("Archivo No Encontrado", className="alert-heading text-center"),
            html.Hr(style={'opacity': '0.5'}),
            html.P(f"Error: {str(e)}", style={'fontSize': '0.9rem'}),
            html.P("Verifica las rutas de los archivos en la documentación", style={'fontSize': '0.85rem', 'color': 'var(--text-secondary)'})
        ], color="warning", className='border-0')
        
        button_text = [
            html.I(className="bi bi-lightning-fill me-2"),
            'Generar Mapa'
        ]
        
        return error_alert, None, False, button_text
        
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO en mapa_peligro.py")
        print(f"Detalle: {str(e)}\n")
        import traceback
        traceback.print_exc()
        
        error_alert = dbc.Alert([
            html.Div([
                html.I(className="bi bi-x-octagon-fill", style={'fontSize': '2.5rem', 'color': '#c0392b', 'marginBottom': '15px'})
            ], className='text-center'),
            html.H5("Error Inesperado", className="alert-heading text-center"),
            html.Hr(style={'opacity': '0.5'}),
            html.P(f"Ocurrió un error: {str(e)}", style={'fontSize': '0.9rem'}),
            html.P("Consulta la terminal para más detalles", style={'fontSize': '0.85rem', 'color': 'var(--text-secondary)'})
        ], color="danger", className='border-0')
        
        button_text = [
            html.I(className="bi bi-lightning-fill me-2"),
            'Generar Mapa'
        ]
        
        return error_alert, None, False, button_text

@app.callback(
    Output('download-map-image', 'data'),
    Input('download-button', 'n_clicks'),
    State('map-filepath-store', 'data'),
    prevent_initial_call=True
)
def download_map(n_clicks, filepath):
    if not n_clicks or not filepath or not os.path.exists(filepath):
        return None
    try:
        print(f"📥 Iniciando descarga: {filepath}")
        return dcc.send_file(filepath)
    except Exception as e:
        print(f"❌ Error al descargar: {e}")
        return None

if __name__ == '__main__':
    print(f"\n{'='*80}")
    print("🔍 VERIFICANDO ARCHIVOS DE PELIGRO".center(80))
    print(f"{'='*80}")
    
    ruta_base_pendiente = "/workspaces/AUTOMATIZACION_DASH/PRUEBA/DATA/PELIGRO/PENDIENTE"
    ruta_base_geomorfo = "/workspaces/AUTOMATIZACION_DASH/PRUEBA/DATA/PELIGRO/GEOMORFOLOGIA"
    ruta_base_ppmax = "/workspaces/AUTOMATIZACION_DASH/PRUEBA/DATA/PELIGRO/PP_MAX"
    
    if os.path.exists(ruta_base_pendiente):
        pendiente_files = [f for r, d, files in os.walk(ruta_base_pendiente) for f in files if f.endswith('.shp')]
        print(f"✅ PENDIENTE: {len(pendiente_files)} archivos")
    else:
        print("⚠️  PENDIENTE: No encontrada")
    
    if os.path.exists(ruta_base_geomorfo):
        geomorfo_files = [f for r, d, files in os.walk(ruta_base_geomorfo) for f in files if f.endswith('.shp')]
        print(f"✅ GEOMORFOLOGÍA: {len(geomorfo_files)} archivos")
    else:
        print("⚠️  GEOMORFOLOGÍA: No encontrada")
    
    if os.path.exists(ruta_base_ppmax):
        ppmax_files = [f for r, d, files in os.walk(ruta_base_ppmax) for f in files if f.endswith('.shp')]
        print(f"✅ PP_MAX: {len(ppmax_files)} archivos")
    else:
        print("⚠️  PP_MAX: No encontrada")
    
    print(f"{'='*80}\n")
    
    print(f"\n{'='*80}")
    print("🚀 DASHBOARD PROFESIONAL - Comprensión de riesgo".center(80))
    print(f"{'='*80}")
    print("🎨 Diseño: Moderno y Profesional")
    print("🎯 Paleta: Gradientes Azul-Rojo con Efectos Glassmorphism")
    print("✨ Animaciones: Suaves y Fluidas")
    print("💧 Tipos de Peligro: Inundación (Activo) | Deslizamiento | Heladas")
    print("📊 Fórmula: (PENDIENTE + GEOMORFOLOGÍA + PP_MAX + GEOLOGIA + DISTANCIA_RIO) / 5")
    print("📈 Clasificación: Baja | Media | Alta | Muy Alta")
    print("🌐 Puerto: 8052")
    print("🔗 URL: http://127.0.0.1:8052")
    print(f"{'='*80}\n")
    
    app.run(debug=True, port=8052)