"""Gestión de conexión con la impresora HT300 - USB y Red.

Guarda la configuración en ~/.config/label-printer/connection.json
"""

import json
import os
import socket
import subprocess
import threading

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "label-printer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "connection.json")

DEFAULT_CONFIG = {
    "mode": "cups",         # "cups", "network", "usb"
    "cups_printer": "HT300-TSPL",
    "network_ip": "192.168.1.100",
    "network_port": 9100,
    "usb_device": "/dev/usb/lp0",
    "usb_vendor_product": "0483:5743",
}


def load_config():
    """Carga la configuración guardada o retorna defaults."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(saved)
            return config
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Guarda la configuración."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def send_tspl(tspl_content, config=None):
    """Envía TSPL según el modo configurado."""
    if config is None:
        config = load_config()

    mode = config.get("mode", "cups")

    if mode == "network":
        return _send_network(tspl_content, config)
    elif mode == "usb":
        return _send_usb(tspl_content, config)
    else:
        return _send_cups(tspl_content, config)


def _send_cups(tspl_content, config):
    """Envía via CUPS (lp -d printer -o raw)."""
    import tempfile
    printer = config.get("cups_printer", "HT300")

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
            return True, f"CUPS: {result.stdout.strip()}"
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return False, f"Error CUPS: {error}"
    except subprocess.TimeoutExpired:
        os.unlink(tmpfile)
        return False, "Timeout al enviar a CUPS"
    except FileNotFoundError:
        os.unlink(tmpfile)
        return False, "Comando 'lp' no encontrado. Instala: sudo apt install cups"
    except Exception as e:
        if os.path.exists(tmpfile):
            os.unlink(tmpfile)
        return False, f"Error: {e}"


def _send_network(tspl_content, config):
    """Envía TSPL directamente via TCP socket (raw port 9100)."""
    ip = config.get("network_ip", "192.168.1.100")
    port = config.get("network_port", 9100)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))

        data = tspl_content
        if not data.endswith('\n'):
            data += '\n'
        sock.sendall(data.encode('utf-8'))
        sock.close()

        return True, f"Enviado a {ip}:{port}"
    except socket.timeout:
        return False, f"Timeout conectando a {ip}:{port}"
    except ConnectionRefusedError:
        return False, f"Conexión rechazada en {ip}:{port}. Verificar que la impresora esté encendida."
    except OSError as e:
        return False, f"Error de red: {e}"


def _send_usb(tspl_content, config):
    """Envía TSPL directamente al dispositivo USB."""
    device = config.get("usb_device", "/dev/usb/lp0")

    if not os.path.exists(device):
        return False, f"Dispositivo {device} no encontrado. Verificar conexión USB."

    try:
        data = tspl_content
        if not data.endswith('\n'):
            data += '\n'
        with open(device, 'wb') as f:
            f.write(data.encode('utf-8'))
        return True, f"Enviado a {device}"
    except PermissionError:
        return False, f"Sin permisos para {device}. Ejecutar: sudo chmod 666 {device}"
    except Exception as e:
        return False, f"Error USB: {e}"


# ── Pruebas de conexión ──

def test_cups(printer_name):
    """Prueba la conexión CUPS."""
    try:
        r = subprocess.run(
            ['lpstat', '-p', printer_name],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            status = r.stdout.strip()
            # Detectar tipo de conexión
            rv = subprocess.run(
                ['lpstat', '-v', printer_name],
                capture_output=True, text=True, timeout=5
            )
            uri = rv.stdout.strip() if rv.returncode == 0 else ""
            return True, f"OK - {status}\n{uri}"
        else:
            return False, f"Impresora '{printer_name}' no encontrada en CUPS"
    except FileNotFoundError:
        return False, "CUPS no instalado"
    except Exception as e:
        return False, f"Error: {e}"


def test_network(ip, port):
    """Prueba la conexión de red al puerto raw."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        sock.close()
        return True, f"Conexión exitosa a {ip}:{port}"
    except socket.timeout:
        return False, f"Timeout: {ip}:{port} no responde"
    except ConnectionRefusedError:
        return False, f"Puerto {port} cerrado en {ip}"
    except OSError as e:
        return False, f"Error: {e}"


def test_usb(device, vendor_product):
    """Prueba la conexión USB."""
    results = []

    # Verificar dispositivo
    if os.path.exists(device):
        results.append(f"OK: {device} existe")
        # Verificar permisos
        if os.access(device, os.W_OK):
            results.append(f"OK: Permisos de escritura en {device}")
        else:
            results.append(f"ERROR: Sin permisos de escritura en {device}")
    else:
        results.append(f"WARN: {device} no encontrado (impresora apagada o en bajo consumo)")

    # Verificar lsusb
    try:
        r = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
        if vendor_product in r.stdout:
            # Extraer línea relevante
            for line in r.stdout.split('\n'):
                if vendor_product in line:
                    results.append(f"OK: {line.strip()}")
                    break
        else:
            results.append(f"WARN: USB ID {vendor_product} no detectado en lsusb")
    except Exception:
        results.append("WARN: No se pudo ejecutar lsusb")

    ok = any("OK:" in r for r in results)
    return ok, "\n".join(results)


def test_connection_async(config, callback):
    """Prueba la conexión en background y llama callback con (ok, message)."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib

    def _worker():
        mode = config.get("mode", "cups")
        if mode == "network":
            ok, msg = test_network(
                config.get("network_ip", "192.168.1.100"),
                config.get("network_port", 9100)
            )
        elif mode == "usb":
            ok, msg = test_usb(
                config.get("usb_device", "/dev/usb/lp0"),
                config.get("usb_vendor_product", "0483:5743")
            )
        else:
            ok, msg = test_cups(config.get("cups_printer", "HT300"))
        GLib.idle_add(callback, ok, msg)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def get_status_async(config, callback):
    """Obtiene el estado de la impresora según modo configurado."""
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib

    def _worker():
        mode = config.get("mode", "cups")
        info = {"mode": mode}

        if mode == "cups":
            printer = config.get("cups_printer", "HT300")
            try:
                r = subprocess.run(
                    ['lpstat', '-p', printer],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0:
                    s = r.stdout.strip().lower()
                    if 'idle' in s:
                        info['status'] = 'Lista'
                        info['ok'] = True
                    elif 'printing' in s:
                        info['status'] = 'Imprimiendo...'
                        info['ok'] = True
                    else:
                        info['status'] = r.stdout.strip()[:40]
                        info['ok'] = True
                else:
                    info['status'] = 'No configurada'
                    info['ok'] = False
            except Exception:
                info['status'] = 'CUPS no disponible'
                info['ok'] = False

            # Tipo de conexión
            try:
                rv = subprocess.run(
                    ['lpstat', '-v', printer],
                    capture_output=True, text=True, timeout=5
                )
                if rv.returncode == 0:
                    uri = rv.stdout.strip()
                    if 'usb://' in uri:
                        info['connection'] = 'USB (CUPS)'
                    elif any(x in uri for x in ['socket://', 'ipp://', 'dnssd://', 'implicitclass://']):
                        info['connection'] = 'Red (CUPS)'
                    else:
                        info['connection'] = 'CUPS'
            except Exception:
                info['connection'] = 'CUPS'

        elif mode == "network":
            ip = config.get("network_ip", "?")
            port = config.get("network_port", 9100)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((ip, port))
                sock.close()
                info['status'] = f'{ip}:{port}'
                info['ok'] = True
                info['connection'] = 'TCP directo'
            except Exception:
                info['status'] = f'{ip}:{port} sin conexión'
                info['ok'] = False
                info['connection'] = 'TCP directo'

        elif mode == "usb":
            device = config.get("usb_device", "/dev/usb/lp0")
            if os.path.exists(device):
                info['status'] = device
                info['ok'] = True
            else:
                info['status'] = 'Desconectada'
                info['ok'] = False
            info['connection'] = 'USB directo'

        GLib.idle_add(callback, info)

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
