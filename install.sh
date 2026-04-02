#!/bin/bash
# Instalador de dependencias para Label Printer en Ubuntu

echo "=== Label Printer - Instalador ==="
echo ""

# Dependencias del sistema
echo "[1/3] Instalando dependencias del sistema..."
sudo apt-get update
sudo apt-get install -y \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    python3-pip \
    python3-venv

# Entorno virtual
echo ""
echo "[2/3] Creando entorno virtual..."
cd "$(dirname "$0")"
python3 -m venv venv --system-site-packages
source venv/bin/activate

# Dependencias Python
echo ""
echo "[3/3] Instalando dependencias Python..."
pip install python-barcode qrcode Pillow

echo ""
echo "=== Instalación completada ==="
echo "Ejecuta: ./run.sh"
