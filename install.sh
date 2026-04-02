#!/bin/bash
# Instalador de dependencias para Label Printer en Ubuntu

echo "=== Label Printer HT300 - Instalador ==="
echo ""

# Dependencias del sistema
echo "[1/2] Instalando dependencias del sistema..."
sudo apt-get update
sudo apt-get install -y \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-3.0 \
    cups \
    python3-pip

# Verificar impresora CUPS
echo ""
echo "[2/2] Verificando impresora CUPS..."
if lpstat -p HT300-TSPL 2>/dev/null | grep -q "printer"; then
    echo "  ✓ Impresora HT300-TSPL configurada en CUPS"
else
    echo "  ✗ Impresora HT300-TSPL NO encontrada en CUPS"
    echo "  Para configurarla:"
    echo "    sudo lpadmin -p HT300-TSPL -v \"usb://XPrinter/BAR%20PRINTER?serial=?\" -m raw -E"
    echo "  O usa la interfaz web de CUPS: http://localhost:631"
fi

echo ""
echo "=== Instalación completada ==="
echo "Ejecutar: ./run.sh"
echo "Interfaz web alternativa: python3 ht300_web.py"
