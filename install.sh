#!/bin/bash
# Instalador de Label Printer HT300 para Ubuntu
# Instala dependencias, icono y acceso directo

set -e

APP_NAME="label-printer"
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
ICON_NAME="label-printer"
DESKTOP_FILE="$HOME/.local/share/applications/${APP_NAME}.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

echo "╔══════════════════════════════════════════════╗"
echo "║   Label Printer HT300 - Instalador           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Directorio: $INSTALL_DIR"
echo ""

# ── 1. Dependencias del sistema ──
echo "[1/4] Instalando dependencias del sistema..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    cups

# ── 2. Instalar icono ──
echo ""
echo "[2/4] Instalando icono..."
mkdir -p "$ICON_DIR"
cp "$INSTALL_DIR/assets/label-printer.svg" "$ICON_DIR/${ICON_NAME}.svg"
echo "  Icono: $ICON_DIR/${ICON_NAME}.svg"

# Actualizar cache de iconos (silencioso)
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# ── 3. Crear acceso directo (.desktop) ──
echo ""
echo "[3/4] Creando acceso directo..."
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Name=Label Printer
GenericName=Impresora de Etiquetas
Comment=Diseña e imprime etiquetas TSPL para HT300 (HPRT)
Exec=${INSTALL_DIR}/run.sh
Icon=${ICON_NAME}
Terminal=false
Type=Application
Categories=Utility;Printing;Office;
Keywords=label;etiqueta;barcode;qr;printer;impresora;tspl;ht300;
StartupNotify=true
DESKTOP

chmod +x "$DESKTOP_FILE"
echo "  Acceso directo: $DESKTOP_FILE"

# Actualizar base de datos de desktop (silencioso)
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# ── 4. Verificar impresora CUPS ──
echo ""
echo "[4/4] Verificando impresora..."
echo ""

if lpstat -p HT300 2>/dev/null | grep -q "printer"; then
    echo "  ✓ Impresora 'HT300' configurada en CUPS"
    lpstat -v HT300 2>/dev/null | sed 's/^/    /'
else
    echo "  ✗ Impresora 'HT300' NO encontrada en CUPS"
    echo ""
    echo "  Para configurarla por USB:"
    echo "    sudo lpadmin -p HT300 -v \"usb://HPRT/HT300\" -m raw -E"
    echo ""
    echo "  Para configurarla por red (puerto 9100):"
    echo "    sudo lpadmin -p HT300 -v \"socket://IP_IMPRESORA:9100\" -m raw -E"
    echo ""
    echo "  O configúrala desde la app (icono de engranaje)"
fi

# Verificar permisos run.sh
chmod +x "$INSTALL_DIR/run.sh"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Instalación completada                     ║"
echo "╠══════════════════════════════════════════════╣"
echo "║                                              ║"
echo "║   Abrir desde:                               ║"
echo "║   • Menú de aplicaciones > Label Printer      ║"
echo "║   • Terminal: ./run.sh                        ║"
echo "║   • Web alternativa: python3 ht300_web.py     ║"
echo "║                                              ║"
echo "╚══════════════════════════════════════════════╝"
