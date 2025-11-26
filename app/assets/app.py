# Archivo: app.py - VERSIÓN COMPLETA CON FILTRADO POR USUARIO Y SIN DESCARGAS DUPLICADAS

from dash import Dash, html, dcc, Input, Output, State, ALL, ctx, callback
import dash_bootstrap_components as dbc
import re
import os
import uuid
from datetime import datetime
from threading import Thread
import queue

# Importamos la lógica de los diferentes tipos de mapas
from geografica_final import generar_mapa_final
from geomorfologia_final import generar_mapa_geomorfologia
from climatica_final import generar_mapa_climatica
from poblacion_final import generar_mapa_poblacion
from vias_final import generar_mapa_vias
from pendientes_final import generar_mapa_pendientes
from geologia_final import generar_mapa_geologia

# ==================== SISTEMA DE COLA DE PROCESAMIENTO ====================
class MapGenerationQueue:
    """Gestiona la cola de generación de mapas con procesamiento en segundo plano"""
    def __init__(self, max_workers=3):
        self.queue = queue.Queue()
        self.tasks = {}  # {task_id: {'status': 'pending'|'processing'|'completed'|'error', ...}}
        self.max_workers = max_workers
        self.workers_active = 0
        
    def add_task(self, user_name, map_type, departamento, provincia, distrito):
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {
            'status': 'pending',
            'user_name': user_name,
            'map_type': map_type,
            'departamento': departamento,
            'provincia': provincia,
            'distrito': distrito,
            'created_at': datetime.now(),
            'filepath': None,
            'error': None
        }
        self.queue.put(task_id)
        return task_id
    
    def get_task_status(self, task_id):
        return self.tasks.get(task_id, {'status': 'not_found'})
    
    def process_task(self, task_id):
        """Procesa un mapa en segundo plano"""
        try:
            task = self.tasks[task_id]
            task['status'] = 'processing'
            task['started_at'] = datetime.now()
            
            user_name = task['user_name']
            map_type = task['map_type']
            departamento = task['departamento']
            provincia = task['provincia']
            distrito = task['distrito']
            
            print(f"⏱️ [{task_id}] Procesando mapa: {distrito} ({map_type}) para {user_name}")
            
            ruta_guardado = None
            
            if map_type == 'geografico':
                ruta_guardado = generar_mapa_final(user_name, departamento, provincia, distrito)
            elif map_type == 'geomorfologia':
                ruta_guardado = generar_mapa_geomorfologia(user_name, departamento, provincia, distrito)
            elif map_type == 'climatica':
                ruta_guardado = generar_mapa_climatica(user_name, departamento, provincia, distrito)
            elif map_type == 'pendientes':
                ruta_pendientes = "/workspaces/AUTOMATIZACION_DASH/PRUEBA/DATA/PENDIENTES/pendientes.tif"
                if not os.path.exists(ruta_pendientes):
                    raise FileNotFoundError(f"Archivo de pendientes no encontrado: {ruta_pendientes}")
                ruta_guardado = generar_mapa_pendientes(user_name, departamento, provincia, distrito)
            elif map_type == 'vias':
                ruta_guardado = generar_mapa_vias(user_name, departamento, provincia, distrito)
            elif map_type == 'centros':
                ruta_guardado = generar_mapa_poblacion(user_name, departamento, provincia, distrito)
            elif map_type == 'geologia':
                ruta_guardado = generar_mapa_geologia(user_name, departamento, provincia, distrito)
            
            if ruta_guardado and os.path.exists(ruta_guardado):
                task['status'] = 'completed'
                task['filepath'] = ruta_guardado
                task['file_size_mb'] = os.path.getsize(ruta_guardado) / (1024 * 1024)
                print(f"✅ [{task_id}] Mapa completado para {user_name}: {os.path.basename(ruta_guardado)}")
            else:
                raise Exception("No se generó archivo")
                
        except Exception as e:
            task['status'] = 'error'
            task['error'] = str(e)
            print(f"❌ [{task_id}] Error para {user_name}: {str(e)}")
        
        finally:
            task['completed_at'] = datetime.now()

map_queue = MapGenerationQueue(max_workers=3)

# ==================== CONFIGURACIÓN DE LA APP ====================
app = Dash(
    __name__, 
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
    ], 
    suppress_callback_exceptions=True
)

# Inyectar CSS con tema verde y animaciones
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Variables de color */
            :root {
                --escuela-verde-claro: #8BC34A;
                --escuela-verde: #7CB342;
                --escuela-verde-oscuro: #558B2F;
                --escuela-verde-profundo: #33691E;
                --gris-carga: #90A4AE;
            }
            
            /* Fuente moderna */
            * {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            
            /* Fondo con gradiente verde */
            body {
                background: linear-gradient(135deg, #8BC34A 0%, #558B2F 50%, #33691E 100%) !important;
                min-height: 100vh;
            }
            
            /* Cards con efecto glassmorphism */
            .card {
                backdrop-filter: blur(10px);
                background: rgba(200, 220, 190, 0.35) !important;
                border: 1px solid rgba(255, 255, 255, 0.25) !important;
                box-shadow: 0 10px 40px rgba(51, 105, 30, 0.2) !important;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                border-radius: 16px !important;
            }
            
            .card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 50px rgba(51, 105, 30, 0.3) !important;
            }
            
            /* Inputs modernos con acento verde */
            .form-control, .form-select {
                border: 2px solid rgba(197, 225, 165, 0.5) !important;
                border-radius: 12px !important;
                padding: 12px 16px !important;
                transition: all 0.3s ease;
                background: rgba(245, 250, 240, 0.4) !important;
                backdrop-filter: blur(5px);
            }
            
            .form-control:focus, .form-select:focus {
                border-color: #7CB342 !important;
                box-shadow: 0 0 0 3px rgba(124, 179, 66, 0.15) !important;
                transform: translateY(-2px);
                background: rgba(255, 255, 255, 0.6) !important;
            }
            
            /* Botón Generar Mapa - Verde */
            .btn-success {
                background: linear-gradient(135deg, #8BC34A 0%, #7CB342 100%) !important;
                border: none !important;
                border-radius: 12px !important;
                padding: 14px 28px !important;
                font-weight: 700 !important;
                letter-spacing: 0.5px !important;
                transition: all 0.3s ease;
                box-shadow: 0 4px 20px rgba(139, 195, 74, 0.4) !important;
                color: white !important;
            }
            
            .btn-success:hover:not(:disabled) {
                background: linear-gradient(135deg, #7CB342 0%, #689F38 100%) !important;
                transform: translateY(-3px);
                box-shadow: 0 6px 30px rgba(139, 195, 74, 0.5) !important;
            }
            
            .btn-success:disabled {
                background: linear-gradient(135deg, #B0BEC5 0%, #90A4AE 100%) !important;
                opacity: 0.7;
                cursor: wait !important;
                box-shadow: 0 2px 10px rgba(144, 164, 174, 0.3) !important;
                animation: pulse-loading 1.5s ease-in-out infinite;
            }
            
            /* Botón Descargar Mapa - Verde Oscuro */
            .btn-info {
                background: linear-gradient(135deg, #558B2F 0%, #33691E 100%) !important;
                border: none !important;
                border-radius: 12px !important;
                padding: 14px 28px !important;
                font-weight: 700 !important;
                transition: all 0.3s ease;
                box-shadow: 0 4px 20px rgba(85, 139, 47, 0.4) !important;
                color: white !important;
            }
            
            .btn-info:hover:not(:disabled) {
                background: linear-gradient(135deg, #33691E 0%, #1B5E20 100%) !important;
                transform: translateY(-3px);
                box-shadow: 0 6px 30px rgba(85, 139, 47, 0.5) !important;
            }
            
            .btn-info:disabled {
                background: linear-gradient(135deg, #B0BEC5 0%, #90A4AE 100%) !important;
                opacity: 0.7;
                cursor: wait !important;
                box-shadow: 0 2px 10px rgba(144, 164, 174, 0.3) !important;
            }
            
            /* Botón Logout */
            .btn-danger {
                background: linear-gradient(135deg, #EF5350 0%, #E53935 100%) !important;
                border: none !important;
                border-radius: 8px !important;
                transition: all 0.3s ease;
                font-weight: 600 !important;
            }
            
            /* Navbar premium */
            .navbar {
                backdrop-filter: blur(10px);
                background: rgba(255, 255, 255, 0.15) !important;
                border-bottom: 1px solid rgba(255, 255, 255, 0.3);
                box-shadow: 0 4px 20px rgba(51, 105, 30, 0.15);
            }
            
            .navbar-custom .container-fluid {
                display: flex !important;
                justify-content: space-between !important;
                align-items: center !important;
            }
            
            .navbar-brand {
                font-weight: 800 !important;
                font-size: 1.3rem !important;
                letter-spacing: 0.5px !important;
                display: flex !important;
                align-items: center !important;
            }
            
            .navbar-nav {
                margin-left: auto !important;
            }
            
            /* Labels con estilo verde */
            label {
                color: #33691E;
                font-weight: 700;
                font-size: 0.8rem;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                margin-bottom: 8px;
            }
            
            /* Alertas modernas */
            .alert {
                border-radius: 16px !important;
                border: none !important;
                padding: 24px !important;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08) !important;
            }
            
            .alert-success {
                background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%) !important;
                border-left: 5px solid #7CB342 !important;
                color: #1B5E20 !important;
            }
            
            /* Hr decorativo */
            hr {
                border-top: 2px solid #C5E1A5 !important;
                opacity: 0.8;
                margin: 24px 0 !important;
            }
            
            /* Login container */
            .login-container {
                backdrop-filter: blur(10px);
                background: rgba(240, 250, 235, 0.45);
                border-radius: 20px;
                padding: 50px;
                box-shadow: 0 25px 70px rgba(51, 105, 30, 0.3);
                border: 2px solid rgba(139, 195, 74, 0.25);
            }
            
            /* Animación de rotación para el logo */
            @keyframes logoRotation {
                from { transform: rotateY(0deg); }
                to { transform: rotateY(360deg); }
            }
            
            .logo-rotation {
                animation: logoRotation 4s linear infinite;
                filter: drop-shadow(0 4px 10px rgba(139, 195, 74, 0.3));
            }
            
            .logo-rotation:hover {
                animation-duration: 1.5s;
            }
            
            /* Animación de pulso para botones en carga */
            @keyframes pulse-loading {
                0%, 100% { 
                    opacity: 0.7;
                    transform: scale(1);
                }
                50% { 
                    opacity: 0.9;
                    transform: scale(1.02);
                }
            }
            
            /* Animaciones generales */
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(30px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            .animated {
                animation: fadeIn 0.7s ease-out;
            }
            
            /* Scrollbar personalizado verde */
            ::-webkit-scrollbar {
                width: 12px;
            }
            
            ::-webkit-scrollbar-track {
                background: #F1F8E9;
            }
            
            ::-webkit-scrollbar-thumb {
                background: linear-gradient(135deg, #8BC34A 0%, #558B2F 100%);
                border-radius: 6px;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: linear-gradient(135deg, #7CB342 0%, #33691E 100%);
            }
            
            /* Panel de control header */
            .panel-header {
                background: linear-gradient(135deg, #8BC34A 0%, #7CB342 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            /* Logo en navbar */
            .navbar-logo {
                height: 40px;
                margin-right: 15px;
                filter: brightness(0) invert(1);
            }
            
            /* Footer de contactos */
            .contact-footer {
                position: fixed;
                bottom: 20px;
                left: 20px;
                background: rgba(240, 250, 235, 0.5);
                backdrop-filter: blur(10px);
                padding: 15px 20px;
                border-radius: 12px;
                border: 2px solid rgba(139, 195, 74, 0.3);
                box-shadow: 0 4px 20px rgba(51, 105, 30, 0.2);
                z-index: 1000;
                transition: all 0.3s ease;
            }
            
            .contact-footer:hover {
                background: rgba(240, 250, 235, 0.7);
                transform: translateY(-3px);
                box-shadow: 0 6px 25px rgba(51, 105, 30, 0.3);
            }
            
            .contact-footer a {
                color: #33691E;
                text-decoration: none;
                font-weight: 600;
                font-size: 0.9rem;
                transition: all 0.3s ease;
                display: inline-flex;
                align-items: center;
                margin: 0 10px;
            }
            
            .contact-footer a:hover {
                color: #7CB342;
                transform: translateX(3px);
            }
            
            .contact-footer a i {
                font-size: 1.2rem;
                margin-right: 6px;
            }
            
            /* Tarjetas de tareas */
            .task-card {
                background: rgba(240, 250, 235, 0.6);
                border: 2px solid #8BC34A;
                border-radius: 12px;
                padding: 15px;
                margin-bottom: 10px;
                transition: all 0.3s ease;
            }
            
            .task-pending {
                border-left: 5px solid #FFA726;
            }
            
            .task-processing {
                border-left: 5px solid #42A5F5;
                animation: pulse-loading 1s infinite;
            }
            
            .task-completed {
                border-left: 5px solid #66BB6A;
            }
            
            .task-error {
                border-left: 5px solid #EF5350;
            }
            
            .task-card:hover {
                transform: translateX(5px);
                box-shadow: 0 4px 15px rgba(51, 105, 30, 0.2);
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

# ==================== ESTADOS DEL CHAT GUÍA ====================
CHAT_STATES = {
    'inicio': {
        'mensaje': '¡Hola! 👋 Soy tu asistente virtual. Te guiaré paso a paso en el análisis de riesgo.',
        'accion': '📝 Comencemos ingresando tu nombre completo como responsable del análisis.',
        'icono': 'bi-chat-dots'
    },
    'esperando_nombre': {
        'mensaje': '✅ Perfecto! Ahora seleccionemos la ubicación geográfica.',
        'accion': '🌎 Selecciona el DEPARTAMENTO/REGIÓN donde realizarás el análisis.',
        'icono': 'bi-geo-alt'
    },
    'esperando_provincia': {
        'mensaje': '👍 Región seleccionada correctamente.',
        'accion': '📍 Ahora selecciona la PROVINCIA específica.',
        'icono': 'bi-pin-map'
    },
    'esperando_distrito': {
        'mensaje': '✅ Provincia registrada.',
        'accion': '🏘️ Finalmente, selecciona el DISTRITO.',
        'icono': 'bi-buildings'
    },
    'ubicacion_completa': {
        'mensaje': '🎯 ¡Ubicación completa!',
        'accion': '⚠️ Ahora selecciona el TIPO DE PELIGRO que deseas analizar (Inundación Pluvial disponible).',
        'icono': 'bi-exclamation-triangle'
    },
    'tipo_seleccionado': {
        'mensaje': '✅ Tipo de peligro seleccionado.',
        'accion': '🚀 Todo listo! Presiona "GENERAR MAPA" para iniciar el análisis.',
        'icono': 'bi-lightning'
    },
    'generando_peligro': {
        'mensaje': '⚙️ Generando Mapa de Peligro...',
        'accion': '🔄 Proceso interno:\n• Cargando capas geográficas\n• Procesando modelo de peligro\n• Aplicando algoritmos de zonificación\n• Renderizando mapa final',
        'icono': 'bi-gear-fill spin'
    },
    'peligro_completado': {
        'mensaje': '✅ ¡Mapa de Peligro generado exitosamente!',
        'accion': '💾 Descarga tu mapa. Luego podrás generar el mapa de Elementos Expuestos.',
        'icono': 'bi-check-circle'
    },
    'peligro_descargado': {
        'mensaje': '📥 Mapa de Peligro descargado.',
        'accion': '🗺️ Opcional: Genera el mapa de ELEMENTOS EXPUESTOS para análisis completo.',
        'icono': 'bi-layers'
    },
    'generando_elementos': {
        'mensaje': '⚙️ Generando Mapa de Elementos Expuestos...',
        'accion': '🔄 Proceso interno:\n• Identificando infraestructura crítica\n• Geolocalizando centros poblados\n• Mapeando instituciones educativas\n• Trazando redes viales\n• Integrando capas temáticas',
        'icono': 'bi-gear-fill spin'
    },
    'elementos_completado': {
        'mensaje': '✅ ¡Mapa de Elementos Expuestos generado!',
        'accion': '💾 Descarga tu mapa. Luego podrás iniciar un nuevo análisis.',
        'icono': 'bi-check-circle'
    },
    'todo_completado': {
        'mensaje': '🎉 ¡Análisis completo finalizado!',
        'accion': '🔄 Usa "NUEVO ANÁLISIS" para comenzar otra evaluación de riesgo.',
        'icono': 'bi-trophy'
    }
}


def leer_sql(ruta):
    if not os.path.exists(ruta):
        print(f"⚠️ ADVERTENCIA: La ruta del archivo SQL no existe: '{ruta}'")
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
    # Footer de contactos
    html.Div([
        html.A([
            html.I(className="bi bi-globe2"),
            "escuelar.org"
        ], href="https://escuelar.org/", target="_blank"),
        html.Span(" | ", style={'color': '#7CB342', 'fontWeight': '700'}),
        html.A([
            html.I(className="bi bi-linkedin"),
            "LinkedIn"
        ], href="https://www.linkedin.com/company/escuelar/about/", target="_blank")
    ], className='contact-footer'),
    
    dbc.Row(
        dbc.Col(
            html.Div([
                html.Div([
                    html.Img(
                        src='/assets/LOGO.png',
                        className='logo-rotation',
                        style={
                            'width': '150px',
                            'height': 'auto',
                            'marginBottom': '20px'
                        }
                    )
                ], className='text-center'),
                
                html.H2("PLATAFORMA DE AUTOMATIZACIÓN MAPAS TEMÁTICOS", 
                       className="text-center mb-4",
                       style={
                           'color': "#FEFFFE", 
                           'fontWeight': '800',
                           'fontSize': '1.8rem',
                           'letterSpacing': '0.5px'
                       }),
                
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Label([
                                html.I(className="bi bi-person-fill me-2"),
                                "Usuario"
                            ], style={'color': '#33691E', 'fontWeight': '700'}),
                            dbc.Input(
                                id='username-input',
                                placeholder='Ingrese su usuario',
                                type='text',
                                className='mb-3'
                            )
                        ]),
                        
                        html.Div([
                            html.Label([
                                html.I(className="bi bi-lock-fill me-2"),
                                "Contraseña"
                            ], style={'color': '#33691E', 'fontWeight': '700'}),
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
                        style={'padding': '14px', 'fontSize': '1.1rem'}),
                        
                        html.Div(id='login-alert', className='mt-3')
                    ])
                ], className='shadow-lg border-0 login-container')
            ], 
            className='animated',
            style={
                'marginTop': '80px',
                'maxWidth': '480px',
                'margin': '80px auto'
            }),
            width=12
        ),
        justify='center'
    )
], fluid=True)

# ==================== LAYOUT DEL DASHBOARD ====================
dashboard_layout = dbc.Container([
    dcc.Download(id="download-map-image"),
    dcc.Interval(id='task-refresh-interval', interval=2000),
    dcc.Store(id='downloaded-tasks', data=[]),
    
    # Footer de contactos
    html.Div([
        html.A([
            html.I(className="bi bi-globe2"),
            "escuelar.org"
        ], href="https://escuelar.org/", target="_blank"),
        html.Span(" | ", style={'color': '#7CB342', 'fontWeight': '700'}),
        html.A([
            html.I(className="bi bi-linkedin"),
            "LinkedIn"
        ], href="https://www.linkedin.com/company/escuelar/about/", target="_blank")
    ], className='contact-footer'),
    
    # Navbar premium
    dbc.NavbarSimple(
        children=[
            dbc.NavItem(
                html.Span(
                    id='user-display-nav',
                    className='navbar-text me-3',
                    style={'color': 'white', 'fontWeight': '600', 'fontSize': '1rem'}
                )
            ),
            dbc.NavItem(
                dbc.Button([
                    html.I(className="bi bi-box-arrow-right me-2"),
                    "Cerrar Sesión"
                ], 
                id='logout-button',
                color='danger',
                size='sm',
                className='btn-danger')
            )
        ],
        brand=[
            html.Img(
                src='/assets/LOGO.png',
                className='navbar-logo'
            ),
            "Sistema de Mapas Geográficos"
        ],
        color="primary",
        dark=True,
        className='mb-4 shadow-sm navbar-custom',
        style={'fontSize': '1.2rem'},
        fluid=True
    ),
    
    dbc.Row([
        # Panel de control izquierdo
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="bi bi-sliders me-2", style={'fontSize': '1.8rem', 'color': "#EEF5E7"}),
                        html.H4("Panel de Control", className='panel-header', style={'display': 'inline', 'fontWeight': '900','color': "#EEF5E7"})
                    ], className='mb-4'),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-person-badge me-2"),
                                    "Nombre de Usuario"
                                ]),
                                dbc.Input(
                                    id='user-name-input',
                                    type='text',
                                    placeholder='Ej: Daniel Porras Núñez',
                                    className='mb-4'
                                )
                            ]),
                            
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-map me-2"),
                                    "Tipo de Mapa"
                                ]),
                                dcc.Dropdown(
                                    id='map-type',
                                    options=[
                                        {'label': '🗺️ Mapa de ubicación Geográfica', 'value': 'geografico'},
                                        {'label': '🌄 Mapa de geomorfología', 'value': 'geomorfologia'},
                                        {'label': '🌡️ Mapa de clasificación climática', 'value': 'climatica'},
                                        {'label': '📐 Mapa de pendientes', 'value': 'pendientes'},
                                        {'label': '🛣️ Mapa de vías', 'value': 'vias'},
                                        {'label': '🏘️ Mapa de centros poblados', 'value': 'centros'},
                                        {'label': '🪨 Mapa de geología', 'value': 'geologia'}
                                    ],
                                    placeholder='Seleccione el tipo de mapa',
                                    className='mb-4'
                                )
                            ])
                        ], md=12)
                    ]),
                    
                    html.Hr(style={'borderTop': '2px dashed #C5E1A5', 'margin': '20px 0'}),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-geo-alt me-2"),
                                    "Departamento"
                                ]),
                                dcc.Dropdown(
                                    id='departamento-dropdown',
                                    options=LISTA_DEPARTAMENTOS,
                                    placeholder='Seleccione departamento',
                                    className='mb-4'
                                )
                            ]),
                            
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-building me-2"),
                                    "Provincia"
                                ]),
                                dcc.Dropdown(
                                    id='provincia-dropdown',
                                    placeholder='Primero elija departamento',
                                    disabled=True,
                                    className='mb-4'
                                )
                            ]),
                            
                            html.Div([
                                html.Label([
                                    html.I(className="bi bi-house me-2"),
                                    "Distrito"
                                ]),
                                dcc.Dropdown(
                                    id='distrito-dropdown',
                                    placeholder='Primero elija provincia',
                                    disabled=True,
                                    className='mb-4'
                                )
                            ]),
                            
                            dbc.Button([
                                html.I(className="bi bi-rocket-takeoff me-2"),
                                'Generar Mapa'
                            ],
                            id='generate-map-button',
                            color='success',
                            size='lg',
                            className='w-100 mb-3',
                            disabled=True)
                        ], md=12)
                    ])
                ])
            ], className='shadow-lg border-0 animated')
        ], md=5, lg=4),
        
        # Panel de resultados derecho
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5([
                        html.I(className="bi bi-clock-history me-2", style={'color': '#7CB342'}),
                        "Mis Peticiones"
                    ], className='mb-3', style={'color': '#33691E', 'fontWeight': '800'}),
                    html.Div(
                        id='tasks-list',
                        children=[
                            dbc.Alert([
                                html.I(className="bi bi-info-circle me-2"),
                                "No tienes peticiones activas"
                            ], color="light", className='mb-0')
                        ],
                        style={'maxHeight': '500px', 'overflowY': 'auto'}
                    )
                ])
            ], className="h-100 shadow-lg border-0 animated")
        ], md=7, lg=8)
    ], className='g-4')
], fluid=True, className="p-4")

# ==================== CHAT FLOTANTE ====================
html.Div([
    # Botón minimizar/expandir
    html.Div([
        dbc.Button(
            html.I(id='chat-toggle-icon', className="bi bi-chevron-down"),
            id='chat-toggle',
            className='chat-toggle-btn',
            n_clicks=0
        )
    ], className='chat-toggle-container'),
    
    # Contenedor del chat
    html.Div([
        # Header del chat
        html.Div([
            html.Div([
                html.I(className="bi bi-robot me-2"),
                html.Strong("Asistente Virtual")
            ], className='chat-header-title'),
            html.Div([
                html.I(id='chat-status-icon', className="bi bi-chat-dots"),
            ], className='chat-status')
        ], className='chat-header'),
        
        # Cuerpo del chat con mensajes
        html.Div([
            html.Div([
                html.I(id='chat-main-icon', className="bi bi-chat-dots chat-icon"),
                html.Div([
                    html.P(id='chat-mensaje', className='chat-message'),
                    html.Div([
                        html.I(className="bi bi-arrow-right-circle me-2"),
                        html.Span(id='chat-accion', className='chat-action')
                    ], className='chat-action-box')
                ], className='chat-text')
            ], className='chat-content')
        ], className='chat-body', id='chat-body')
    ], id='chat-container', className='chat-assistant')
], className='chat-wrapper')




# ==================== LAYOUT PRINCIPAL ====================
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='session-store', storage_type='session'),
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
            "Por favor, complete todos los campos"
        ], color="warning")
    if username in VALID_USERS and VALID_USERS[username] == password: 
        return {'logged_in': True, 'username': username}, None
    return {'logged_in': False}, dbc.Alert([
        html.I(className="bi bi-x-circle me-2"),
        "Usuario o contraseña incorrectos"
    ], color="danger")

@app.callback(Output('session-store', 'data', allow_duplicate=True), Input('logout-button', 'n_clicks'), prevent_initial_call=True)
def logout_user(n_clicks): 
    return {'logged_in': False}

@app.callback(Output('user-display-nav', 'children'), Input('session-store', 'data'))
def display_user_nav(session_data): 
    return [
        html.I(className="bi bi-person-circle me-2"),
        session_data.get('username', 'Usuario')
    ] if session_data and session_data.get('logged_in') else None

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
    [Input(c, 'value') for c in ['user-name-input', 'map-type', 'departamento-dropdown', 'provincia-dropdown', 'distrito-dropdown']]
)
def enable_button(*values): 
    return not all(values)

# CALLBACK PARA CREAR NUEVA PETICIÓN
@app.callback(
    Output('generate-map-button', 'n_clicks'),
    Input('generate-map-button', 'n_clicks'),
    [State('user-name-input', 'value'),
     State('map-type', 'value'),
     State('departamento-dropdown', 'value'),
     State('provincia-dropdown', 'value'),
     State('distrito-dropdown', 'value')],
    prevent_initial_call=True
)
def add_map_request(n_clicks, user_name, map_type, departamento, provincia, distrito):
    task_id = map_queue.add_task(user_name, map_type, departamento, provincia, distrito)
    
    # Procesar en thread
    thread = Thread(target=map_queue.process_task, args=(task_id,), daemon=True)
    thread.start()
    
    print(f"✅ Petición agregada a la cola: {task_id} para usuario: {user_name}")
    return 0

# CALLBACK PARA ACTUALIZAR LISTA DE PETICIONES (FILTRADO POR USUARIO)
@app.callback(
    Output('tasks-list', 'children'),
    [Input('task-refresh-interval', 'n_intervals'),
     Input('user-name-input', 'value')]
)
def update_tasks_list(n_intervals, current_user_name):
    # Si no hay nombre de usuario ingresado, mostrar mensaje
    if not current_user_name:
        return dbc.Alert([
            html.I(className="bi bi-info-circle me-2"),
            "Ingresa tu nombre de usuario para ver tus peticiones"
        ], color="light", className='mb-0')
    
    # Filtrar tareas del usuario actual (por user_name_input)
    user_tasks = {
        task_id: task 
        for task_id, task in map_queue.tasks.items() 
        if task.get('user_name') == current_user_name
    }
    
    if not user_tasks:
        return dbc.Alert([
            html.I(className="bi bi-info-circle me-2"),
            "No tienes peticiones activas"
        ], color="light", className='mb-0')
    
    task_cards = []
    for task_id, task in sorted(user_tasks.items(), key=lambda x: x[1]['created_at'], reverse=True)[:10]:
        status = task['status']
        status_icons = {'pending': '⏳', 'processing': '⚙️', 'completed': '✅', 'error': '❌'}
        status_text = {'pending': 'Pendiente', 'processing': 'Procesando', 'completed': 'Completado', 'error': 'Error'}
        
        card_class = f"task-card task-{status}"
        
        content_items = [
            html.Div([
                html.Span(f"{status_icons[status]} {task_id}", style={'fontWeight': '700', 'color': '#33691E', 'fontSize': '0.95rem'}),
                html.Span(status_text[status], style={'float': 'right', 'fontWeight': '700', 'color': '#7CB342', 'fontSize': '0.85rem'})
            ], className='mb-2'),
            html.Div(f"📍 {task['distrito']} | 🗺️ {task['map_type']}", style={'fontSize': '0.9rem', 'color': '#558B2F', 'marginBottom': '8px'}),
        ]
        
        if status == 'completed':
            content_items.append(html.Div(f"💾 Tamaño: {task['file_size_mb']:.2f} MB", style={'fontSize': '0.85rem', 'color': '#558B2F', 'marginBottom': '8px'}))
            content_items.append(
                dbc.Button([
                    html.I(className="bi bi-download me-1"),
                    'Descargar'
                ],
                id={'type': 'download-btn', 'index': task_id},
                color='info',
                size='sm',
                className='w-100 btn-info')
            )
        elif status == 'error':
            error_msg = task['error'][:60] + '...' if len(task['error']) > 60 else task['error']
            content_items.append(html.Div(f"⚠️ {error_msg}", style={'fontSize': '0.85rem', 'color': '#C62828', 'marginTop': '5px'}))
        
        task_cards.append(html.Div(content_items, className=card_class))
    
    return task_cards if task_cards else dbc.Alert([
        html.I(className="bi bi-info-circle me-2"),
        "No tienes peticiones"
    ], color="light", className='mb-0')

# CALLBACK PARA DESCARGAR MAPA (SIN DUPLICADOS)
@app.callback(
    Output('download-map-image', 'data'),
    Output('downloaded-tasks', 'data'),
    [Input({'type': 'download-btn', 'index': ALL}, 'n_clicks')],
    [State({'type': 'download-btn', 'index': ALL}, 'id'),
     State('downloaded-tasks', 'data')],
    prevent_initial_call=True
)
def download_map(n_clicks_list, ids, downloaded_tasks):
    if not ctx.triggered or not n_clicks_list:
        return None, downloaded_tasks
    
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not triggered_id:
        return None, downloaded_tasks
    
    import json
    task_id = json.loads(triggered_id).get('index')
    
    # Evitar descargas duplicadas
    if not downloaded_tasks:
        downloaded_tasks = []
    
    if task_id in downloaded_tasks:
        print(f"⚠️ Descarga duplicada evitada: {task_id}")
        return None, downloaded_tasks
    
    if not task_id or task_id not in map_queue.tasks:
        return None, downloaded_tasks
    
    filepath = map_queue.tasks[task_id].get('filepath')
    
    if filepath and os.path.exists(filepath):
        print(f"📥 Descargando ÚNICA VEZ [{task_id}]: {os.path.basename(filepath)}")
        downloaded_tasks.append(task_id)
        return dcc.send_file(filepath), downloaded_tasks
    
    return None, downloaded_tasks

if __name__ == '__main__':
    try:
        import geopandas, contextily, matplotlib_scalebar, rasterio
        print("✅ Librerías geoespaciales detectadas correctamente")
    except ImportError as e:
        print(f"\n{'='*80}")
        print(" FALTAN LIBRERÍAS GEOESPACIALES ".center(80, "!"))
        print(f"{'='*80}\n")
    
    print(f"\n{'='*80}")
    print("🗺️ VERIFICANDO ARCHIVO DE PENDIENTES".center(80))
    print(f"{'='*80}")
    
    ruta_pendientes = "/workspaces/AUTOMATIZACION_DASH/PRUEBA/DATA/PENDIENTES/pendientes.tif"
    if os.path.exists(ruta_pendientes):
        print(f"✅ Archivo encontrado: {os.path.getsize(ruta_pendientes) / (1024*1024):.2f} MB")
    else:
        print("⚠️ ADVERTENCIA: Archivo de pendientes no encontrado")
    print(f"{'='*80}\n")
    
    print(f"\n{'='*80}")
    print("🪨 VERIFICANDO ARCHIVOS DE GEOLOGÍA".center(80))
    print(f"{'='*80}")
    
    ruta_geologia_base = "/workspaces/AUTOMATIZACION_DASH/PRUEBA/DATA/GEOLOGIA"
    if os.path.exists(ruta_geologia_base):
        departamentos_geo = [d for d in os.listdir(ruta_geologia_base) if os.path.isdir(os.path.join(ruta_geologia_base, d))]
        print(f"✅ Carpeta de geología encontrada")
        print(f"   📂 Departamentos con datos geológicos: {len(departamentos_geo)}")
        if departamentos_geo:
            print(f"   📋 Primeros 5: {', '.join(sorted(departamentos_geo)[:5])}")
    else:
        print("⚠️ ADVERTENCIA: Carpeta de geología no encontrada")
    print(f"{'='*80}\n")
    
    print(f"\n{'='*80}")
    print("🚀 INICIANDO SERVIDOR DASH - SISTEMA CON FILTRADO POR USUARIO".center(80))
    print(f"{'='*80}")
    print("✅ Filtrado por usuario implementado")
    print("✅ Sistema anti-descargas duplicadas")
    print("✅ Cada usuario solo ve sus propias peticiones")
    print("🔌 Puerto: 8051")
    print("🌐 URL: http://127.0.0.1:8051")
    print(f"{'='*80}\n")
    
    app.run(debug=True, port=8051, threaded=True)