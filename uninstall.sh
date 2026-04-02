#!/bin/bash
# Desinstalador de Label Printer

APP_NAME="label-printer"
DESKTOP_FILE="$HOME/.local/share/applications/${APP_NAME}.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/scalable/apps/${APP_NAME}.svg"
CONFIG_DIR="$HOME/.config/label-printer"

echo "=== Desinstalar Label Printer ==="
echo ""

# Eliminar acceso directo
if [ -f "$DESKTOP_FILE" ]; then
    rm "$DESKTOP_FILE"
    echo "  ✓ Acceso directo eliminado"
else
    echo "  - Acceso directo no encontrado"
fi

# Eliminar icono
if [ -f "$ICON_FILE" ]; then
    rm "$ICON_FILE"
    echo "  ✓ Icono eliminado"
else
    echo "  - Icono no encontrado"
fi

# Preguntar por config
if [ -d "$CONFIG_DIR" ]; then
    read -p "  ¿Eliminar configuración guardada? (s/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo "  ✓ Configuración eliminada"
    else
        echo "  - Configuración conservada en $CONFIG_DIR"
    fi
fi

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "Desinstalación completada. Los archivos del proyecto no se eliminaron."
