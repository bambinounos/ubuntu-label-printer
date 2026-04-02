"""Impresión via CUPS - envía comandos TSPL raw a la impresora HT300."""

import os
import subprocess
import tempfile

CUPS_PRINTER = "HT300-TSPL"
USB_DEVICE = "/dev/usb/lp0"


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
    """Obtiene el estado de la impresora."""
    printer = printer_name or CUPS_PRINTER
    info = {}

    try:
        r = subprocess.run(
            ['lpstat', '-p', printer],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            status = r.stdout.strip()
            if 'idle' in status.lower():
                info['cups'] = 'Lista'
                info['cups_ok'] = True
            elif 'printing' in status.lower():
                info['cups'] = 'Imprimiendo...'
                info['cups_ok'] = True
            else:
                info['cups'] = status
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

    info['usb'] = 'Conectado' if os.path.exists(USB_DEVICE) else 'Bajo consumo'

    try:
        r = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
        if '0483:5743' in r.stdout:
            info['device'] = 'HT300 detectada en USB'
            info['device_ok'] = True
        else:
            info['device'] = 'HT300 no detectada'
            info['device_ok'] = False
    except Exception:
        info['device'] = 'No se pudo verificar'
        info['device_ok'] = False

    return info


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
