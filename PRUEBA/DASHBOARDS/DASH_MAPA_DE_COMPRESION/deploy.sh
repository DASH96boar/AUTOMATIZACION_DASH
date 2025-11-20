#!/bin/bash

# ==================== SCRIPT DE DESPLIEGUE AUTOMÁTICO ====================
echo "=================================="
echo "🚀 DESPLIEGUE DASHBOARD RIESGO"
echo "=================================="

# ==================== VARIABLES ====================
PROJECT_DIR="/var/www/dashboard-riesgo"
VENV_DIR="$PROJECT_DIR/venv"
DOMAIN="tu-dominio.com"  # ⚠️ CAMBIAR POR TU DOMINIO

# ==================== COLORES ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ==================== FUNCIONES ====================
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# ==================== VERIFICAR ROOT ====================
if [[ $EUID -ne 0 ]]; then
   print_error "Este script debe ejecutarse como root (sudo)"
   exit 1
fi

print_success "Permisos de root confirmados"

# ==================== ACTUALIZAR SISTEMA ====================
print_info "Actualizando sistema..."
apt update && apt upgrade -y
print_success "Sistema actualizado"

# ==================== INSTALAR DEPENDENCIAS ====================
print_info "Instalando dependencias del sistema..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    git \
    build-essential \
    libgdal-dev \
    gdal-bin \
    python3-gdal
print_success "Dependencias instaladas"

# ==================== CREAR DIRECTORIOS ====================
print_info "Creando estructura de directorios..."
mkdir -p $PROJECT_DIR
mkdir -p $PROJECT_DIR/logs
mkdir -p $PROJECT_DIR/assets
mkdir -p $PROJECT_DIR/DATA
print_success "Directorios creados"

# ==================== CREAR ENTORNO VIRTUAL ====================
print_info "Creando entorno virtual Python..."
cd $PROJECT_DIR
python3 -m venv venv
source venv/bin/activate
print_success "Entorno virtual creado"

# ==================== INSTALAR DEPENDENCIAS PYTHON ====================
print_info "Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Dependencias Python instaladas"

# ==================== CONFIGURAR PERMISOS ====================
print_info "Configurando permisos..."
chown -R www-data:www-data $PROJECT_DIR
chmod -R 755 $PROJECT_DIR
chmod -R 777 $PROJECT_DIR/logs
print_success "Permisos configurados"

# ==================== CONFIGURAR NGINX ====================
print_info "Configurando Nginx..."

cat > /etc/nginx/sites-available/dashboard-riesgo <<EOF
upstream dashboard_app {
    server 127.0.0.1:8052 fail_timeout=0;
}

server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    client_max_body_size 100M;
    
    access_log /var/log/nginx/dashboard-access.log;
    error_log /var/log/nginx/dashboard-error.log;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript;

    location /assets/ {
        alias $PROJECT_DIR/assets/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://dashboard_app;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/dashboard-riesgo /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t
if [ $? -eq 0 ]; then
    print_success "Configuración de Nginx válida"
else
    print_error "Error en configuración de Nginx"
    exit 1
fi

systemctl restart nginx
print_success "Nginx configurado y reiniciado"

# ==================== CONFIGURAR SERVICIO SYSTEMD ====================
print_info "Configurando servicio Systemd..."

cat > /etc/systemd/system/dashboard.service <<EOF
[Unit]
Description=Dashboard Comprensión de Riesgo
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/gunicorn app_peligro_refactored:app.server -c gunicorn_config.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable dashboard
systemctl start dashboard

if systemctl is-active --quiet dashboard; then
    print_success "Servicio dashboard iniciado correctamente"
else
    print_error "Error al iniciar servicio dashboard"
    systemctl status dashboard
    exit 1
fi

# ==================== CONFIGURAR SSL (OPCIONAL) ====================
read -p "¿Deseas configurar SSL con Let's Encrypt? (y/n): " setup_ssl

if [[ $setup_ssl == "y" || $setup_ssl == "Y" ]]; then
    print_info "Instalando Certbot..."
    apt install -y certbot python3-certbot-nginx
    
    print_info "Obteniendo certificado SSL..."
    certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
    
    if [ $? -eq 0 ]; then
        print_success "SSL configurado correctamente"
    else
        print_warning "Error al configurar SSL, continúa con HTTP"
    fi
fi

# ==================== CONFIGURAR FIREWALL (OPCIONAL) ====================
read -p "¿Deseas configurar firewall UFW? (y/n): " setup_firewall

if [[ $setup_firewall == "y" || $setup_firewall == "Y" ]]; then
    print_info "Configurando firewall..."
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    echo "y" | ufw enable
    print_success "Firewall configurado"
fi

# ==================== RESUMEN ====================
echo ""
echo "=================================="
echo "✅ DESPLIEGUE COMPLETADO"
echo "=================================="
echo ""
echo "📊 Información del servicio:"
echo "   • Directorio: $PROJECT_DIR"
echo "   • Puerto: 8052"
echo "   • Dominio: http://$DOMAIN"
echo "   • Usuario: www-data"
echo ""
echo "🔍 Comandos útiles:"
echo "   • Ver status:    sudo systemctl status dashboard"
echo "   • Ver logs:      sudo journalctl -u dashboard -f"
echo "   • Reiniciar:     sudo systemctl restart dashboard"
echo "   • Detener:       sudo systemctl stop dashboard"
echo ""
echo "📝 Logs:"
echo "   • App:    $PROJECT_DIR/logs/error.log"
echo "   • Nginx:  /var/log/nginx/dashboard-error.log"
echo ""
echo "🌐 Accede a tu aplicación en: http://$DOMAIN"
echo ""

print_info "Estado de servicios:"
systemctl status nginx --no-pager -l
systemctl status dashboard --no-pager -l

print_success "¡Despliegue completado exitosamente!"