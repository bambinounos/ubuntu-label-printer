#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Label Printer HT300 - Desinstalador del sistema
#  Elimina la aplicación de /opt y todas las integraciones
# ═══════════════════════════════════════════════════════════

APP_ID="com.antigravity.labelprinter"
INSTALL_DIR="/opt/label-printer"
DESKTOP_FILE="/usr/share/applications/${APP_ID}.desktop"
ICON_FILE="/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
METAINFO_FILE="/usr/share/metainfo/${APP_ID}.metainfo.xml"
BIN_LINK="/usr/local/bin/label-printer"
USER_CONFIG="$HOME/.config/label-printer"

echo "╔══════════════════════════════════════════════════╗"
echo "║   Label Printer HT300 — Desinstalador            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Verificar instalación
if [ ! -d "$INSTALL_DIR" ] && [ ! -f "$DESKTOP_FILE" ]; then
    echo "Label Printer no parece estar instalado."
    exit 0
fi

# Mostrar qué se va a eliminar
echo "Se eliminará:"
[ -d "$INSTALL_DIR" ]    && echo "  • Aplicación:  $INSTALL_DIR"
[ -f "$DESKTOP_FILE" ]   && echo "  • Acceso:      $DESKTOP_FILE"
[ -f "$ICON_FILE" ]      && echo "  • Icono:       $ICON_FILE"
[ -f "$METAINFO_FILE" ]  && echo "  • Metadata:    $METAINFO_FILE"
[ -L "$BIN_LINK" ]       && echo "  • Comando:     $BIN_LINK"
echo ""

read -p "¿Continuar con la desinstalación? (s/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Cancelado."
    exit 0
fi

echo ""

# Necesita sudo para /opt y /usr/share
if ! sudo -v; then
    echo "Error: Se necesitan permisos de administrador."
    exit 1
fi

# ── Eliminar componentes ──
echo "Desinstalando..."

if [ -d "$INSTALL_DIR" ]; then
    sudo rm -rf "$INSTALL_DIR"
    echo "  ✓ Aplicación eliminada"
fi

if [ -f "$DESKTOP_FILE" ]; then
    sudo rm -f "$DESKTOP_FILE"
    sudo update-desktop-database /usr/share/applications 2>/dev/null || true
    echo "  ✓ Acceso directo eliminado"
fi

if [ -f "$ICON_FILE" ]; then
    sudo rm -f "$ICON_FILE"
    sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    echo "  ✓ Icono eliminado"
fi

if [ -f "$METAINFO_FILE" ]; then
    sudo rm -f "$METAINFO_FILE"
    sudo appstreamcli refresh-cache 2>/dev/null || true
    echo "  ✓ Metadata AppStream eliminada"
fi

if [ -L "$BIN_LINK" ]; then
    sudo rm -f "$BIN_LINK"
    echo "  ✓ Comando 'label-printer' eliminado"
fi

# ── Limpiar también instalación vieja en ~/.local (si existe) ──
OLD_DESKTOP="$HOME/.local/share/applications/label-printer.desktop"
OLD_ICON="$HOME/.local/share/icons/hicolor/scalable/apps/label-printer.svg"
if [ -f "$OLD_DESKTOP" ]; then
    rm -f "$OLD_DESKTOP"
    echo "  ✓ Acceso directo viejo (~/.local) eliminado"
fi
if [ -f "$OLD_ICON" ]; then
    rm -f "$OLD_ICON"
    echo "  ✓ Icono viejo (~/.local) eliminado"
fi

# ── Configuración del usuario ──
if [ -d "$USER_CONFIG" ]; then
    echo ""
    read -p "¿Eliminar configuración guardada ($USER_CONFIG)? (s/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        rm -rf "$USER_CONFIG"
        echo "  ✓ Configuración eliminada"
    else
        echo "  ─ Configuración conservada"
    fi
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   ✓ Label Printer desinstalado completamente     ║"
echo "╚══════════════════════════════════════════════════╝"
