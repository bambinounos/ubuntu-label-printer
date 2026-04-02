#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Label Printer HT300 - Instalador del sistema
#  Copia la aplicación a /opt e integra con el escritorio
# ═══════════════════════════════════════════════════════════

set -e

APP_ID="com.antigravity.labelprinter"
APP_NAME="label-printer"
INSTALL_DIR="/opt/label-printer"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="0.2.0"

DESKTOP_FILE="/usr/share/applications/${APP_ID}.desktop"
ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
METAINFO_DIR="/usr/share/metainfo"
BIN_LINK="/usr/local/bin/label-printer"

echo "╔══════════════════════════════════════════════════╗"
echo "║   Label Printer HT300 — Instalador v${VERSION}       ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║   Se instalará en: /opt/label-printer            ║"
echo "║   Se necesitan permisos de administrador (sudo)  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Verificar sudo
if ! sudo -v; then
    echo "Error: Se necesitan permisos de administrador."
    exit 1
fi

# ── 1. Dependencias ──
echo "[1/6] Instalando dependencias del sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    cups \
    > /dev/null
echo "  ✓ Dependencias instaladas"

# ── 2. Copiar aplicación a /opt ──
echo ""
echo "[2/6] Instalando aplicación en ${INSTALL_DIR}..."

# Si existe una instalación previa, respaldar config
if [ -d "$INSTALL_DIR" ]; then
    echo "  Actualizando instalación existente..."
    # Preservar configuración del usuario si existe
    if [ -f "$INSTALL_DIR/.install_source" ]; then
        echo "  (instalación previa detectada)"
    fi
    sudo rm -rf "$INSTALL_DIR"
fi

sudo mkdir -p "$INSTALL_DIR"
sudo cp -r "$SOURCE_DIR/src" "$INSTALL_DIR/src"
sudo cp -r "$SOURCE_DIR/assets" "$INSTALL_DIR/assets"
sudo cp "$SOURCE_DIR/ht300_web.py" "$INSTALL_DIR/ht300_web.py" 2>/dev/null || true
sudo cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"
sudo cp "$SOURCE_DIR/setup.py" "$INSTALL_DIR/setup.py"

# Guardar info de instalación
sudo bash -c "cat > '$INSTALL_DIR/.install_info' << INFO
version=${VERSION}
installed=$(date -Is)
source=${SOURCE_DIR}
repo=https://github.com/bambinounos/ubuntu-label-printer
INFO"

# Script de ejecución
sudo bash -c "cat > '$INSTALL_DIR/run.sh' << 'RUNNER'
#!/bin/bash
cd /opt/label-printer
exec python3 -m src.main \"\$@\"
RUNNER"
sudo chmod +x "$INSTALL_DIR/run.sh"

echo "  ✓ Aplicación copiada a ${INSTALL_DIR}"

# ── 3. Instalar icono ──
echo ""
echo "[3/6] Instalando icono..."
sudo mkdir -p "$ICON_DIR"
sudo cp "$SOURCE_DIR/assets/label-printer.svg" "$ICON_DIR/${APP_ID}.svg"
sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
echo "  ✓ Icono instalado"

# ── 4. Crear acceso directo (.desktop) ──
echo ""
echo "[4/6] Registrando en el menú de aplicaciones..."

sudo bash -c "cat > '${DESKTOP_FILE}' << DESKTOP
[Desktop Entry]
Name=Label Printer
Name[es]=Impresora de Etiquetas
GenericName=Label Printer
GenericName[es]=Impresora de Etiquetas
Comment=Design and print TSPL labels for HT300 (HPRT)
Comment[es]=Diseña e imprime etiquetas TSPL para HT300 (HPRT)
Exec=/opt/label-printer/run.sh
Icon=${APP_ID}
Terminal=false
Type=Application
Categories=Utility;Printing;Office;
Keywords=label;etiqueta;barcode;qr;printer;impresora;tspl;ht300;hprt;
StartupNotify=true
X-GNOME-UsesNotifications=false
DESKTOP"

sudo chmod 644 "$DESKTOP_FILE"
sudo update-desktop-database /usr/share/applications 2>/dev/null || true
echo "  ✓ Acceso directo creado"

# ── 5. AppStream metadata (para GNOME Software / Ubuntu Software) ──
echo ""
echo "[5/6] Registrando en el centro de software..."
sudo mkdir -p "$METAINFO_DIR"
sudo cp "$SOURCE_DIR/assets/${APP_ID}.metainfo.xml" "$METAINFO_DIR/${APP_ID}.metainfo.xml"
sudo chmod 644 "$METAINFO_DIR/${APP_ID}.metainfo.xml"
# Revalidar appstream cache
sudo appstreamcli refresh-cache 2>/dev/null || true
echo "  ✓ Metadata AppStream instalada"

# ── 6. Crear enlace simbólico en PATH ──
echo ""
echo "[6/6] Creando comando 'label-printer'..."
sudo ln -sf "$INSTALL_DIR/run.sh" "$BIN_LINK"
echo "  ✓ Puedes ejecutar: label-printer"

# ── Verificar impresora ──
echo ""
echo "─── Estado de impresora ───"
if lpstat -p HT300 2>/dev/null | grep -q "printer"; then
    echo "  ✓ Impresora 'HT300' configurada en CUPS"
    lpstat -v HT300 2>/dev/null | sed 's/^/    /'
else
    echo "  ✗ Impresora 'HT300' no encontrada en CUPS"
    echo "    Configúrala desde la app (icono de engranaje) o con:"
    echo "    USB:  sudo lpadmin -p HT300 -v \"usb://HPRT/HT300\" -m raw -E"
    echo "    Red:  sudo lpadmin -p HT300 -v \"socket://IP:9100\" -m raw -E"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   ✓ Instalación completada                       ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║                                                  ║"
echo "║   Abrir:                                         ║"
echo "║   • Buscar 'Label Printer' en Actividades        ║"
echo "║   • Terminal: label-printer                       ║"
echo "║                                                  ║"
echo "║   Actualizar:  ./update.sh                       ║"
echo "║   Desinstalar: sudo ./uninstall.sh               ║"
echo "║   (o desde Ubuntu Software / GNOME Software)     ║"
echo "║                                                  ║"
echo "╚══════════════════════════════════════════════════╝"
