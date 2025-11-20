# ==================== CONFIGURACIÓN GUNICORN ====================
import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
threads = 2

timeout = 600
graceful_timeout = 120
keepalive = 5

bind = '127.0.0.1:8052'
backlog = 2048

accesslog = '/var/www/dashboard-riesgo/logs/access.log'
errorlog = '/var/www/dashboard-riesgo/logs/error.log'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

daemon = False
pidfile = '/var/www/dashboard-riesgo/logs/gunicorn.pid'
user = 'www-data'
group = 'www-data'
umask = 0o007

worker_tmp_dir = '/dev/shm'
max_requests = 1000
max_requests_jitter = 50
preload_app = True

def on_starting(server):
    print("=" * 80)
    print("🚀 GUNICORN INICIANDO".center(80))
    print("=" * 80)
    print(f"Workers: {workers}")
    print(f"Timeout: {timeout}s")
    print(f"Bind: {bind}")
    print("=" * 80)

def worker_exit(server, worker):
    print(f"⚠️  Worker {worker.pid} terminado")

def on_reload(server):
    print("🔄 Recargando aplicación...")

def post_worker_init(worker):
    print(f"✅ Worker {worker.pid} iniciado correctamente")