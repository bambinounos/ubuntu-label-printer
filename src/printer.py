"""Impresión via CUPS - envía comandos TSPL raw a la impresora HT300.

Soporta conexión USB directa y red (IPP/mDNS).
"""

import os
import subprocess
import tempfile
import threading

CUPS_PRINTER = "HT300-TSPL"
USB_DEVICE = "/dev/usb/lp0"
USB_VENDOR_PRODUCT = "0483:5743"


def send_to_printer(tspl_content, printer_name=None):
    """Envía TSPL via CUPS (lp -d printer -o raw)."""
    printer = printer_name or CUPS_PRINTER

    with tempfile.NamedTemporaryFile(mode='w', suffix='.tspl', delete=False) as f:
        f.write(tspl_content)
        if not tspl_content.endswith('\n'):
            f.write('\n')
        tmpfile = f.name

    try:
        result = subprocess.run(
            ['lp', '-d', printer, '-o', 'raw', tmpfile],
            capture_output=True, text=True, timeout=10
        )
        os.unlink(tmpfile)

        if result.returncode == 0:
            job_info = result.stdout.strip()
            return True, f"Enviado correctamente. {job_info}"
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return False, f"Error CUPS: {error}"
    except subprocess.TimeoutExpired:
        os.unlink(tmpfile)
        return False, "Timeout al enviar a CUPS"
    except FileNotFoundError:
        os.unlink(tmpfile)
        return False, "Comando 'lp' no encontrado. Instala CUPS: sudo apt install cups"
    except Exception as e:
        if os.path.exists(tmpfile):
            os.unlink(tmpfile)
        return False, f"Error: {str(e)}"


def get_printer_status(printer_name=None):
    """Obtiene el estado de la impresora (no bloquear con esto en main thread)."""
    printer = printer_name or CUPS_PRINTER
    info = {}

    # Estado CUPS
    try:
        r = subprocess.run(
            ['lpstat', '-p', printer],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            status = r.stdout.strip()
            if 'idle' in status.lower():
                info['cups'] = 'Lista (idle)'
                info['cups_ok'] = True
            elif 'printing' in status.lower():
                info['cups'] = 'Imprimiendo...'
                info['cups_ok'] = True
            else:
                info['cups'] = status.split('\n')[0][:50]
                info['cups_ok'] = True
        else:
            info['cups'] = 'No configurada'
            info['cups_ok'] = False
    except FileNotFoundError:
        info['cups'] = 'CUPS no instalado'
        info['cups_ok'] = False
    except Exception:
        info['cups'] = 'CUPS no disponible'
        info['cups_ok'] = False

    # Tipo de conexión: USB o red
    connection = _detect_connection(printer)
    info['connection'] = connection['type']
    info['connection_detail'] = connection['detail']
    info['device_ok'] = connection['ok']

    return info


def _detect_connection(printer):
    """Detecta si la impresora está conectada via USB o red."""
    # Verificar device URI en CUPS
    try:
        r = subprocess.run(
            ['lpstat', '-v', printer],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            uri = r.stdout.strip()
            if 'usb://' in uri:
                usb_connected = os.path.exists(USB_DEVICE)
                return {
                    'type': 'USB',
                    'detail': f"USB {'conectado' if usb_connected else 'desconectado'}",
                    'ok': usb_connected,
                }
            elif 'socket://' in uri or 'ipp://' in uri or 'dnssd://' in uri or 'implicitclass://' in uri:
                return {
                    'type': 'Red',
                    'detail': 'Red (IPP/mDNS)',
                    'ok': True,
                }
    except Exception:
        pass

    # Fallback: verificar USB directamente
    try:
        r = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
        if USB_VENDOR_PRODUCT in r.stdout:
            return {'type': 'USB', 'detail': 'HT300 en USB', 'ok': True}
    except Exception:
        pass

    return {'type': 'Desconocido', 'detail': 'No detectada', 'ok': False}


def get_printer_status_async(callback, printer_name=None):
    """Obtiene estado en background thread y llama callback en main thread."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib

    def _worker():
        status = get_printer_status(printer_name)
        GLib.idle_add(callback, status)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def list_printers():
    """Lista las impresoras disponibles en CUPS."""
    try:
        r = subprocess.run(
            ['lpstat', '-a'],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            printers = []
            for line in r.stdout.strip().split('\n'):
                if line.strip():
                    name = line.split()[0]
                    printers.append(name)
            return printers
    except Exception:
        pass
    return []
