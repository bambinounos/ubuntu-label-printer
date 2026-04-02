#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Label Printer HT300 - Actualizador
#  Descarga la última versión de GitHub y reinstala
# ═══════════════════════════════════════════════════════════

set -e

INSTALL_DIR="/opt/label-printer"
REPO_URL="https://github.com/bambinounos/ubuntu-label-printer"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════════════╗"
echo "║   Label Printer HT300 — Actualizador             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Verificar instalación
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Error: Label Printer no está instalado en $INSTALL_DIR"
    echo "Ejecuta primero: ./install.sh"
    exit 1
fi

# Mostrar versión actual
if [ -f "$INSTALL_DIR/.install_info" ]; then
    CURRENT=$(grep "^version=" "$INSTALL_DIR/.install_info" | cut -d= -f2)
    INSTALLED=$(grep "^installed=" "$INSTALL_DIR/.install_info" | cut -d= -f2)
    echo "  Versión instalada: ${CURRENT:-desconocida}"
    echo "  Fecha instalación: ${INSTALLED:-desconocida}"
    echo ""
fi

# ── Descargar cambios ──
echo "[1/2] Obteniendo última versión..."

# Si estamos en un repo git, hacer pull
if [ -d "$SOURCE_DIR/.git" ]; then
    echo "  Repositorio local detectado, actualizando..."
    cd "$SOURCE_DIR"

    # Guardar estado
    BEFORE=$(git rev-parse HEAD)

    # Pull
    git fetch origin 2>/dev/null
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/master 2>/dev/null || git rev-parse origin/main 2>/dev/null)

    if [ "$LOCAL" = "$REMOTE" ]; then
        echo "  ✓ Ya tienes la última versión"
        echo ""
        read -p "  ¿Reinstalar de todas formas? (s/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Ss]$ ]]; then
            echo "  Cancelado."
            exit 0
        fi
    else
        echo "  Hay actualizaciones disponibles"
        git log --oneline "$LOCAL..$REMOTE" 2>/dev/null | head -10 | sed 's/^/    /'
        echo ""
        git pull origin master 2>/dev/null || git pull origin main 2>/dev/null
        echo "  ✓ Código actualizado"
    fi
else
    # No hay repo local, clonar temporal
    echo "  No hay repositorio local. Clonando desde GitHub..."
    TMPDIR=$(mktemp -d)
    git clone --depth 1 "$REPO_URL" "$TMPDIR/label-printer"
    SOURCE_DIR="$TMPDIR/label-printer"
    echo "  ✓ Descargado"
fi

# ── Reinstalar ──
echo ""
echo "[2/2] Reinstalando..."
cd "$SOURCE_DIR"
bash install.sh

# Limpiar temporal si se usó
if [ -n "$TMPDIR" ] && [ -d "$TMPDIR" ]; then
    rm -rf "$TMPDIR"
fi

echo ""
echo "  ✓ Actualización completada"
