#!/usr/bin/env python3
"""
HT300 Label Printer - Web Interface
Interfaz web para enviar comandos TSPL a la impresora HT300 (HPRT)
Usa CUPS (lp -d HT300-TSPL -o raw) para enviar los trabajos.
Uso: python3 ht300_web.py [--port 5080]
"""

import os
import sys
import json
import subprocess
import tempfile
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
from datetime import datetime

CUPS_PRINTER = "HT300-TSPL"
USB_DEVICE = "/dev/usb/lp0"
DEFAULT_PORT = 5080

PLANTILLAS = {
    "etiqueta_producto": {
        "nombre": "Etiqueta de Producto",
        "descripcion": "Código, descripción, precio y código de barras",
        "tspl": "SIZE 60 mm,40 mm\nGAP 2 mm,0 mm\nDIRECTION 1,0\nREFERENCE 0,0\nOFFSET 0 mm\nSET PEEL OFF\nSET TEAR ON\nCLS\nTEXT 60,0,\"4\",0,1,1,\"WG9719230025\"\nTEXT 60,40,\"TSS24.BF2\",0,1,1,\"IMPORTADORA HELLBAM S.A\"\nTEXT 60,80,\"TSS24.BF2\",0,1,1,\"CANT: 1 U, USD 178.98\"\nTEXT 60,120,\"TSS24.BF2\",0,1,1,\"SINOTRUK CLUTCH BOOSTER\"\nBARCODE 60,150,\"39C\",100,1,0,2,2,\"WG9719230025\"\nPRINT 1"
    },
    "etiqueta_qr": {
        "nombre": "Etiqueta con QR",
        "descripcion": "Texto y código QR",
        "tspl": "SIZE 60 mm,40 mm\nGAP 2 mm,0 mm\nDIRECTION 1,0\nCLS\nTEXT 30,10,\"4\",0,1,1,\"HELLBAM S.A.\"\nTEXT 30,50,\"TSS24.BF2\",0,1,1,\"FILTRO DE ACEITE\"\nTEXT 30,80,\"TSS24.BF2\",0,1,1,\"REF: SH996C\"\nQRCODE 350,10,H,5,A,0,\"SH996C-HELLBAM\"\nPRINT 1"
    },
    "estanteria": {
        "nombre": "Estantería",
        "descripcion": "Código y código de barras simple",
        "tspl": "SIZE 60 mm,40 mm\nGAP 2 mm,0 mm\nDIRECTION 1,0\nREFERENCE 0,0\nOFFSET 0 mm\nSET PEEL OFF\nSET TEAR ON\nCLS\nTEXT 30,90,\"4\",0,1,1,\"MSL - C1P06k\"\nBARCODE 30,150,\"128M\",100,1,0,2,2,\"MSL - C1P06k\"\nPRINT 1"
    },
    "etiqueta_cat": {
        "nombre": "Etiqueta Caterpillar",
        "descripcion": "Repuesto Caterpillar con código de barras",
        "tspl": "SIZE 60 mm,40 mm\nGAP 2 mm,0 mm\nDIRECTION 1,0\nCLS\nTEXT 60,0,\"4\",0,1,1,\"CATERPILLAR\"\nTEXT 60,40,\"TSS24.BF2\",0,1,1,\"WASHER\"\nTEXT 60,80,\"TSS24.BF2\",0,1,1,\"QTY: 4 EA\"\nTEXT 60,120,\"TSS24.BF2\",0,1,1,\"416-420 SERIES\"\nBARCODE 60,150,\"39\",100,1,0,2,2,\"9R-0158\"\nPRINT 1"
    },
    "vacio": {
        "nombre": "En blanco",
        "descripcion": "Plantilla vacía para escribir TSPL",
        "tspl": "SIZE 60 mm,40 mm\nGAP 2 mm,0 mm\nDIRECTION 1,0\nCLS\n\nPRINT 1"
    }
}


def enviar_cups(tspl_content):
    """Enviar via CUPS (lp -d HT300-TSPL -o raw)"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(tspl_content)
            if not tspl_content.endswith('\n'):
                f.write('\n')
            tmpfile = f.name

        result = subprocess.run(
            ['lp', '-d', CUPS_PRINTER, '-o', 'raw', tmpfile],
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
        return False, "Timeout al enviar a CUPS"
    except Exception as e:
        return False, f"Error: {str(e)}"


def obtener_estado():
    """Obtener estado de la impresora"""
    info = {}
    try:
        r = subprocess.run(['lpstat', '-p', CUPS_PRINTER],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            status = r.stdout.strip()
            if 'idle' in status.lower():
                info['cups'] = 'Lista'
            elif 'printing' in status.lower():
                info['cups'] = 'Imprimiendo...'
            else:
                info['cups'] = status
        else:
            info['cups'] = 'No configurada'
    except:
        info['cups'] = 'CUPS no disponible'

    info['usb'] = 'Conectado' if os.path.exists(USB_DEVICE) else 'Bajo consumo (normal)'

    try:
        r = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
        if '0483:5743' in r.stdout:
            info['dispositivo'] = 'HT300 detectada en USB'
        else:
            info['dispositivo'] = 'HT300 no detectada'
    except:
        info['dispositivo'] = 'No se pudo verificar'

    return info


HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HT300 - Impresora de Etiquetas</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #242836;
    --border: #2e3347;
    --text: #e4e7f1;
    --text-dim: #8b90a5;
    --accent: #f59e0b;
    --accent-hover: #fbbf24;
    --success: #34d399;
    --error: #f87171;
    --mono: 'JetBrains Mono', monospace;
    --sans: 'DM Sans', sans-serif;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
}
.header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
}
.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}
.logo {
    width: 36px; height: 36px;
    background: var(--accent);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px; color: #000;
    font-family: var(--mono);
}
.header h1 {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.5px;
}
.header h1 span { color: var(--text-dim); font-weight: 400; }
.status-bar {
    display: flex; gap: 16px; align-items: center;
    font-size: 13px;
}
.status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 4px;
}
.status-dot.on { background: var(--success); box-shadow: 0 0 8px var(--success); }
.status-dot.off { background: var(--error); }
.status-dot.warn { background: var(--accent); }
.main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px;
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: 20px;
}
.sidebar h2 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-dim);
    margin-bottom: 12px;
}
.plantilla-btn {
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    color: var(--text);
    cursor: pointer;
    text-align: left;
    margin-bottom: 8px;
    transition: all 0.15s;
    font-family: var(--sans);
}
.plantilla-btn:hover {
    border-color: var(--accent);
    background: var(--surface2);
}
.plantilla-btn.active {
    border-color: var(--accent);
    background: rgba(245, 158, 11, 0.08);
}
.plantilla-btn .name {
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 2px;
}
.plantilla-btn .desc {
    font-size: 12px;
    color: var(--text-dim);
}
.editor-area {
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
}
.editor-header h2 {
    font-size: 15px;
    font-weight: 600;
}
.controls {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
}
.btn {
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 600;
    padding: 8px 18px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    gap: 6px;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary {
    background: var(--accent);
    color: #000;
}
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); transform: translateY(-1px); }
.btn-primary:active:not(:disabled) { transform: translateY(0); }
textarea {
    width: 100%;
    min-height: 380px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    line-height: 1.6;
    resize: vertical;
    outline: none;
    transition: border-color 0.15s;
}
textarea:focus { border-color: var(--accent); }
.copies-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
}
.copies-row label { color: var(--text-dim); white-space: nowrap; }
.copies-row input[type=number] {
    width: 55px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 8px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    outline: none;
}
.copies-row input:focus { border-color: var(--accent); }
.toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    padding: 14px 20px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    max-width: 420px;
    transform: translateY(100px);
    opacity: 0;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    z-index: 100;
}
.toast.show { transform: translateY(0); opacity: 1; }
.toast.success { background: #065f46; color: #d1fae5; border: 1px solid #34d399; }
.toast.error { background: #7f1d1d; color: #fecaca; border: 1px solid #f87171; }
.ref-section {
    margin-top: 8px;
    padding: 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
}
.ref-section summary {
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    color: var(--text-dim);
    user-select: none;
}
.ref-section summary:hover { color: var(--text); }
.ref-content {
    margin-top: 12px;
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.8;
    color: var(--text-dim);
}
.ref-content code {
    background: var(--surface2);
    padding: 1px 5px;
    border-radius: 3px;
    color: var(--accent);
}
.spinner {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid rgba(0,0,0,0.2);
    border-top-color: #000;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 768px) {
    .main {
        grid-template-columns: 1fr;
        padding: 16px;
    }
    .sidebar {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 4px;
    }
    .sidebar h2 { display: none; }
    .plantilla-btn { min-width: 150px; flex-shrink: 0; }
    .header { flex-direction: column; align-items: flex-start; }
    textarea { min-height: 260px; }
}
</style>
</head>
<body>

<div class="header">
    <div class="header-left">
        <div class="logo">HT</div>
        <h1>HT300 <span>Etiquetas TSPL</span></h1>
    </div>
    <div class="status-bar">
        <span><span class="status-dot" id="dotCups"></span> CUPS: <span id="statusCups">...</span></span>
        <span><span class="status-dot" id="dotUsb"></span> USB: <span id="statusUsb">...</span></span>
    </div>
</div>

<div class="main">
    <div class="sidebar">
        <h2>Plantillas</h2>
    </div>

    <div class="editor-area">
        <div class="editor-header">
            <h2>Editor TSPL</h2>
            <div class="controls">
                <div class="copies-row">
                    <label>Copias:</label>
                    <input type="number" id="copias" value="1" min="1" max="99">
                </div>
                <button class="btn btn-primary" id="btnImprimir" onclick="imprimir()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9V2h12v7M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                    Imprimir
                </button>
            </div>
        </div>

        <textarea id="tspl" spellcheck="false" placeholder="Escribe o pega comandos TSPL aquí..."></textarea>

        <details class="ref-section">
            <summary>Referencia rápida TSPL</summary>
            <div class="ref-content">
                <strong>IMPORTANTE:</strong> Usar espacio antes de <code>mm</code> → <code>SIZE 60 mm,40 mm</code> (NO <code>60MM,40MM</code>)<br><br>
                <strong>Configuración:</strong> <code>SIZE 60 mm,40 mm</code> <code>GAP 2 mm,0 mm</code> <code>CLS</code> <code>PRINT 1</code><br><br>
                <strong>Texto:</strong> <code>TEXT x,y,"fuente",rot,mx,my,"texto"</code><br>
                Fuentes: <code>"1"</code>=8x12 <code>"2"</code>=12x20 <code>"3"</code>=16x24 <code>"4"</code>=24x32 <code>"5"</code>=32x48 <code>"TSS24.BF2"</code>=asiática<br><br>
                <strong>Código de barras:</strong> <code>BARCODE x,y,"tipo",alto,legible,rot,estrecho,ancho,"datos"</code><br>
                Tipos: <code>"128"</code> <code>"128M"</code> <code>"39"</code> <code>"EAN13"</code> <code>"UPCA"</code><br><br>
                <strong>QR:</strong> <code>QRCODE x,y,ECC,celda,modo,rot,"datos"</code><br>
                ECC: <code>L</code> <code>M</code> <code>Q</code> <code>H</code> | Celda: <code>1-12</code><br><br>
                <strong>Gráficos:</strong> <code>BAR x,y,ancho,alto</code> <code>BOX x1,y1,x2,y2,grosor</code> <code>REVERSE x,y,ancho,alto</code><br><br>
                <strong>Nota:</strong> 203 DPI → 1 mm = 8 dots | Área máx: 480×320 dots (60×40mm)
            </div>
        </details>
    </div>
</div>

<div class="toast" id="toast"></div>

<script>
var PLANTILLAS = PLANTILLAS_JSON;

function init() {
    var sidebar = document.querySelector('.sidebar');
    Object.entries(PLANTILLAS).forEach(function(entry) {
        var key = entry[0], p = entry[1];
        var btn = document.createElement('button');
        btn.className = 'plantilla-btn';
        btn.innerHTML = '<div class="name">' + p.nombre + '</div><div class="desc">' + p.descripcion + '</div>';
        btn.onclick = function() {
            document.getElementById('tspl').value = p.tspl;
            document.querySelectorAll('.plantilla-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
        };
        sidebar.appendChild(btn);
    });

    checkStatus();
    setInterval(checkStatus, 10000);
}

function checkStatus() {
    fetch('/api/status').then(function(r) { return r.json(); }).then(function(data) {
        var dotCups = document.getElementById('dotCups');
        var statusCups = document.getElementById('statusCups');
        var cupsOk = data.cups && data.cups !== 'No configurada' && data.cups !== 'CUPS no disponible';
        dotCups.className = 'status-dot ' + (cupsOk ? 'on' : 'off');
        statusCups.textContent = data.cups;

        var dotUsb = document.getElementById('dotUsb');
        var statusUsb = document.getElementById('statusUsb');
        var usbConnected = data.usb === 'Conectado';
        dotUsb.className = 'status-dot ' + (usbConnected ? 'on' : 'warn');
        statusUsb.textContent = data.usb;
    }).catch(function() {});
}

function imprimir() {
    var tspl = document.getElementById('tspl').value.trim();
    if (!tspl) { showToast('Escribe comandos TSPL primero', 'error'); return; }

    var copias = parseInt(document.getElementById('copias').value) || 1;
    var btn = document.getElementById('btnImprimir');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Enviando...';

    var contenido = tspl;
    if (copias > 1) {
        contenido = contenido.replace(/PRINT\\s+\\d+/gi, 'PRINT ' + copias);
    }

    fetch('/api/print', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ tspl: contenido })
    }).then(function(r) { return r.json(); }).then(function(data) {
        showToast(data.mensaje, data.ok ? 'success' : 'error');
    }).catch(function() {
        showToast('Error de conexión con el servidor', 'error');
    }).finally(function() {
        btn.disabled = false;
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9V2h12v7M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg> Imprimir';
    });
}

function showToast(msg, type) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast ' + type + ' show';
    setTimeout(function() { t.classList.remove('show'); }, 4000);
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"[{ts}] {args[0]}")

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            page = HTML_PAGE.replace('PLANTILLAS_JSON', json.dumps(PLANTILLAS, ensure_ascii=False))
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(page.encode('utf-8'))

        elif self.path == '/api/status':
            estado = obtener_estado()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(estado).encode('utf-8'))

        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/print':
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            tspl = body.get('tspl', '')

            ok, msg = enviar_cups(tspl)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': ok, 'mensaje': msg}).encode('utf-8'))
        else:
            self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description='HT300 Label Printer Web Interface')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'Puerto (default: {DEFAULT_PORT})')
    args = parser.parse_args()

    try:
        r = subprocess.run(['lpstat', '-p', CUPS_PRINTER], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            print(f"ADVERTENCIA: Impresora '{CUPS_PRINTER}' no encontrada en CUPS.")
            print(f"Configurar con: sudo lpadmin -p {CUPS_PRINTER} -v \"usb://XPrinter/BAR%20PRINTER?serial=?\" -m raw -E")
    except:
        pass

    server = HTTPServer(('0.0.0.0', args.port), Handler)
    print(f"""
╔══════════════════════════════════════════════╗
║   HT300 - Impresora de Etiquetas TSPL       ║
║   http://localhost:{args.port}                    ║
║   Impresora CUPS: {CUPS_PRINTER:<26s}║
║   Ctrl+C para detener                        ║
╚══════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        server.server_close()


if __name__ == '__main__':
    main()
